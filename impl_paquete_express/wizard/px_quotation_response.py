# -*- coding: utf-8 -*-

from odoo import models, fields


class PxQuotationResponse(models.TransientModel):
    _name = 'px.quotation.response'

    client_id = fields.Char(string='ID de Cliente')
    client_dest = fields.Char(string='Destino del Cliente')
    clnt_clasif_tarif = fields.Char(string='Clasificación Tarifaria del Cliente')
    agreement_type = fields.Char(string='Tipo de Acuerdo')
    pymt_mode = fields.Char(string='Modo de Pago')

    client_addr_orig_colony_name = fields.Char(string='Nombre de la Colonia de Origen')
    client_addr_orig_zip_code = fields.Char(string='Código Postal de Origen')
    client_addr_orig_branch = fields.Char(string='Sucursal de Origen')
    client_addr_orig_zone = fields.Char(string='Zona de Origen')
    client_addr_orig_ol = fields.Char(string='OL de Origen')

    client_addr_dest_colony_name = fields.Char(string='Nombre de la Colonia de Destino')
    client_addr_dest_zip_code = fields.Char(string='Código Postal de Destino')
    client_addr_dest_branch = fields.Char(string='Sucursal de Destino')
    client_addr_dest_zone = fields.Char(string='Zona de Destino')
    client_addr_dest_ol = fields.Char(string='OL de Destino')

    quote_services = fields.One2many('px.quotation.response.service', 'px_quotation_response_id',string='Servicios')



class PxQuotationResponseService(models.TransientModel):
    _name = 'px.quotation.response.service'
    _description = 'Quotation Service'

    px_quotation_response_id = fields.Many2one('px.quotation.response', string='Respuesta cotizacion', ondelete='cascade', index=True)
    service_type = fields.Char(string='Tipo de Servicio')
    service_id = fields.Char(string='ID de Servicio')
    service_id_ref = fields.Char(string='ID de Referencia de Servicio')
    service_name = fields.Char(string='Nombre de Servicio')
    service_info_descr = fields.Char(string='Descripción de Información del Servicio')
    service_info_descr_long = fields.Char(string='Descripción Larga de Información del Servicio')
    cutoff_date_time = fields.Char(string='Fecha y Hora de Corte')
    cutoff_time = fields.Char(string='Hora de Corte')
    max_rad_time = fields.Char(string='Tiempo Máximo de RAD')
    max_bok_time = fields.Char(string='Tiempo Máximo de BOK')
    on_time = fields.Boolean(string='A Tiempo')
    promise_date = fields.Date(string='Fecha Prometida')
    promise_date_days_qty = fields.Integer(string='Cantidad de Días para la Fecha Prometida')
    promise_date_hours_qty = fields.Integer(string='Cantidad de Horas para la Fecha Prometida')
    in_offer = fields.Boolean(string='En Oferta')

    # Service
    services_dlvy_type = fields.Char(string='Tipo de Entrega')
    services_ack_type = fields.Char(string='Tipo de Acuse de Recibo')
    services_totl_decl_vlue = fields.Float(string='Valor Total Declarado')
    services_inv_type = fields.Char(string='Tipo de Factura')
    services_rad_type = fields.Char(string='Tipo de RAD')
    services_dlvy_type_amt = fields.Float(string='Monto de Tipo de Entrega')
    services_dlvy_type_amt_disc = fields.Float(string='Descuento del Monto de Tipo de Entrega')
    services_dlvy_type_amt_tax = fields.Float(string='Impuesto del Monto de Tipo de Entrega')
    services_dlvy_type_amt_ret_tax = fields.Float(string='Impuesto Retenido del Monto de Tipo de Entrega')
    services_inv_type_amt = fields.Float(string='Monto de Tipo de Factura')
    services_inv_type_amt_disc = fields.Float(string='Descuento del Monto de Tipo de Factura')
    services_inv_type_amt_tax = fields.Float(string='Impuesto del Monto de Tipo de Factura')
    services_inv_type_amt_ret_tax = fields.Float(string='Impuesto Retenido del Monto de Tipo de Factura')
    services_rad_type_amt = fields.Float(string='Monto de Tipo de RAD')
    services_rad_type_amt_disc = fields.Float(string='Descuento del Monto de Tipo de RAD')
    services_rad_type_amt_tax = fields.Float(string='Impuesto del Monto de Tipo de RAD')
    services_rad_type_amt_ret_tax = fields.Float(string='Impuesto Retenido del Monto de Tipo de RAD')

    # Amount
    amount_shp_amnt = fields.Float(string='Monto de Envío')
    amount_disc_amnt = fields.Float(string='Monto de Descuento')
    amount_srvc_amnt = fields.Float(string='Monto de Servicio')
    amount_sub_totl_amnt = fields.Float(string='Monto Subtotal')
    amount_tax_amnt = fields.Float(string='Monto de Impuesto')
    amount_tax_ret_amnt = fields.Float(string='Monto de Impuesto Retenido')
    amount_total_amnt = fields.Float(string='Monto Total')
