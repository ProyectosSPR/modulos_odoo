# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MercadolibreLogisticType(models.Model):
    _name = 'mercadolibre.logistic.type'
    _description = 'Tipo Logistico MercadoLibre'
    _order = 'sequence, name'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre descriptivo del tipo logistico'
    )
    code = fields.Selection([
        ('fulfillment', 'Full (Mercado Libre)'),
        ('xd_drop_off', 'Agencia/Places'),
        ('cross_docking', 'Colectas'),
        ('drop_off', 'Drop Off'),
        ('self_service', 'Flex'),
        ('custom', 'Envio Propio'),
        ('not_specified', 'A Convenir'),
    ], string='Codigo ML', required=True,
       help='Codigo del tipo logistico en MercadoLibre')

    sequence = fields.Integer(
        string='Secuencia',
        default=10
    )
    active = fields.Boolean(
        string='Activo',
        default=True
    )

    # Scope
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        help='Dejar vacio para aplicar a todas las cuentas'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compania',
        default=lambda self: self.env.company
    )

    # Auto-actions
    auto_confirm_order = fields.Boolean(
        string='Confirmar Orden Auto',
        default=False,
        help='Confirmar la orden de venta automaticamente al crearla'
    )
    auto_confirm_picking = fields.Boolean(
        string='Confirmar Picking Auto',
        default=False,
        help='Confirmar/validar el picking automaticamente (solo si auto_confirm_order esta activo)'
    )
    auto_validate_stock_move = fields.Boolean(
        string='Validar Movimiento Stock',
        default=False,
        help='Validar automaticamente los movimientos de stock'
    )

    # Download/Print Labels
    download_shipping_label = fields.Boolean(
        string='Descargar Etiqueta',
        default=False,
        help='Descargar automaticamente la etiqueta de envio'
    )
    auto_print_label = fields.Boolean(
        string='Imprimir Etiqueta Auto',
        default=False,
        help='Enviar etiqueta a impresion automaticamente'
    )

    # Warehouse
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Almacen',
        help='Almacen a usar para este tipo logistico'
    )
    picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Tipo Operacion',
        domain="[('code', '=', 'outgoing')]",
        help='Tipo de operacion de salida a usar'
    )

    # Team and Tags
    team_id = fields.Many2one(
        'crm.team',
        string='Equipo de Ventas',
        help='Equipo de ventas a asignar a las ordenes'
    )
    tag_ids = fields.Many2many(
        'crm.tag',
        string='Etiquetas',
        help='Etiquetas a asignar a las ordenes de este tipo'
    )

    # Carrier
    carrier_id = fields.Many2one(
        'delivery.carrier',
        string='Transportista',
        help='Transportista por defecto para este tipo logistico'
    )

    # Description
    description = fields.Text(
        string='Descripcion',
        help='Descripcion y notas sobre este tipo logistico'
    )

    # Statistics
    order_count = fields.Integer(
        string='Ordenes',
        compute='_compute_order_count'
    )

    @api.depends('code', 'account_id')
    def _compute_order_count(self):
        for record in self:
            domain = [('logistic_type', '=', record.code)]
            if record.account_id:
                domain.append(('account_id', '=', record.account_id.id))
            record.order_count = self.env['mercadolibre.order'].search_count(domain)

    def action_view_orders(self):
        """Ver ordenes de este tipo logistico"""
        self.ensure_one()
        domain = [('logistic_type', '=', self.code)]
        if self.account_id:
            domain.append(('account_id', '=', self.account_id.id))

        return {
            'type': 'ir.actions.act_window',
            'name': f'Ordenes - {self.name}',
            'res_model': 'mercadolibre.order',
            'view_mode': 'tree,form',
            'domain': domain,
        }
