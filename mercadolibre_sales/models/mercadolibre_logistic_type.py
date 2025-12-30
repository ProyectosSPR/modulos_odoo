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
        help='Descargar automaticamente la etiqueta de envio de MercadoLibre y guardarla como adjunto'
    )
    auto_print_label = fields.Boolean(
        string='Imprimir Etiqueta Auto',
        default=False,
        help='Enviar etiqueta a impresora HTTP automaticamente despues de descargarla'
    )
    # Configuracion de impresora HTTP
    printer_url = fields.Char(
        string='URL Impresora',
        default='https://ticketsmagic.automateai.com.mx/api/print',
        help='URL del endpoint HTTP para enviar la etiqueta a imprimir'
    )
    printer_name = fields.Char(
        string='Nombre Impresora',
        default='Beeprt BY-426BT',
        help='Nombre de la impresora configurada en el servidor de impresion'
    )
    printer_copies = fields.Integer(
        string='Copias',
        default=1,
        help='Numero de copias a imprimir'
    )
    label_format = fields.Selection([
        ('pdf', 'PDF'),
        ('zpl2', 'ZPL2 (Zebra)'),
    ], string='Formato Etiqueta', default='pdf',
       help='Formato de etiqueta a descargar de MercadoLibre')

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

    # =========================================================================
    # CONFIGURACION DE ETIQUETAS PARA ORDEN FACTURADA
    # =========================================================================
    invoiced_tag_ids = fields.Many2many(
        'crm.tag',
        'mercadolibre_logistic_type_invoiced_tag_rel',
        'logistic_type_id', 'tag_id',
        string='Tags a Agregar (Facturado)',
        help='Etiquetas que se AGREGAN cuando la orden de venta está facturada'
    )
    invoiced_tags_to_remove_ids = fields.Many2many(
        'crm.tag',
        'mercadolibre_logistic_type_invoiced_remove_tag_rel',
        'logistic_type_id', 'tag_id',
        string='Tags a Quitar (Facturado)',
        help='Etiquetas específicas que se QUITAN cuando la orden está facturada. '
             'Las demás etiquetas se mantienen intactas.'
    )

    # =========================================================================
    # CONFIGURACION DE ACTUALIZACIÓN DE CAMPOS POR ESTADO
    # =========================================================================
    field_update_config_ids = fields.One2many(
        'mercadolibre.field.update.config',
        'logistic_type_id',
        string='Actualización de Campos',
        help='Configuración de campos a actualizar según el estado de envío o pago'
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
        import logging
        _logger = logging.getLogger(__name__)

        self.ensure_one()

        _logger.info(
            '[SHIPMENT_TAGS] Buscando tags para ship_status=%s en config=%s (total configs: %d)',
            shipment_status, self.name, len(self.shipment_status_config_ids)
        )

        config = self.shipment_status_config_ids.filtered(
            lambda c: shipment_status in c.get_status_list()
        )

        if config:
            _logger.info(
                '[SHIPMENT_TAGS] Match! Config "%s" -> Tags: %s',
                config[0].name, config[0].tag_ids.mapped('name')
            )
            return config[0].tag_ids

        _logger.info('[SHIPMENT_TAGS] No se encontró config para ship_status=%s', shipment_status)
        return self.env['crm.tag']

    def get_all_configured_shipment_tags(self):
        """
        Obtiene TODAS las etiquetas configuradas en todos los estados de envío.
        Útil para saber qué tags quitar al cambiar de estado.

        Returns:
            recordset de crm.tag con todos los tags de estados de envío
        """
        self.ensure_one()
        all_tags = self.env['crm.tag']
        for config in self.shipment_status_config_ids:
            all_tags |= config.tag_ids
        return all_tags

    def calculate_and_apply_tags(self, sale_order, shipment_status=None, payment_status=None,
                                  account_id=None, company_id=None):
        """
        Calcula y aplica los tags correctos a una orden de venta según su estado actual.

        LÓGICA:
        - Estados de envío/pago: REEMPLAZA tags (quita anteriores, pone nuevos)
        - Facturación: AGREGA tags configurados, QUITA solo los específicos configurados

        Args:
            sale_order: sale.order record
            shipment_status: Estado de envío actual (opcional)
            payment_status: Estado de pago actual (opcional)
            account_id: ID de cuenta ML (opcional)
            company_id: ID de compañía (opcional)

        Returns:
            dict con información de los cambios realizados
        """
        import logging
        _logger = logging.getLogger(__name__)

        self.ensure_one()

        _logger.info(
            '[CALC_TAGS] Iniciando para %s: config=%s, ship_status=%s, pay_status=%s',
            sale_order.name, self.name, shipment_status, payment_status
        )

        result = {
            'tags_added': [],
            'tags_removed': [],
            'final_tags': [],
        }

        # Obtener tags actuales de la orden
        current_tags = sale_order.tag_ids
        new_tags = self.env['crm.tag']

        _logger.info('[CALC_TAGS] Tags actuales: %s', current_tags.mapped('name'))

        # =====================================================
        # 1. TAGS POR DEFECTO DEL TIPO LOGÍSTICO (siempre se mantienen)
        # =====================================================
        if self.default_tag_ids:
            new_tags |= self.default_tag_ids
            _logger.info('[CALC_TAGS] Tags por defecto: %s', self.default_tag_ids.mapped('name'))

        # =====================================================
        # 2. TAGS POR ESTADO DE ENVÍO (reemplazar)
        # =====================================================
        if shipment_status:
            shipment_tags = self.get_tags_for_shipment_status(shipment_status)
            _logger.info(
                '[CALC_TAGS] Tags para estado envío "%s": %s (configs: %d)',
                shipment_status,
                shipment_tags.mapped('name') if shipment_tags else 'NINGUNO',
                len(self.shipment_status_config_ids)
            )
            if shipment_tags:
                new_tags |= shipment_tags
        else:
            _logger.info('[CALC_TAGS] Sin estado de envío para buscar tags')

        # =====================================================
        # 3. TAGS POR ESTADO DE PAGO (reemplazar)
        # =====================================================
        if payment_status:
            PaymentConfig = self.env['mercadolibre.payment.status.config']
            payment_tags = PaymentConfig.get_tags_for_payment_status(
                payment_status,
                account_id=account_id,
                company_id=company_id
            )
            _logger.info(
                '[CALC_TAGS] Tags para estado pago "%s": %s',
                payment_status,
                payment_tags.mapped('name') if payment_tags else 'NINGUNO'
            )
            if payment_tags:
                new_tags |= payment_tags
        else:
            _logger.info('[CALC_TAGS] Sin estado de pago para buscar tags')

        # =====================================================
        # 4. TAGS DE FACTURACIÓN (lógica especial)
        # =====================================================
        is_invoiced = sale_order.invoice_status == 'invoiced' or \
                      (sale_order.invoice_ids and any(inv.state == 'posted' for inv in sale_order.invoice_ids))

        _logger.info('[CALC_TAGS] Facturado: %s (invoice_status=%s)', is_invoiced, sale_order.invoice_status)

        if is_invoiced:
            # Agregar tags de facturación
            if self.invoiced_tag_ids:
                new_tags |= self.invoiced_tag_ids
                _logger.info('[CALC_TAGS] Tags facturación agregados: %s', self.invoiced_tag_ids.mapped('name'))

            # Quitar solo los tags específicos configurados para quitar
            if self.invoiced_tags_to_remove_ids:
                new_tags -= self.invoiced_tags_to_remove_ids
                _logger.info('[CALC_TAGS] Tags facturación quitados: %s', self.invoiced_tags_to_remove_ids.mapped('name'))

        # =====================================================
        # 5. PRESERVAR TAGS QUE NO SON DE ML
        # =====================================================
        # Obtener todos los tags que están configurados en ML (para no quitar tags manuales)
        all_ml_tags = self.default_tag_ids | self.get_all_configured_shipment_tags()
        all_ml_tags |= self.invoiced_tag_ids | self.invoiced_tags_to_remove_ids

        # Obtener tags de pago configurados
        PaymentConfig = self.env['mercadolibre.payment.status.config']
        all_payment_configs = PaymentConfig.search([])
        for pc in all_payment_configs:
            all_ml_tags |= pc.tag_ids

        # Tags manuales (los que tiene la orden pero no están en ninguna config ML)
        manual_tags = current_tags - all_ml_tags

        # Agregar tags manuales al resultado final
        new_tags |= manual_tags

        _logger.info('[CALC_TAGS] Tags manuales preservados: %s', manual_tags.mapped('name'))
        _logger.info('[CALC_TAGS] Tags finales calculados: %s', new_tags.mapped('name'))

        # =====================================================
        # 6. APLICAR CAMBIOS
        # =====================================================
        if set(new_tags.ids) != set(current_tags.ids):
            result['tags_removed'] = (current_tags - new_tags).mapped('name')
            result['tags_added'] = (new_tags - current_tags).mapped('name')

            sale_order.write({'tag_ids': [(6, 0, new_tags.ids)]})
            _logger.info(
                '[CALC_TAGS] Cambios aplicados en %s: +%s -%s',
                sale_order.name, result['tags_added'], result['tags_removed']
            )
        else:
            _logger.info('[CALC_TAGS] Sin cambios necesarios en tags para %s', sale_order.name)

        result['final_tags'] = new_tags.mapped('name')

        return result

    def apply_field_updates(self, sale_order, shipment_status=None, payment_status=None):
        """
        Aplica las actualizaciones de campos configuradas según el estado.

        Args:
            sale_order: sale.order record
            shipment_status: Estado de envío actual (opcional)
            payment_status: Estado de pago/orden actual (opcional)

        Returns:
            dict con información de los campos actualizados
        """
        import logging
        _logger = logging.getLogger(__name__)

        self.ensure_one()

        result = {
            'fields_updated': [],
            'errors': [],
        }

        if not self.field_update_config_ids:
            return result

        _logger.info(
            '[FIELD_UPDATES] Verificando %d configs para %s (ship=%s, pay=%s)',
            len(self.field_update_config_ids), sale_order.name,
            shipment_status, payment_status
        )

        # Obtener picking relacionado si es necesario
        picking = None

        for config in self.field_update_config_ids.filtered('active'):
            try:
                # Verificar si debe activarse
                should_apply = False

                if config.trigger_type == 'shipment' and shipment_status:
                    should_apply = config.should_trigger('shipment', shipment_status)
                elif config.trigger_type == 'payment' and payment_status:
                    should_apply = config.should_trigger('payment', payment_status)

                if not should_apply:
                    continue

                _logger.info(
                    '[FIELD_UPDATES] Config "%s" activada para %s',
                    config.name, sale_order.name
                )

                # Determinar el registro destino
                if config.target_model == 'sale.order':
                    target_record = sale_order
                elif config.target_model == 'stock.picking':
                    # Obtener picking si no lo tenemos
                    if picking is None:
                        picking = sale_order.picking_ids.filtered(
                            lambda p: p.state not in ('done', 'cancel') and p.picking_type_code == 'outgoing'
                        )[:1]
                        if not picking:
                            # Buscar el último picking de salida
                            picking = sale_order.picking_ids.filtered(
                                lambda p: p.picking_type_code == 'outgoing'
                            ).sorted('id', reverse=True)[:1]

                    if not picking:
                        _logger.warning(
                            '[FIELD_UPDATES] No hay picking para orden %s, saltando config %s',
                            sale_order.name, config.name
                        )
                        continue

                    target_record = picking
                else:
                    continue

                # Aplicar la actualización
                update_result = config.apply_to_record(target_record)

                if update_result.get('applied'):
                    result['fields_updated'].append({
                        'config': config.name,
                        'model': config.target_model,
                        'field': update_result['field'],
                        'old_value': update_result['old_value'],
                        'new_value': update_result['new_value'],
                    })

                if update_result.get('error'):
                    result['errors'].append({
                        'config': config.name,
                        'error': update_result['error'],
                    })

            except Exception as e:
                _logger.error(
                    '[FIELD_UPDATES] Error en config %s: %s',
                    config.name, e
                )
                result['errors'].append({
                    'config': config.name,
                    'error': str(e),
                })

        if result['fields_updated']:
            _logger.info(
                '[FIELD_UPDATES] Campos actualizados en %s: %s',
                sale_order.name,
                [f"{u['model']}.{u['field']}" for u in result['fields_updated']]
            )

        return result


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
        help='Etiquetas a asignar a la orden cuando el envio tenga alguno de los estados seleccionados'
    )

    description = fields.Text(
        string='Notas',
        help='Descripcion de cuando se aplica esta configuracion'
    )

    # Campo computed para mostrar estados en tree
    status_display = fields.Char(
        string='Estados',
        compute='_compute_status_display',
        help='Muestra los estados seleccionados'
    )

    @api.depends(
        'status_pending', 'status_handling', 'status_ready_to_ship',
        'status_shipped', 'status_in_transit', 'status_out_for_delivery',
        'status_delivered', 'status_not_delivered', 'status_returned', 'status_cancelled'
    )
    def _compute_status_display(self):
        """Genera texto con los estados seleccionados para mostrar en el tree"""
        status_labels = {
            'pending': 'Pendiente',
            'handling': 'Preparación',
            'ready_to_ship': 'Listo',
            'shipped': 'Enviado',
            'in_transit': 'Tránsito',
            'out_for_delivery': 'Reparto',
            'delivered': 'Entregado',
            'not_delivered': 'No Entregado',
            'returned': 'Devuelto',
            'cancelled': 'Cancelado',
        }
        for record in self:
            statuses = record.get_status_list()
            labels = [status_labels.get(s, s) for s in statuses]
            record.status_display = ', '.join(labels) if labels else 'Sin estados'

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

    # =========================================================================
    # ESTADOS DE ORDEN ML (los que vienen en mercadolibre.order.status)
    # =========================================================================
    status_confirmed = fields.Boolean(string='Confirmada', help='Estado orden: confirmed')
    status_payment_required = fields.Boolean(string='Pago Requerido', help='Estado orden: payment_required')
    status_payment_in_process = fields.Boolean(string='Pago en Proceso', help='Estado orden: payment_in_process')
    status_partially_paid = fields.Boolean(string='Parcialmente Pagada', help='Estado orden: partially_paid')
    status_paid = fields.Boolean(string='Pagada', help='Estado orden: paid')
    status_partially_refunded = fields.Boolean(string='Parcialmente Reembolsada', help='Estado orden: partially_refunded')
    status_pending_cancel = fields.Boolean(string='Cancelación Pendiente', help='Estado orden: pending_cancel')
    status_cancelled = fields.Boolean(string='Cancelada', help='Estado: cancelled')

    # =========================================================================
    # ESTADOS DE PAGO (los que vienen del API de pagos - por compatibilidad)
    # =========================================================================
    status_pending = fields.Boolean(string='Pendiente', help='Estado pago: pending')
    status_approved = fields.Boolean(string='Aprobado', help='Estado pago: approved')
    status_authorized = fields.Boolean(string='Autorizado', help='Estado pago: authorized')
    status_in_process = fields.Boolean(string='En Proceso (Pago)', help='Estado pago: in_process')
    status_in_mediation = fields.Boolean(string='En Mediacion', help='Estado pago: in_mediation')
    status_rejected = fields.Boolean(string='Rechazado', help='Estado pago: rejected')
    status_refunded = fields.Boolean(string='Reembolsado', help='Estado pago: refunded')
    status_charged_back = fields.Boolean(string='Contracargo', help='Estado pago: charged_back')

    # Etiquetas a asignar
    tag_ids = fields.Many2many(
        'crm.tag',
        'mercadolibre_payment_status_config_tag_rel',
        'config_id', 'tag_id',
        string='Etiquetas',
        help='Etiquetas a asignar a la orden cuando el pago tenga alguno de los estados seleccionados'
    )

    description = fields.Text(
        string='Notas'
    )

    def get_status_list(self):
        """Retorna lista de estados seleccionados (tanto de orden como de pago)"""
        self.ensure_one()
        statuses = []

        # Estados de orden ML
        if self.status_confirmed:
            statuses.append('confirmed')
        if self.status_payment_required:
            statuses.append('payment_required')
        if self.status_payment_in_process:
            statuses.append('payment_in_process')
        if self.status_partially_paid:
            statuses.append('partially_paid')
        if self.status_paid:
            statuses.append('paid')
        if self.status_partially_refunded:
            statuses.append('partially_refunded')
        if self.status_pending_cancel:
            statuses.append('pending_cancel')
        if self.status_cancelled:
            statuses.append('cancelled')

        # Estados de pago (API de pagos)
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
        if self.status_refunded:
            statuses.append('refunded')
        if self.status_charged_back:
            statuses.append('charged_back')

        return statuses

    @api.model
    def get_tags_for_payment_status(self, payment_status, account_id=None, company_id=None):
        """
        Obtiene las etiquetas correspondientes a un estado de pago/orden.

        Args:
            payment_status: Estado del pago/orden (paid, confirmed, approved, etc.)
            account_id: ID de la cuenta ML (opcional)
            company_id: ID de la compania (opcional)

        Returns:
            recordset de crm.tag
        """
        import logging
        _logger = logging.getLogger(__name__)

        domain = [('active', '=', True)]
        if account_id:
            domain.append(('account_id', 'in', [False, account_id]))
        if company_id:
            domain.append(('company_id', 'in', [False, company_id]))

        configs = self.search(domain)
        _logger.info(
            '[PAYMENT_TAGS] Buscando tags para status=%s, account=%s, company=%s: encontradas %d configs',
            payment_status, account_id, company_id, len(configs)
        )

        for config in configs:
            status_list = config.get_status_list()
            _logger.debug(
                '[PAYMENT_TAGS] Config "%s" tiene estados: %s',
                config.name, status_list
            )
            if payment_status in status_list:
                _logger.info(
                    '[PAYMENT_TAGS] Match! Config "%s" -> Tags: %s',
                    config.name, config.tag_ids.mapped('name')
                )
                return config.tag_ids

        _logger.info('[PAYMENT_TAGS] No se encontró config para status=%s', payment_status)
        return self.env['crm.tag']


class MercadolibreFieldUpdateConfig(models.Model):
    """
    Configuración para actualizar campos de sale.order o stock.picking
    según el estado de envío o pago.

    Permite a clientes con desarrollos personalizados actualizar campos
    custom (x_*) automáticamente cuando cambia el estado.
    """
    _name = 'mercadolibre.field.update.config'
    _description = 'Configuración de Actualización de Campos por Estado'
    _order = 'sequence, id'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre descriptivo (ej: "Marcar Entregado", "Fecha de Pago")'
    )
    active = fields.Boolean(
        string='Activo',
        default=True
    )
    sequence = fields.Integer(
        string='Secuencia',
        default=10
    )

    # =========================================================================
    # RELACIÓN CON TIPO LOGÍSTICO
    # =========================================================================
    logistic_type_id = fields.Many2one(
        'mercadolibre.logistic.type',
        string='Tipo Logístico',
        required=True,
        ondelete='cascade',
        help='Tipo logístico donde aplica esta configuración'
    )

    # =========================================================================
    # TIPO DE DISPARADOR
    # =========================================================================
    trigger_type = fields.Selection([
        ('shipment', 'Estado de Envío'),
        ('payment', 'Estado de Pago/Orden'),
    ], string='Tipo de Disparador', required=True, default='shipment',
       help='Qué tipo de estado activa esta actualización')

    # =========================================================================
    # ESTADOS DE ENVÍO QUE ACTIVAN
    # =========================================================================
    ship_status_pending = fields.Boolean(string='Pendiente', help='Estado envío: pending')
    ship_status_handling = fields.Boolean(string='En Preparación', help='Estado envío: handling')
    ship_status_ready_to_ship = fields.Boolean(string='Listo para Enviar', help='Estado envío: ready_to_ship')
    ship_status_shipped = fields.Boolean(string='Enviado', help='Estado envío: shipped')
    ship_status_in_transit = fields.Boolean(string='En Tránsito', help='Estado envío: in_transit')
    ship_status_out_for_delivery = fields.Boolean(string='En Reparto', help='Estado envío: out_for_delivery')
    ship_status_delivered = fields.Boolean(string='Entregado', help='Estado envío: delivered')
    ship_status_not_delivered = fields.Boolean(string='No Entregado', help='Estado envío: not_delivered')
    ship_status_returned = fields.Boolean(string='Devuelto', help='Estado envío: returned')
    ship_status_cancelled = fields.Boolean(string='Cancelado', help='Estado envío: cancelled')

    # =========================================================================
    # ESTADOS DE PAGO/ORDEN QUE ACTIVAN
    # =========================================================================
    pay_status_confirmed = fields.Boolean(string='Confirmada', help='Estado orden: confirmed')
    pay_status_payment_required = fields.Boolean(string='Pago Requerido', help='Estado orden: payment_required')
    pay_status_payment_in_process = fields.Boolean(string='Pago en Proceso', help='Estado orden: payment_in_process')
    pay_status_partially_paid = fields.Boolean(string='Parcialmente Pagada', help='Estado orden: partially_paid')
    pay_status_paid = fields.Boolean(string='Pagada', help='Estado orden: paid')
    pay_status_partially_refunded = fields.Boolean(string='Parcialmente Reembolsada', help='Estado orden: partially_refunded')
    pay_status_pending_cancel = fields.Boolean(string='Cancelación Pendiente', help='Estado orden: pending_cancel')
    pay_status_cancelled = fields.Boolean(string='Cancelada', help='Estado orden: cancelled')

    # =========================================================================
    # CAMPO A ACTUALIZAR
    # =========================================================================
    target_model = fields.Selection([
        ('sale.order', 'Orden de Venta'),
        ('stock.picking', 'Albarán/Picking'),
    ], string='Modelo', required=True, default='sale.order',
       help='Modelo donde se actualizará el campo')

    field_id = fields.Many2one(
        'ir.model.fields',
        string='Campo a Actualizar',
        required=True,
        ondelete='cascade',
        domain="[('model', '=', target_model), ('store', '=', True), "
               "('ttype', 'in', ['boolean', 'char', 'text', 'integer', 'float', "
               "'date', 'datetime', 'selection', 'many2one'])]",
        help='Campo que se actualizará cuando se active el estado'
    )
    field_name = fields.Char(
        related='field_id.name',
        string='Nombre Técnico',
        readonly=True
    )
    field_type = fields.Selection(
        related='field_id.ttype',
        string='Tipo de Campo',
        readonly=True
    )

    # =========================================================================
    # VALOR A ASIGNAR
    # =========================================================================
    value_type = fields.Selection([
        ('fixed', 'Valor Fijo'),
        ('current_date', 'Fecha Actual'),
        ('current_datetime', 'Fecha y Hora Actual'),
        ('current_user', 'Usuario Actual'),
        ('clear', 'Limpiar/Vaciar'),
    ], string='Tipo de Valor', required=True, default='fixed',
       help='Cómo se determina el valor a asignar')

    value_fixed = fields.Char(
        string='Valor Fijo',
        help='Valor a asignar. Para booleanos usar "True" o "False". '
             'Para Many2one usar el ID numérico.'
    )

    # =========================================================================
    # DESCRIPCIÓN
    # =========================================================================
    description = fields.Text(
        string='Notas',
        help='Descripción de qué hace esta configuración'
    )

    # =========================================================================
    # CAMPO COMPUTED PARA MOSTRAR ESTADOS EN TREE
    # =========================================================================
    status_display = fields.Char(
        string='Estados',
        compute='_compute_status_display',
        help='Muestra los estados seleccionados que disparan esta actualización'
    )

    @api.depends(
        'trigger_type',
        'ship_status_pending', 'ship_status_handling', 'ship_status_ready_to_ship',
        'ship_status_shipped', 'ship_status_in_transit', 'ship_status_out_for_delivery',
        'ship_status_delivered', 'ship_status_not_delivered', 'ship_status_returned',
        'ship_status_cancelled',
        'pay_status_confirmed', 'pay_status_payment_required', 'pay_status_payment_in_process',
        'pay_status_partially_paid', 'pay_status_paid', 'pay_status_partially_refunded',
        'pay_status_pending_cancel', 'pay_status_cancelled'
    )
    def _compute_status_display(self):
        """Genera texto con los estados seleccionados para mostrar en el tree"""
        status_labels = {
            # Envío
            'pending': 'Pendiente',
            'handling': 'Preparación',
            'ready_to_ship': 'Listo',
            'shipped': 'Enviado',
            'in_transit': 'Tránsito',
            'out_for_delivery': 'Reparto',
            'delivered': 'Entregado',
            'not_delivered': 'No Entregado',
            'returned': 'Devuelto',
            'cancelled': 'Cancelado',
            # Pago
            'confirmed': 'Confirmada',
            'payment_required': 'Pago Req.',
            'payment_in_process': 'En Proceso',
            'partially_paid': 'Parc. Pagado',
            'paid': 'Pagado',
            'partially_refunded': 'Parc. Reemb.',
            'pending_cancel': 'Pend. Cancelar',
        }
        for record in self:
            if record.trigger_type == 'shipment':
                statuses = record.get_shipment_status_list()
            else:
                statuses = record.get_payment_status_list()

            labels = [status_labels.get(s, s) for s in statuses]
            record.status_display = ', '.join(labels) if labels else 'Sin estados'

    def get_shipment_status_list(self):
        """Retorna lista de estados de envío seleccionados"""
        self.ensure_one()
        statuses = []
        if self.ship_status_pending:
            statuses.append('pending')
        if self.ship_status_handling:
            statuses.append('handling')
        if self.ship_status_ready_to_ship:
            statuses.append('ready_to_ship')
        if self.ship_status_shipped:
            statuses.append('shipped')
        if self.ship_status_in_transit:
            statuses.append('in_transit')
        if self.ship_status_out_for_delivery:
            statuses.append('out_for_delivery')
        if self.ship_status_delivered:
            statuses.append('delivered')
        if self.ship_status_not_delivered:
            statuses.append('not_delivered')
        if self.ship_status_returned:
            statuses.append('returned')
        if self.ship_status_cancelled:
            statuses.append('cancelled')
        return statuses

    def get_payment_status_list(self):
        """Retorna lista de estados de pago/orden seleccionados"""
        self.ensure_one()
        statuses = []
        if self.pay_status_confirmed:
            statuses.append('confirmed')
        if self.pay_status_payment_required:
            statuses.append('payment_required')
        if self.pay_status_payment_in_process:
            statuses.append('payment_in_process')
        if self.pay_status_partially_paid:
            statuses.append('partially_paid')
        if self.pay_status_paid:
            statuses.append('paid')
        if self.pay_status_partially_refunded:
            statuses.append('partially_refunded')
        if self.pay_status_pending_cancel:
            statuses.append('pending_cancel')
        if self.pay_status_cancelled:
            statuses.append('cancelled')
        return statuses

    def should_trigger(self, trigger_type, status):
        """
        Verifica si esta configuración debe activarse para el estado dado.

        Args:
            trigger_type: 'shipment' o 'payment'
            status: El estado actual (ej: 'delivered', 'paid')

        Returns:
            bool: True si debe activarse
        """
        self.ensure_one()

        if self.trigger_type != trigger_type:
            return False

        if trigger_type == 'shipment':
            return status in self.get_shipment_status_list()
        else:
            return status in self.get_payment_status_list()

    def get_value_to_set(self):
        """
        Obtiene el valor a asignar según la configuración.

        Returns:
            El valor convertido al tipo correcto del campo
        """
        self.ensure_one()

        if self.value_type == 'clear':
            return False

        if self.value_type == 'current_date':
            return fields.Date.today()

        if self.value_type == 'current_datetime':
            return fields.Datetime.now()

        if self.value_type == 'current_user':
            return self.env.user.id

        # Valor fijo - convertir según tipo de campo
        if self.value_type == 'fixed':
            return self._convert_fixed_value()

        return False

    def _convert_fixed_value(self):
        """Convierte el valor fijo al tipo correcto del campo"""
        self.ensure_one()

        if not self.value_fixed:
            return False

        field_type = self.field_type
        value = self.value_fixed.strip()

        try:
            if field_type == 'boolean':
                return value.lower() in ('true', '1', 'yes', 'si', 'sí')

            elif field_type == 'integer':
                return int(value)

            elif field_type == 'float':
                return float(value)

            elif field_type == 'many2one':
                return int(value)  # ID del registro

            elif field_type == 'date':
                # Soportar 'today' o fecha ISO
                if value.lower() == 'today':
                    return fields.Date.today()
                return value

            elif field_type == 'datetime':
                if value.lower() == 'now':
                    return fields.Datetime.now()
                return value

            elif field_type in ('char', 'text', 'selection'):
                return value

        except (ValueError, TypeError) as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning(
                'Error convirtiendo valor "%s" para campo %s (tipo %s): %s',
                value, self.field_name, field_type, e
            )
            return False

        return value

    def apply_to_record(self, record):
        """
        Aplica la actualización del campo al registro.

        Args:
            record: El registro (sale.order o stock.picking)

        Returns:
            dict: {'field': field_name, 'old_value': ..., 'new_value': ..., 'applied': bool}
        """
        self.ensure_one()
        import logging
        _logger = logging.getLogger(__name__)

        result = {
            'field': self.field_name,
            'old_value': None,
            'new_value': None,
            'applied': False,
            'error': None,
        }

        try:
            # Verificar que el campo existe en el modelo
            if self.field_name not in record._fields:
                result['error'] = f'Campo {self.field_name} no existe en {record._name}'
                _logger.warning('[FIELD_UPDATE] %s', result['error'])
                return result

            # Obtener valor actual
            result['old_value'] = record[self.field_name]

            # Obtener nuevo valor
            new_value = self.get_value_to_set()
            result['new_value'] = new_value

            # Aplicar si es diferente
            if result['old_value'] != new_value:
                record.write({self.field_name: new_value})
                result['applied'] = True
                _logger.info(
                    '[FIELD_UPDATE] %s.%s: %s → %s (config: %s)',
                    record._name, self.field_name,
                    result['old_value'], new_value, self.name
                )
            else:
                _logger.debug(
                    '[FIELD_UPDATE] %s.%s sin cambios (valor ya es %s)',
                    record._name, self.field_name, new_value
                )

        except Exception as e:
            result['error'] = str(e)
            _logger.error(
                '[FIELD_UPDATE] Error aplicando %s a %s: %s',
                self.name, record, e
            )

        return result
