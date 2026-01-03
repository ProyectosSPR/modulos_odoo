# -*- coding: utf-8 -*-
"""
Controlador PÚBLICO del portal de facturación.
Solo permite BUSCAR órdenes sin login.
Para FACTURAR se requiere autenticación en Odoo.
"""

from odoo import http, _
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class BillingPortalPublic(http.Controller):
    """
    Rutas públicas - No requieren autenticación.
    Solo búsqueda de órdenes.
    """

    @http.route('/portal/billing', type='http', auth='public', website=True, methods=['GET', 'POST'])
    def billing_search(self, **kwargs):
        """
        Página principal de búsqueda de órdenes.
        PÚBLICO - No requiere login.

        GET: Muestra formulario de búsqueda
        POST: Busca órdenes por client_order_ref, name, ml_order_id o ml_pack_id

        Retorna MÚLTIPLES órdenes para permitir selección.
        """
        error = None
        orders = []
        order_ref = kwargs.get('order_ref', '').strip()

        # Verificar si el usuario está logueado
        is_logged_in = request.env.user.id != request.env.ref('base.public_user').id

        # Obtener órdenes ya seleccionadas (del carrito de facturación)
        selected_ids = kwargs.get('selected_orders', '').strip()
        selected_order_ids = []
        if selected_ids:
            selected_order_ids = [int(x) for x in selected_ids.split(',') if x.strip().isdigit()]

        # Cargar órdenes seleccionadas previamente
        selected_orders = []
        if selected_order_ids:
            selected_orders = request.env['sale.order'].sudo().browse(selected_order_ids).exists()

        if request.httprequest.method == 'POST' and order_ref:
            _logger.info("Búsqueda de orden: '%s'", order_ref)

            # Buscar por múltiples campos:
            # - client_order_ref: Referencia del cliente
            # - name: Nombre de la orden (ej: DML00123)
            # - ml_order_id: ID de orden de MercadoLibre
            # - ml_pack_id: ID de pack de MercadoLibre
            search_domain = [
                '|', '|', '|',
                ('client_order_ref', 'ilike', order_ref),
                ('name', 'ilike', order_ref),
                ('ml_order_id', '=', order_ref),
                ('ml_pack_id', '=', order_ref),
            ]

            # Filtrar solo órdenes facturables (excluye productos excluidos)
            domain = ['&', ('is_portal_billable', '=', True)] + search_domain

            # Buscar hasta 20 órdenes coincidentes
            orders = request.env['sale.order'].sudo().search(domain, limit=20, order='date_order desc')

            if orders:
                _logger.info("Órdenes encontradas: %d", len(orders))
            else:
                # Si no hay órdenes facturables, verificar si existen pero no son facturables
                all_orders = request.env['sale.order'].sudo().search(search_domain, limit=5)
                if all_orders:
                    # Hay órdenes pero no son facturables
                    non_billable_reasons = []
                    for order in all_orders:
                        is_billable, reason = order.get_billing_eligibility()
                        if not is_billable:
                            non_billable_reasons.append(f"{order.name}: {reason}")
                    if non_billable_reasons:
                        error = _('Se encontraron pedidos pero no son facturables:\n%s') % '\n'.join(non_billable_reasons)
                    else:
                        error = _('Se encontraron pedidos pero no son facturables desde el portal.')
                else:
                    error = _('No se encontró ningún pedido con esa referencia: %s') % order_ref
                _logger.info("Orden NO encontrada para: '%s'", order_ref)

        return request.render('billing_portal.portal_search', {
            'orders': orders,
            'selected_orders': selected_orders,
            'order_ref': order_ref,
            'error': error,
            'is_logged_in': is_logged_in,
            'page_title': _('Portal de Facturación'),
        })

    @http.route('/portal/billing/view/<int:order_id>', type='http', auth='public', website=True)
    def billing_view_order(self, order_id, **kwargs):
        """
        Ver detalles de una orden (público).
        Para facturar debe loguearse.
        """
        order = request.env['sale.order'].sudo().browse(order_id)

        if not order.exists():
            return request.render('billing_portal.portal_error', {
                'error_title': _('Orden no encontrada'),
                'error_message': _('La orden especificada no existe.')
            })

        # Verificar si usuario está logueado
        is_logged_in = request.env.user.id != request.env.ref('base.public_user').id

        # Verificar si es facturable
        is_billable = getattr(order, 'is_portal_billable', True)
        not_billable_reason = None

        if not is_billable:
            if order.invoice_status == 'invoiced':
                not_billable_reason = _('Esta orden ya está completamente facturada.')
            elif order.state not in ('sale', 'done'):
                not_billable_reason = _('La orden aún no está confirmada.')
            else:
                not_billable_reason = _('Esta orden no puede facturarse actualmente.')

        return request.render('billing_portal.portal_order_view', {
            'order': order,
            'is_logged_in': is_logged_in,
            'is_billable': is_billable,
            'not_billable_reason': not_billable_reason,
            'page_title': _('Orden %s') % order.name,
        })
