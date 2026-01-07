# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MercadolibreClaimConfigWarehouse(models.Model):
    _name = 'mercadolibre.claim.config.warehouse'
    _description = 'Configuracion de Almacen por Tipo Logistico'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)

    config_id = fields.Many2one(
        'mercadolibre.claim.config',
        string='Configuracion',
        required=True,
        ondelete='cascade'
    )
    company_id = fields.Many2one(
        'res.company',
        related='config_id.company_id',
        store=True
    )

    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True
    )

    # === TIPO LOGISTICO ===
    logistic_type = fields.Selection([
        ('fulfillment', 'Full (Mercado Libre)'),
        ('xd_drop_off', 'Agencia/Places'),
        ('cross_docking', 'Colectas'),
        ('drop_off', 'Drop Off'),
        ('self_service', 'Flex'),
        ('custom', 'Envio Propio'),
        ('not_specified', 'A Convenir'),
        ('default', 'Por Defecto (Otros)'),
    ], string='Tipo Logistico', required=True, default='default',
       help='Tipo de logistica de MercadoLibre. "Por Defecto" aplica cuando no coincide ningun otro tipo.')

    # === ALMACEN Y UBICACION ===
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Almacen',
        required=True,
        help='Almacen donde se recibiran las devoluciones de este tipo logistico'
    )

    location_id = fields.Many2one(
        'stock.location',
        string='Ubicacion Destino',
        help='Ubicacion especifica para recibir devoluciones. Si no se especifica, usa la ubicacion de stock del almacen.'
    )

    scrap_location_id = fields.Many2one(
        'stock.location',
        string='Ubicacion Merma',
        help='Ubicacion para productos danados de este tipo logistico'
    )

    # === AUTOMATIZACION ===
    auto_create_picking = fields.Boolean(
        string='Crear Picking Automaticamente',
        default=True,
        help='Crear el picking de devolucion automaticamente cuando se detecta un reclamo'
    )

    auto_validate = fields.Boolean(
        string='Validar Automaticamente',
        default=False,
        help='Validar el picking de devolucion automaticamente (la mercancia se registra como recibida)'
    )

    require_review = fields.Boolean(
        string='Requiere Revision',
        default=True,
        help='Si esta activo, la devolucion quedara pendiente de revision antes de completarse'
    )

    # === NOTAS ===
    notes = fields.Text(
        string='Notas',
        help='Instrucciones especiales para este tipo logistico'
    )

    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('logistic_type_config_uniq', 'unique(config_id, logistic_type)',
         'Ya existe una configuracion para este tipo logistico en esta cuenta.')
    ]

    @api.depends('logistic_type', 'warehouse_id')
    def _compute_name(self):
        type_labels = dict(self._fields['logistic_type'].selection)
        for record in self:
            type_name = type_labels.get(record.logistic_type, record.logistic_type)
            wh_name = record.warehouse_id.name if record.warehouse_id else ''
            record.name = f'{type_name} → {wh_name}'

    @api.onchange('logistic_type')
    def _onchange_logistic_type(self):
        """Sugerir auto_validate para Fulfillment"""
        if self.logistic_type == 'fulfillment':
            self.auto_validate = True
            self.require_review = False
        else:
            self.auto_validate = False
            self.require_review = True

    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        """Establecer ubicacion por defecto del almacen"""
        if self.warehouse_id and not self.location_id:
            self.location_id = self.warehouse_id.lot_stock_id


class MercadolibreClaimConfig(models.Model):
    _inherit = 'mercadolibre.claim.config'

    # === CONFIGURACION DE ALMACENES POR TIPO LOGISTICO ===
    warehouse_config_ids = fields.One2many(
        'mercadolibre.claim.config.warehouse',
        'config_id',
        string='Configuracion por Tipo Logistico'
    )

    def get_warehouse_config(self, logistic_type):
        """
        Obtiene la configuracion de almacen para un tipo logistico.
        Si no existe configuracion especifica, busca la configuracion 'default'.

        Args:
            logistic_type: str - Tipo logistico de ML (fulfillment, cross_docking, etc.)

        Returns:
            mercadolibre.claim.config.warehouse record o False
        """
        self.ensure_one()

        # Buscar configuracion especifica para este tipo
        config = self.warehouse_config_ids.filtered(
            lambda c: c.logistic_type == logistic_type and c.active
        )

        if config:
            return config[0]

        # Buscar configuracion por defecto
        default_config = self.warehouse_config_ids.filtered(
            lambda c: c.logistic_type == 'default' and c.active
        )

        if default_config:
            return default_config[0]

        return False

    def action_create_default_warehouse_configs(self):
        """Crea configuraciones por defecto para los tipos logisticos comunes"""
        self.ensure_one()

        # Obtener almacen por defecto de la compania
        default_warehouse = self.env['stock.warehouse'].search([
            ('company_id', '=', self.company_id.id)
        ], limit=1)

        if not default_warehouse:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('No se encontro un almacen para esta compania'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        # Tipos logisticos a crear (tipo, auto_validate, require_review)
        types_to_create = [
            ('fulfillment', True, False),   # Full (Mercado Libre) - auto validar
            ('xd_drop_off', False, True),   # Agencia/Places
            ('cross_docking', False, True), # Colectas
            ('drop_off', False, True),      # Drop Off
            ('self_service', False, True),  # Flex
            ('custom', False, True),        # Envio Propio
            ('not_specified', False, True), # A Convenir
            ('default', False, True),       # Por Defecto (Otros)
        ]

        created = 0
        for logistic_type, auto_val, req_review in types_to_create:
            existing = self.warehouse_config_ids.filtered(
                lambda c: c.logistic_type == logistic_type
            )
            if not existing:
                self.env['mercadolibre.claim.config.warehouse'].create({
                    'config_id': self.id,
                    'logistic_type': logistic_type,
                    'warehouse_id': default_warehouse.id,
                    'location_id': default_warehouse.lot_stock_id.id,
                    'auto_create_picking': True,
                    'auto_validate': auto_val,
                    'require_review': req_review,
                })
                created += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Se crearon %d configuraciones de almacen') % created,
                'type': 'success',
                'sticky': False,
            }
        }
