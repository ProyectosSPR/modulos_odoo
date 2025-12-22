# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
import json
import base64
import logging

_logger = logging.getLogger(__name__)


class BillingPortalAPI(http.Controller):
    """API JSON para el portal de facturación"""

    def _get_portal_session(self):
        """Obtiene la sesión actual del portal"""
        token = request.httprequest.cookies.get('billing_portal_token')
        if not token:
            # También verificar token de invitado
            token = request.httprequest.cookies.get('billing_portal_guest_token')
            if token:
                return {'is_guest': True}
            return None

        external_db = request.env['billing.external.db'].sudo()
        return external_db.validate_portal_session(token)

    @http.route('/portal/billing/api/validate-csf', type='json', auth='public', csrf=False)
    def api_validate_csf(self, **kwargs):
        """
        Valida un PDF de CSF y extrae los datos.

        Espera:
            csf_pdf: string base64 del PDF

        Retorna:
            {success: bool, data: {...}, errors: [...], method: 'local'|'ai'}
        """
        session = self._get_portal_session()
        if not session:
            return {'success': False, 'errors': [_('No autorizado')]}

        pdf_content = kwargs.get('csf_pdf')
        if not pdf_content:
            return {'success': False, 'errors': [_('No se recibió archivo PDF')]}

        try:
            # Decodificar base64
            if ',' in pdf_content:
                # Formato data:application/pdf;base64,xxxxx
                pdf_content = pdf_content.split(',')[1]

            pdf_bytes = base64.b64decode(pdf_content)

            # Validar CSF
            validator = request.env['billing.csf.validator'].sudo()
            result = validator.validate_csf(pdf_bytes)

            # Si tuvo éxito, buscar IDs de Odoo para catálogos
            if result.get('success'):
                data = result.get('data', {})

                # Buscar régimen fiscal
                if data.get('regimen_fiscal') and not data.get('regimen_fiscal_id'):
                    regimen_value = data.get('regimen_fiscal')
                    if isinstance(regimen_value, list) and len(regimen_value) > 0:
                        code = regimen_value[0].get('codigo', '')
                    elif isinstance(regimen_value, dict):
                        code = regimen_value.get('codigo', '')
                    else:
                        code = str(regimen_value)[:3] if regimen_value else ''

                    if code:
                        regimen = request.env['catalogo.regimen.fiscal'].sudo().search([
                            ('code', '=', code)
                        ], limit=1)
                        if regimen:
                            data['regimen_fiscal_id'] = regimen.id
                            data['regimen_fiscal_display'] = regimen.display_name

                # Buscar estado
                if data.get('entidad_federativa') and not data.get('state_id'):
                    state = request.env['res.country.state'].sudo().search([
                        ('country_id', '=', request.env.ref('base.mx').id),
                        ('name', 'ilike', data.get('entidad_federativa'))
                    ], limit=1)
                    if state:
                        data['state_id'] = state.id
                        data['state_name'] = state.name

            return result

        except Exception as e:
            _logger.exception("Error validando CSF")
            return {
                'success': False,
                'errors': [str(e)]
            }

    @http.route('/portal/billing/api/search-orders', type='json', auth='public', csrf=False)
    def api_search_orders(self, **kwargs):
        """
        Busca órdenes para el usuario.

        Espera:
            search: string de búsqueda
            receiver_id: (opcional) filtrar por receiver_id

        Retorna:
            {success: bool, orders: [...]}
        """
        _logger.info("=" * 60)
        _logger.info("API search-orders llamada")
        _logger.info("kwargs recibidos: %s", kwargs)

        session = self._get_portal_session()
        _logger.info("Sesión: %s", session)

        if not session:
            _logger.warning("No hay sesión válida")
            return {'success': False, 'errors': [_('No autorizado')]}

        search_term = kwargs.get('search', '')
        _logger.info("Término de búsqueda: '%s'", search_term)

        receiver_id = session.get('receiver_id') if not session.get('is_guest') else None
        _logger.info("Receiver ID de sesión: %s", receiver_id)

        try:
            orders = request.env['sale.order'].sudo().search_for_billing_portal(
                search_term,
                receiver_id=receiver_id,
                limit=50
            )

            _logger.info("Órdenes encontradas por API: %d", len(orders))
            _logger.info("=" * 60)

            return {
                'success': True,
                'orders': orders
            }
        except Exception as e:
            _logger.exception("Error buscando órdenes")
            return {
                'success': False,
                'errors': [str(e)]
            }

    @http.route('/portal/billing/api/submit-request', type='json', auth='public', csrf=False)
    def api_submit_request(self, **kwargs):
        """
        Envía una solicitud de facturación.

        Espera:
            order_ids: lista de IDs de órdenes
            email: email del cliente
            phone: teléfono (opcional)
            csf_pdf: base64 del PDF de CSF
            csf_data: datos extraídos del CSF
            uso_cfdi_id: ID del uso CFDI
            forma_pago_id: ID de forma de pago

        Retorna:
            {success: bool, request_id: int, ...}
        """
        session = self._get_portal_session()
        if not session:
            return {'success': False, 'errors': [_('No autorizado')]}

        try:
            order_ids = kwargs.get('order_ids', [])
            if isinstance(order_ids, str):
                order_ids = [int(x) for x in order_ids.split(',') if x]

            if not order_ids:
                return {'success': False, 'errors': [_('No se seleccionaron órdenes')]}

            # Verificar órdenes
            orders = request.env['sale.order'].sudo().browse(order_ids)
            non_billable = orders.filtered(lambda o: not o.is_portal_billable)
            if non_billable:
                return {
                    'success': False,
                    'errors': [_('Las siguientes órdenes no pueden facturarse: %s') %
                              ', '.join(non_billable.mapped('name'))]
                }

            # Crear attachment para CSF si viene
            csf_attachment = None
            csf_pdf = kwargs.get('csf_pdf')
            if csf_pdf:
                if ',' in csf_pdf:
                    csf_pdf = csf_pdf.split(',')[1]

                csf_attachment = request.env['ir.attachment'].sudo().create({
                    'name': f'CSF_{kwargs.get("email", "cliente")}.pdf',
                    'type': 'binary',
                    'datas': csf_pdf,
                    'mimetype': 'application/pdf',
                })

            # Crear solicitud
            csf_data = kwargs.get('csf_data', {})
            if isinstance(csf_data, str):
                csf_data = json.loads(csf_data)

            billing_request = request.env['billing.request'].sudo().create({
                'receiver_id': session.get('receiver_id'),
                'email': kwargs.get('email'),
                'phone': kwargs.get('phone'),
                'order_ids': [(6, 0, order_ids)],
                'order_references': ', '.join(orders.mapped('client_order_ref')),
                'csf_attachment_id': csf_attachment.id if csf_attachment else False,
                'csf_data': json.dumps(csf_data, ensure_ascii=False) if csf_data else False,
                'rfc': csf_data.get('rfc'),
                'razon_social': csf_data.get('razon_social'),
                'codigo_postal': csf_data.get('codigo_postal'),
                'regimen_fiscal_id': csf_data.get('regimen_fiscal_id'),
                'uso_cfdi_id': int(kwargs.get('uso_cfdi_id')) if kwargs.get('uso_cfdi_id') else False,
                'forma_pago_id': int(kwargs.get('forma_pago_id')) if kwargs.get('forma_pago_id') else False,
                'ip_address': request.httprequest.remote_addr,
                'user_agent': request.httprequest.user_agent.string,
                'state': 'csf_validated' if csf_data.get('rfc') else 'draft',
                'progress': 30 if csf_data.get('rfc') else 0,
            })

            # Iniciar proceso automático si CSF ya fue validado
            if billing_request.state == 'csf_validated':
                billing_request.action_create_partner()
                if billing_request.partner_id:
                    billing_request.action_create_invoice()

            return {
                'success': True,
                'request_id': billing_request.id,
                'request_name': billing_request.name,
                'state': billing_request.state,
                'progress': billing_request.progress,
            }

        except Exception as e:
            _logger.exception("Error creando solicitud")
            return {
                'success': False,
                'errors': [str(e)]
            }

    @http.route('/portal/billing/api/request-status/<int:request_id>', type='json', auth='public', csrf=False)
    def api_request_status(self, request_id, **kwargs):
        """
        Obtiene el estado de una solicitud.

        Retorna:
            {success: bool, status: {...}}
        """
        billing_request = request.env['billing.request'].sudo().browse(request_id)

        if not billing_request.exists():
            return {'success': False, 'errors': [_('Solicitud no encontrada')]}

        return {
            'success': True,
            'status': billing_request.get_status_for_portal()
        }

    @http.route('/portal/billing/api/upload-csf/<int:request_id>', type='json', auth='public', csrf=False)
    def api_upload_csf(self, request_id, **kwargs):
        """
        Sube el CSF para una solicitud existente y lo valida.

        Espera:
            csf_pdf: base64 del PDF

        Retorna:
            {success: bool, data: {...}}
        """
        billing_request = request.env['billing.request'].sudo().browse(request_id)

        if not billing_request.exists():
            return {'success': False, 'errors': [_('Solicitud no encontrada')]}

        if billing_request.state not in ('draft', 'error'):
            return {'success': False, 'errors': [_('La solicitud no puede modificarse')]}

        csf_pdf = kwargs.get('csf_pdf')
        if not csf_pdf:
            return {'success': False, 'errors': [_('No se recibió archivo')]}

        try:
            if ',' in csf_pdf:
                csf_pdf = csf_pdf.split(',')[1]

            # Crear attachment
            csf_attachment = request.env['ir.attachment'].sudo().create({
                'name': f'CSF_{billing_request.name}.pdf',
                'type': 'binary',
                'datas': csf_pdf,
                'mimetype': 'application/pdf',
                'res_model': 'billing.request',
                'res_id': billing_request.id,
            })

            billing_request.write({
                'csf_attachment_id': csf_attachment.id
            })

            # Validar
            billing_request.action_validate_csf()

            return {
                'success': billing_request.state != 'error',
                'state': billing_request.state,
                'data': json.loads(billing_request.csf_data or '{}'),
                'errors': [billing_request.error_message] if billing_request.error_message else []
            }

        except Exception as e:
            _logger.exception("Error subiendo CSF")
            return {
                'success': False,
                'errors': [str(e)]
            }

    @http.route('/portal/billing/api/catalogs', type='json', auth='public', csrf=False)
    def api_get_catalogs(self, **kwargs):
        """
        Obtiene los catálogos necesarios para el formulario.

        Retorna:
            {
                usos_cfdi: [...],
                formas_pago: [...],
                regimenes: [...]
            }
        """
        try:
            usos = request.env['catalogo.uso.cfdi'].sudo().search_read(
                [], ['id', 'code', 'name', 'display_name']
            )

            formas = request.env['catalogo.forma.pago'].sudo().search_read(
                [], ['id', 'code', 'name', 'display_name']
            )

            regimenes = request.env['catalogo.regimen.fiscal'].sudo().search_read(
                [], ['id', 'code', 'name', 'display_name']
            )

            return {
                'success': True,
                'usos_cfdi': usos,
                'formas_pago': formas,
                'regimenes': regimenes,
            }
        except Exception as e:
            return {
                'success': False,
                'errors': [str(e)]
            }

    @http.route('/portal/billing/api/process-request/<int:request_id>', type='json', auth='public', csrf=False)
    def api_process_request(self, request_id, **kwargs):
        """
        Procesa una solicitud paso a paso.

        Espera:
            action: 'validate_csf' | 'create_partner' | 'create_invoice'

        Retorna:
            {success: bool, status: {...}}
        """
        billing_request = request.env['billing.request'].sudo().browse(request_id)

        if not billing_request.exists():
            return {'success': False, 'errors': [_('Solicitud no encontrada')]}

        action = kwargs.get('action')

        try:
            if action == 'validate_csf':
                billing_request.action_validate_csf()
            elif action == 'create_partner':
                billing_request.action_create_partner()
            elif action == 'create_invoice':
                billing_request.action_create_invoice()
            elif action == 'mark_done':
                billing_request.action_mark_done()
            else:
                return {'success': False, 'errors': [_('Acción no válida')]}

            return {
                'success': billing_request.state != 'error',
                'status': billing_request.get_status_for_portal()
            }

        except Exception as e:
            _logger.exception(f"Error procesando acción {action}")
            return {
                'success': False,
                'errors': [str(e)]
            }

    # =============================================
    # API para Mensajería Cliente-Contador
    # =============================================

    @http.route('/portal/billing/api/send-message/<int:request_id>', type='json', auth='public', csrf=False)
    def api_send_message(self, request_id, **kwargs):
        """
        Envía un mensaje del cliente al contador.

        Espera:
            message: texto del mensaje

        Retorna:
            {success: bool}
        """
        billing_request = request.env['billing.request'].sudo().browse(request_id)

        if not billing_request.exists():
            return {'success': False, 'errors': [_('Solicitud no encontrada')]}

        message = kwargs.get('message', '').strip()
        if not message:
            return {'success': False, 'errors': [_('El mensaje no puede estar vacío')]}

        try:
            billing_request.action_send_client_message(message)
            return {
                'success': True,
                'message': _('Mensaje enviado correctamente')
            }
        except Exception as e:
            _logger.exception("Error enviando mensaje")
            return {
                'success': False,
                'errors': [str(e)]
            }

    @http.route('/portal/billing/api/get-messages/<int:request_id>', type='json', auth='public', csrf=False)
    def api_get_messages(self, request_id, **kwargs):
        """
        Obtiene los mensajes de una solicitud.

        Retorna:
            {success: bool, messages: [...]}
        """
        billing_request = request.env['billing.request'].sudo().browse(request_id)

        if not billing_request.exists():
            return {'success': False, 'errors': [_('Solicitud no encontrada')]}

        return {
            'success': True,
            'message_from_client': billing_request.message_from_client or '',
            'message_to_client': billing_request.message_to_client or '',
            'last_message_date': billing_request.last_message_date.isoformat() if billing_request.last_message_date else None,
        }

    # =============================================
    # API para Descarga de Archivos CFDI
    # =============================================

    @http.route('/portal/billing/download/xml/<int:request_id>', type='http', auth='public', csrf=False)
    def download_cfdi_xml(self, request_id, **kwargs):
        """
        Descarga el XML del CFDI.
        """
        billing_request = request.env['billing.request'].sudo().browse(request_id)

        if not billing_request.exists():
            return request.not_found()

        if not billing_request.cfdi_xml_file:
            return request.not_found()

        filename = billing_request.cfdi_xml_filename or f'CFDI_{billing_request.name}.xml'
        content = base64.b64decode(billing_request.cfdi_xml_file)

        return request.make_response(
            content,
            headers=[
                ('Content-Type', 'application/xml'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
                ('Content-Length', len(content)),
            ]
        )

    @http.route('/portal/billing/download/pdf/<int:request_id>', type='http', auth='public', csrf=False)
    def download_cfdi_pdf(self, request_id, **kwargs):
        """
        Descarga el PDF del CFDI.
        """
        billing_request = request.env['billing.request'].sudo().browse(request_id)

        if not billing_request.exists():
            return request.not_found()

        # Intentar obtener PDF del campo o generar uno
        if billing_request.cfdi_pdf_file:
            content = base64.b64decode(billing_request.cfdi_pdf_file)
            filename = billing_request.cfdi_pdf_filename or f'CFDI_{billing_request.name}.pdf'
        elif billing_request.invoice_id:
            # Generar PDF de la factura
            try:
                pdf_content, _ = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
                    'account.account_invoices',
                    [billing_request.invoice_id.id]
                )
                content = pdf_content
                filename = f'{billing_request.invoice_id.name.replace("/", "_")}.pdf'
            except Exception as e:
                _logger.exception("Error generando PDF")
                return request.not_found()
        else:
            return request.not_found()

        return request.make_response(
            content,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
                ('Content-Length', len(content)),
            ]
        )

    @http.route('/portal/billing/api/cfdi-files/<int:request_id>', type='json', auth='public', csrf=False)
    def api_cfdi_files_info(self, request_id, **kwargs):
        """
        Obtiene información sobre los archivos CFDI disponibles.

        Retorna:
            {success: bool, has_xml: bool, has_pdf: bool, folio_fiscal: str}
        """
        billing_request = request.env['billing.request'].sudo().browse(request_id)

        if not billing_request.exists():
            return {'success': False, 'errors': [_('Solicitud no encontrada')]}

        return {
            'success': True,
            'has_xml': bool(billing_request.cfdi_xml_file),
            'has_pdf': bool(billing_request.cfdi_pdf_file) or bool(billing_request.invoice_id),
            'folio_fiscal': billing_request.folio_fiscal or '',
            'cfdi_state': billing_request.cfdi_state or '',
            'invoice_name': billing_request.invoice_name or '',
            'download_xml_url': f'/portal/billing/download/xml/{request_id}' if billing_request.cfdi_xml_file else None,
            'download_pdf_url': f'/portal/billing/download/pdf/{request_id}' if (billing_request.cfdi_pdf_file or billing_request.invoice_id) else None,
        }
