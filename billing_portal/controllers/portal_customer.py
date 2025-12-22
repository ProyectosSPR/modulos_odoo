# -*- coding: utf-8 -*-
"""
Controlador que extiende CustomerPortal para integrar billing_portal
con el portal estándar de Odoo.

Rutas nuevas bajo /my/billing/*:
- /my/billing/orders - Órdenes disponibles para facturar
- /my/billing/requests - Historial de solicitudes
- /my/billing/request/<id> - Detalle de una solicitud
"""

from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
import logging

_logger = logging.getLogger(__name__)


class BillingCustomerPortal(CustomerPortal):
    """Extiende CustomerPortal para agregar funcionalidades de facturación."""

    def _prepare_home_portal_values(self, counters):
        """Agrega contadores de facturación al portal home."""
        values = super()._prepare_home_portal_values(counters)

        user = request.env.user
        partner = user.partner_id

        # Contador de órdenes facturables
        if 'billing_orders_count' in counters:
            domain = self._get_billing_orders_domain(partner)
            values['billing_orders_count'] = request.env['sale.order'].sudo().search_count(domain)

        # Contador de solicitudes de factura
        if 'billing_requests_count' in counters:
            domain = self._get_billing_requests_domain(user, partner)
            values['billing_requests_count'] = request.env['billing.request'].sudo().search_count(domain)

        return values

    def _get_billing_orders_domain(self, partner):
        """Dominio para órdenes facturables del partner."""
        return [
            '|',
            ('partner_id', '=', partner.id),
            ('billing_partner_id', '=', partner.id),
            ('state', 'in', ['sale', 'done']),
            # Solo órdenes que no tienen solicitud activa
            # TODO: Agregar filtro si existe campo de factura
        ]

    def _get_billing_requests_domain(self, user, partner):
        """Dominio para solicitudes de factura del usuario."""
        return [
            '|',
            ('user_id', '=', user.id),
            ('partner_id', '=', partner.id),
        ]

    # =========================================
    # Rutas de Órdenes Facturables
    # =========================================

    @http.route(['/my/billing/orders', '/my/billing/orders/page/<int:page>'],
                type='http', auth='user', website=True)
    def my_billing_orders(self, page=1, sortby=None, filterby=None, search=None, **kw):
        """Lista de órdenes disponibles para facturar."""
        values = self._prepare_portal_layout_values()
        SaleOrder = request.env['sale.order'].sudo()

        user = request.env.user
        partner = user.partner_id

        domain = self._get_billing_orders_domain(partner)

        # Búsqueda
        if search:
            domain = ['&'] + domain + [
                '|',
                ('name', 'ilike', search),
                ('client_order_ref', 'ilike', search),
            ]

        # Opciones de ordenamiento
        searchbar_sortings = {
            'date': {'label': _('Fecha (Reciente)'), 'order': 'date_order desc'},
            'name': {'label': _('Referencia'), 'order': 'name'},
            'amount': {'label': _('Monto'), 'order': 'amount_total desc'},
        }
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        # Paginación
        orders_count = SaleOrder.search_count(domain)
        pager = portal_pager(
            url='/my/billing/orders',
            url_args={'sortby': sortby, 'search': search or ''},
            total=orders_count,
            page=page,
            step=self._items_per_page,
        )

        orders = SaleOrder.search(
            domain,
            order=order,
            limit=self._items_per_page,
            offset=pager['offset']
        )

        values.update({
            'orders': orders,
            'page_name': 'billing_orders',
            'pager': pager,
            'default_url': '/my/billing/orders',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
            'search': search or '',
        })

        return request.render('billing_portal.portal_my_billing_orders', values)

    @http.route('/my/billing/request', type='http', auth='user', website=True, methods=['GET'])
    def billing_request_redirect(self, order_ids=None, **kw):
        """
        Redirige al formulario de facturación con las órdenes seleccionadas.
        Recibe los IDs de órdenes desde el formulario de selección.
        """
        if not order_ids:
            return request.redirect('/my/billing/orders')

        # Redirigir al formulario existente del billing_portal
        return request.redirect(f'/portal/billing/request?order_ids={order_ids}')

    # =========================================
    # Rutas de Solicitudes de Factura
    # =========================================

    @http.route(['/my/billing/requests', '/my/billing/requests/page/<int:page>'],
                type='http', auth='user', website=True)
    def my_billing_requests(self, page=1, sortby=None, filterby=None, **kw):
        """Lista de solicitudes de factura del usuario."""
        values = self._prepare_portal_layout_values()
        BillingRequest = request.env['billing.request'].sudo()

        user = request.env.user
        partner = user.partner_id

        domain = self._get_billing_requests_domain(user, partner)

        # Opciones de ordenamiento
        searchbar_sortings = {
            'date': {'label': _('Fecha (Reciente)'), 'order': 'create_date desc'},
            'name': {'label': _('Número'), 'order': 'name desc'},
            'state': {'label': _('Estado'), 'order': 'state'},
        }
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        # Filtros por estado
        searchbar_filters = {
            'all': {'label': _('Todas'), 'domain': []},
            'pending': {'label': _('En Proceso'), 'domain': [('state', 'in', ['draft', 'validating_csf', 'csf_validated', 'creating_partner', 'creating_invoice', 'pending_stamp'])]},
            'completed': {'label': _('Completadas'), 'domain': [('state', 'in', ['stamped', 'sent'])]},
            'error': {'label': _('Con Error'), 'domain': [('state', '=', 'error')]},
        }
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']

        # Paginación
        requests_count = BillingRequest.search_count(domain)
        pager = portal_pager(
            url='/my/billing/requests',
            url_args={'sortby': sortby, 'filterby': filterby},
            total=requests_count,
            page=page,
            step=self._items_per_page,
        )

        billing_requests = BillingRequest.search(
            domain,
            order=order,
            limit=self._items_per_page,
            offset=pager['offset']
        )

        values.update({
            'billing_requests': billing_requests,
            'page_name': 'billing_requests',
            'pager': pager,
            'default_url': '/my/billing/requests',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
            'searchbar_filters': searchbar_filters,
            'filterby': filterby,
        })

        return request.render('billing_portal.portal_my_billing_requests', values)

    @http.route('/my/billing/request/<int:request_id>', type='http', auth='user', website=True)
    def my_billing_request_detail(self, request_id, **kw):
        """Detalle de una solicitud de factura."""
        values = self._prepare_portal_layout_values()

        billing_request = request.env['billing.request'].sudo().browse(request_id)

        if not billing_request.exists():
            return request.redirect('/my/billing/requests')

        # Verificar que pertenece al usuario
        user = request.env.user
        is_owner = (
            billing_request.user_id.id == user.id or
            billing_request.partner_id.id == user.partner_id.id or
            user.has_group('base.group_system')
        )

        if not is_owner:
            return request.redirect('/my/billing/requests')

        values.update({
            'billing_request': billing_request,
            'page_name': 'billing_request_detail',
        })

        return request.render('billing_portal.portal_billing_request_detail', values)
