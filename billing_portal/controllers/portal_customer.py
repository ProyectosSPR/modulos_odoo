# -*- coding: utf-8 -*-
"""
Controlador que extiende CustomerPortal para integrar billing_portal
con el portal estándar de Odoo.

Rutas nuevas bajo /my/billing/*:
- /my/billing/orders - Órdenes disponibles para facturar
- /my/billing/requests - Historial de solicitudes
- /my/billing/request/<id> - Detalle de una solicitud

También extiende /my/orders para mostrar órdenes por billing_partner_id

IMPORTANTE: Heredamos de sale.controllers.portal.CustomerPortal
para sobrescribir correctamente los métodos _prepare_orders_domain
"""

from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import pager as portal_pager
# Heredar del controlador de SALE, no del portal base
from odoo.addons.sale.controllers.portal import CustomerPortal
import logging

_logger = logging.getLogger(__name__)


class BillingCustomerPortal(CustomerPortal):
    """Extiende CustomerPortal para agregar funcionalidades de facturación."""

    # =========================================
    # Sobrescribir dominios de /my/orders y /my/quotes
    # para incluir órdenes por billing_partner_id
    # =========================================

    def _prepare_orders_domain(self, partner):
        """
        Dominio de /my/orders - Busca por partner_id O billing_partner_id.
        Las órdenes aparecen si:
        - El usuario es el partner original de la orden
        - El usuario fue asignado como billing_partner (cliente de facturación)
        """
        return [
            '|',
            ('partner_id', '=', partner.id),
            ('billing_partner_id', '=', partner.id),
            ('state', 'in', ['sale', 'done']),
        ]

    def _prepare_quotations_domain(self, partner):
        """
        Dominio de /my/quotes - Misma lógica para cotizaciones.
        """
        return [
            '|',
            ('partner_id', '=', partner.id),
            ('billing_partner_id', '=', partner.id),
            ('state', 'in', ['sent', 'cancel']),
        ]

    # =========================================
    # Contadores para portal home
    # =========================================

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
        """Dominio para órdenes facturables del partner (billing portal)."""
        return [
            '|',
            ('partner_id', '=', partner.id),
            ('billing_partner_id', '=', partner.id),
            ('state', 'in', ['sale', 'done']),
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
    # API para vincular órdenes al usuario
    # =========================================

    @http.route('/my/billing/api/claim-orders', type='json', auth='user', methods=['POST'])
    def api_claim_orders(self, order_ids=None, **kw):
        """
        Vincula órdenes al usuario actual asignando billing_partner_id.

        Esto permite que las órdenes encontradas en búsqueda pública
        aparezcan en "Mis Órdenes" del usuario logueado.

        Args:
            order_ids: Lista de IDs de órdenes o string separado por comas

        Returns:
            dict con success, claimed_count, orders, errors
        """
        result = {
            'success': False,
            'claimed_count': 0,
            'orders': [],
            'errors': []
        }

        if not order_ids:
            result['errors'].append(_('No se especificaron órdenes'))
            return result

        # Parsear order_ids si es string
        if isinstance(order_ids, str):
            order_id_list = [int(x.strip()) for x in order_ids.split(',') if x.strip().isdigit()]
        elif isinstance(order_ids, list):
            order_id_list = [int(x) for x in order_ids if str(x).isdigit()]
        else:
            order_id_list = [int(order_ids)]

        if not order_id_list:
            result['errors'].append(_('IDs de órdenes inválidos'))
            return result

        user = request.env.user
        partner = user.partner_id

        # Buscar órdenes
        orders = request.env['sale.order'].sudo().browse(order_id_list).exists()

        if not orders:
            result['errors'].append(_('No se encontraron las órdenes especificadas'))
            return result

        # Filtrar solo órdenes que pueden ser reclamadas
        # (no tienen billing_partner_id o ya pertenecen al usuario)
        claimable_orders = orders.filtered(
            lambda o: not o.billing_partner_id or o.billing_partner_id.id == partner.id
        )

        already_claimed = orders.filtered(
            lambda o: o.billing_partner_id and o.billing_partner_id.id != partner.id
        )

        if already_claimed:
            result['errors'].append(
                _('Las siguientes órdenes ya fueron reclamadas por otro usuario: %s') %
                ', '.join(already_claimed.mapped('name'))
            )

        # Asignar billing_partner_id a las órdenes reclamables
        if claimable_orders:
            claimable_orders.write({'billing_partner_id': partner.id})
            _logger.info(
                "Usuario %s (partner_id=%d) reclamó %d órdenes: %s",
                user.login, partner.id, len(claimable_orders),
                ', '.join(claimable_orders.mapped('name'))
            )

            result['success'] = True
            result['claimed_count'] = len(claimable_orders)
            result['orders'] = [{
                'id': o.id,
                'name': o.name,
                'client_order_ref': o.client_order_ref or '',
                'amount_total': o.amount_total,
                'date_order': o.date_order.isoformat() if o.date_order else '',
            } for o in claimable_orders]

        return result

    @http.route('/my/billing/api/release-orders', type='json', auth='user', methods=['POST'])
    def api_release_orders(self, order_ids=None, **kw):
        """
        Libera órdenes del usuario actual (quita billing_partner_id).

        Args:
            order_ids: Lista de IDs de órdenes

        Returns:
            dict con success, released_count, errors
        """
        result = {
            'success': False,
            'released_count': 0,
            'errors': []
        }

        if not order_ids:
            result['errors'].append(_('No se especificaron órdenes'))
            return result

        # Parsear order_ids
        if isinstance(order_ids, str):
            order_id_list = [int(x.strip()) for x in order_ids.split(',') if x.strip().isdigit()]
        elif isinstance(order_ids, list):
            order_id_list = [int(x) for x in order_ids if str(x).isdigit()]
        else:
            order_id_list = [int(order_ids)]

        user = request.env.user
        partner = user.partner_id

        # Buscar solo órdenes que pertenecen al usuario
        orders = request.env['sale.order'].sudo().search([
            ('id', 'in', order_id_list),
            ('billing_partner_id', '=', partner.id),
        ])

        if orders:
            orders.write({'billing_partner_id': False})
            _logger.info(
                "Usuario %s liberó %d órdenes: %s",
                user.login, len(orders), ', '.join(orders.mapped('name'))
            )

            result['success'] = True
            result['released_count'] = len(orders)
        else:
            result['errors'].append(_('No se encontraron órdenes para liberar'))

        return result

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
