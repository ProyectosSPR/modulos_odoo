# -*- coding: utf-8 -*-
from odoo import api, models, fields
from odoo.exceptions import UserError
import requests
import json


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def validation_credential_px(self):
        """
        Valida que todas las credenciales necesarias para usar el API estén presentes,
        así como la información de la dirección de la empresa.

        :raises UserError: Si falta alguna información requerida.
        """
        if not self.env.company.x_px_uri or not self.env.company.x_px_quotation_user or not self.env.company.x_px_quotation_password or not self.env.company.x_px_quotation_type or not self.env.company.x_px_quotation_token:
            raise UserError('Algunos datos requeridos para el uso del API no estan completos.')
        
        if not self.env.company.zip:
            raise UserError('Zip de la empresa es requerido.')
        
        if not self.env.company.street:
            raise UserError('La direcccion de la empresa es requerido.')

    def validation_data_to_quotation(self, zip, state):
        """
        Valida dirección y zip de entrega.

        :param zip: Código postal de la entrega.
        :param state: Dirección de la entrega.
        :raises UserError: Si falta alguna información requerida.
        """
        self.validation_credential_px()
        if not zip:
            raise UserError('Zip de la entrega es requerido.')
        
        if not state:
            raise UserError('La direcccion de la entrega es requerido.')

    def amount_shipments_quotation(self):
        """
        Calcula el monto total de los envíos en la cotización sumando el precio de lista del producto 
        y la cantidad de la unidad de medida para cada registro en 'move_ids_without_package'.

        :return: El monto total de los envíos.
        :rtype: float
        """
        amount = sum(record.product_id.list_price + record.product_uom_qty for record in self.move_ids_without_package)
        return amount
    
    def validation_shipments_for_quotation(self, product, qty):
        """
        Valida datos requeridos del producto y la cantidad.

        :param product: Modelo del producto.
        :param qty: Cantidad.
        :raises UserError: Si falta alguna información requerida del producto o si la cantidad es menor o igual a 0.
        """
        if not product.x_px_shp_code:
                raise UserError("El tipo de paquete configurado en el producto es requerido.")

        if not product.weight:
            raise UserError("El peso configurado en el producto es requerido.")
        
        if not product.volume:
            raise UserError("El volumen configurado en el producto es requerido.")
        
        if int(qty) <= 0:
            raise UserError("La cantidad del producto debe ser mayor a 0.")
    
    def shipments_for_quotation(self, details_product):
        """
        Genera los detalles de los envíos para una cotización basada en los productos proporcionados.

        :param details_product: Una lista de diccionarios que contienen información del producto, 
                                incluyendo 'product_id' y 'qty' (cantidad).
        :type details_product: list
        :return: Una lista de diccionarios con los detalles de los envíos, incluyendo la secuencia, 
                 cantidad, código del tipo de paquete, peso y volumen.
        :rtype: list
        :raises UserError: Si falta alguna validacion falla.
        """

        details = []
        
        for idx, record in enumerate(details_product):
            product = self.env['product.product'].browse(record['product_id'])

            self.validation_shipments_for_quotation(product, record['qty'])

            details.append({
                "sequence": idx + 1, # consecutivo xd
                "quantity": int(record['qty']),
                "shpCode": product.x_px_shp_code.code, # sonbre,. caja, etc
                "weight": product.weight, # peso
                "volume": product.volume, #volumen
                # "longShip": 80, # largo
                # "widthShip": 80, # ancho
                # "highShip": 49 # alto 
            })

        return details
    
    def px_api_header(self):
        return {
            "security": {
                "user": self.env.company.x_px_quotation_user,
                "password": self.env.company.x_px_quotation_password,
                "type": self.env.company.x_px_quotation_type,
                "token": self.env.company.x_px_quotation_token,
            },
            "device": {
                "appName": "Odoo",
                "type": "Web",
                "ip": "",
                "idDevice": ""
            },
            # "target": {
            #     "module": "QUOTER",
            #     "version": "1.0",
            #     "service": "quoter",
            #     "uri": "quotes",
            #     "event": "R"
            # },
            # "output": "JSON",
            # "language": None
        }
        
    @api.model
    def px_api_quotation(self, zip, state, amount, shipmentDetail):
        self.validation_data_to_quotation(zip, state)

        url = "{0}/WsQuotePaquetexpress/api/apiQuoter/v2/getQuotation".format(self.env.company.x_px_uri)

        payload = json.dumps({
            "header": self.px_api_header(),
            "body": {
                "request": {
                    "data": {
                        "clientAddrOrig": {
                            "zipCode": self.env.company.zip,
                            "colonyName": self.env.company.street
                        },
                        "clientAddrDest": {
                            "zipCode": zip,
                            "colonyName": state
                        },
                        "services": {
                            "dlvyType": "1",
                            "ackType": "N",
                            "totlDeclVlue": amount,
                            "invType": "A",
                            "radType": "1"
                        },
                        "otherServices": {
                            "otherServices": []
                        },
                        "shipmentDetail": {
                            "shipments": shipmentDetail
                        },
                        "quoteServices": ["ALL"]
                    },
                    "objectDTO": None
                },
                "response": None
            }
        })

        headers = {
            'Content-Type': 'application/json'
        }

        response = requests.request("POST", url, headers=headers, data=payload)

        if response.status_code is not 200:
            raise UserError("Ocurrio un error al obtener una respuesta del Api.")
        
        data = json.loads(response.text)
        
        print(json.dumps(data, indent=4))

        return data


    def action_quotation(self):

        details_product = self.move_ids_without_package.mapped(lambda line: {'product_id': line.product_id.id, 'qty': line.product_uom_qty})

        details_px = self.shipments_for_quotation(details_product)


        data = self.px_api_quotation(
            self.partner_id.zip, 
            self.partner_id.state_id.display_name, 
            self.amount_shipments_quotation(), 
            details_px
        )

        quotation_data = data["body"]["response"]["data"]

        if data["body"]["response"]["success"]:
            quote_services = []
            for record in quotation_data['quotations']:
                quote_services.append((0, 0, {
                    "service_type": record["serviceType"],
                    "service_id": record["id"],
                    "service_id_ref": record["idRef"],
                    "service_name": record["serviceName"],
                    "service_info_descr": record["serviceInfoDescr"],
                    "service_info_descr_long": record["serviceInfoDescrLong"],
                    "cutoff_date_time": record["cutoffDateTime"],
                    "cutoff_time": record["cutoffTime"],
                    "max_rad_time": record["maxRadTime"],
                    "max_bok_time": record["maxBokTime"],
                    "on_time": record["onTime"],
                    "promise_date": record["promiseDate"],
                    "promise_date_days_qty": record["promiseDateDaysQty"],
                    "promise_date_hours_qty": record["promiseDateHoursQty"],
                    "in_offer": record["inOffer"],
                    # Servicios
                    "services_dlvy_type": record["services"]["dlvyType"],
                    "services_ack_type": record["services"]["ackType"],
                    "services_totl_decl_vlue": record["services"]["totlDeclVlue"],
                    "services_inv_type": record["services"]["invType"],
                    "services_rad_type": record["services"]["radType"],
                    "services_dlvy_type_amt": record["services"]["dlvyTypeAmt"],
                    "services_dlvy_type_amt_disc": record["services"]["dlvyTypeAmtDisc"],
                    "services_dlvy_type_amt_tax": record["services"]["dlvyTypeAmtTax"],
                    "services_dlvy_type_amt_ret_tax": record["services"]["dlvyTypeAmtRetTax"],
                    "services_inv_type_amt": record["services"]["invTypeAmt"],
                    "services_inv_type_amt_disc": record["services"]["invTypeAmtDisc"],
                    "services_inv_type_amt_tax": record["services"]["invTypeAmtTax"],
                    "services_inv_type_amt_ret_tax": record["services"]["invTypeAmtRetTax"],
                    "services_rad_type_amt": record["services"]["radTypeAmt"],
                    "services_rad_type_amt_disc": record["services"]["radTypeAmtDisc"],
                    "services_rad_type_amt_tax": record["services"]["radTypeAmtTax"],
                    "services_rad_type_amt_ret_tax": record["services"]["radTypeAmtRetTax"],
                    # Montos
                    "amount_shp_amnt": record["amount"]["shpAmnt"],
                    "amount_disc_amnt": record["amount"]["discAmnt"],
                    "amount_srvc_amnt": record["amount"]["srvcAmnt"],
                    "amount_sub_totl_amnt": record["amount"]["subTotlAmnt"],
                    "amount_tax_amnt": record["amount"]["taxAmnt"],
                    "amount_tax_ret_amnt": record["amount"]["taxRetAmnt"],
                    "amount_total_amnt": record["amount"]["totalAmnt"]
                }))


            data_create = {
                'client_id': quotation_data['clientId'],
                'client_dest': quotation_data['clientDest'],
                'clnt_clasif_tarif': quotation_data['clntClasifTarif'],
                'agreement_type': quotation_data['agreementType'],
                'pymt_mode': quotation_data['pymtMode'],
                'client_addr_orig_colony_name': quotation_data['clientAddrOrig']['colonyName'],
                'client_addr_orig_zip_code': quotation_data['clientAddrOrig']['zipCode'],
                'client_addr_orig_branch': quotation_data['clientAddrOrig']['branch'],
                'client_addr_orig_zone': quotation_data['clientAddrOrig']['zone'],
                'client_addr_orig_ol': quotation_data['clientAddrOrig']['ol'],
                'client_addr_dest_colony_name': quotation_data['clientAddrDest']['colonyName'],
                'client_addr_dest_zip_code': quotation_data['clientAddrDest']['zipCode'],
                'client_addr_dest_branch': quotation_data['clientAddrDest']['branch'],
                'client_addr_dest_zone': quotation_data['clientAddrDest']['zone'],
                'client_addr_dest_ol': quotation_data['clientAddrDest']['ol'],
                'quote_services': quote_services
            }

            quotation_register = self.env['px.quotation.response'].create(data_create)

            return {
                'type': 'ir.actions.act_window',
                'name': 'Cotización',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'px.quotation.response',
                'domain': [],
                'res_id': quotation_register.id,
                'context': {},
                'target': 'new'
            }
        else:
            messages_error = []
            for record in data["body"]["response"]["messages"]:
                messages_error.append((0, 0, {
                    "code": record["code"],
                    "name": record["description"]
                }))

            return {
                'type': 'ir.actions.act_window',
                'name': 'Cotización',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'px.errors.messages',
                'context': {
                    "default_name": "Error de cotización",
                    "default_details": messages_error
                },
                'target': 'new'
            }
        
    @api.model
    def px_api_generate_shipment(self, order):
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info('[PX_API_GUIA] ========== INICIO px_api_generate_shipment ==========')
        _logger.info('[PX_API_GUIA] Orden: %s', order.name)

        url = "{0}/RadRestFul/api/rad/v1/guia".format(self.env.company.x_px_uri)
        _logger.info('[PX_API_GUIA] URL: %s', url)

        payload = json.dumps({
            "header": self.px_api_header(),
            "body": {
                "request":{
                    "data":[
                        {
                            "billRad":"REQUEST",
                            "billClntId":"22081002",
                            "pymtMode":"PAID",
                            "pymtType":"C",
                            "comt":"Na",
                            "radGuiaAddrDTOList":[
                                {
                                    "addrLin1":"MEXICO",
                                    "addrLin3":" ",
                                    "addrLin4":" ",
                                    "addrLin5":" ",
                                    "addrLin6": self.env.company.state_id.display_name,
                                    "zipCode": self.env.company.zip,
                                    "strtName": self.env.company.street,
                                    "drnr": self.env.company.street2,
                                    "phno1": self.env.company.phone,
                                    "clntName":"CLIENTE ORIGEN",
                                    "email": self.env.company.email,
                                    "contacto": "CONTACTO QUIEN ENTREGA",
                                    "addrType": "ORIGIN"
                                },
                                {
                                    "addrLin1":"MEXICO",
                                    "addrLin3":" ",
                                    "addrLin4":" ",
                                    "addrLin5":" ",
                                    "addrLin6": order.partner_shipping_id.state_id.display_name,
                                    "zipCode": order.partner_shipping_id.zip,
                                    "strtName": order.partner_shipping_id.street,
                                    "drnr": order.partner_shipping_id.street2,
                                    "phno1": order.partner_shipping_id.phone,
                                    "clntName": order.partner_shipping_id.name,
                                    "email": order.partner_shipping_id.email,
                                    "contacto": order.partner_shipping_id.name,
                                    "addrType":"DESTINATION"
                                }
                            ],
                            "radSrvcItemDTOList":[
                                {
                                    "srvcId":"PACKETS",
                                    "productIdSAT":"01010101",
                                    "weight":"1",
                                    "volL":"35",
                                    "volW":"24",
                                    "volH":"14",
                                    "cont":"CONTENIDO CAJA",
                                    "qunt":"1"
                                }
                            ],
                            "listSrvcItemDTO":[
                                {
                                    "srvcId":"EAD",
                                    "value1":""
                                },
                                {
                                    "srvcId":"RAD",
                                    "value1":""
                                }
                                                                
                            ],
                            "typeSrvcId": order.partner_shipping_id.ref.split('#')[1] if order.partner_shipping_id.ref and '#' in order.partner_shipping_id.ref else 'STANDARD',
                            # "listRefs":[
                            #     {
                            #         "grGuiaRefr":"TLALPAN"
                            #     }
                            # ]
                        }
                    ],
                    "objectDTO": None
                },
                "response":None
            }
        })

        headers = {
            'Content-Type': 'application/json'
        }

        _logger.info('[PX_API_GUIA] Enviando request a API...')
        _logger.info('[PX_API_GUIA] Destino: %s, CP: %s',
                    order.partner_shipping_id.name if order.partner_shipping_id else 'N/A',
                    order.partner_shipping_id.zip if order.partner_shipping_id else 'N/A')

        response = requests.request("POST", url, headers=headers, data=payload)

        _logger.info('[PX_API_GUIA] Status Code: %s', response.status_code)

        if response.status_code != 200:
            _logger.error('[PX_API_GUIA] Error HTTP: %s - %s', response.status_code, response.text)
            raise UserError("Error al obtener respuesta del API. Status: %s" % response.status_code)

        data = json.loads(response.text)

        _logger.info('[PX_API_GUIA] Respuesta: success=%s',
                    data.get("body", {}).get("response", {}).get("success"))
        _logger.info('[PX_API_GUIA] ========== FIN px_api_generate_shipment ==========')

        return data

    def action_px_api_generate_shipment(self, order_id):
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info('[PX_SHIPMENT] ========== INICIO action_px_api_generate_shipment ==========')
        _logger.info('[PX_SHIPMENT] order_id: %s', order_id)

        order = self.env['sale.order'].sudo().browse(order_id)
        _logger.info('[PX_SHIPMENT] Orden: %s', order.name)
        _logger.info('[PX_SHIPMENT] Partner envio: %s', order.partner_shipping_id.name if order.partner_shipping_id else 'NINGUNO')

        try:
            _logger.info('[PX_SHIPMENT] Llamando px_api_generate_shipment...')
            data = self.px_api_generate_shipment(order)
            _logger.info('[PX_SHIPMENT] Respuesta API recibida')
        except Exception as e:
            _logger.error('[PX_SHIPMENT] Error en API: %s', str(e), exc_info=True)
            raise

        generate_shipment_data = data["body"]["response"]
        _logger.info('[PX_SHIPMENT] success: %s', generate_shipment_data.get("success"))

        if generate_shipment_data["success"]:
            _logger.info('[PX_SHIPMENT] Creando px.shipment...')
            order.px_shipment_data = str(data)

            shipment = self.env['px.shipment'].create({
                "data": generate_shipment_data.get("data"),
                "object_dto": generate_shipment_data.get("objectDTO"),
                "credit_amnt": generate_shipment_data.get("additionalData", {}).get("creditAmnt", 0),
                "sub_totl_amnt": generate_shipment_data.get("additionalData", {}).get("subTotlAmnt", 0),
                "total_amnt": generate_shipment_data.get("additionalData", {}).get("totalAmnt", 0),
                "sale_order_id": order.id
            })
            _logger.info('[PX_SHIPMENT] px.shipment creado: ID=%s', shipment.id)
            _logger.info('[PX_SHIPMENT] ========== FIN (exito) ==========')
            return shipment
        else:
            _logger.warning('[PX_SHIPMENT] API retorno error: %s', generate_shipment_data)
            messages = generate_shipment_data.get("messages", [])
            error_msg = ', '.join([m.get('description', str(m)) for m in messages]) if messages else 'Error desconocido'
            _logger.info('[PX_SHIPMENT] ========== FIN (error) ==========')
            raise UserError(f'Error al crear guia: {error_msg}')