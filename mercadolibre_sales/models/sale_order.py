# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # MercadoLibre Fields
    ml_order_id = fields.Char(
        string='Order ID ML',
        readonly=True,
        index=True,
        copy=False,
        help='ID de la orden en MercadoLibre'
    )
    ml_pack_id = fields.Char(
        string='Pack ID ML',
        readonly=True,
        index=True,
        copy=False,
        help='ID del pack/carrito en MercadoLibre'
    )
    ml_shipment_id = fields.Char(
        string='Shipment ID ML',
        readonly=True,
        copy=False,
        help='ID del envio en MercadoLibre'
    )
    ml_account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        readonly=True,
        copy=False
    )
    ml_logistic_type = fields.Selection([
        ('fulfillment', 'Full (Mercado Libre)'),
        ('xd_drop_off', 'Agencia/Places'),
        ('cross_docking', 'Colectas'),
        ('drop_off', 'Drop Off'),
        ('self_service', 'Flex'),
        ('custom', 'Envio Propio'),
        ('not_specified', 'A Convenir'),
    ], string='Tipo Logistico ML', readonly=True, copy=False)

    ml_channel = fields.Selection([
        ('marketplace', 'Marketplace'),
        ('mshops', 'Mercado Shops'),
        ('proximity', 'Proximity'),
        ('mp-channel', 'MercadoPago Channel'),
        ('meli_cofunding', 'Aporte ML (Co-fondeo)'),
    ], string='Canal ML', readonly=True, copy=False)

    ml_sync_date = fields.Datetime(
        string='Fecha Sync ML',
        readonly=True,
        copy=False
    )

    # Link to ML Order
    ml_order_ids = fields.One2many(
        'mercadolibre.order',
        'sale_order_id',
        string='Ordenes ML',
        readonly=True
    )

    is_ml_order = fields.Boolean(
        string='Es Orden ML',
        compute='_compute_is_ml_order',
        store=True
    )

    @api.depends('ml_order_id')
    def _compute_is_ml_order(self):
        for record in self:
            record.is_ml_order = bool(record.ml_order_id)

    def action_view_ml_orders(self):
        """Ver ordenes ML asociadas"""
        self.ensure_one()
        if self.ml_pack_id:
            domain = [('ml_pack_id', '=', self.ml_pack_id)]
        elif self.ml_order_id:
            domain = [('ml_order_id', '=', self.ml_order_id)]
        else:
            return False

        return {
            'type': 'ir.actions.act_window',
            'name': 'Ordenes MercadoLibre',
            'res_model': 'mercadolibre.order',
            'view_mode': 'tree,form',
            'domain': domain,
        }

    def action_download_shipping_label(self):
        """Descarga la etiqueta de envio desde la orden ML asociada"""
        self.ensure_one()
        ml_order = self._get_ml_order()
        if not ml_order:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin Orden ML',
                    'message': 'No hay orden de MercadoLibre asociada.',
                    'type': 'warning',
                }
            }
        return ml_order.action_download_shipping_label()

    def action_print_shipping_label(self):
        """Imprime la etiqueta de envio desde la orden ML asociada"""
        self.ensure_one()
        ml_order = self._get_ml_order()
        if not ml_order:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin Orden ML',
                    'message': 'No hay orden de MercadoLibre asociada.',
                    'type': 'warning',
                }
            }
        return ml_order.action_print_shipping_label()

    def _get_ml_order(self):
        """Obtiene la orden ML principal asociada"""
        self.ensure_one()
        if self.ml_order_ids:
            return self.ml_order_ids[0]
        if self.ml_order_id:
            return self.env['mercadolibre.order'].search([
                ('ml_order_id', '=', self.ml_order_id)
            ], limit=1)
        return False


    def action_mass_cancel(self):
        """
        Cancela masivamente ordenes de venta sin mostrar wizard de confirmacion.
        Solo cancela ordenes en estado 'sale'.
        """
        orders_to_cancel = self.filtered(lambda o: o.state == 'sale')
        cancelled_count = 0
        errors = []

        for order in orders_to_cancel:
            try:
                # Cancelar sin mostrar wizard - usar _action_cancel directamente
                # El context disable_cancel_warning evita validaciones innecesarias
                order.with_context(disable_cancel_warning=True)._action_cancel()
                cancelled_count += 1
            except Exception as e:
                errors.append(f'{order.name}: {str(e)}')

        # Preparar mensaje de resultado
        message_parts = []
        if cancelled_count:
            message_parts.append(f'{cancelled_count} orden(es) cancelada(s)')

        skipped = len(self) - len(orders_to_cancel)
        if skipped:
            message_parts.append(f'{skipped} orden(es) omitida(s) (no estaban en estado "Venta")')

        if errors:
            message_parts.append(f'{len(errors)} error(es): {"; ".join(errors[:3])}')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Cancelacion Masiva',
                'message': '. '.join(message_parts) if message_parts else 'No hay ordenes para cancelar',
                'type': 'success' if cancelled_count and not errors else ('warning' if errors else 'info'),
                'sticky': bool(errors),
            }
        }



class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # MercadoLibre Fields
    ml_item_id = fields.Char(
        string='Item ID ML',
        readonly=True,
        copy=False,
        help='ID del item/publicacion en MercadoLibre'
    )
    ml_seller_sku = fields.Char(
        string='SKU ML',
        readonly=True,
        copy=False,
        help='SKU del vendedor en MercadoLibre'
    )
