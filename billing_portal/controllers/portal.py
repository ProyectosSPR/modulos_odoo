# -*- coding: utf-8 -*-
"""
Controlador PRIVADO del portal de facturación.
REQUIERE autenticación de Odoo para todas las operaciones.
"""

from odoo import http, _
from odoo.http import request
import logging
import base64

_logger = logging.getLogger(__name__)


class BillingPortalPrivate(http.Controller):
    """
    Rutas privadas - Requieren autenticación de Odoo.
    Facturación, historial, progreso.
    """

    @http.route(['/portal/billing/request/<int:order_id>',
                 '/portal/billing/request'], type='http', auth='user', website=True, methods=['GET', 'POST'])
    def billing_request(self, order_id=None, order_ids=None, **kwargs):
        """
        Solicitar factura para una o varias órdenes.
        REQUIERE LOGIN - auth='user'

        Soporta:
        - /portal/billing/request/123 (una orden)
        - /portal/billing/request?order_ids=123,456,789 (múltiples órdenes)

        GET: Muestra formulario de facturación
        POST: Crea solicitud de facturación
        """
        # Obtener IDs de órdenes
        if order_id:
            # Ruta con ID único
            order_id_list = [order_id]
        elif order_ids:
            # Parámetro con múltiples IDs separados por coma
            if isinstance(order_ids, str):
                order_id_list = [int(x.strip()) for x in order_ids.split(',') if x.strip().isdigit()]
            else:
                order_id_list = [int(order_ids)]
        elif kwargs.get('order_ids'):
            # Desde formulario POST
            ids_str = kwargs.get('order_ids', '')
            if isinstance(ids_str, str):
                order_id_list = [int(x.strip()) for x in ids_str.split(',') if x.strip().isdigit()]
            else:
                order_id_list = [int(ids_str)]
        else:
            return request.render('billing_portal.portal_error', {
                'error_title': _('Sin órdenes'),
                'error_message': _('No se especificaron órdenes para facturar.')
            })

        # Buscar órdenes
        orders = request.env['sale.order'].sudo().browse(order_id_list)
        orders = orders.exists()  # Filtrar solo las que existen

        if not orders:
            return request.render('billing_portal.portal_error', {
                'error_title': _('Órdenes no encontradas'),
                'error_message': _('Las órdenes especificadas no existen.')
            })

        # Verificar cuáles son facturables
        non_billable = orders.filtered(lambda o: not getattr(o, 'is_portal_billable', True))
        if non_billable:
            return request.render('billing_portal.portal_error', {
                'error_title': _('Órdenes no facturables'),
                'error_message': _('Las siguientes órdenes no pueden facturarse: %s') % ', '.join(non_billable.mapped('name'))
            })

        if request.httprequest.method == 'GET':
            # Mostrar formulario
            usos_cfdi = request.env['catalogo.uso.cfdi'].sudo().search([])
            formas_pago = request.env['catalogo.forma.pago'].sudo().search([])

            # Datos del usuario logueado
            user = request.env.user
            partner = user.partner_id

            # Preparar order_ids como string para el formulario
            order_ids_str = ','.join(str(o.id) for o in orders)

            return request.render('billing_portal.portal_billing_form', {
                'orders': orders,
                'order_ids': order_ids_str,
                'usos_cfdi': usos_cfdi,
                'formas_pago': formas_pago,
                'user': user,
                'partner': partner,
                'saved_data': {
                    'email': partner.email or '',
                    'telefono': partner.phone or '',
                },
                'page_title': _('Solicitar Factura - %d órdenes') % len(orders) if len(orders) > 1 else _('Solicitar Factura - %s') % orders[0].name,
            })

        # POST - Crear solicitud
        _logger.info("Creando solicitud de facturación para %d órdenes", len(orders))
        _logger.info("Usuario: %s", request.env.user.login)

        try:
            # Referencias de órdenes
            order_refs = ', '.join(o.client_order_ref or o.name for o in orders)

            billing_request = request.env['billing.request'].sudo().create({
                'user_id': request.env.user.id,
                'partner_id': request.env.user.partner_id.id,
                'email': kwargs.get('email') or request.env.user.email,
                'phone': kwargs.get('phone') or request.env.user.partner_id.phone,
                'order_ids': [(6, 0, orders.ids)],
                'order_references': order_refs,
                'rfc': kwargs.get('rfc'),
                'razon_social': kwargs.get('razon_social'),
                'codigo_postal': kwargs.get('codigo_postal'),
                'uso_cfdi_id': int(kwargs.get('uso_cfdi_id')) if kwargs.get('uso_cfdi_id') else False,
                'forma_pago_id': int(kwargs.get('forma_pago_id')) if kwargs.get('forma_pago_id') else False,
                'ip_address': request.httprequest.remote_addr,
                'user_agent': request.httprequest.user_agent.string,
            })

            _logger.info("Solicitud creada: %s", billing_request.name)

            return request.redirect(f'/portal/billing/progress/{billing_request.id}')

        except Exception as e:
            _logger.exception("Error creando solicitud de facturación")
            return request.render('billing_portal.portal_error', {
                'error_title': _('Error'),
                'error_message': str(e)
            })

    @http.route('/portal/billing/progress/<int:request_id>', type='http', auth='user', website=True)
    def billing_progress(self, request_id, **kwargs):
        """
        Ver progreso de una solicitud de facturación.
        REQUIERE LOGIN.
        """
        billing_request = request.env['billing.request'].sudo().browse(request_id)

        if not billing_request.exists():
            return request.render('billing_portal.portal_error', {
                'error_title': _('No encontrada'),
                'error_message': _('Solicitud no encontrada.')
            })

        # Verificar que pertenece al usuario (o es admin)
        is_owner = (
            billing_request.user_id.id == request.env.user.id or
            billing_request.partner_id.id == request.env.user.partner_id.id or
            request.env.user.has_group('base.group_system')
        )

        if not is_owner:
            return request.render('billing_portal.portal_error', {
                'error_title': _('Acceso denegado'),
                'error_message': _('No tiene permiso para ver esta solicitud.')
            })

        return request.render('billing_portal.portal_progress', {
            'billing_request': billing_request,
            'page_title': _('Estado de Solicitud #%s') % billing_request.name,
        })

    @http.route('/portal/billing/history', type='http', auth='user', website=True)
    def billing_history(self, **kwargs):
        """
        Historial de solicitudes del usuario.
        REQUIERE LOGIN.
        """
        user = request.env.user
        partner = user.partner_id

        # Buscar solicitudes del usuario
        domain = [
            '|',
            ('user_id', '=', user.id),
            ('partner_id', '=', partner.id),
        ]

        requests_list = request.env['billing.request'].sudo().search(
            domain, order='create_date desc', limit=50
        )

        return request.render('billing_portal.portal_history', {
            'requests': requests_list,
            'user': user,
            'page_title': _('Historial de Solicitudes'),
        })

    @http.route('/portal/billing/orders', type='http', auth='user', website=True)
    def my_orders(self, search=None, **kwargs):
        """
        Mis órdenes facturables.
        REQUIERE LOGIN.
        """
        user = request.env.user
        partner = user.partner_id

        # Buscar órdenes del partner
        domain = [
            ('partner_id', '=', partner.id),
        ]

        # Filtro de búsqueda
        if search and len(search.strip()) >= 2:
            search = search.strip()
            domain += [
                '|',
                ('client_order_ref', 'ilike', search),
                ('name', 'ilike', search),
            ]

        orders = request.env['sale.order'].sudo().search(
            domain, limit=50, order='date_order desc'
        )

        return request.render('billing_portal.portal_my_orders', {
            'orders': orders,
            'search': search or '',
            'user': user,
            'page_title': _('Mis Órdenes'),
        })

    # =========================================
    # Descargas de archivos CFDI
    # =========================================

    @http.route('/portal/billing/download/xml/<int:request_id>', type='http', auth='user')
    def download_xml(self, request_id, **kwargs):
        """
        Descargar XML del CFDI.
        REQUIERE LOGIN.
        """
        billing_request = request.env['billing.request'].sudo().browse(request_id)

        if not billing_request.exists() or not billing_request.cfdi_xml_file:
            return request.not_found()

        # Verificar acceso
        is_owner = (
            billing_request.user_id.id == request.env.user.id or
            billing_request.partner_id.id == request.env.user.partner_id.id or
            request.env.user.has_group('base.group_system')
        )

        if not is_owner:
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

    @http.route('/portal/billing/download/pdf/<int:request_id>', type='http', auth='user')
    def download_pdf(self, request_id, **kwargs):
        """
        Descargar PDF del CFDI.
        REQUIERE LOGIN.
        """
        billing_request = request.env['billing.request'].sudo().browse(request_id)

        if not billing_request.exists():
            return request.not_found()

        # Verificar acceso
        is_owner = (
            billing_request.user_id.id == request.env.user.id or
            billing_request.partner_id.id == request.env.user.partner_id.id or
            request.env.user.has_group('base.group_system')
        )

        if not is_owner:
            return request.not_found()

        # Obtener PDF
        if billing_request.cfdi_pdf_file:
            content = base64.b64decode(billing_request.cfdi_pdf_file)
            filename = billing_request.cfdi_pdf_filename or f'CFDI_{billing_request.name}.pdf'
        elif billing_request.invoice_id:
            try:
                pdf_content, _ = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
                    'account.account_invoices',
                    [billing_request.invoice_id.id]
                )
                content = pdf_content
                filename = f'{billing_request.invoice_id.name.replace("/", "_")}.pdf'
            except Exception:
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
