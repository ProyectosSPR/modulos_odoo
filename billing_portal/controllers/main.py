# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class BillingPortalMain(http.Controller):
    """Controlador principal del portal de facturación"""

    def _get_portal_session(self):
        """Obtiene la sesión actual del portal"""
        token = request.httprequest.cookies.get('billing_portal_token')
        if not token:
            return None

        external_db = request.env['billing.external.db'].sudo()
        return external_db.validate_portal_session(token)

    def _require_auth(self):
        """Verifica que el usuario esté autenticado"""
        session = self._get_portal_session()
        if not session:
            return request.redirect('/portal/billing/login')
        return session

    @http.route('/portal/billing', type='http', auth='public', website=True)
    def portal_billing_home(self, **kwargs):
        """Página principal del portal de facturación"""
        session = self._get_portal_session()
        if not session:
            return request.redirect('/portal/billing/login')

        return request.redirect('/portal/billing/orders')

    @http.route('/portal/billing/orders', type='http', auth='public', website=True)
    def portal_billing_orders(self, search=None, **kwargs):
        """Página de órdenes del usuario"""
        session = self._get_portal_session()
        if not session:
            return request.redirect('/portal/billing/login')

        receiver_id = session.get('receiver_id')

        # Buscar órdenes en Odoo
        domain = [
            ('is_portal_billable', '=', True),
        ]

        # Filtrar por receiver_id si existe
        if receiver_id:
            domain.append(('ml_receiver_id', '=', receiver_id))

        # Búsqueda adicional (se agrega con AND implícito)
        if search and len(search.strip()) >= 2:
            domain += [
                '|', '|', '|',
                ('client_order_ref', 'ilike', search),
                ('name', 'ilike', search),
                ('ml_order_id', 'ilike', search),
                ('ml_pack_id', 'ilike', search),
            ]

        orders = request.env['sale.order'].sudo().search(domain, limit=50, order='date_order desc')

        # Obtener solicitudes pendientes
        pending_requests = request.env['billing.request'].sudo().search([
            ('receiver_id', '=', receiver_id),
            ('state', 'not in', ['done', 'cancelled', 'error'])
        ])

        return request.render('billing_portal.portal_orders', {
            'orders': orders,
            'search': search or '',
            'user_data': session,
            'pending_requests': pending_requests,
            'page_title': _('Mis Órdenes'),
        })

    @http.route('/portal/billing/request', type='http', auth='public', website=True, methods=['GET', 'POST'])
    def portal_billing_request(self, order_ids=None, **kwargs):
        """Página de solicitud de facturación"""
        session = self._get_portal_session()
        if not session:
            return request.redirect('/portal/billing/login')

        if request.httprequest.method == 'GET':
            # Mostrar formulario
            if not order_ids:
                return request.redirect('/portal/billing/orders')

            # Convertir order_ids a lista
            if isinstance(order_ids, str):
                order_ids = [int(x) for x in order_ids.split(',')]
            else:
                order_ids = [int(order_ids)]

            orders = request.env['sale.order'].sudo().browse(order_ids)

            # Verificar que todas son facturables
            non_billable = orders.filtered(lambda o: not o.is_portal_billable)
            if non_billable:
                return request.render('billing_portal.portal_error', {
                    'error_title': _('Órdenes no facturables'),
                    'error_message': _('Las siguientes órdenes no pueden facturarse: %s') %
                                    ', '.join(non_billable.mapped('name'))
                })

            # Obtener catálogos
            usos_cfdi = request.env['catalogo.uso.cfdi'].sudo().search([])
            formas_pago = request.env['catalogo.forma.pago'].sudo().search([])
            regimenes = request.env['catalogo.regimen.fiscal'].sudo().search([])

            # Datos del usuario guardados
            saved_data = {
                'rfc': session.get('rfc', ''),
                'razon_social': session.get('razon_social', ''),
                'email': session.get('email', ''),
                'telefono': session.get('telefono', ''),
            }

            return request.render('billing_portal.portal_billing_form', {
                'orders': orders,
                'order_ids': ','.join(str(o.id) for o in orders),
                'usos_cfdi': usos_cfdi,
                'formas_pago': formas_pago,
                'regimenes': regimenes,
                'user_data': session,
                'saved_data': saved_data,
                'page_title': _('Solicitar Factura'),
            })

        # POST - Procesar solicitud
        return self._process_billing_request(session, **kwargs)

    def _process_billing_request(self, session, **kwargs):
        """Procesa la solicitud de facturación"""
        try:
            order_ids = kwargs.get('order_ids', '')
            if isinstance(order_ids, str):
                order_ids = [int(x) for x in order_ids.split(',') if x]

            orders = request.env['sale.order'].sudo().browse(order_ids)

            # Crear solicitud
            billing_request = request.env['billing.request'].sudo().create({
                'receiver_id': session.get('receiver_id'),
                'email': kwargs.get('email'),
                'phone': kwargs.get('phone'),
                'order_ids': [(6, 0, order_ids)],
                'order_references': ', '.join(orders.mapped('client_order_ref')),
                'uso_cfdi_id': int(kwargs.get('uso_cfdi_id')) if kwargs.get('uso_cfdi_id') else False,
                'forma_pago_id': int(kwargs.get('forma_pago_id')) if kwargs.get('forma_pago_id') else False,
                'ip_address': request.httprequest.remote_addr,
                'user_agent': request.httprequest.user_agent.string,
            })

            # Redirigir a página de progreso
            return request.redirect(f'/portal/billing/progress/{billing_request.id}')

        except Exception as e:
            _logger.exception("Error procesando solicitud de facturación")
            return request.render('billing_portal.portal_error', {
                'error_title': _('Error'),
                'error_message': str(e)
            })

    @http.route('/portal/billing/progress/<int:request_id>', type='http', auth='public', website=True)
    def portal_billing_progress(self, request_id, **kwargs):
        """Página de progreso de la solicitud"""
        session = self._get_portal_session()
        if not session:
            return request.redirect('/portal/billing/login')

        billing_request = request.env['billing.request'].sudo().browse(request_id)

        if not billing_request.exists():
            return request.render('billing_portal.portal_error', {
                'error_title': _('No encontrado'),
                'error_message': _('Solicitud no encontrada')
            })

        # Verificar que pertenece al usuario
        if billing_request.receiver_id != session.get('receiver_id'):
            return request.render('billing_portal.portal_error', {
                'error_title': _('Acceso denegado'),
                'error_message': _('No tiene permiso para ver esta solicitud')
            })

        return request.render('billing_portal.portal_progress', {
            'billing_request': billing_request,
            'user_data': session,
            'page_title': _('Estado de Solicitud'),
        })

    @http.route('/portal/billing/history', type='http', auth='public', website=True)
    def portal_billing_history(self, **kwargs):
        """Historial de solicitudes"""
        session = self._get_portal_session()
        if not session:
            return request.redirect('/portal/billing/login')

        requests_list = request.env['billing.request'].sudo().search([
            ('receiver_id', '=', session.get('receiver_id'))
        ], order='create_date desc', limit=50)

        return request.render('billing_portal.portal_history', {
            'requests': requests_list,
            'user_data': session,
            'page_title': _('Historial de Solicitudes'),
        })
