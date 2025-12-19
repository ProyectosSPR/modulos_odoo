# -*- coding: utf-8 -*-

import base64
import logging
import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class MercadolibreClaimSendMessageWizard(models.TransientModel):
    _name = 'mercadolibre.claim.send.message.wizard'
    _description = 'Wizard Enviar Mensaje a Reclamo'

    claim_id = fields.Many2one(
        'mercadolibre.claim',
        string='Reclamo',
        required=True,
        default=lambda self: self.env.context.get('default_claim_id')
    )

    claim_stage = fields.Selection(
        related='claim_id.stage',
        readonly=True
    )
    claim_status = fields.Selection(
        related='claim_id.status',
        readonly=True
    )

    receiver_role = fields.Selection([
        ('complainant', 'Comprador'),
        ('mediator', 'Mediador ML'),
    ], string='Destinatario', required=True)

    message = fields.Text(
        string='Mensaje',
        required=True,
        help='Mensaje a enviar. Maximo 2000 caracteres.'
    )

    attachment_ids = fields.Many2many(
        'ir.attachment',
        'mercadolibre_claim_send_msg_attachment_rel',
        'wizard_id',
        'attachment_id',
        string='Adjuntos',
        help='Maximo 5MB por archivo. Formatos: JPG, PNG, PDF'
    )

    info_message = fields.Html(
        string='Informacion',
        compute='_compute_info_message'
    )

    @api.depends('claim_stage')
    def _compute_info_message(self):
        for rec in self:
            if rec.claim_stage == 'claim':
                rec.info_message = '''
                <div class="alert alert-info">
                    <strong>Etapa: Reclamo</strong><br/>
                    Puede enviar mensajes directamente al comprador.
                </div>
                '''
            elif rec.claim_stage == 'dispute':
                rec.info_message = '''
                <div class="alert alert-warning">
                    <strong>Etapa: Mediacion</strong><br/>
                    Solo puede enviar mensajes al mediador de MercadoLibre.
                    La comunicacion directa con el comprador no esta disponible.
                </div>
                '''
            else:
                rec.info_message = ''

    @api.onchange('claim_stage')
    def _onchange_claim_stage(self):
        """Ajusta destinatario segun etapa"""
        if self.claim_stage == 'dispute':
            self.receiver_role = 'mediator'
        elif self.claim_stage == 'claim':
            self.receiver_role = 'complainant'

    @api.constrains('message')
    def _check_message_length(self):
        for rec in self:
            if rec.message and len(rec.message) > 2000:
                raise ValidationError(_('El mensaje no puede exceder 2000 caracteres.'))

    @api.constrains('attachment_ids')
    def _check_attachments(self):
        for rec in self:
            for attachment in rec.attachment_ids:
                # Verificar tamano (5MB max)
                if attachment.file_size > 5 * 1024 * 1024:
                    raise ValidationError(
                        _('El archivo "%s" excede el tamano maximo de 5MB.') % attachment.name
                    )
                # Verificar tipo
                allowed_types = ['image/jpeg', 'image/png', 'application/pdf']
                if attachment.mimetype not in allowed_types:
                    raise ValidationError(
                        _('El archivo "%s" no es un tipo permitido. Use JPG, PNG o PDF.') % attachment.name
                    )

    def action_send(self):
        """Envia el mensaje a MercadoLibre"""
        self.ensure_one()

        claim = self.claim_id
        account = claim.account_id

        # Validar que el claim este abierto
        if claim.status != 'opened':
            raise UserError(_('No se pueden enviar mensajes a un reclamo cerrado.'))

        # Validar destinatario segun etapa
        if claim.stage == 'dispute' and self.receiver_role != 'mediator':
            raise UserError(_('En etapa de mediacion solo puede enviar mensajes al mediador.'))

        access_token = account.get_valid_token_with_retry()
        if not access_token:
            raise UserError(_('No se pudo obtener token valido'))

        # 1. Subir adjuntos primero (si hay)
        uploaded_filenames = []
        for attachment in self.attachment_ids:
            filename = self._upload_attachment(claim, access_token, attachment)
            if filename:
                uploaded_filenames.append(filename)
            else:
                raise UserError(_('Error subiendo archivo: %s') % attachment.name)

        # 2. Enviar mensaje
        url = f'https://api.mercadolibre.com/post-purchase/v1/claims/{claim.ml_claim_id}/actions/send-message'

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        body = {
            'receiver_role': self.receiver_role,
            'message': self.message,
        }

        if uploaded_filenames:
            body['attachments'] = uploaded_filenames

        try:
            response = requests.post(url, headers=headers, json=body, timeout=30)

            if response.status_code not in (200, 201):
                error_data = response.json() if response.text else {}
                error_msg = error_data.get('message', response.text)
                raise UserError(_('Error enviando mensaje: %s') % error_msg)

        except requests.exceptions.RequestException as e:
            raise UserError(_('Error de conexion: %s') % str(e))

        # 3. Registrar en el chatter del claim
        receiver_label = 'Comprador' if self.receiver_role == 'complainant' else 'Mediador ML'
        attachments_info = f'<br/><small>{len(uploaded_filenames)} adjunto(s)</small>' if uploaded_filenames else ''

        claim.message_post(
            body=f'''
            <p><strong>Mensaje enviado a {receiver_label}:</strong></p>
            <blockquote>{self.message}</blockquote>
            {attachments_info}
            ''',
            message_type='comment',
        )

        # 4. Registrar en action log
        claim._log_action(
            f'send_message_to_{self.receiver_role}',
            f'Mensaje enviado a {receiver_label}'
        )

        # 5. Refrescar mensajes
        claim._sync_messages()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Mensaje enviado correctamente'),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def _upload_attachment(self, claim, access_token, attachment):
        """Sube un adjunto a MercadoLibre y retorna el filename"""
        url = f'https://api.mercadolibre.com/post-purchase/v1/claims/{claim.ml_claim_id}/attachments'

        headers = {
            'Authorization': f'Bearer {access_token}',
        }

        # Preparar archivo
        file_content = base64.b64decode(attachment.datas)
        files = {
            'file': (attachment.name, file_content, attachment.mimetype)
        }

        try:
            response = requests.post(url, headers=headers, files=files, timeout=60)

            if response.status_code == 200:
                data = response.json()
                filename = data.get('filename')
                _logger.info('Archivo subido exitosamente: %s -> %s', attachment.name, filename)
                return filename
            else:
                _logger.error('Error subiendo adjunto: %s - %s', response.status_code, response.text)
                return None

        except requests.exceptions.RequestException as e:
            _logger.error('Error de conexion subiendo adjunto: %s', str(e))
            return None
