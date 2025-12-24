# -*- coding: utf-8 -*-

import base64
import json
import logging
import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MercadolibreClaimEvidence(models.Model):
    _name = 'mercadolibre.claim.evidence'
    _description = 'Evidencia de Reclamo MercadoLibre'
    _order = 'date_created desc'

    claim_id = fields.Many2one(
        'mercadolibre.claim',
        string='Reclamo',
        required=True,
        ondelete='cascade',
        index=True
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta',
        related='claim_id.account_id',
        store=True
    )

    # === TIPO DE EVIDENCIA ===
    evidence_type = fields.Selection([
        ('shipping_evidence', 'Evidencia de Envio'),
        ('handling_shipping_evidence', 'Promesa de Envio'),
    ], string='Tipo', readonly=True)

    # === DATOS DE ENVIO ===
    shipping_method = fields.Selection([
        ('mail', 'Correo'),
        ('entrusted', 'Encomienda/Transportista'),
        ('personal_delivery', 'Entrega en Mano'),
        ('email', 'Email'),
    ], string='Metodo de Envio', readonly=True)

    shipping_company_name = fields.Char(
        string='Empresa de Envio',
        readonly=True
    )
    tracking_number = fields.Char(
        string='Numero de Rastreo',
        readonly=True
    )
    destination_agency = fields.Char(
        string='Agencia Destino',
        readonly=True
    )

    # === FECHAS ===
    date_shipped = fields.Datetime(
        string='Fecha Envio',
        readonly=True
    )
    date_delivered = fields.Datetime(
        string='Fecha Entrega',
        readonly=True
    )
    handling_date = fields.Datetime(
        string='Fecha Promesa Envio',
        readonly=True,
        help='Fecha prometida de envio (para handling_shipping_evidence)'
    )
    date_created = fields.Datetime(
        string='Fecha Creacion',
        readonly=True
    )

    # === RECEPTOR ===
    receiver_name = fields.Char(
        string='Nombre Receptor',
        readonly=True
    )
    receiver_id = fields.Char(
        string='ID Receptor',
        readonly=True
    )
    receiver_email = fields.Char(
        string='Email Receptor',
        readonly=True
    )

    # === ADJUNTOS ===
    attachment_ids = fields.One2many(
        'mercadolibre.claim.evidence.attachment',
        'evidence_id',
        string='Adjuntos'
    )

    # === RAW DATA ===
    raw_data = fields.Text(
        string='Datos Crudos',
        readonly=True
    )

    display_name = fields.Char(
        compute='_compute_display_name'
    )

    @api.depends('evidence_type', 'shipping_method', 'date_shipped')
    def _compute_display_name(self):
        method_labels = {
            'mail': 'Correo',
            'entrusted': 'Transportista',
            'personal_delivery': 'Entrega Personal',
            'email': 'Email',
        }
        for rec in self:
            method = method_labels.get(rec.shipping_method, '')
            date_str = rec.date_shipped.strftime('%d/%m/%Y') if rec.date_shipped else ''
            if rec.evidence_type == 'handling_shipping_evidence':
                rec.display_name = f'Promesa Envio - {date_str}'
            else:
                rec.display_name = f'{method} - {date_str}' if method else f'Evidencia - {date_str}'

    @api.model
    def create_from_ml_data(self, data, claim):
        """Crea una evidencia desde datos de la API"""
        vals = {
            'claim_id': claim.id,
            'evidence_type': data.get('type', ''),
            'shipping_method': data.get('shipping_method', ''),
            'shipping_company_name': data.get('shipping_company_name', ''),
            'tracking_number': data.get('tracking_number', ''),
            'destination_agency': data.get('destination_agency', ''),
            'date_shipped': claim._parse_datetime(data.get('date_shipped')),
            'date_delivered': claim._parse_datetime(data.get('date_delivered')),
            'handling_date': claim._parse_datetime(data.get('handling_date')),
            'receiver_name': data.get('receiver_name', ''),
            'receiver_id': str(data.get('receiver_id', '')),
            'receiver_email': data.get('receiver_email', ''),
            'raw_data': json.dumps(data, indent=2, ensure_ascii=False),
            'date_created': fields.Datetime.now(),
        }

        evidence = self.create(vals)

        # Crear adjuntos
        for att_data in data.get('attachments', []):
            self.env['mercadolibre.claim.evidence.attachment'].create({
                'evidence_id': evidence.id,
                'filename': att_data.get('filename', ''),
                'original_filename': att_data.get('original_filename', ''),
                'file_size': att_data.get('size', 0),
                'file_type': att_data.get('type', ''),
            })

        return evidence


class MercadolibreClaimEvidenceAttachment(models.Model):
    _name = 'mercadolibre.claim.evidence.attachment'
    _description = 'Adjunto de Evidencia de Reclamo'

    evidence_id = fields.Many2one(
        'mercadolibre.claim.evidence',
        string='Evidencia',
        required=True,
        ondelete='cascade'
    )
    claim_id = fields.Many2one(
        'mercadolibre.claim',
        string='Reclamo',
        related='evidence_id.claim_id',
        store=True
    )

    filename = fields.Char(
        string='Nombre Archivo ML',
        readonly=True
    )
    original_filename = fields.Char(
        string='Nombre Original',
        readonly=True
    )
    file_size = fields.Integer(
        string='Tamano (bytes)',
        readonly=True
    )
    file_type = fields.Char(
        string='Tipo MIME',
        readonly=True
    )

    attachment_id = fields.Many2one(
        'ir.attachment',
        string='Archivo Odoo'
    )
    is_downloaded = fields.Boolean(
        string='Descargado',
        compute='_compute_is_downloaded'
    )

    @api.depends('attachment_id')
    def _compute_is_downloaded(self):
        for rec in self:
            rec.is_downloaded = bool(rec.attachment_id)

    def action_download(self):
        """Descarga el archivo desde MercadoLibre"""
        self.ensure_one()

        if self.attachment_id:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{self.attachment_id.id}?download=true',
                'target': 'new',
            }

        claim = self.evidence_id.claim_id
        account = claim.account_id

        access_token = account.get_valid_token_with_retry()
        if not access_token:
            raise UserError(_('No se pudo obtener token valido'))

        url = f'https://api.mercadolibre.com/post-purchase/v1/claims/{claim.ml_claim_id}/attachments-evidences/{self.filename}/download'
        headers = {
            'Authorization': f'Bearer {access_token}',
        }

        try:
            response = requests.get(url, headers=headers, timeout=60)

            if response.status_code != 200:
                raise UserError(_('Error descargando archivo: %s') % response.text)

            attachment = self.env['ir.attachment'].create({
                'name': self.original_filename or self.filename,
                'type': 'binary',
                'datas': base64.b64encode(response.content),
                'mimetype': self.file_type or 'application/octet-stream',
                'res_model': self._name,
                'res_id': self.id,
            })

            self.attachment_id = attachment.id

            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'new',
            }

        except requests.exceptions.RequestException as e:
            raise UserError(_('Error de conexion: %s') % str(e))
