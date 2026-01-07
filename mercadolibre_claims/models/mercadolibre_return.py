# -*- coding: utf-8 -*-

import json
import logging
import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class MercadolibreReturn(models.Model):
    _name = 'mercadolibre.return'
    _description = 'Devolucion MercadoLibre'
    _order = 'create_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # === IDENTIFICADORES ===
    name = fields.Char(
        string='Referencia',
        compute='_compute_name',
        store=True
    )
    ml_return_id = fields.Char(
        string='Return ID ML',
        readonly=True,
        index=True,
        help='ID de la devolucion en MercadoLibre'
    )
    claim_id = fields.Many2one(
        'mercadolibre.claim',
        string='Reclamo',
        ondelete='cascade',
        index=True
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        required=True,
        ondelete='restrict'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compania',
        related='account_id.company_id',
        store=True,
        readonly=True
    )

    # === TIPO Y ORIGEN ===
    return_type = fields.Selection([
        ('claim', 'Por Reclamo'),
        ('dispute', 'Por Disputa'),
        ('automatic', 'Automatica'),
    ], string='Tipo de Devolucion', default='claim', tracking=True)

    is_fulfillment = fields.Boolean(
        string='Es Fulfillment',
        default=False,
        help='Si es True, la mercancia esta en almacen de MercadoLibre'
    )

    # === ESTADO EN MERCADOLIBRE ===
    ml_status = fields.Selection([
        ('opened', 'Abierta'),
        ('shipped', 'En Transito'),
        ('delivered', 'Entregada al Vendedor'),
        ('closed', 'Cerrada'),
        ('cancelled', 'Cancelada'),
        ('failed', 'Fallida'),
        ('expired', 'Expirada'),
        ('not_delivered', 'No Entregada'),
    ], string='Estado ML', default='opened', tracking=True, index=True)

    # === RELACION CON ODOO ===
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Orden de Venta',
        help='Orden de venta original que se esta devolviendo'
    )
    ml_order_id = fields.Char(
        string='Order ID ML',
        readonly=True,
        index=True
    )
    original_picking_id = fields.Many2one(
        'stock.picking',
        string='Picking Original',
        help='Picking de salida original que se esta devolviendo'
    )
    return_picking_id = fields.Many2one(
        'stock.picking',
        string='Picking de Devolucion',
        help='Picking de devolucion creado en Odoo'
    )
    return_picking_state = fields.Selection(
        related='return_picking_id.state',
        string='Estado Picking',
        readonly=True
    )

    # === ESTADO DE PROCESAMIENTO EN ODOO ===
    odoo_state = fields.Selection([
        ('pending', 'Pendiente'),
        ('return_created', 'Devolucion Creada'),
        ('waiting_arrival', 'Esperando Mercancia'),
        ('received', 'Mercancia Recibida'),
        ('reviewed', 'Revisado'),
        ('completed', 'Completado'),
        ('cancelled', 'Cancelado'),
        ('error', 'Error'),
    ], string='Estado Odoo', default='pending', tracking=True)

    odoo_error_message = fields.Text(
        string='Mensaje de Error',
        readonly=True
    )

    # === PRODUCTOS DEVUELTOS ===
    line_ids = fields.One2many(
        'mercadolibre.return.line',
        'return_id',
        string='Productos'
    )
    line_count = fields.Integer(
        string='Num. Productos',
        compute='_compute_line_count'
    )

    # === REVISION DEL PRODUCTO ===
    review_status = fields.Selection([
        ('pending', 'Pendiente'),
        ('ok', 'OK - Buen Estado'),
        ('damaged', 'Danado'),
        ('incomplete', 'Incompleto'),
        ('different', 'Producto Diferente'),
        ('not_received', 'No Llego'),
    ], string='Estado Revision', default='pending', tracking=True)

    review_notes = fields.Text(string='Notas de Revision')
    review_date = fields.Datetime(string='Fecha Revision', readonly=True)
    reviewed_by = fields.Many2one('res.users', string='Revisado por', readonly=True)

    # === ALMACEN Y UBICACION ===
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Almacen Destino'
    )
    location_dest_id = fields.Many2one(
        'stock.location',
        string='Ubicacion Destino',
        help='Ubicacion donde se recibira la mercancia devuelta'
    )

    # === CONFIGURACION DE TIPO LOGISTICO ===
    logistic_type = fields.Selection([
        ('fulfillment', 'Full (Mercado Libre)'),
        ('xd_drop_off', 'Agencia/Places'),
        ('cross_docking', 'Colectas'),
        ('drop_off', 'Drop Off'),
        ('self_service', 'Flex'),
        ('custom', 'Envio Propio'),
        ('not_specified', 'A Convenir'),
        ('default', 'Por Defecto'),
    ], string='Tipo Logistico', default='default',
       help='Tipo logistico de MercadoLibre para esta devolucion')

    auto_validate = fields.Boolean(
        string='Validar Automaticamente',
        default=False,
        help='Si esta activo, el picking se valida automaticamente al crearse'
    )

    require_review = fields.Boolean(
        string='Requiere Revision',
        default=True,
        help='Si esta activo, la devolucion requiere revision antes de completarse'
    )

    # === TRACKING DE ENVIO ===
    tracking_number = fields.Char(string='Numero de Guia')
    carrier = fields.Char(string='Transportista')
    shipment_id = fields.Char(string='Shipment ID ML')

    # === FECHAS ===
    date_created = fields.Datetime(
        string='Fecha Creacion ML',
        readonly=True
    )
    date_shipped = fields.Datetime(
        string='Fecha Envio',
        readonly=True
    )
    date_delivered = fields.Datetime(
        string='Fecha Entrega',
        readonly=True
    )
    date_closed = fields.Datetime(
        string='Fecha Cierre',
        readonly=True
    )

    # === RAW DATA ===
    raw_data = fields.Text(
        string='Datos Crudos JSON',
        readonly=True
    )

    notes = fields.Text(string='Notas')

    _sql_constraints = [
        ('ml_return_id_uniq', 'unique(ml_return_id, account_id)',
         'Esta devolucion ya existe para esta cuenta.')
    ]

    # =====================================================
    # CAMPOS COMPUTADOS
    # =====================================================

    @api.depends('ml_return_id', 'claim_id')
    def _compute_name(self):
        for record in self:
            if record.ml_return_id:
                record.name = f'DEV-{record.ml_return_id}'
            elif record.claim_id:
                record.name = f'DEV-{record.claim_id.ml_claim_id}'
            else:
                record.name = f'DEV-{record.id or "Nuevo"}'

    @api.depends('line_ids')
    def _compute_line_count(self):
        for record in self:
            record.line_count = len(record.line_ids)

    # =====================================================
    # METODOS DE CREACION/ACTUALIZACION
    # =====================================================

    @api.model
    def create_from_claim(self, claim, return_data=None):
        """
        Crea una devolucion desde un claim.

        Args:
            claim: mercadolibre.claim record
            return_data: dict con datos de la devolucion desde API (opcional)

        Returns:
            mercadolibre.return record
        """
        # Verificar si ya existe
        if claim.return_id:
            existing = self.search([
                ('ml_return_id', '=', claim.return_id),
                ('account_id', '=', claim.account_id.id)
            ], limit=1)
            if existing:
                return existing

        # Buscar sale.order relacionada
        sale_order = self._find_sale_order(claim)

        # Determinar tipo logistico
        logistic_type = 'default'
        is_fulfillment = claim.type == 'fulfillment'

        if sale_order and hasattr(sale_order, 'ml_logistic_type') and sale_order.ml_logistic_type:
            logistic_type = sale_order.ml_logistic_type
            is_fulfillment = logistic_type == 'fulfillment'
        elif is_fulfillment:
            logistic_type = 'fulfillment'

        # Obtener configuracion
        config = self.env['mercadolibre.claim.config'].search([
            ('account_id', '=', claim.account_id.id),
            ('state', '=', 'active'),
        ], limit=1)

        # Obtener configuracion de almacen segun tipo logistico
        warehouse_id = False
        location_dest_id = False
        auto_validate = False
        require_review = True

        if config:
            wh_config = config.get_warehouse_config(logistic_type)
            if wh_config:
                warehouse_id = wh_config.warehouse_id.id
                location_dest_id = wh_config.location_id.id if wh_config.location_id else wh_config.warehouse_id.lot_stock_id.id
                auto_validate = wh_config.auto_validate
                require_review = wh_config.require_review
            else:
                # Fallback a configuracion antigua si existe
                if is_fulfillment and config.fulfillment_warehouse_id:
                    warehouse_id = config.fulfillment_warehouse_id.id
                    location_dest_id = config.fulfillment_warehouse_id.lot_stock_id.id
                    auto_validate = config.auto_validate_fulfillment
                elif config.return_warehouse_id:
                    warehouse_id = config.return_warehouse_id.id
                    location_dest_id = config.return_location_id.id if config.return_location_id else config.return_warehouse_id.lot_stock_id.id

        vals = {
            'claim_id': claim.id,
            'account_id': claim.account_id.id,
            'ml_return_id': claim.return_id or '',
            'ml_order_id': claim.ml_order_id or '',
            'return_type': 'dispute' if claim.stage == 'dispute' else 'claim',
            'is_fulfillment': is_fulfillment,
            'logistic_type': logistic_type,
            'ml_status': 'opened',
            'odoo_state': 'pending',
            'sale_order_id': sale_order.id if sale_order else False,
            'warehouse_id': warehouse_id,
            'location_dest_id': location_dest_id,
            'auto_validate': auto_validate,
            'require_review': require_review,
            'date_created': fields.Datetime.now(),
        }

        # Agregar datos de la API si vienen
        if return_data:
            vals.update({
                'ml_status': return_data.get('status', 'opened'),
                'tracking_number': return_data.get('tracking_number', ''),
                'carrier': return_data.get('carrier', ''),
                'shipment_id': return_data.get('shipment_id', ''),
                'raw_data': json.dumps(return_data, indent=2, ensure_ascii=False),
            })

        ml_return = self.create(vals)

        # Crear lineas de productos desde los items del claim
        if claim.item_ids:
            for item in claim.item_ids:
                self.env['mercadolibre.return.line'].create({
                    'return_id': ml_return.id,
                    'product_id': item.product_id.id if item.product_id else False,
                    'ml_item_id': item.ml_item_id,
                    'title': item.title,
                    'seller_sku': item.seller_sku,
                    'quantity': item.claimed_quantity or item.quantity,
                })

        _logger.info('Devolucion %s creada desde claim %s', ml_return.name, claim.name)

        return ml_return

    def _find_sale_order(self, claim):
        """Busca la orden de venta relacionada con el claim"""
        SaleOrder = self.env['sale.order']

        if claim.ml_order_id:
            # Buscar por ml_order_id
            sale_order = SaleOrder.search([
                ('ml_order_id', '=', claim.ml_order_id)
            ], limit=1)
            if sale_order:
                return sale_order

        if claim.resource == 'order' and claim.resource_id:
            sale_order = SaleOrder.search([
                ('ml_order_id', '=', claim.resource_id)
            ], limit=1)
            if sale_order:
                return sale_order

        if claim.ml_payment_id and claim.ml_payment_id.sale_order_id:
            return claim.ml_payment_id.sale_order_id

        return False

    # =====================================================
    # ACCIONES DE DEVOLUCION EN ODOO
    # =====================================================

    def action_create_return_picking(self):
        """Crea el picking de devolucion en Odoo"""
        self.ensure_one()

        if self.return_picking_id:
            raise UserError(_('Ya existe un picking de devolucion para esta devolucion'))

        if not self.sale_order_id:
            # Intentar encontrar la orden
            if self.claim_id:
                self.sale_order_id = self._find_sale_order(self.claim_id)

        if not self.sale_order_id:
            raise UserError(_('No se encontro orden de venta para crear la devolucion'))

        # Buscar el picking de salida original
        original_picking = self.sale_order_id.picking_ids.filtered(
            lambda p: p.picking_type_code == 'outgoing' and p.state == 'done'
        )

        if not original_picking:
            raise UserError(_('No se encontro un picking de salida validado para devolver'))

        # Usar el primer picking si hay varios
        original_picking = original_picking[0]
        self.original_picking_id = original_picking

        try:
            # Crear wizard de devolucion
            StockReturnPicking = self.env['stock.return.picking']
            return_wizard = StockReturnPicking.with_context(
                active_id=original_picking.id,
                active_model='stock.picking'
            ).create({})

            # Cargar productos
            return_wizard._onchange_picking_id()

            # Ajustar cantidades segun las lineas de devolucion ML
            if self.line_ids:
                product_qty = {}
                for line in self.line_ids:
                    if line.product_id:
                        product_qty[line.product_id.id] = line.quantity

                for wiz_line in return_wizard.product_return_moves:
                    if wiz_line.product_id.id in product_qty:
                        wiz_line.quantity = product_qty[wiz_line.product_id.id]
                    # Si no esta en la lista, dejamos la cantidad original (devolucion completa)

            # Establecer ubicacion destino si esta configurada
            if self.location_dest_id:
                return_wizard.location_id = self.location_dest_id

            # Crear el picking de devolucion
            new_picking_id, _ = return_wizard._create_returns()
            return_picking = self.env['stock.picking'].browse(new_picking_id)

            # Agregar referencia al picking
            return_picking.write({
                'origin': f'{return_picking.origin} - {self.name}',
            })

            # Vincular con este registro
            self.write({
                'return_picking_id': return_picking.id,
                'odoo_state': 'return_created',
                'odoo_error_message': False,
            })

            # Post en chatter
            self.message_post(
                body=_('Picking de devolucion %s creado') % return_picking.name,
                message_type='notification'
            )

            _logger.info('Picking de devolucion %s creado para %s', return_picking.name, self.name)

            # Si auto_validate esta activo, validar automaticamente
            if self.auto_validate:
                self.action_validate_return()

            return return_picking

        except Exception as e:
            self.write({
                'odoo_state': 'error',
                'odoo_error_message': str(e),
            })
            _logger.error('Error creando picking de devolucion: %s', str(e))
            raise UserError(_('Error al crear devolucion: %s') % str(e))

    def action_validate_return(self):
        """Valida el picking de devolucion (mercancia recibida)"""
        self.ensure_one()

        if not self.return_picking_id:
            raise UserError(_('No hay picking de devolucion para validar'))

        if self.return_picking_id.state == 'done':
            self.write({'odoo_state': 'received'})
            return True

        if self.return_picking_id.state == 'cancel':
            raise UserError(_('El picking de devolucion esta cancelado'))

        try:
            # Establecer cantidades
            for move in self.return_picking_id.move_ids:
                move.quantity_done = move.product_uom_qty

            # Validar
            self.return_picking_id.button_validate()

            self.write({
                'odoo_state': 'received',
                'date_delivered': fields.Datetime.now(),
                'odoo_error_message': False,
            })

            # Post en chatter
            self.message_post(
                body=_('Devolucion recibida - Picking %s validado') % self.return_picking_id.name,
                message_type='notification'
            )

            _logger.info('Picking de devolucion %s validado', self.return_picking_id.name)

            return True

        except Exception as e:
            self.write({
                'odoo_state': 'error',
                'odoo_error_message': str(e),
            })
            _logger.error('Error validando picking: %s', str(e))
            raise UserError(_('Error al validar devolucion: %s') % str(e))

    def action_complete_review(self):
        """Abre wizard para completar la revision del producto"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Revision de Devolucion'),
            'res_model': 'mercadolibre.return.review.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_return_id': self.id,
            },
        }

    def action_mark_reviewed(self, review_status='ok', notes=None):
        """Marca la devolucion como revisada"""
        self.ensure_one()

        vals = {
            'review_status': review_status,
            'review_date': fields.Datetime.now(),
            'reviewed_by': self.env.uid,
        }

        if notes:
            vals['review_notes'] = notes

        # Determinar estado final
        if review_status == 'ok':
            vals['odoo_state'] = 'completed'
        elif review_status in ('damaged', 'incomplete', 'different'):
            vals['odoo_state'] = 'reviewed'
        elif review_status == 'not_received':
            vals['odoo_state'] = 'error'
            vals['odoo_error_message'] = 'Producto no recibido'

        self.write(vals)

        # Si el producto esta danado, mover a ubicacion de scrap
        if review_status == 'damaged':
            self._move_to_scrap()

        # Post en chatter
        status_labels = dict(self._fields['review_status'].selection)
        self.message_post(
            body=_('Revision completada: %s') % status_labels.get(review_status, review_status),
            message_type='notification'
        )

        return True

    def _move_to_scrap(self):
        """Mueve los productos danados a ubicacion de scrap"""
        self.ensure_one()

        if not self.return_picking_id or self.return_picking_id.state != 'done':
            return False

        config = self.env['mercadolibre.claim.config'].search([
            ('account_id', '=', self.account_id.id),
            ('state', '=', 'active'),
        ], limit=1)

        if not config or not config.scrap_location_id:
            _logger.warning('No hay ubicacion de scrap configurada')
            return False

        try:
            for move in self.return_picking_id.move_ids:
                if move.state == 'done' and move.product_id.type == 'product':
                    scrap = self.env['stock.scrap'].create({
                        'product_id': move.product_id.id,
                        'scrap_qty': move.quantity_done,
                        'product_uom_id': move.product_uom.id,
                        'location_id': move.location_dest_id.id,
                        'scrap_location_id': config.scrap_location_id.id,
                        'origin': self.name,
                    })
                    scrap.action_validate()

            self.message_post(
                body=_('Productos movidos a ubicacion de merma/scrap'),
                message_type='notification'
            )
            return True

        except Exception as e:
            _logger.error('Error moviendo a scrap: %s', str(e))
            return False

    def action_cancel(self):
        """Cancela la devolucion"""
        self.ensure_one()

        if self.return_picking_id and self.return_picking_id.state not in ('done', 'cancel'):
            self.return_picking_id.action_cancel()

        self.write({
            'odoo_state': 'cancelled',
        })

        return True

    # =====================================================
    # SINCRONIZACION CON MERCADOLIBRE
    # =====================================================

    def action_sync_from_ml(self):
        """Sincroniza el estado de la devolucion desde MercadoLibre"""
        self.ensure_one()

        if not self.claim_id:
            raise UserError(_('Esta devolucion no tiene un claim asociado'))

        access_token = self.account_id.get_valid_token_with_retry()
        if not access_token:
            raise UserError(_('No se pudo obtener token valido'))

        url = f'https://api.mercadolibre.com/post-purchase/v1/claims/{self.claim_id.ml_claim_id}/returns'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code != 200:
                _logger.error('Error obteniendo returns: %s', response.text)
                return False

            data = response.json()

            # Actualizar estado
            if data:
                return_data = data[0] if isinstance(data, list) else data
                self.write({
                    'ml_status': return_data.get('status', self.ml_status),
                    'tracking_number': return_data.get('tracking_number') or self.tracking_number,
                    'raw_data': json.dumps(return_data, indent=2, ensure_ascii=False),
                })

                # Si ML dice que fue entregada, validar en Odoo si esta configurado
                if return_data.get('status') == 'delivered':
                    config = self.env['mercadolibre.claim.config'].search([
                        ('account_id', '=', self.account_id.id),
                        ('state', '=', 'active'),
                    ], limit=1)

                    if config and config.auto_validate_on_delivered and self.return_picking_id:
                        if self.return_picking_id.state not in ('done', 'cancel'):
                            self.action_validate_return()

            return True

        except requests.exceptions.RequestException as e:
            _logger.error('Error sincronizando return: %s', str(e))
            return False

    # =====================================================
    # ACCIONES DE NAVEGACION
    # =====================================================

    def action_view_claim(self):
        """Abre el claim asociado"""
        self.ensure_one()
        if not self.claim_id:
            raise UserError(_('Esta devolucion no tiene un reclamo asociado'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Reclamo'),
            'res_model': 'mercadolibre.claim',
            'res_id': self.claim_id.id,
            'view_mode': 'form',
        }

    def action_view_sale_order(self):
        """Abre la orden de venta"""
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError(_('Esta devolucion no tiene una orden de venta asociada'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Orden de Venta'),
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
        }

    def action_view_return_picking(self):
        """Abre el picking de devolucion"""
        self.ensure_one()
        if not self.return_picking_id:
            raise UserError(_('No hay picking de devolucion'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Picking de Devolucion'),
            'res_model': 'stock.picking',
            'res_id': self.return_picking_id.id,
            'view_mode': 'form',
        }


class MercadolibreReturnLine(models.Model):
    _name = 'mercadolibre.return.line'
    _description = 'Linea de Devolucion MercadoLibre'

    return_id = fields.Many2one(
        'mercadolibre.return',
        string='Devolucion',
        required=True,
        ondelete='cascade'
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto'
    )
    ml_item_id = fields.Char(
        string='Item ID ML'
    )
    title = fields.Char(
        string='Titulo'
    )
    seller_sku = fields.Char(
        string='SKU'
    )
    quantity = fields.Float(
        string='Cantidad a Devolver',
        default=1.0
    )
    quantity_received = fields.Float(
        string='Cantidad Recibida',
        default=0.0
    )
    condition = fields.Selection([
        ('new', 'Nuevo'),
        ('used', 'Usado'),
        ('damaged', 'Danado'),
        ('missing', 'Faltante'),
    ], string='Condicion', default='new')

    notes = fields.Text(string='Notas')
