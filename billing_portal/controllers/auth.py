# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
import uuid
import logging

_logger = logging.getLogger(__name__)


class BillingPortalAuth(http.Controller):
    """Controlador de autenticación del portal"""

    @http.route('/portal/billing/login', type='http', auth='public', website=True, methods=['GET', 'POST'])
    def portal_login(self, **kwargs):
        """Página de login del portal"""

        # Si ya tiene sesión, redirigir
        token = request.httprequest.cookies.get('billing_portal_token')
        if token:
            external_db = request.env['billing.external.db'].sudo()
            session = external_db.validate_portal_session(token)
            if session:
                return request.redirect('/portal/billing/orders')

        error = None

        if request.httprequest.method == 'POST':
            identifier = kwargs.get('identifier', '').strip()

            if not identifier:
                error = _('Ingrese su ID de MercadoLibre o email')
            else:
                # Intentar login
                result = self._do_login(identifier)
                if result.get('success'):
                    response = request.redirect('/portal/billing/orders')
                    response.set_cookie(
                        'billing_portal_token',
                        result['token'],
                        max_age=86400,  # 24 horas
                        httponly=True,
                        samesite='Lax'
                    )
                    return response
                else:
                    error = result.get('error', _('Error de autenticación'))

        return request.render('billing_portal.portal_login', {
            'error': error,
            'page_title': _('Iniciar Sesión'),
        })

    def _do_login(self, identifier):
        """Realiza el proceso de login"""
        external_db = request.env['billing.external.db'].sudo()

        # Buscar usuario en BD externa
        user = external_db.get_user_from_portal(identifier)

        if not user:
            # Verificar si el identifier es un receiver_id válido
            is_valid = external_db.validate_receiver_id(identifier)
            if is_valid:
                # Es un receiver_id nuevo, redirigir a registro
                return {
                    'success': False,
                    'error': _('Usuario no registrado. Complete su primera solicitud de factura para registrarse.'),
                    'needs_registration': True,
                    'receiver_id': identifier
                }
            else:
                # No existe
                return {
                    'success': False,
                    'error': _('No se encontró ninguna cuenta con ese ID o email. '
                              'Si es su primera vez, solicite una factura para registrarse.')
                }

        # Usuario encontrado, crear sesión
        token = str(uuid.uuid4())

        session_id = external_db.create_portal_session(
            user_id=user['id'],
            token=token,
            ip_address=request.httprequest.remote_addr,
            user_agent=request.httprequest.user_agent.string,
            duration_hours=24
        )

        if not session_id:
            return {
                'success': False,
                'error': _('Error creando sesión')
            }

        return {
            'success': True,
            'token': token,
            'user': user
        }

    @http.route('/portal/billing/logout', type='http', auth='public', website=True)
    def portal_logout(self, **kwargs):
        """Cierra la sesión del portal"""
        token = request.httprequest.cookies.get('billing_portal_token')

        if token:
            external_db = request.env['billing.external.db'].sudo()
            external_db.invalidate_session(token)

        response = request.redirect('/portal/billing/login')
        response.delete_cookie('billing_portal_token')
        return response

    @http.route('/portal/billing/guest', type='http', auth='public', website=True, methods=['GET', 'POST'])
    def portal_guest_access(self, order_ref=None, **kwargs):
        """
        Acceso como invitado para solicitar factura de una orden específica.
        No requiere login previo.
        """
        _logger.warning("=" * 80)
        _logger.warning("🌐 /portal/billing/guest ACCEDIDO")
        _logger.warning("📥 Método: %s", request.httprequest.method)
        _logger.warning("📥 IP: %s", request.httprequest.remote_addr)

        error = None

        if request.httprequest.method == 'POST':
            _logger.warning("📝 POST recibido - Búsqueda de orden")
            _logger.warning("=" * 80)
            _logger.warning("DEBUG - TODOS LOS DATOS DEL POST:")
            _logger.warning("  1. Parámetro order_ref de función: '%s'", order_ref)
            _logger.warning("  2. kwargs completo: %s", kwargs)
            _logger.warning("  3. request.params: %s", dict(request.params))
            _logger.warning("  4. request.httprequest.form: %s", dict(request.httprequest.form))
            _logger.warning("  5. request.httprequest.values: %s", dict(request.httprequest.values))
            _logger.warning("=" * 80)

            # Intentar obtener de múltiples fuentes
            order_ref = order_ref or kwargs.get('order_ref') or request.params.get('order_ref') or ''
            order_ref = order_ref.strip() if order_ref else ''

            _logger.warning("🔎 Referencia FINAL buscada: '%s'", order_ref)

            if not order_ref:
                _logger.warning("❌ Referencia vacía")
                error = _('Ingrese el número de pedido')
            else:
                # Buscar la orden (sin filtros de facturabilidad)
                _logger.warning("📞 Llamando a _find_order_by_ref()...")
                order = self._find_order_by_ref(order_ref)
                if order:
                    _logger.warning("✅ Orden encontrada!")
                    _logger.warning("   ID: %d", order.id)
                    _logger.warning("   Name: %s", order.name)
                    _logger.warning("   Ref: %s", order.client_order_ref or 'N/A')
                    _logger.warning("   Estado: %s", order.state)
                    _logger.warning("   Facturable: %s", order.is_portal_billable)
                    _logger.warning("🔄 Redirigiendo a formulario de facturación...")
                    _logger.warning("=" * 80)

                    # Siempre mostrar la orden encontrada
                    # Las validaciones de facturabilidad se hacen en el formulario
                    token = str(uuid.uuid4())
                    response = request.redirect(f'/portal/billing/guest/request?order_id={order.id}')
                    response.set_cookie(
                        'billing_portal_guest_token',
                        token,
                        max_age=3600,  # 1 hora
                        httponly=True
                    )
                    return response
                else:
                    _logger.warning("❌ No se encontró ninguna orden")
                    _logger.warning("=" * 80)
                    error = _('No se encontró ningún pedido con esa referencia')

        return request.render('billing_portal.portal_guest_access', {
            'error': error,
            'order_ref': order_ref or '',
            'page_title': _('Solicitar Factura'),
        })

    def _find_order_by_ref(self, ref):
        """
        Busca una orden por diferentes referencias.
        Usa el método del modelo para que se recargue con -u.
        """
        return request.env['sale.order'].sudo().find_order_by_ref_flexible(ref)

    @http.route('/portal/billing/guest/request', type='http', auth='public', website=True, methods=['GET', 'POST'])
    def portal_guest_request(self, order_id=None, **kwargs):
        """Formulario de facturación para invitados"""
        guest_token = request.httprequest.cookies.get('billing_portal_guest_token')

        if not guest_token:
            return request.redirect('/portal/billing/guest')

        if not order_id:
            return request.redirect('/portal/billing/guest')

        order = request.env['sale.order'].sudo().browse(int(order_id))

        if not order.exists():
            return request.render('billing_portal.portal_error', {
                'error_title': _('Orden no encontrada'),
                'error_message': _('La orden no existe')
            })

        # Verificar facturabilidad y obtener razón si no es facturable
        is_billable = order.is_portal_billable
        not_billable_reason = None

        if not is_billable:
            # Determinar la razón
            if order.invoice_status == 'invoiced':
                not_billable_reason = _('Esta orden ya está completamente facturada.')
            elif order.state not in ('sale', 'done'):
                not_billable_reason = _('La orden aún no está confirmada.')
            elif order.ml_shipment_status and order.ml_shipment_status != 'delivered':
                status_labels = {'pending': 'pendiente', 'shipped': 'en camino', 'cancelled': 'cancelado'}
                status_text = status_labels.get(order.ml_shipment_status, order.ml_shipment_status)
                not_billable_reason = _('El envío aún no ha sido entregado (estado: %s). Podrá solicitar factura cuando reciba su pedido.') % status_text
            elif order.invoice_status == 'no':
                not_billable_reason = _('No hay nada que facturar en esta orden.')
            else:
                not_billable_reason = _('Esta orden no puede facturarse actualmente.')

        if request.httprequest.method == 'GET':
            # Mostrar formulario (siempre, con o sin facturabilidad)
            usos_cfdi = request.env['catalogo.uso.cfdi'].sudo().search([])
            formas_pago = request.env['catalogo.forma.pago'].sudo().search([])

            return request.render('billing_portal.portal_billing_form', {
                'orders': order,
                'order_ids': str(order.id),
                'usos_cfdi': usos_cfdi,
                'formas_pago': formas_pago,
                'is_guest': True,
                'is_billable': is_billable,
                'not_billable_reason': not_billable_reason,
                'page_title': _('Solicitar Factura'),
            })

        # POST - Procesar (solo si es facturable)
        if not is_billable:
            return request.render('billing_portal.portal_error', {
                'error_title': _('Orden no facturable'),
                'error_message': not_billable_reason or _('Esta orden no puede facturarse actualmente.')
            })

        try:
            billing_request = request.env['billing.request'].sudo().create({
                'email': kwargs.get('email'),
                'phone': kwargs.get('phone'),
                'order_ids': [(6, 0, [order.id])],
                'order_references': order.client_order_ref,
                'uso_cfdi_id': int(kwargs.get('uso_cfdi_id')) if kwargs.get('uso_cfdi_id') else False,
                'forma_pago_id': int(kwargs.get('forma_pago_id')) if kwargs.get('forma_pago_id') else False,
                'ip_address': request.httprequest.remote_addr,
                'user_agent': request.httprequest.user_agent.string,
            })

            response = request.redirect(f'/portal/billing/guest/progress/{billing_request.id}')
            return response

        except Exception as e:
            _logger.exception("Error procesando solicitud guest")
            return request.render('billing_portal.portal_error', {
                'error_title': _('Error'),
                'error_message': str(e)
            })

    @http.route('/portal/billing/guest/progress/<int:request_id>', type='http', auth='public', website=True)
    def portal_guest_progress(self, request_id, **kwargs):
        """Página de progreso para invitados"""
        billing_request = request.env['billing.request'].sudo().browse(request_id)

        if not billing_request.exists():
            return request.render('billing_portal.portal_error', {
                'error_title': _('No encontrado'),
                'error_message': _('Solicitud no encontrada')
            })

        return request.render('billing_portal.portal_progress', {
            'billing_request': billing_request,
            'is_guest': True,
            'page_title': _('Estado de Solicitud'),
        })
