# -*- coding: utf-8 -*-

import base64
import logging
import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MercadolibreClaimMessage(models.Model):
    _name = 'mercadolibre.claim.message'
    _description = 'Mensaje de Reclamo MercadoLibre'
    _order = 'message_date asc, id asc'
    _rec_name = 'display_name'

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

    # === PARTICIPANTES ===
    sender_role = fields.Selection([
        ('complainant', 'Comprador'),
        ('respondent', 'Vendedor'),
        ('mediator', 'Mediador ML'),
    ], string='Remitente', readonly=True)

    receiver_role = fields.Selection([
        ('complainant', 'Comprador'),
        ('respondent', 'Vendedor'),
        ('mediator', 'Mediador ML'),
    ], string='Destinatario', readonly=True)

    # === CONTENIDO ===
    message = fields.Text(
        string='Mensaje',
        readonly=True
    )
    translated_message = fields.Text(
        string='Mensaje Traducido',
        readonly=True,
        help='Solo para casos CBT (Cross Border Trade)'
    )

    # === FECHAS ===
    message_date = fields.Datetime(
        string='Fecha Envio',
        readonly=True
    )
    date_created = fields.Datetime(
        string='Fecha Creacion',
        readonly=True
    )
    date_read = fields.Datetime(
        string='Fecha Lectura',
        readonly=True
    )

    # === ESTADO Y ETAPA ===
    stage = fields.Selection([
        ('claim', 'Reclamo'),
        ('dispute', 'Mediacion'),
    ], string='Etapa', readonly=True)

    status = fields.Selection([
        ('available', 'Disponible'),
        ('moderated', 'Moderado'),
        ('rejected', 'Rechazado'),
        ('pending_translation', 'Pendiente Traduccion'),
    ], string='Estado', readonly=True)

    # === MODERACION ===
    moderation_status = fields.Selection([
        ('clean', 'Limpio'),
        ('rejected', 'Rechazado'),
        ('pending', 'Pendiente'),
        ('non_moderated', 'Sin Moderar'),
    ], string='Estado Moderacion', readonly=True)

    moderation_reason = fields.Char(
        string='Razon Moderacion',
        readonly=True,
        help='Ej: OUT_OF_PLACE_LANGUAGE'
    )

    # === ADJUNTOS ===
    attachment_ids = fields.One2many(
        'mercadolibre.claim.message.attachment',
        'message_id',
        string='Adjuntos'
    )
    attachment_count = fields.Integer(
        string='Num. Adjuntos',
        compute='_compute_attachment_count',
        store=True
    )

    # === IDENTIFICADOR UNICO ===
    hash = fields.Char(
        string='Hash Unico',
        readonly=True,
        index=True,
        help='Identificador unico para evitar duplicados'
    )

    # === CAMPOS CALCULADOS ===
    display_name = fields.Char(
        string='Nombre',
        compute='_compute_display_name'
    )
    is_from_us = fields.Boolean(
        string='Es Nuestro',
        compute='_compute_is_from_us',
        store=True,
        help='True si el mensaje fue enviado por nosotros (vendedor)'
    )
    is_unread = fields.Boolean(
        string='Sin Leer',
        compute='_compute_is_unread',
        store=True
    )
    sender_label = fields.Char(
        string='Remitente',
        compute='_compute_sender_label'
    )
    receiver_label = fields.Char(
        string='Destinatario',
        compute='_compute_receiver_label'
    )

    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        for record in self:
            record.attachment_count = len(record.attachment_ids)

    @api.depends('sender_role')
    def _compute_is_from_us(self):
        for rec in self:
            rec.is_from_us = rec.sender_role == 'respondent'

    @api.depends('date_read', 'is_from_us')
    def _compute_is_unread(self):
        for rec in self:
            rec.is_unread = not rec.is_from_us and not rec.date_read

    @api.depends('sender_role', 'message_date')
    def _compute_display_name(self):
        role_labels = {
            'complainant': 'Comprador',
            'respondent': 'Vendedor',
            'mediator': 'Mediador',
        }
        for rec in self:
            sender = role_labels.get(rec.sender_role, 'Desconocido')
            date_str = rec.message_date.strftime('%d/%m %H:%M') if rec.message_date else ''
            rec.display_name = f"[{sender}] {date_str}"

    @api.depends('sender_role')
    def _compute_sender_label(self):
        role_labels = {
            'complainant': 'Comprador',
            'respondent': 'Vendedor (Tu)',
            'mediator': 'Mediador ML',
        }
        for rec in self:
            rec.sender_label = role_labels.get(rec.sender_role, 'Desconocido')

    @api.depends('receiver_role')
    def _compute_receiver_label(self):
        role_labels = {
            'complainant': 'Comprador',
            'respondent': 'Vendedor',
            'mediator': 'Mediador ML',
        }
        for rec in self:
            rec.receiver_label = role_labels.get(rec.receiver_role, 'Desconocido')


class MercadolibreClaimMessageAttachment(models.Model):
    _name = 'mercadolibre.claim.message.attachment'
    _description = 'Adjunto de Mensaje de Reclamo'
    _order = 'date_created desc'

    message_id = fields.Many2one(
        'mercadolibre.claim.message',
        string='Mensaje',
        required=True,
        ondelete='cascade'
    )
    claim_id = fields.Many2one(
        'mercadolibre.claim',
        string='Reclamo',
        related='message_id.claim_id',
        store=True
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta',
        related='message_id.account_id',
        store=True
    )

    filename = fields.Char(
        string='Nombre Archivo ML',
        readonly=True,
        help='Nombre del archivo en MercadoLibre'
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
    date_created = fields.Datetime(
        string='Fecha Creacion',
        readonly=True
    )

    # Archivo descargado
    attachment_id = fields.Many2one(
        'ir.attachment',
        string='Archivo Odoo',
        help='Archivo descargado y almacenado en Odoo'
    )
    is_downloaded = fields.Boolean(
        string='Descargado',
        compute='_compute_is_downloaded'
    )

    display_name = fields.Char(
        compute='_compute_display_name'
    )

    @api.depends('attachment_id')
    def _compute_is_downloaded(self):
        for rec in self:
            rec.is_downloaded = bool(rec.attachment_id)

    @api.depends('original_filename', 'filename')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.original_filename or rec.filename or 'Archivo'

    def action_download(self):
        """Descarga el archivo desde MercadoLibre"""
        self.ensure_one()

        if self.attachment_id:
            # Ya descargado, abrir
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{self.attachment_id.id}?download=true',
                'target': 'new',
            }

        # Descargar y guardar
        self._download_and_attach()

        if self.attachment_id:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{self.attachment_id.id}?download=true',
                'target': 'new',
            }

    def _download_and_attach(self, post_to_chatter=True):
        """
        Descarga el archivo desde MercadoLibre y lo guarda.
        Si post_to_chatter=True, también lo adjunta al chatter del claim.
        """
        self.ensure_one()

        if self.attachment_id:
            return self.attachment_id

        claim = self.message_id.claim_id
        account = claim.account_id

        access_token = account.get_valid_token_with_retry()
        if not access_token:
            _logger.error('No se pudo obtener token para descargar archivo')
            return False

        url = f'https://api.mercadolibre.com/post-purchase/v1/claims/{claim.ml_claim_id}/attachments/{self.filename}/download'
        headers = {
            'Authorization': f'Bearer {access_token}',
        }

        try:
            response = requests.get(url, headers=headers, timeout=60)

            if response.status_code != 200:
                _logger.error('Error descargando archivo %s: %s', self.filename, response.text)
                return False

            # Crear attachment en Odoo vinculado al claim para que aparezca en el chatter
            attachment = self.env['ir.attachment'].create({
                'name': self.original_filename or self.filename,
                'type': 'binary',
                'datas': base64.b64encode(response.content),
                'mimetype': self.file_type or 'application/octet-stream',
                'res_model': 'mercadolibre.claim',
                'res_id': claim.id,
            })

            self.attachment_id = attachment.id

            # Publicar mensaje en el chatter del claim con el adjunto
            if post_to_chatter:
                sender_labels = {
                    'complainant': 'Comprador',
                    'respondent': 'Vendedor',
                    'mediator': 'Mediador ML',
                }
                sender = sender_labels.get(self.message_id.sender_role, 'Usuario')

                claim.message_post(
                    body=f'<p><strong>Archivo adjunto de {sender}:</strong> {self.original_filename or self.filename}</p>',
                    attachment_ids=[attachment.id],
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                )

            _logger.info('Archivo %s descargado y adjuntado al claim %s',
                        self.filename, claim.ml_claim_id)

            return attachment

        except requests.exceptions.RequestException as e:
            _logger.error('Error de conexion descargando archivo: %s', str(e))
            return False

    def action_download_all(self):
        """Descarga todos los adjuntos seleccionados"""
        for record in self:
            if not record.attachment_id:
                record._download_and_attach()

    def action_preview(self):
        """Vista previa del archivo (si es imagen)"""
        self.ensure_one()

        if not self.attachment_id:
            self.action_download()

        if self.attachment_id:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{self.attachment_id.id}',
                'target': 'new',
            }
