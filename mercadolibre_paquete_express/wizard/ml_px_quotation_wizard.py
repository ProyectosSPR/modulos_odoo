# -*- coding: utf-8 -*-

import json
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Prefijo para logs de este módulo
LOG_PREFIX = '[ML_PX_QUOTATION]'


class MlPxQuotationWizard(models.TransientModel):
    _name = 'ml.px.quotation.wizard'
    _description = 'Wizard Cotizacion Paquete Express para MercadoLibre'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Orden de Venta',
        required=True,
        readonly=True
    )

    # Origen (de la empresa)
    origin_zip = fields.Char(
        string='CP Origen',
        required=True
    )
    origin_address = fields.Char(
        string='Direccion Origen',
        required=True
    )

    # Destino (entrada libre)
    dest_name = fields.Char(
        string='Nombre Receptor',
        required=True
    )
    dest_phone = fields.Char(
        string='Telefono'
    )
    dest_street = fields.Char(
        string='Calle y Numero',
        required=True
    )
    dest_colony = fields.Char(
        string='Colonia'
    )
    dest_city = fields.Char(
        string='Ciudad',
        required=True
    )
    dest_state = fields.Char(
        string='Estado',
        required=True
    )
    dest_zip = fields.Char(
        string='Codigo Postal',
        required=True
    )
    dest_comments = fields.Text(
        string='Referencias / Comentarios'
    )

    # Lineas de paquetes
    package_line_ids = fields.One2many(
        'ml.px.quotation.wizard.line',
        'wizard_id',
        string='Paquetes'
    )

    # Totales
    total_weight = fields.Float(
        string='Peso Total (kg)',
        compute='_compute_totals',
        store=True,
        digits=(16, 3)
    )
    total_volume = fields.Float(
        string='Volumen Total (m3)',
        compute='_compute_totals',
        store=True,
        digits=(16, 6)
    )
    total_amount = fields.Float(
        string='Valor Declarado',
        compute='_compute_totals',
        store=True,
        digits=(16, 2)
    )

    # Fuente de datos
    address_source = fields.Selection([
        ('ml_shipment', 'Envio MercadoLibre'),
        ('partner', 'Partner de Envio'),
        ('manual', 'Ingreso Manual'),
    ], string='Fuente de Direccion', readonly=True)

    ml_shipment_id = fields.Many2one(
        'mercadolibre.shipment',
        string='Envio ML',
        readonly=True
    )

    @api.depends('package_line_ids.weight', 'package_line_ids.volume',
                 'package_line_ids.quantity', 'package_line_ids.unit_price')
    def _compute_totals(self):
        for wizard in self:
            total_weight = 0.0
            total_volume = 0.0
            total_amount = 0.0
            for line in wizard.package_line_ids:
                total_weight += line.weight * line.quantity
                total_volume += line.volume * line.quantity
                total_amount += line.unit_price * line.quantity
            wizard.total_weight = total_weight
            wizard.total_volume = total_volume
            wizard.total_amount = total_amount

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        # Obtener orden de venta del contexto
        sale_order_id = self._context.get('active_id')
        _logger.info('%s ========== INICIO default_get ==========', LOG_PREFIX)
        _logger.info('%s sale_order_id del contexto: %s', LOG_PREFIX, sale_order_id)

        if not sale_order_id:
            _logger.warning('%s No se encontro sale_order_id en contexto', LOG_PREFIX)
            return res

        sale_order = self.env['sale.order'].browse(sale_order_id)
        res['sale_order_id'] = sale_order_id
        _logger.info('%s Orden de venta: %s (ID: %s)', LOG_PREFIX, sale_order.name, sale_order.id)
        _logger.info('%s ml_order_id: %s', LOG_PREFIX, sale_order.ml_order_id)

        # Origen: datos de la empresa
        company = self.env.company
        res['origin_zip'] = company.zip or ''
        res['origin_address'] = company.street or ''
        _logger.info('%s Origen - CP: %s, Direccion: %s', LOG_PREFIX, company.zip, company.street)

        # Intentar obtener direccion de destino desde ML shipment
        ml_shipment = None
        address_source = 'manual'

        if sale_order.ml_order_id:
            _logger.info('%s Buscando mercadolibre.order con ml_order_id=%s', LOG_PREFIX, sale_order.ml_order_id)
            # Buscar shipment asociado
            ml_order = self.env['mercadolibre.order'].search([
                ('ml_order_id', '=', sale_order.ml_order_id)
            ], limit=1)
            _logger.info('%s mercadolibre.order encontrado: ID=%s', LOG_PREFIX, ml_order.id if ml_order else None)

            if ml_order and ml_order.ml_shipment_id:
                _logger.info('%s ml_shipment_id en orden: %s', LOG_PREFIX, ml_order.ml_shipment_id)
                ml_shipment = self.env['mercadolibre.shipment'].search([
                    ('ml_shipment_id', '=', ml_order.ml_shipment_id)
                ], limit=1)
                _logger.info('%s mercadolibre.shipment encontrado: ID=%s', LOG_PREFIX, ml_shipment.id if ml_shipment else None)

        if ml_shipment and ml_shipment.zip_code:
            # Usar datos del envio ML
            address_source = 'ml_shipment'
            _logger.info('%s Usando datos de ML Shipment', LOG_PREFIX)
            _logger.info('%s Receptor: %s', LOG_PREFIX, ml_shipment.receiver_name)
            _logger.info('%s Telefono: %s', LOG_PREFIX, ml_shipment.receiver_phone)
            _logger.info('%s CP Destino: %s', LOG_PREFIX, ml_shipment.zip_code)
            _logger.info('%s Ciudad: %s, Estado: %s', LOG_PREFIX, ml_shipment.city, ml_shipment.state)

            res['ml_shipment_id'] = ml_shipment.id
            res['dest_name'] = ml_shipment.receiver_name or ''
            res['dest_phone'] = ml_shipment.receiver_phone or ''

            # Construir direccion
            street_parts = []
            if ml_shipment.street_name:
                street_parts.append(ml_shipment.street_name)
            if ml_shipment.street_number:
                street_parts.append(ml_shipment.street_number)
            res['dest_street'] = ' '.join(street_parts)

            res['dest_colony'] = ''  # ML no siempre tiene colonia separada
            res['dest_city'] = ml_shipment.city or ''
            res['dest_state'] = ml_shipment.state or ''
            res['dest_zip'] = ml_shipment.zip_code or ''
            res['dest_comments'] = ml_shipment.comments or ''

        elif sale_order.partner_shipping_id:
            # Usar partner de envio
            address_source = 'partner'
            partner = sale_order.partner_shipping_id
            _logger.info('%s Usando datos de Partner de envio: %s', LOG_PREFIX, partner.name)
            _logger.info('%s CP Partner: %s', LOG_PREFIX, partner.zip)

            res['dest_name'] = partner.name or ''
            res['dest_phone'] = partner.phone or partner.mobile or ''
            res['dest_street'] = partner.street or ''
            res['dest_colony'] = partner.street2 or ''
            res['dest_city'] = partner.city or ''
            res['dest_state'] = partner.state_id.name if partner.state_id else ''
            res['dest_zip'] = partner.zip or ''
            res['dest_comments'] = ''
        else:
            _logger.warning('%s No se encontro direccion de destino (ni ML shipment ni partner)', LOG_PREFIX)

        res['address_source'] = address_source
        _logger.info('%s Fuente de direccion: %s', LOG_PREFIX, address_source)

        # Crear lineas de paquetes desde las lineas de la orden
        package_lines = self._prepare_package_lines(sale_order)
        res['package_line_ids'] = [(0, 0, line) for line in package_lines]
        _logger.info('%s Lineas de paquetes creadas: %d', LOG_PREFIX, len(package_lines))
        _logger.info('%s ========== FIN default_get ==========', LOG_PREFIX)

        return res

    def _prepare_package_lines(self, sale_order):
        """
        Prepara las lineas de paquetes desde las lineas de la orden.
        Maneja productos kit expandiendo sus componentes.
        """
        _logger.info('%s Preparando lineas de paquetes para orden %s', LOG_PREFIX, sale_order.name)
        lines = []
        has_mrp = 'mrp.bom' in self.env.registry

        for order_line in sale_order.order_line:
            product = order_line.product_id

            if not product or product.type == 'service':
                continue

            qty = order_line.product_uom_qty
            _logger.info('%s Producto: %s (qty=%s, peso=%s, vol=%s)',
                        LOG_PREFIX, product.name, qty, product.weight, product.volume)

            # Verificar si es un kit (product.template con bom tipo kit)
            bom = False
            if has_mrp:
                bom = self.env['mrp.bom'].search([
                    ('product_tmpl_id', '=', product.product_tmpl_id.id),
                    ('type', '=', 'phantom')
                ], limit=1)

            if bom:
                # Es un kit - sumar peso/volumen de componentes
                _logger.info('%s Producto %s es KIT, calculando componentes', LOG_PREFIX, product.name)
                total_weight, total_volume = self._get_kit_weight_volume(bom, qty)
                lines.append({
                    'product_id': product.id,
                    'name': f'{product.name} (Kit)',
                    'quantity': qty,
                    'weight': total_weight / qty if qty else 0,  # Peso por unidad de kit
                    'volume': total_volume / qty if qty else 0,
                    'unit_price': order_line.price_unit,
                    'package_type_id': product.x_px_shp_code.id if hasattr(product, 'x_px_shp_code') and product.x_px_shp_code else False,
                    'is_kit': True,
                })
            else:
                # Producto normal
                pkg_type = product.x_px_shp_code if hasattr(product, 'x_px_shp_code') else None
                _logger.info('%s Tipo paquete: %s', LOG_PREFIX, pkg_type.code if pkg_type else 'NO CONFIGURADO')
                lines.append({
                    'product_id': product.id,
                    'name': product.name,
                    'quantity': qty,
                    'weight': product.weight or 0.0,
                    'volume': product.volume or 0.0,
                    'unit_price': order_line.price_unit,
                    'package_type_id': pkg_type.id if pkg_type else False,
                    'is_kit': False,
                })

        return lines

    def _get_kit_weight_volume(self, bom, kit_qty=1):
        """
        Calcula el peso y volumen total de un kit basado en sus componentes.
        """
        total_weight = 0.0
        total_volume = 0.0
        has_mrp = 'mrp.bom' in self.env.registry

        for line in bom.bom_line_ids:
            component = line.product_id
            component_qty = line.product_qty * kit_qty

            # Verificar si el componente tambien es un kit (recursivo)
            sub_bom = False
            if has_mrp:
                sub_bom = self.env['mrp.bom'].search([
                    ('product_tmpl_id', '=', component.product_tmpl_id.id),
                    ('type', '=', 'phantom')
                ], limit=1)

            if sub_bom:
                sub_weight, sub_volume = self._get_kit_weight_volume(sub_bom, component_qty)
                total_weight += sub_weight
                total_volume += sub_volume
            else:
                total_weight += (component.weight or 0.0) * component_qty
                total_volume += (component.volume or 0.0) * component_qty

        return total_weight, total_volume

    def action_get_quotation(self):
        """
        Obtiene cotizacion de Paquete Express usando la API.
        """
        self.ensure_one()
        _logger.info('%s ========== INICIO action_get_quotation ==========', LOG_PREFIX)
        _logger.info('%s Orden: %s', LOG_PREFIX, self.sale_order_id.name)
        _logger.info('%s Destino: CP=%s, Estado=%s, Ciudad=%s',
                    LOG_PREFIX, self.dest_zip, self.dest_state, self.dest_city)
        _logger.info('%s Total: Peso=%s, Volumen=%s, Monto=%s',
                    LOG_PREFIX, self.total_weight, self.total_volume, self.total_amount)

        # Validar datos requeridos
        if not self.dest_zip:
            raise UserError(_('El codigo postal de destino es requerido.'))
        if not self.dest_state:
            raise UserError(_('El estado de destino es requerido.'))
        if not self.package_line_ids:
            raise UserError(_('Debe tener al menos una linea de paquete.'))

        # Validar que las lineas tengan peso y volumen
        for line in self.package_line_ids:
            if not line.weight:
                raise UserError(_('El producto "%s" no tiene peso configurado.') % line.name)
            if not line.volume:
                raise UserError(_('El producto "%s" no tiene volumen configurado.') % line.name)
            if not line.package_type_id:
                raise UserError(_('El producto "%s" no tiene tipo de paquete configurado.') % line.name)

        # Preparar detalles de envio para la API
        shipment_details = []
        for idx, line in enumerate(self.package_line_ids):
            detail = {
                "sequence": idx + 1,
                "quantity": int(line.quantity),
                "shpCode": line.package_type_id.code,
                "weight": line.weight,
                "volume": line.volume,
            }
            shipment_details.append(detail)
            _logger.info('%s Detalle envio %d: %s', LOG_PREFIX, idx + 1, detail)

        # Construir direccion de destino para API
        dest_address = self.dest_state
        if self.dest_colony:
            dest_address = f'{self.dest_colony}, {dest_address}'

        _logger.info('%s Direccion destino para API: %s', LOG_PREFIX, dest_address)

        # Llamar API de Paquete Express usando el metodo existente
        StockPicking = self.env['stock.picking']

        try:
            _logger.info('%s Llamando px_api_quotation...', LOG_PREFIX)
            data = StockPicking.px_api_quotation(
                self.dest_zip,
                dest_address,
                self.total_amount,
                shipment_details
            )
            _logger.info('%s Respuesta API recibida', LOG_PREFIX)
        except Exception as e:
            _logger.error('%s Error en px_api_quotation: %s', LOG_PREFIX, str(e), exc_info=True)
            raise UserError(_('Error al obtener cotizacion: %s') % str(e))

        # Procesar respuesta
        response_success = data.get("body", {}).get("response", {}).get("success")
        _logger.info('%s Respuesta exitosa: %s', LOG_PREFIX, response_success)

        if response_success:
            quotation_data = data["body"]["response"]["data"]
            quotations = quotation_data.get('quotations', [])
            _logger.info('%s Cotizaciones recibidas: %d', LOG_PREFIX, len(quotations))

            # Crear registro de respuesta usando el modelo existente
            quote_services = []
            for record in quotations:
                _logger.info('%s Servicio: %s - %s (Total: %s)',
                            LOG_PREFIX, record.get("serviceType"), record.get("serviceName"),
                            record.get("amount", {}).get("totalAmnt"))
                quote_services.append((0, 0, {
                    "service_type": record.get("serviceType", ""),
                    "service_id": record.get("id", ""),
                    "service_id_ref": record.get("idRef", ""),
                    "service_name": record.get("serviceName", ""),
                    "service_info_descr": record.get("serviceInfoDescr", ""),
                    "service_info_descr_long": record.get("serviceInfoDescrLong", ""),
                    "cutoff_date_time": record.get("cutoffDateTime", ""),
                    "cutoff_time": record.get("cutoffTime", ""),
                    "max_rad_time": record.get("maxRadTime", ""),
                    "max_bok_time": record.get("maxBokTime", ""),
                    "on_time": record.get("onTime", False),
                    "promise_date": record.get("promiseDate"),
                    "promise_date_days_qty": record.get("promiseDateDaysQty", 0),
                    "promise_date_hours_qty": record.get("promiseDateHoursQty", 0),
                    "in_offer": record.get("inOffer", False),
                    "services_dlvy_type": record.get("services", {}).get("dlvyType", ""),
                    "services_ack_type": record.get("services", {}).get("ackType", ""),
                    "services_totl_decl_vlue": record.get("services", {}).get("totlDeclVlue", 0),
                    "services_inv_type": record.get("services", {}).get("invType", ""),
                    "services_rad_type": record.get("services", {}).get("radType", ""),
                    "services_dlvy_type_amt": record.get("services", {}).get("dlvyTypeAmt", 0),
                    "services_dlvy_type_amt_disc": record.get("services", {}).get("dlvyTypeAmtDisc", 0),
                    "services_dlvy_type_amt_tax": record.get("services", {}).get("dlvyTypeAmtTax", 0),
                    "services_dlvy_type_amt_ret_tax": record.get("services", {}).get("dlvyTypeAmtRetTax", 0),
                    "services_inv_type_amt": record.get("services", {}).get("invTypeAmt", 0),
                    "services_inv_type_amt_disc": record.get("services", {}).get("invTypeAmtDisc", 0),
                    "services_inv_type_amt_tax": record.get("services", {}).get("invTypeAmtTax", 0),
                    "services_inv_type_amt_ret_tax": record.get("services", {}).get("invTypeAmtRetTax", 0),
                    "services_rad_type_amt": record.get("services", {}).get("radTypeAmt", 0),
                    "services_rad_type_amt_disc": record.get("services", {}).get("radTypeAmtDisc", 0),
                    "services_rad_type_amt_tax": record.get("services", {}).get("radTypeAmtTax", 0),
                    "services_rad_type_amt_ret_tax": record.get("services", {}).get("radTypeAmtRetTax", 0),
                    "amount_shp_amnt": record.get("amount", {}).get("shpAmnt", 0),
                    "amount_disc_amnt": record.get("amount", {}).get("discAmnt", 0),
                    "amount_srvc_amnt": record.get("amount", {}).get("srvcAmnt", 0),
                    "amount_sub_totl_amnt": record.get("amount", {}).get("subTotlAmnt", 0),
                    "amount_tax_amnt": record.get("amount", {}).get("taxAmnt", 0),
                    "amount_tax_ret_amnt": record.get("amount", {}).get("taxRetAmnt", 0),
                    "amount_total_amnt": record.get("amount", {}).get("totalAmnt", 0),
                }))

            data_create = {
                'client_id': quotation_data.get('clientId', ''),
                'client_dest': quotation_data.get('clientDest', ''),
                'clnt_clasif_tarif': quotation_data.get('clntClasifTarif', ''),
                'agreement_type': quotation_data.get('agreementType', ''),
                'pymt_mode': quotation_data.get('pymtMode', ''),
                'client_addr_orig_colony_name': quotation_data.get('clientAddrOrig', {}).get('colonyName', ''),
                'client_addr_orig_zip_code': quotation_data.get('clientAddrOrig', {}).get('zipCode', ''),
                'client_addr_orig_branch': quotation_data.get('clientAddrOrig', {}).get('branch', ''),
                'client_addr_orig_zone': quotation_data.get('clientAddrOrig', {}).get('zone', ''),
                'client_addr_orig_ol': quotation_data.get('clientAddrOrig', {}).get('ol', ''),
                'client_addr_dest_colony_name': quotation_data.get('clientAddrDest', {}).get('colonyName', ''),
                'client_addr_dest_zip_code': quotation_data.get('clientAddrDest', {}).get('zipCode', ''),
                'client_addr_dest_branch': quotation_data.get('clientAddrDest', {}).get('branch', ''),
                'client_addr_dest_zone': quotation_data.get('clientAddrDest', {}).get('zone', ''),
                'client_addr_dest_ol': quotation_data.get('clientAddrDest', {}).get('ol', ''),
                'quote_services': quote_services,
                'sale_order_id': self.sale_order_id.id,  # Guardar referencia a la orden
                # Datos de destino del wizard para usar al crear guia
                'dest_name': self.dest_name,
                'dest_phone': self.dest_phone,
                'dest_street': self.dest_street,
                'dest_colony': self.dest_colony,
                'dest_city': self.dest_city,
                'dest_state': self.dest_state,
                'dest_zip': self.dest_zip,
                'dest_comments': self.dest_comments,
            }

            quotation_register = self.env['px.quotation.response'].create(data_create)
            _logger.info('%s px.quotation.response creado: ID=%s', LOG_PREFIX, quotation_register.id)

            # Guardar referencia en la orden de venta
            self.sale_order_id.write({
                'px_quotation_data': json.dumps(data),
            })

            _logger.info('%s ========== FIN action_get_quotation (exito) ==========', LOG_PREFIX)

            return {
                'type': 'ir.actions.act_window',
                'name': 'Cotizacion Paquete Express',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'px.quotation.response',
                'res_id': quotation_register.id,
                'target': 'new',
                'context': {
                    'default_sale_order_id': self.sale_order_id.id,
                }
            }
        else:
            # Mostrar errores
            messages = data.get("body", {}).get("response", {}).get("messages", [])
            _logger.warning('%s Cotizacion fallida. Mensajes: %s', LOG_PREFIX, messages)

            messages_error = []
            for record in messages:
                messages_error.append((0, 0, {
                    "code": record.get("code", ""),
                    "name": record.get("description", "")
                }))

            _logger.info('%s ========== FIN action_get_quotation (error) ==========', LOG_PREFIX)

            return {
                'type': 'ir.actions.act_window',
                'name': 'Error de Cotizacion',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'px.errors.messages',
                'context': {
                    "default_name": "Error de cotizacion",
                    "default_details": messages_error
                },
                'target': 'new',
            }


class MlPxQuotationWizardLine(models.TransientModel):
    _name = 'ml.px.quotation.wizard.line'
    _description = 'Linea de Paquete para Cotizacion'

    wizard_id = fields.Many2one(
        'ml.px.quotation.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True
    )
    name = fields.Char(
        string='Descripcion',
        required=True
    )
    quantity = fields.Float(
        string='Cantidad',
        default=1.0,
        required=True
    )
    weight = fields.Float(
        string='Peso (kg)',
        digits=(16, 3),
        required=True,
        help='Peso en kilogramos'
    )
    volume = fields.Float(
        string='Volumen (m3)',
        digits=(16, 6),
        required=True,
        help='Volumen en metros cubicos'
    )
    unit_price = fields.Float(
        string='Precio Unit.',
        digits=(16, 2),
        help='Precio unitario para el valor declarado'
    )
    package_type_id = fields.Many2one(
        'px.anexo.01',
        string='Tipo Paquete',
        required=True,
        help='Tipo de paquete para Paquete Express (sobre, caja, etc.)'
    )
    is_kit = fields.Boolean(
        string='Es Kit',
        default=False,
        help='Indica si el peso/volumen fue calculado de componentes'
    )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.name
            self.weight = self.product_id.weight or 0.0
            self.volume = self.product_id.volume or 0.0
            if hasattr(self.product_id, 'x_px_shp_code'):
                self.package_type_id = self.product_id.x_px_shp_code.id
