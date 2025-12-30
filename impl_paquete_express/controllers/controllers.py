# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.addons.website_sale.controllers.main import WebsiteSale, PaymentPortal
from odoo.addons.website_sale_delivery.controllers.main import WebsiteSaleDelivery

from odoo.exceptions import AccessDenied, ValidationError, UserError
from odoo.http import request
import json


class MondialRelay(http.Controller):

    @http.route(['/website_sale_delivery_paquete_express/api_quotation'], type='json', auth="public", website=True)
    def paquete_express_api_quotation(self, **data):
        return request.env['stock.picking'].sudo().px_api_quotation(data['partner_zip'], data['partner_state'], data['amount_total'], data['products'])


    @http.route(['/website_sale_delivery_paquete_express/update_shipping'], type='json', auth="public", website=True)
    def paquete_express_update_shipping(self, **data):
        order = request.website.sale_get_order()

        if order.partner_id == request.website.user_id.sudo().partner_id:
            raise AccessDenied('Customer of the order cannot be the public user at this step.')
        
        order.px_service_data = json.dumps(data['px_service'])
        
        for record in order.order_line.filtered(lambda line: line.product_id.default_code == 'PX'):
            record.price_unit = data['px_service']['amount']['totalAmnt']

        # if order.carrier_id.country_ids:
        #     country_is_allowed = data['Pays'][:2].upper() in order.carrier_id.country_ids.mapped(lambda c: c.code.upper())
        #     assert country_is_allowed, _("%s is not allowed for this delivery carrier.", data['Pays'])

        partner_shipping = order.partner_id.sudo()._paquete_express_search_or_create({
            'id': data['px_service']['id'],
            'name': order.partner_shipping_id.name,
            'street': order.partner_shipping_id.street,
            'street2': order.partner_shipping_id.street2,
            'zip': order.partner_shipping_id.zip,
            'state_id': order.partner_shipping_id.state_id.id,
            'email': order.partner_shipping_id.email,
            'phone': order.partner_shipping_id.phone,
            'country_code': 'mx',
        })
        if order.partner_shipping_id != partner_shipping:
            order.partner_shipping_id = partner_shipping

        return {
            'address': request.env['ir.qweb']._render('website_sale.address_on_payment', {
                'order': order,
                'only_services': order and order.only_services,
            }),
            'new_partner_shipping_id': order.partner_shipping_id.id,
        }


class WebsiteSaleMondialrelay(WebsiteSale):

    @http.route()
    def address(self, **kw):
        res = super().address(**kw)
        Partner_sudo = request.env['res.partner'].sudo()
        partner_id = res.qcontext.get('partner_id', 0)
        if partner_id > 0 and Partner_sudo.browse(partner_id).is_paquete_express:
            raise UserError(_('You cannot edit the address of a Point Relais®.'))
        return res
    
    @http.route(['/shop/carrier_rate_shipment'], type='json', auth='public', methods=['POST'], website=True)
    def cart_carrier_rate_shipment(self, carrier_id, **kw):
        res = super().cart_carrier_rate_shipment(carrier_id, **kw)

        carrier = request.env['delivery.carrier'].sudo().browse(int(carrier_id))

        res['is_paquete_express'] = carrier.is_paquete_express

        if carrier.is_paquete_express:
            res['is_free_delivery'] = False

        return res
    
    @http.route(['/shop/confirmation'], type='http', auth="public", website=True, sitemap=False)
    def shop_payment_confirmation(self, **post):
        res = super().shop_payment_confirmation(**post)

        sale_order_id = request.session.get('sale_last_order_id')

        if res.status_code == 200:
            print(sale_order_id)
            request.env['stock.picking'].sudo().action_px_api_generate_shipment(sale_order_id)
            
        return res




class WebsiteSaleDeliveryPaqueteExpress(WebsiteSaleDelivery):

    def getProductToWebsiteDevilery(self, order):
        order_line = order.order_line.filtered(lambda line: line.product_id.default_code != 'PX')
        details = order_line.mapped(lambda line: { 'product_id': line.product_id.id, 'qty': line.product_qty })
        return request.env['stock.picking'].sudo().shipments_for_quotation(details)

    def _update_website_sale_delivery_return(self, order, **post):
        res = super()._update_website_sale_delivery_return(order, **post)
        
        if order.carrier_id.is_paquete_express:
            res['paquete_express'] = {
                'partner_street': order.partner_shipping_id.street,
                'partner_state': order.partner_shipping_id.state_id.display_name,
                'partner_zip': order.partner_shipping_id.zip,
                'amount_total': order.amount_total,
                'partner_country_code': order.partner_shipping_id.country_id.code.upper(),
                'allowed_countries': ','.join(order.carrier_id.country_ids.mapped('code')).upper(),
                'products': self.getProductToWebsiteDevilery(order)
            }
            if order.partner_shipping_id.is_paquete_express:
                res['paquete_express']['current'] = '%s-%s' % (
                    res['paquete_express']['partner_country_code'],
                    order.partner_shipping_id.ref.lstrip('PX#'),
                )

        return res


class PaymentPortalMondialRelay(PaymentPortal):

    @http.route()
    def shop_payment_transaction(self, *args, **kwargs):
        order = request.website.sale_get_order()
        if order.partner_shipping_id.is_paquete_express and order.carrier_id and not order.carrier_id.is_paquete_express and order.delivery_set:
            raise ValidationError(_('Point Relais® can only be used with the delivery method Mondial Relay.'))
        elif not order.partner_shipping_id.is_paquete_express and order.carrier_id.is_paquete_express:
            raise ValidationError(_('Delivery method Mondial Relay can only ship to Point Relais®.'))
        return super().shop_payment_transaction(*args, **kwargs)
