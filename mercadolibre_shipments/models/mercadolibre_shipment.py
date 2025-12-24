# -*- coding: utf-8 -*-

import json
import logging
import requests
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class MercadolibreShipment(models.Model):
    _name = 'mercadolibre.shipment'
    _description = 'Envio MercadoLibre'
    _order = 'date_created desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Referencia',
        compute='_compute_name',
        store=True
    )

    # Relaciones principales
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        required=True,
        ondelete='restrict',
        tracking=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compania',
        related='account_id.company_id',
        store=True,
        readonly=True
    )
    order_id = fields.Many2one(
        'mercadolibre.order',
        string='Orden ML',
        ondelete='set null',
        tracking=True
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Orden de Venta',
        related='order_id.sale_order_id',
        store=True,
        readonly=True
    )

    # IDs de MercadoLibre
    ml_shipment_id = fields.Char(
        string='Shipment ID',
        required=True,
        readonly=True,
        index=True,
        help='ID del envio en MercadoLibre'
    )
    ml_order_id = fields.Char(
        string='Order ID',
        readonly=True,
        index=True,
        help='ID de la orden asociada'
    )

    # Estado del envio
    status = fields.Selection([
        ('pending', 'Pendiente'),
        ('handling', 'En Preparacion'),
        ('ready_to_ship', 'Listo para Enviar'),
        ('shipped', 'Enviado'),
        ('in_transit', 'En Transito'),
        ('out_for_delivery', 'En Reparto'),
        ('delivered', 'Entregado'),
        ('not_delivered', 'No Entregado'),
        ('returned', 'Devuelto'),
        ('cancelled', 'Cancelado'),
    ], string='Estado', default='pending', tracking=True, index=True)

    substatus = fields.Char(
        string='Subestado',
        readonly=True,
        help='Detalle del estado del envio'
    )

    status_history_ids = fields.One2many(
        'mercadolibre.shipment.status.history',
        'shipment_id',
        string='Historial de Estados'
    )

    # Tipo logistico
    logistic_type = fields.Selection([
        ('fulfillment', 'Full (Mercado Libre)'),
        ('xd_drop_off', 'Agencia/Places'),
        ('cross_docking', 'Colectas'),
        ('drop_off', 'Drop Off'),
        ('self_service', 'Flex'),
        ('custom', 'Envio Propio'),
        ('not_specified', 'A Convenir'),
    ], string='Tipo Logistico', readonly=True, tracking=True)

    shipping_mode = fields.Selection([
        ('me1', 'Mercado Envios 1'),
        ('me2', 'Mercado Envios 2'),
        ('custom', 'Personalizado'),
        ('not_specified', 'No especificado'),
    ], string='Modo de Envio', readonly=True)

    # Tracking
    tracking_number = fields.Char(
        string='Numero de Guia',
        readonly=True,
        tracking=True
    )
    tracking_method = fields.Char(
        string='Metodo de Tracking',
        readonly=True
    )
    tracking_url = fields.Char(
        string='URL de Seguimiento',
        readonly=True
    )
    service_id = fields.Char(
        string='ID Servicio',
        readonly=True
    )

    # Transportista
    carrier_name = fields.Char(
        string='Transportista',
        readonly=True
    )
    carrier_id_ml = fields.Char(
        string='ID Transportista ML',
        readonly=True
    )

    # Fechas
    date_created = fields.Datetime(
        string='Fecha Creacion',
        readonly=True
    )
    date_ready_to_ship = fields.Datetime(
        string='Listo para Enviar',
        readonly=True
    )
    date_shipped = fields.Datetime(
        string='Fecha Envio',
        readonly=True,
        tracking=True
    )
    date_delivered = fields.Datetime(
        string='Fecha Entrega',
        readonly=True,
        tracking=True
    )
    date_first_printed = fields.Datetime(
        string='Primera Impresion',
        readonly=True
    )
    estimated_delivery_date = fields.Date(
        string='Entrega Estimada',
        readonly=True
    )
    estimated_delivery_time_from = fields.Datetime(
        string='Entrega Estimada Desde',
        readonly=True
    )
    estimated_delivery_time_to = fields.Datetime(
        string='Entrega Estimada Hasta',
        readonly=True
    )

    # Costos
    shipping_cost = fields.Float(
        string='Costo Envio',
        readonly=True,
        digits=(16, 2)
    )
    base_cost = fields.Float(
        string='Costo Base',
        readonly=True,
        digits=(16, 2)
    )

    # Direccion de entrega
    receiver_name = fields.Char(
        string='Nombre Receptor',
        readonly=True
    )
    receiver_phone = fields.Char(
        string='Telefono Receptor',
        readonly=True
    )

    # Direccion
    street_name = fields.Char(
        string='Calle',
        readonly=True
    )
    street_number = fields.Char(
        string='Numero',
        readonly=True
    )
    address_line = fields.Char(
        string='Direccion Completa',
        compute='_compute_address_line',
        store=True
    )
    floor = fields.Char(
        string='Piso',
        readonly=True
    )
    apartment = fields.Char(
        string='Departamento',
        readonly=True
    )
    city = fields.Char(
        string='Ciudad',
        readonly=True
    )
    state = fields.Char(
        string='Estado/Provincia',
        readonly=True
    )
    zip_code = fields.Char(
        string='Codigo Postal',
        readonly=True
    )
    country = fields.Char(
        string='Pais',
        readonly=True
    )
    latitude = fields.Float(
        string='Latitud',
        readonly=True,
        digits=(10, 6)
    )
    longitude = fields.Float(
        string='Longitud',
        readonly=True,
        digits=(10, 6)
    )
    delivery_preference = fields.Char(
        string='Preferencia de Entrega',
        readonly=True
    )
    comments = fields.Text(
        string='Comentarios de Direccion',
        readonly=True
    )

    # Informacion del paquete
    dimensions = fields.Char(
        string='Dimensiones',
        readonly=True,
        help='Alto x Ancho x Largo en cm'
    )
    weight = fields.Float(
        string='Peso (gr)',
        readonly=True
    )

    # Etiqueta
    label_printed = fields.Boolean(
        string='Etiqueta Impresa',
        default=False,
        tracking=True
    )
    label_url = fields.Char(
        string='URL Etiqueta',
        readonly=True
    )

    # Sincronizacion
    last_sync_date = fields.Datetime(
        string='Ultima Sincronizacion',
        readonly=True
    )
    sync_error = fields.Text(
        string='Error Sincronizacion',
        readonly=True
    )

    # Datos crudos
    raw_data = fields.Text(
        string='Datos Crudos',
        readonly=True,
        help='JSON completo del envio desde MercadoLibre'
    )

    notes = fields.Text(
        string='Notas'
    )

    _sql_constraints = [
        ('ml_shipment_id_account_uniq', 'unique(ml_shipment_id, account_id)',
         'Este envio ya existe para esta cuenta.')
    ]

    @api.depends('ml_shipment_id', 'status')
    def _compute_name(self):
        for record in self:
            status_name = dict(self._fields['status'].selection).get(record.status, '')
            record.name = f'ENV-{record.ml_shipment_id or "NUEVO"}'

    @api.depends('street_name', 'street_number', 'city', 'state', 'zip_code')
    def _compute_address_line(self):
        for record in self:
            parts = []
            if record.street_name:
                addr = record.street_name
                if record.street_number:
                    addr += f' {record.street_number}'
                parts.append(addr)
            if record.city:
                parts.append(record.city)
            if record.state:
                parts.append(record.state)
            if record.zip_code:
                parts.append(f'CP {record.zip_code}')
            record.address_line = ', '.join(parts) if parts else ''

    # =========================================================================
    # SINCRONIZACION DESDE API
    # =========================================================================

    @api.model
    def sync_from_ml_data(self, data, account, order=None):
        """
        Crea o actualiza un envio desde los datos de MercadoLibre API.

        Args:
            data: dict con los datos del shipment desde la API
            account: mercadolibre.account record
            order: mercadolibre.order record (opcional)

        Returns:
            (mercadolibre.shipment record, bool is_new)
        """
        ml_shipment_id = str(data.get('id', ''))

        if not ml_shipment_id:
            _logger.error('No se encontro ID de envio en los datos')
            return False, False

        # Buscar envio existente
        existing = self.search([
            ('ml_shipment_id', '=', ml_shipment_id),
            ('account_id', '=', account.id)
        ], limit=1)

        # Extraer datos de status
        status_data = data.get('status', '')
        substatus_data = data.get('substatus', '')

        # Mapear status de ML a nuestro selection
        status = self._map_ml_status(status_data)

        # Extraer tipo logistico
        logistic_type = self._extract_logistic_type(data)

        # Extraer datos de shipping_option
        shipping_option = data.get('shipping_option', {}) or {}

        # Extraer datos del receptor
        receiver_data = data.get('receiver_address', {}) or {}
        receiver_info = receiver_data.get('receiver', {}) or {}

        # Extraer tracking info
        tracking_number = ''
        tracking_method = ''
        tracking_url = ''

        if data.get('tracking_number'):
            tracking_number = data.get('tracking_number')

        lead_time = data.get('lead_time', {}) or {}
        if lead_time.get('shipping', {}).get('tracking_number'):
            tracking_number = lead_time['shipping']['tracking_number']

        # Extraer carrier info
        carrier_name = ''
        carrier_id = ''
        if shipping_option.get('carrier', {}).get('name'):
            carrier_name = shipping_option['carrier']['name']
            carrier_id = str(shipping_option['carrier'].get('id', ''))

        # Extraer dimensiones
        dimensions = ''
        weight = 0.0
        if shipping_option.get('dimensions', {}):
            dims = shipping_option['dimensions']
            if dims.get('height') and dims.get('width') and dims.get('length'):
                dimensions = f"{dims['height']} x {dims['width']} x {dims['length']} cm"
            weight = dims.get('weight', 0.0)

        # Extraer fecha estimada de entrega
        estimated_delivery = None
        estimated_from = None
        estimated_to = None
        if lead_time.get('estimated_delivery_time', {}):
            est = lead_time['estimated_delivery_time']
            estimated_delivery = self._parse_date(est.get('date'))
            estimated_from = self._parse_datetime(est.get('from'))
            estimated_to = self._parse_datetime(est.get('to'))

        vals = {
            'account_id': account.id,
            'ml_shipment_id': ml_shipment_id,
            'ml_order_id': str(data.get('order_id', '')) if data.get('order_id') else '',
            'status': status,
            'substatus': substatus_data,
            'logistic_type': logistic_type,
            'shipping_mode': self._map_shipping_mode(data.get('mode', '')),
            'tracking_number': tracking_number,
            'tracking_method': tracking_method,
            'service_id': str(shipping_option.get('service_id', '')) if shipping_option.get('service_id') else '',
            'carrier_name': carrier_name,
            'carrier_id_ml': carrier_id,
            'date_created': self._parse_datetime(data.get('date_created')),
            'date_ready_to_ship': self._parse_datetime(data.get('date_ready_to_ship')),
            'date_shipped': self._parse_datetime(data.get('date_shipped')),
            'date_delivered': self._parse_datetime(data.get('date_delivered')),
            'date_first_printed': self._parse_datetime(data.get('date_first_printed')),
            'estimated_delivery_date': estimated_delivery,
            'estimated_delivery_time_from': estimated_from,
            'estimated_delivery_time_to': estimated_to,
            'shipping_cost': data.get('shipping_cost', 0.0) or shipping_option.get('cost', 0.0),
            'base_cost': data.get('base_cost', 0.0),
            'receiver_name': receiver_info.get('name', ''),
            'receiver_phone': receiver_info.get('phone', ''),
            'street_name': receiver_data.get('street_name', ''),
            'street_number': receiver_data.get('street_number', ''),
            'floor': receiver_data.get('floor', ''),
            'apartment': receiver_data.get('apartment', ''),
            'city': receiver_data.get('city', {}).get('name', '') if isinstance(receiver_data.get('city'), dict) else receiver_data.get('city', ''),
            'state': receiver_data.get('state', {}).get('name', '') if isinstance(receiver_data.get('state'), dict) else receiver_data.get('state', ''),
            'zip_code': receiver_data.get('zip_code', ''),
            'country': receiver_data.get('country', {}).get('name', '') if isinstance(receiver_data.get('country'), dict) else receiver_data.get('country', ''),
            'latitude': receiver_data.get('latitude', 0.0),
            'longitude': receiver_data.get('longitude', 0.0),
            'delivery_preference': receiver_data.get('delivery_preference', ''),
            'comments': receiver_data.get('comment', ''),
            'dimensions': dimensions,
            'weight': weight,
            'raw_data': json.dumps(data, indent=2, ensure_ascii=False),
            'last_sync_date': fields.Datetime.now(),
            'sync_error': False,
        }

        # Vincular con orden si se proporciona
        if order:
            vals['order_id'] = order.id

        old_status = existing.status if existing else None

        if existing:
            _logger.info('Actualizando envio existente: %s', ml_shipment_id)
            existing.write(vals)
            shipment = existing
            is_new = False
        else:
            _logger.info('Creando nuevo envio: %s', ml_shipment_id)
            shipment = self.create(vals)
            is_new = True

        # Registrar cambio de estado en historial
        if status and (is_new or old_status != status):
            shipment._create_status_history(status, substatus_data)

        return shipment, is_new

    def _map_ml_status(self, ml_status):
        """Mapea el status de ML a nuestro selection"""
        status_map = {
            'pending': 'pending',
            'handling': 'handling',
            'ready_to_ship': 'ready_to_ship',
            'shipped': 'shipped',
            'in_transit': 'in_transit',
            'out_for_delivery': 'out_for_delivery',
            'delivered': 'delivered',
            'not_delivered': 'not_delivered',
            'returned': 'returned',
            'cancelled': 'cancelled',
        }
        return status_map.get(ml_status, 'pending')

    def _map_shipping_mode(self, mode):
        """Mapea el modo de envio de ML"""
        mode_map = {
            'me1': 'me1',
            'me2': 'me2',
            'custom': 'custom',
            'not_specified': 'not_specified',
        }
        return mode_map.get(mode, 'not_specified')

    def _extract_logistic_type(self, data):
        """Extrae el tipo logistico de los datos del shipment"""
        # Intentar desde logistic_type directamente
        logistic = data.get('logistic_type', '')

        if logistic:
            logistic_map = {
                'fulfillment': 'fulfillment',
                'xd_drop_off': 'xd_drop_off',
                'cross_docking': 'cross_docking',
                'drop_off': 'drop_off',
                'self_service': 'self_service',
                'custom': 'custom',
                'not_specified': 'not_specified',
            }
            return logistic_map.get(logistic, 'not_specified')

        # Intentar inferir desde tags o shipping_option
        tags = data.get('tags', []) or []
        if 'fulfillment' in str(tags).lower():
            return 'fulfillment'

        shipping_option = data.get('shipping_option', {}) or {}
        if shipping_option.get('name', '').lower() == 'full':
            return 'fulfillment'

        return 'not_specified'

    def _parse_datetime(self, dt_string):
        """Parsea fecha/hora de MercadoLibre"""
        if not dt_string:
            return False

        try:
            if 'T' in dt_string:
                dt_string = dt_string.split('.')[0].replace('T', ' ')
                if '+' in dt_string:
                    dt_string = dt_string.split('+')[0]
                if '-' in dt_string and dt_string.count('-') > 2:
                    parts = dt_string.rsplit('-', 1)
                    dt_string = parts[0]
                return datetime.strptime(dt_string, '%Y-%m-%d %H:%M:%S')
            return datetime.strptime(dt_string, '%Y-%m-%d')
        except (ValueError, TypeError) as e:
            _logger.warning('Error parseando fecha %s: %s', dt_string, str(e))
            return False

    def _parse_date(self, date_string):
        """Parsea solo fecha de MercadoLibre"""
        if not date_string:
            return False

        try:
            if 'T' in date_string:
                date_string = date_string.split('T')[0]
            return datetime.strptime(date_string, '%Y-%m-%d').date()
        except (ValueError, TypeError) as e:
            _logger.warning('Error parseando fecha %s: %s', date_string, str(e))
            return False

    def _create_status_history(self, status, substatus=None):
        """Crea registro en historial de estados"""
        self.ensure_one()
        self.env['mercadolibre.shipment.status.history'].create({
            'shipment_id': self.id,
            'status': status,
            'substatus': substatus,
            'date': fields.Datetime.now(),
        })

    # =========================================================================
    # SINCRONIZACION MANUAL
    # =========================================================================

    def action_sync_from_api(self):
        """Sincroniza este envio desde la API de MercadoLibre"""
        self.ensure_one()

        if not self.ml_shipment_id:
            raise UserError(_('No hay ID de envio para sincronizar'))

        try:
            access_token = self.account_id.get_valid_token()
        except Exception as e:
            raise UserError(_('Error obteniendo token: %s') % str(e))

        url = f'https://api.mercadolibre.com/shipments/{self.ml_shipment_id}'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                self.sync_from_ml_data(data, self.account_id, self.order_id)
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Sincronizacion exitosa'),
                        'message': _('Envio actualizado correctamente'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                error_msg = f'Error {response.status_code}: {response.text}'
                self.write({
                    'sync_error': error_msg,
                    'last_sync_date': fields.Datetime.now(),
                })
                raise UserError(_('Error sincronizando: %s') % error_msg)

        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            self.write({
                'sync_error': error_msg,
                'last_sync_date': fields.Datetime.now(),
            })
            raise UserError(_('Error de conexion: %s') % error_msg)

    @api.model
    def sync_shipment_by_id(self, ml_shipment_id, account):
        """
        Sincroniza un envio especifico por su ID.

        Args:
            ml_shipment_id: ID del shipment en MercadoLibre
            account: mercadolibre.account record

        Returns:
            mercadolibre.shipment record o False
        """
        if not ml_shipment_id:
            return False

        try:
            access_token = account.get_valid_token()
        except Exception as e:
            _logger.error('Error obteniendo token: %s', str(e))
            return False

        url = f'https://api.mercadolibre.com/shipments/{ml_shipment_id}'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()

                # Buscar orden asociada
                order = False
                ml_order_id = str(data.get('order_id', ''))
                if ml_order_id:
                    order = self.env['mercadolibre.order'].search([
                        ('ml_order_id', '=', ml_order_id),
                        ('account_id', '=', account.id)
                    ], limit=1)

                shipment, is_new = self.sync_from_ml_data(data, account, order)

                # Actualizar logistic_type en la orden si existe
                if order and shipment and shipment.logistic_type:
                    if order.logistic_type != shipment.logistic_type:
                        order.write({'logistic_type': shipment.logistic_type})
                        _logger.info('Actualizado logistic_type de orden %s a %s',
                                   order.ml_order_id, shipment.logistic_type)

                return shipment
            else:
                _logger.error('Error obteniendo shipment %s: %s',
                            ml_shipment_id, response.text)
                return False

        except Exception as e:
            _logger.error('Error sincronizando shipment %s: %s', ml_shipment_id, str(e))
            return False

    # =========================================================================
    # ETIQUETAS
    # =========================================================================

    def action_get_label(self):
        """Obtiene la URL de la etiqueta de envio"""
        self.ensure_one()

        if not self.ml_shipment_id:
            raise UserError(_('No hay ID de envio'))

        try:
            access_token = self.account_id.get_valid_token()
        except Exception as e:
            raise UserError(_('Error obteniendo token: %s') % str(e))

        # Intentar obtener etiqueta ZPL (para impresoras termicas)
        url = f'https://api.mercadolibre.com/shipment_labels?shipment_ids={self.ml_shipment_id}&response_type=zpl2'
        headers = {
            'Authorization': f'Bearer {access_token}',
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                # Guardar URL de etiqueta PDF
                pdf_url = f'https://api.mercadolibre.com/shipment_labels?shipment_ids={self.ml_shipment_id}&response_type=pdf'
                self.write({
                    'label_url': pdf_url,
                    'label_printed': True,
                })

                return {
                    'type': 'ir.actions.act_url',
                    'url': pdf_url + f'&access_token={access_token}',
                    'target': 'new',
                }
            else:
                raise UserError(_('Error obteniendo etiqueta: %s') % response.text)

        except requests.exceptions.RequestException as e:
            raise UserError(_('Error de conexion: %s') % str(e))

    def action_download_label_pdf(self):
        """Descarga la etiqueta en formato PDF"""
        self.ensure_one()

        if not self.ml_shipment_id:
            raise UserError(_('No hay ID de envio'))

        try:
            access_token = self.account_id.get_valid_token()
        except Exception as e:
            raise UserError(_('Error obteniendo token: %s') % str(e))

        url = f'https://api.mercadolibre.com/shipment_labels?shipment_ids={self.ml_shipment_id}&response_type=pdf&access_token={access_token}'

        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }

    # =========================================================================
    # ACCIONES
    # =========================================================================

    def action_view_order(self):
        """Ver la orden ML asociada"""
        self.ensure_one()
        if not self.order_id:
            raise UserError(_('No hay orden asociada'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Orden MercadoLibre'),
            'res_model': 'mercadolibre.order',
            'res_id': self.order_id.id,
            'view_mode': 'form',
        }

    def action_view_sale_order(self):
        """Ver la orden de venta asociada"""
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError(_('No hay orden de venta asociada'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Orden de Venta'),
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
        }

    def action_view_raw_data(self):
        """Muestra los datos crudos del envio"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Datos Crudos - {self.name}',
            'res_model': 'mercadolibre.shipment',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('mercadolibre_shipments.view_mercadolibre_shipment_raw_form').id,
            'target': 'new',
        }

    def action_open_tracking_url(self):
        """Abre URL de tracking si existe"""
        self.ensure_one()

        if self.tracking_url:
            return {
                'type': 'ir.actions.act_url',
                'url': self.tracking_url,
                'target': 'new',
            }
        elif self.tracking_number:
            # Construir URL generica de MercadoLibre
            url = f'https://www.mercadolibre.com.mx/tracking/{self.ml_shipment_id}'
            return {
                'type': 'ir.actions.act_url',
                'url': url,
                'target': 'new',
            }
        else:
            raise UserError(_('No hay informacion de tracking disponible'))

    def action_view_map(self):
        """Abre ubicacion en mapa si hay coordenadas"""
        self.ensure_one()

        if self.latitude and self.longitude:
            url = f'https://www.google.com/maps?q={self.latitude},{self.longitude}'
            return {
                'type': 'ir.actions.act_url',
                'url': url,
                'target': 'new',
            }
        else:
            raise UserError(_('No hay coordenadas disponibles'))

    # =========================================================================
    # CRON
    # =========================================================================

    @api.model
    def _cron_sync_shipments(self):
        """
        Cron job para sincronizar envios pendientes.
        Sincroniza envios de ordenes que:
        - Tienen shipment_id pero no tienen registro de shipment
        - Tienen shipment no entregado (para actualizar estado)
        """
        Order = self.env['mercadolibre.order']
        accounts = self.env['mercadolibre.account'].search([
            ('state', '=', 'connected')
        ])

        for account in accounts:
            try:
                # Sincronizar ordenes sin shipment
                orders_without_shipment = Order.search([
                    ('account_id', '=', account.id),
                    ('ml_shipment_id', '!=', False),
                    ('ml_shipment_id', '!=', ''),
                    ('shipment_id', '=', False),
                ], limit=50)

                for order in orders_without_shipment:
                    try:
                        shipment = self.sync_shipment_by_id(
                            order.ml_shipment_id,
                            account
                        )
                        if shipment and not shipment.order_id:
                            shipment.order_id = order.id
                        self.env.cr.commit()
                    except Exception as e:
                        _logger.error('Error sync shipment %s: %s',
                                    order.ml_shipment_id, str(e))
                        self.env.cr.rollback()

                # Actualizar envios no entregados (para tracking)
                pending_shipments = self.search([
                    ('account_id', '=', account.id),
                    ('status', 'not in', ['delivered', 'cancelled', 'returned']),
                ], limit=100)

                for shipment in pending_shipments:
                    try:
                        shipment.action_sync_from_api()
                        self.env.cr.commit()
                    except Exception as e:
                        _logger.error('Error updating shipment %s: %s',
                                    shipment.ml_shipment_id, str(e))
                        self.env.cr.rollback()

            except Exception as e:
                _logger.error('Error in cron sync shipments for account %s: %s',
                            account.name, str(e))

        return True
