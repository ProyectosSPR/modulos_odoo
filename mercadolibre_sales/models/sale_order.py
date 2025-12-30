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

    # Estados de MercadoLibre
    ml_status = fields.Selection([
        ('confirmed', 'Confirmada'),
        ('payment_required', 'Pago Requerido'),
        ('payment_in_process', 'Pago en Proceso'),
        ('partially_paid', 'Parcialmente Pagada'),
        ('paid', 'Pagada'),
        ('partially_refunded', 'Parcialmente Reembolsada'),
        ('pending_cancel', 'Cancelación Pendiente'),
        ('cancelled', 'Cancelada'),
    ], string='Estado ML', readonly=True, copy=False, tracking=True)

    ml_shipping_status = fields.Selection([
        ('pending', 'Pendiente'),
        ('handling', 'En Preparación'),
        ('ready_to_ship', 'Listo para Enviar'),
        ('shipped', 'Enviado'),
        ('delivered', 'Entregado'),
        ('not_delivered', 'No Entregado'),
        ('cancelled', 'Cancelado'),
    ], string='Estado Envío ML', readonly=True, copy=False, tracking=True)

    ml_tags = fields.Char(
        string='Tags ML',
        readonly=True,
        copy=False,
        help='Etiquetas de la orden en MercadoLibre (separadas por coma)'
    )

    ml_paid_amount = fields.Float(
        string='Monto Pagado ML',
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

    def _update_ml_status_and_tags(self, shipment_status=None, payment_status=None,
                                    ml_tags=None, paid_amount=None):
        """
        Método centralizado para actualizar estados ML y tags de Odoo.
        Puede ser llamado desde cualquier webhook (orders_v2, shipments, payments, etc.)

        Args:
            shipment_status: Nuevo estado de envío (opcional)
            payment_status: Nuevo estado de pago/orden (opcional)
            ml_tags: Tags de ML como string (opcional)
            paid_amount: Monto pagado (opcional)

        Returns:
            dict con información de los cambios realizados
        """
        import logging
        _logger = logging.getLogger(__name__)

        self.ensure_one()

        _logger.info(
            '[UPDATE_ML_TAGS] Iniciando para %s: shipment=%s, payment=%s, logistic_type=%s',
            self.name, shipment_status, payment_status, self.ml_logistic_type
        )

        result = {
            'updated': False,
            'status_changes': [],
            'tags_added': [],
            'tags_removed': [],
            'fields_updated': [],
        }

        if not self.is_ml_order:
            _logger.info('[UPDATE_ML_TAGS] %s no es orden ML, saltando', self.name)
            return result

        update_vals = {}

        # Actualizar estado de envío si cambió
        if shipment_status and shipment_status != self.ml_shipping_status:
            update_vals['ml_shipping_status'] = shipment_status
            result['status_changes'].append(
                f'envío: {self.ml_shipping_status or "vacío"} → {shipment_status}'
            )

        # Actualizar estado de pago/orden si cambió
        if payment_status and payment_status != self.ml_status:
            update_vals['ml_status'] = payment_status
            result['status_changes'].append(
                f'estado: {self.ml_status or "vacío"} → {payment_status}'
            )

        # Actualizar tags ML si cambiaron
        if ml_tags is not None and ml_tags != (self.ml_tags or ''):
            update_vals['ml_tags'] = ml_tags
            result['status_changes'].append('ml_tags actualizados')

        # Actualizar monto pagado si cambió
        if paid_amount is not None and paid_amount != self.ml_paid_amount:
            update_vals['ml_paid_amount'] = paid_amount
            result['status_changes'].append(
                f'pago: {self.ml_paid_amount or 0} → {paid_amount}'
            )

        # Actualizar fecha de sync
        update_vals['ml_sync_date'] = fields.Datetime.now()

        # Escribir cambios de estado
        if update_vals:
            self.write(update_vals)
            result['updated'] = True
            _logger.info('[UPDATE_ML_TAGS] Estados actualizados en %s: %s', self.name, result['status_changes'])

        # =====================================================
        # ACTUALIZAR TAGS DE ODOO SEGÚN CONFIGURACIÓN
        # =====================================================
        logistic_config = None
        if self.ml_logistic_type:
            logistic_config = self.env['mercadolibre.logistic.type'].search([
                ('code', '=', self.ml_logistic_type),
                '|',
                ('account_id', '=', self.ml_account_id.id if self.ml_account_id else False),
                ('account_id', '=', False),
            ], limit=1)
            _logger.info(
                '[UPDATE_ML_TAGS] Buscando config logistica para code=%s, account=%s: encontrada=%s',
                self.ml_logistic_type,
                self.ml_account_id.id if self.ml_account_id else None,
                logistic_config.name if logistic_config else 'NO'
            )
        else:
            _logger.warning('[UPDATE_ML_TAGS] %s no tiene ml_logistic_type, no se pueden aplicar tags', self.name)

        if logistic_config:
            # Usar el estado actualizado o el existente
            current_ship_status = shipment_status or self.ml_shipping_status
            current_pay_status = payment_status or self.ml_status

            # =====================================================
            # ACTUALIZAR TAGS DE ODOO
            # =====================================================
            try:
                _logger.info(
                    '[UPDATE_ML_TAGS] Llamando calculate_and_apply_tags: ship=%s, pay=%s',
                    current_ship_status, current_pay_status
                )

                tag_result = logistic_config.calculate_and_apply_tags(
                    sale_order=self,
                    shipment_status=current_ship_status,
                    payment_status=current_pay_status,
                    account_id=self.ml_account_id.id if self.ml_account_id else None,
                    company_id=self.company_id.id if self.company_id else None
                )

                if tag_result.get('tags_added'):
                    result['tags_added'] = tag_result['tags_added']
                    result['updated'] = True
                if tag_result.get('tags_removed'):
                    result['tags_removed'] = tag_result['tags_removed']
                    result['updated'] = True

                _logger.info(
                    '[UPDATE_ML_TAGS] Resultado tags en %s: +%s -%s',
                    self.name,
                    result['tags_added'],
                    result['tags_removed']
                )

            except Exception as e:
                _logger.error('[UPDATE_ML_TAGS] Error en tags de %s: %s', self.name, e, exc_info=True)

            # =====================================================
            # ACTUALIZAR CAMPOS PERSONALIZADOS SEGÚN CONFIGURACIÓN
            # =====================================================
            try:
                field_result = logistic_config.apply_field_updates(
                    sale_order=self,
                    shipment_status=current_ship_status,
                    payment_status=current_pay_status,
                )

                if field_result.get('fields_updated'):
                    result['fields_updated'] = field_result['fields_updated']
                    result['updated'] = True
                    _logger.info(
                        '[UPDATE_ML_TAGS] Campos actualizados en %s: %s',
                        self.name,
                        [f['field'] for f in field_result['fields_updated']]
                    )

            except Exception as e:
                _logger.error('[UPDATE_ML_TAGS] Error en campos de %s: %s', self.name, e, exc_info=True)

        else:
            _logger.warning('[UPDATE_ML_TAGS] Sin config logistica para %s, no se aplicaron tags/campos', self.name)

        return result

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
