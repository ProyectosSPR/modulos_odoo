# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MercadolibreLogisticType(models.Model):
    _name = 'mercadolibre.logistic.type'
    _description = 'Configuracion de Tipo Logistico MercadoLibre'
    _order = 'sequence, name'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre descriptivo de la configuracion'
    )
    code = fields.Selection([
        ('fulfillment', 'Full (Mercado Libre)'),
        ('xd_drop_off', 'Agencia/Places'),
        ('cross_docking', 'Colectas'),
        ('drop_off', 'Drop Off'),
        ('self_service', 'Flex'),
        ('custom', 'Envio Propio'),
        ('not_specified', 'A Convenir'),
    ], string='Tipo Logistico ML', required=True,
       help='Tipo logistico de MercadoLibre que esta configuracion maneja')

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

    # =========================================================================
    # ETIQUETAS POR DEFECTO PARA ESTE TIPO LOGISTICO
    # =========================================================================
    default_tag_ids = fields.Many2many(
        'crm.tag',
        'mercadolibre_logistic_type_default_tag_rel',
        'logistic_type_id', 'tag_id',
        string='Etiquetas por Defecto',
        help='Etiquetas que se asignaran a todas las ordenes de este tipo logistico'
    )

    # =========================================================================
    # AUTOMATIZACION
    # =========================================================================
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
    stock_validation_policy = fields.Selection([
        ('strict', 'Estricto - Solo si hay stock completo'),
        ('partial', 'Parcial - Validar lo disponible, notificar faltantes'),
        ('force', 'Forzar - Validar aunque no haya stock (puede generar negativos)'),
    ], string='Politica de Validacion de Stock',
       default='strict',
       help='Define como manejar la validacion cuando no hay stock suficiente:\n'
            '- Estricto: No valida si falta stock, notifica el error\n'
            '- Parcial: Valida lo disponible y crea backorder para el resto\n'
            '- Forzar: Valida todo aunque genere stock negativo (no recomendado)'
    )
    notify_stock_issues = fields.Boolean(
        string='Notificar Problemas de Stock',
        default=True,
        help='Crear actividad/notificacion cuando hay problemas de stock'
    )
    stock_issue_user_id = fields.Many2one(
        'res.users',
        string='Usuario a Notificar',
        help='Usuario que recibira las notificaciones de problemas de stock. '
             'Si no se especifica, se notifica al responsable del almacen.'
    )

    # =========================================================================
    # ETIQUETAS DE ENVIO ML
    # =========================================================================
    download_shipping_label = fields.Boolean(
        string='Descargar Etiqueta ML',
        default=False,
        help='Descargar automaticamente la etiqueta de envio de MercadoLibre'
    )
    auto_print_label = fields.Boolean(
        string='Imprimir Etiqueta Auto',
        default=False,
        help='Enviar etiqueta a impresion automaticamente'
    )

    # =========================================================================
    # ALMACEN Y OPERACIONES
    # =========================================================================
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Almacen',
        help='Almacen a usar para ordenes de este tipo logistico'
    )
    picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Tipo Operacion',
        domain="[('code', '=', 'outgoing')]",
        help='Tipo de operacion de salida a usar'
    )

    # =========================================================================
    # EQUIPO Y TRANSPORTISTA
    # =========================================================================
    team_id = fields.Many2one(
        'crm.team',
        string='Equipo de Ventas',
        help='Equipo de ventas a asignar a las ordenes'
    )
    carrier_id = fields.Many2one(
        'delivery.carrier',
        string='Transportista',
        help='Transportista por defecto para este tipo logistico'
    )

    # =========================================================================
    # TARIFA DE PRECIOS
    # =========================================================================
    pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Tarifa de Precios',
        help='Tarifa de precios a usar para ordenes de este tipo logistico'
    )

    # =========================================================================
    # CONFIGURACION DE ETIQUETAS POR ESTADO DE ENVIO
    # =========================================================================
    shipment_status_config_ids = fields.One2many(
        'mercadolibre.shipment.status.config',
        'logistic_type_id',
        string='Etiquetas por Estado de Envio',
        help='Configuracion de etiquetas a asignar segun el estado del envio'
    )

    # Description
    description = fields.Text(
        string='Notas',
        help='Descripcion y notas sobre esta configuracion'
    )

    # Statistics
    order_count = fields.Integer(
        string='Ordenes',
        compute='_compute_order_count'
    )

    _sql_constraints = [
        ('code_account_uniq', 'unique(code, account_id, company_id)',
         'Ya existe una configuracion para este tipo logistico en esta cuenta/compania.')
    ]

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

    def get_tags_for_shipment_status(self, shipment_status):
        """
        Obtiene las etiquetas correspondientes a un estado de envio.

        Args:
            shipment_status: Estado del envio (pending, shipped, delivered, etc.)

        Returns:
            recordset de crm.tag
        """
        self.ensure_one()
        config = self.shipment_status_config_ids.filtered(
            lambda c: shipment_status in c.get_status_list()
        )
        if config:
            return config[0].tag_ids
        return self.env['crm.tag']


class MercadolibreShipmentStatusConfig(models.Model):
    """
    Configuracion de etiquetas por estado de envio.
    Permite mapear uno o varios estados de envio de ML a etiquetas de Odoo.
    """
    _name = 'mercadolibre.shipment.status.config'
    _description = 'Configuracion de Etiquetas por Estado de Envio'
    _order = 'sequence, id'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre descriptivo de esta configuracion (ej: "En Preparacion", "En Transito")'
    )
    logistic_type_id = fields.Many2one(
        'mercadolibre.logistic.type',
        string='Config. Tipo Logistico',
        required=True,
        ondelete='cascade'
    )
    sequence = fields.Integer(
        string='Secuencia',
        default=10
    )
    active = fields.Boolean(
        string='Activo',
        default=True
    )

    # Estados de envio que aplican a esta configuracion
    status_pending = fields.Boolean(string='Pendiente', help='Estado: pending')
    status_handling = fields.Boolean(string='En Preparacion', help='Estado: handling')
    status_ready_to_ship = fields.Boolean(string='Listo para Enviar', help='Estado: ready_to_ship')
    status_shipped = fields.Boolean(string='Enviado', help='Estado: shipped')
    status_in_transit = fields.Boolean(string='En Transito', help='Estado: in_transit')
    status_out_for_delivery = fields.Boolean(string='En Reparto', help='Estado: out_for_delivery')
    status_delivered = fields.Boolean(string='Entregado', help='Estado: delivered')
    status_not_delivered = fields.Boolean(string='No Entregado', help='Estado: not_delivered')
    status_returned = fields.Boolean(string='Devuelto', help='Estado: returned')
    status_cancelled = fields.Boolean(string='Cancelado', help='Estado: cancelled')

    # Etiquetas a asignar cuando el envio tenga alguno de estos estados
    tag_ids = fields.Many2many(
        'crm.tag',
        'mercadolibre_shipment_status_config_tag_rel',
        'config_id', 'tag_id',
        string='Etiquetas',
        required=True,
        help='Etiquetas a asignar a la orden cuando el envio tenga alguno de los estados seleccionados'
    )

    description = fields.Text(
        string='Notas',
        help='Descripcion de cuando se aplica esta configuracion'
    )

    def get_status_list(self):
        """Retorna lista de estados seleccionados"""
        self.ensure_one()
        statuses = []
        if self.status_pending:
            statuses.append('pending')
        if self.status_handling:
            statuses.append('handling')
        if self.status_ready_to_ship:
            statuses.append('ready_to_ship')
        if self.status_shipped:
            statuses.append('shipped')
        if self.status_in_transit:
            statuses.append('in_transit')
        if self.status_out_for_delivery:
            statuses.append('out_for_delivery')
        if self.status_delivered:
            statuses.append('delivered')
        if self.status_not_delivered:
            statuses.append('not_delivered')
        if self.status_returned:
            statuses.append('returned')
        if self.status_cancelled:
            statuses.append('cancelled')
        return statuses

    @api.depends('status_pending', 'status_handling', 'status_ready_to_ship',
                 'status_shipped', 'status_in_transit', 'status_out_for_delivery',
                 'status_delivered', 'status_not_delivered', 'status_returned', 'status_cancelled')
    def _compute_display_name(self):
        for record in self:
            statuses = record.get_status_list()
            if statuses:
                record.display_name = f"{record.name} ({len(statuses)} estados)"
            else:
                record.display_name = record.name


class MercadolibrePaymentStatusConfig(models.Model):
    """
    Configuracion de etiquetas por estado de pago.
    Permite mapear uno o varios estados de pago de ML a etiquetas de Odoo.
    """
    _name = 'mercadolibre.payment.status.config'
    _description = 'Configuracion de Etiquetas por Estado de Pago'
    _order = 'sequence, id'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre descriptivo de esta configuracion'
    )
    sequence = fields.Integer(
        string='Secuencia',
        default=10
    )
    active = fields.Boolean(
        string='Activo',
        default=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compania',
        default=lambda self: self.env.company
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        help='Dejar vacio para aplicar a todas las cuentas'
    )

    # Estados de pago que aplican a esta configuracion
    status_pending = fields.Boolean(string='Pendiente', help='Estado: pending')
    status_approved = fields.Boolean(string='Aprobado', help='Estado: approved')
    status_authorized = fields.Boolean(string='Autorizado', help='Estado: authorized')
    status_in_process = fields.Boolean(string='En Proceso', help='Estado: in_process')
    status_in_mediation = fields.Boolean(string='En Mediacion', help='Estado: in_mediation')
    status_rejected = fields.Boolean(string='Rechazado', help='Estado: rejected')
    status_cancelled = fields.Boolean(string='Cancelado', help='Estado: cancelled')
    status_refunded = fields.Boolean(string='Reembolsado', help='Estado: refunded')
    status_charged_back = fields.Boolean(string='Contracargo', help='Estado: charged_back')

    # Etiquetas a asignar
    tag_ids = fields.Many2many(
        'crm.tag',
        'mercadolibre_payment_status_config_tag_rel',
        'config_id', 'tag_id',
        string='Etiquetas',
        required=True,
        help='Etiquetas a asignar a la orden cuando el pago tenga alguno de los estados seleccionados'
    )

    description = fields.Text(
        string='Notas'
    )

    def get_status_list(self):
        """Retorna lista de estados seleccionados"""
        self.ensure_one()
        statuses = []
        if self.status_pending:
            statuses.append('pending')
        if self.status_approved:
            statuses.append('approved')
        if self.status_authorized:
            statuses.append('authorized')
        if self.status_in_process:
            statuses.append('in_process')
        if self.status_in_mediation:
            statuses.append('in_mediation')
        if self.status_rejected:
            statuses.append('rejected')
        if self.status_cancelled:
            statuses.append('cancelled')
        if self.status_refunded:
            statuses.append('refunded')
        if self.status_charged_back:
            statuses.append('charged_back')
        return statuses

    @api.model
    def get_tags_for_payment_status(self, payment_status, account_id=None, company_id=None):
        """
        Obtiene las etiquetas correspondientes a un estado de pago.

        Args:
            payment_status: Estado del pago (pending, approved, etc.)
            account_id: ID de la cuenta ML (opcional)
            company_id: ID de la compania (opcional)

        Returns:
            recordset de crm.tag
        """
        domain = [('active', '=', True)]
        if account_id:
            domain.append(('account_id', 'in', [False, account_id]))
        if company_id:
            domain.append(('company_id', 'in', [False, company_id]))

        configs = self.search(domain)
        for config in configs:
            if payment_status in config.get_status_list():
                return config.tag_ids
        return self.env['crm.tag']
