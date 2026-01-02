# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

LOG_PREFIX = '[ML_PX_QUOTATION]'


class PxQuotationResponseExtend(models.TransientModel):
    _inherit = 'px.quotation.response'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Orden de Venta',
        help='Orden de venta asociada a esta cotizacion'
    )

    # Datos de destino guardados del wizard
    dest_name = fields.Char(string='Nombre Receptor')
    dest_phone = fields.Char(string='Telefono')
    dest_street = fields.Char(string='Calle')
    dest_colony = fields.Char(string='Colonia')
    dest_city = fields.Char(string='Ciudad')
    dest_state = fields.Char(string='Estado')
    dest_zip = fields.Char(string='CP')
    dest_comments = fields.Text(string='Referencias')


class PxQuotationResponseServiceExtend(models.TransientModel):
    _inherit = 'px.quotation.response.service'

    def action_create_shipment(self):
        self.ensure_one()
        _logger.info('%s ========== INICIO action_create_shipment ==========', LOG_PREFIX)
        _logger.info('%s Servicio: %s - %s (Total: %s)', LOG_PREFIX,
                    self.service_type, self.service_name, self.amount_total_amnt)

        quotation_response = self.px_quotation_response_id
        sale_order_id = quotation_response.sale_order_id.id if quotation_response.sale_order_id else self._context.get('default_sale_order_id')

        _logger.info('%s sale_order_id: %s', LOG_PREFIX, sale_order_id)

        if not sale_order_id:
            raise UserError(_('No se encontro la orden de venta. Vuelva a cotizar.'))

        sale_order = self.env['sale.order'].browse(sale_order_id)
        _logger.info('%s Orden: %s', LOG_PREFIX, sale_order.name)

        # Guardar servicio seleccionado
        sale_order.write({
            'px_service_data': f'{self.service_type}|{self.service_id}|{self.service_name}',
        })

        # Obtener datos de destino de ML shipment o del contexto
        shipping_data = self._get_ml_shipping_data(sale_order, quotation_response)
        _logger.info('%s Datos envio: %s', LOG_PREFIX, shipping_data)

        try:
            _logger.info('%s Llamando action_ml_px_generate_shipment...', LOG_PREFIX)
            result = self.action_ml_px_generate_shipment(sale_order, shipping_data)
            _logger.info('%s ========== FIN action_create_shipment ==========', LOG_PREFIX)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Guia Creada'),
                    'message': _('La guia de Paquete Express ha sido creada.'),
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }
        except Exception as e:
            _logger.error('%s Error: %s', LOG_PREFIX, str(e), exc_info=True)
            raise UserError(_('Error al crear guia: %s') % str(e))

    def _get_ml_shipping_data(self, sale_order, quotation_response):
        """Obtiene los datos de envio desde ML shipment o quotation_response"""
        _logger.info('%s Obteniendo datos de envio...', LOG_PREFIX)

        # Primero intentar desde quotation_response si tiene los datos guardados
        if quotation_response.dest_name:
            _logger.info('%s Usando datos de quotation_response', LOG_PREFIX)
            return {
                'name': quotation_response.dest_name or 'CLIENTE',
                'phone': quotation_response.dest_phone or '0000000000',
                'street': quotation_response.dest_street or '',
                'street2': quotation_response.dest_colony or '',
                'city': quotation_response.dest_city or '',
                'state': quotation_response.dest_state or '',
                'zip': quotation_response.dest_zip or '',
                'comments': quotation_response.dest_comments or '',
            }

        # Si es orden ML, buscar en mercadolibre.shipment
        if sale_order.ml_order_id:
            _logger.info('%s Buscando ML shipment para ml_order_id=%s', LOG_PREFIX, sale_order.ml_order_id)
            ml_order = self.env['mercadolibre.order'].search([
                ('ml_order_id', '=', sale_order.ml_order_id)
            ], limit=1)

            if ml_order and ml_order.ml_shipment_id:
                ml_shipment = self.env['mercadolibre.shipment'].search([
                    ('ml_shipment_id', '=', ml_order.ml_shipment_id)
                ], limit=1)

                if ml_shipment:
                    _logger.info('%s Usando datos de ML shipment ID=%s', LOG_PREFIX, ml_shipment.id)
                    return {
                        'name': ml_shipment.receiver_name or 'CLIENTE',
                        'phone': ml_shipment.receiver_phone or '0000000000',
                        'street': f"{ml_shipment.street_name or ''} {ml_shipment.street_number or ''}".strip(),
                        'street2': '',
                        'city': ml_shipment.city or '',
                        'state': ml_shipment.state or '',
                        'zip': ml_shipment.zip_code or '',
                        'comments': ml_shipment.comments or '',
                    }

        # Fallback a partner_shipping_id
        partner = sale_order.partner_shipping_id
        if partner:
            _logger.info('%s Usando datos de partner_shipping_id', LOG_PREFIX)
            return {
                'name': partner.name or 'CLIENTE',
                'phone': partner.phone or partner.mobile or '0000000000',
                'street': partner.street or '',
                'street2': partner.street2 or '',
                'city': partner.city or '',
                'state': partner.state_id.name if partner.state_id else '',
                'zip': partner.zip or '',
                'comments': '',
            }

        raise UserError(_('No se encontraron datos de direccion de envio.'))

    def action_ml_px_generate_shipment(self, order, shipping_data):
        """Genera la guia usando los datos de envio proporcionados"""
        import json
        import requests

        _logger.info('%s ========== INICIO action_ml_px_generate_shipment ==========', LOG_PREFIX)

        company = self.env.company
        url = "{0}/RadRestFul/api/rad/v1/guia".format(company.x_px_uri)
        _logger.info('%s URL: %s', LOG_PREFIX, url)

        # Construir header usando metodo existente
        StockPicking = self.env['stock.picking']
        header = StockPicking.px_api_header()

        payload = json.dumps({
            "header": header,
            "body": {
                "request": {
                    "data": [{
                        "billRad": "REQUEST",
                        "billClntId": "22081002",
                        "pymtMode": "PAID",
                        "pymtType": "C",
                        "comt": shipping_data.get('comments') or "Orden MercadoLibre",
                        "radGuiaAddrDTOList": [
                            {
                                "addrLin1": "MEXICO",
                                "addrLin3": " ",
                                "addrLin4": " ",
                                "addrLin5": " ",
                                "addrLin6": company.state_id.display_name if company.state_id else "",
                                "zipCode": company.zip or "",
                                "strtName": company.street or "",
                                "drnr": company.street2 or "",
                                "phno1": company.phone or "0000000000",
                                "clntName": company.name or "REMITENTE",
                                "email": company.email or "",
                                "contacto": "CONTACTO ORIGEN",
                                "addrType": "ORIGIN"
                            },
                            {
                                "addrLin1": "MEXICO",
                                "addrLin3": " ",
                                "addrLin4": " ",
                                "addrLin5": " ",
                                "addrLin6": shipping_data.get('state') or "",
                                "zipCode": shipping_data.get('zip') or "",
                                "strtName": shipping_data.get('street') or "",
                                "drnr": shipping_data.get('street2') or "",
                                "phno1": shipping_data.get('phone') or "0000000000",
                                "clntName": shipping_data.get('name') or "DESTINATARIO",
                                "email": "",
                                "contacto": shipping_data.get('name') or "DESTINATARIO",
                                "addrType": "DESTINATION"
                            }
                        ],
                        "radSrvcItemDTOList": [{
                            "srvcId": "PACKETS",
                            "productIdSAT": "01010101",
                            "weight": "1",
                            "volL": "35",
                            "volW": "24",
                            "volH": "14",
                            "cont": "CONTENIDO PAQUETE",
                            "qunt": "1"
                        }],
                        "listSrvcItemDTO": [
                            {"srvcId": "EAD", "value1": ""},
                            {"srvcId": "RAD", "value1": ""}
                        ],
                        "typeSrvcId": self.service_type or "STANDARD",
                    }],
                    "objectDTO": None
                },
                "response": None
            }
        })

        _logger.info('%s Enviando request...', LOG_PREFIX)
        _logger.info('%s Destino: %s, CP: %s, Tel: %s',
                    LOG_PREFIX, shipping_data.get('name'), shipping_data.get('zip'), shipping_data.get('phone'))

        headers = {'Content-Type': 'application/json'}
        response = requests.request("POST", url, headers=headers, data=payload)

        _logger.info('%s Status Code: %s', LOG_PREFIX, response.status_code)

        if response.status_code != 200:
            _logger.error('%s Error HTTP: %s', LOG_PREFIX, response.text)
            raise UserError("Error en API Paquete Express. Status: %s" % response.status_code)

        data = json.loads(response.text)
        generate_shipment_data = data.get("body", {}).get("response", {})

        _logger.info('%s success: %s', LOG_PREFIX, generate_shipment_data.get("success"))

        if generate_shipment_data.get("success"):
            _logger.info('%s Creando px.shipment...', LOG_PREFIX)
            order.px_shipment_data = str(data)

            shipment = self.env['px.shipment'].create({
                "data": generate_shipment_data.get("data"),
                "object_dto": generate_shipment_data.get("objectDTO"),
                "credit_amnt": generate_shipment_data.get("additionalData", {}).get("creditAmnt", 0),
                "sub_totl_amnt": generate_shipment_data.get("additionalData", {}).get("subTotlAmnt", 0),
                "total_amnt": generate_shipment_data.get("additionalData", {}).get("totalAmnt", 0),
                "sale_order_id": order.id
            })
            _logger.info('%s px.shipment creado: ID=%s', LOG_PREFIX, shipment.id)
            _logger.info('%s ========== FIN action_ml_px_generate_shipment ==========', LOG_PREFIX)
            return shipment
        else:
            messages = generate_shipment_data.get("messages", [])
            error_msg = ', '.join([m.get('description', str(m)) for m in messages]) if messages else 'Error desconocido'
            _logger.warning('%s API error: %s', LOG_PREFIX, error_msg)
            raise UserError(f'Error al crear guia: {error_msg}')
