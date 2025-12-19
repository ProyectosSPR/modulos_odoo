# -*- coding: utf-8 -*-

import json
import time
import logging
import requests
import pytz
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)

MEXICO_TZ = pytz.timezone('America/Mexico_City')


class MercadolibreClaim(models.Model):
    _name = 'mercadolibre.claim'
    _description = 'Reclamo MercadoLibre'
    _order = 'date_created desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # === IDENTIFICADORES ===
    name = fields.Char(
        string='Referencia',
        compute='_compute_name',
        store=True
    )
    ml_claim_id = fields.Char(
        string='Claim ID',
        required=True,
        readonly=True,
        index=True,
        help='ID del reclamo en MercadoLibre'
    )
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

    # === RECURSO ASOCIADO ===
    resource = fields.Selection([
        ('order', 'Orden'),
        ('payment', 'Pago'),
        ('shipment', 'Envio'),
        ('purchase', 'Compra'),
    ], string='Tipo Recurso', readonly=True)

    resource_id = fields.Char(
        string='ID Recurso',
        readonly=True,
        index=True,
        help='ID del recurso asociado (order_id, payment_id, etc.)'
    )

    # Relaciones con modelos Odoo
    ml_payment_id = fields.Many2one(
        'mercadolibre.payment',
        string='Pago ML',
        help='Pago de MercadoLibre asociado a este reclamo'
    )
    ml_order_id = fields.Char(
        string='Order ID ML',
        readonly=True,
        index=True
    )

    # === ESTADOS ===
    status = fields.Selection([
        ('opened', 'Abierto'),
        ('closed', 'Cerrado'),
    ], string='Estado', readonly=True, tracking=True, index=True)

    stage = fields.Selection([
        ('claim', 'Reclamo'),
        ('dispute', 'Mediacion/Disputa'),
        ('recontact', 'Recontacto'),
        ('stale', 'Estancado'),
        ('none', 'Sin Etapa'),
    ], string='Etapa', readonly=True, tracking=True)

    type = fields.Selection([
        ('mediations', 'Mediacion'),
        ('returns', 'Devolucion'),
        ('fulfillment', 'Fulfillment'),
        ('ml_case', 'Caso ML'),
        ('cancel_sale', 'Cancelacion Venta'),
        ('cancel_purchase', 'Cancelacion Compra'),
        ('change', 'Cambio'),
        ('service', 'Servicio'),
    ], string='Tipo de Reclamo', readonly=True)

    # === MOTIVO DEL RECLAMO ===
    reason_id = fields.Char(
        string='Reason ID',
        readonly=True,
        help='ID del motivo del reclamo (ej: PDD9549, PNR3430)'
    )
    reason_type = fields.Selection([
        ('PNR', 'Producto No Recibido'),
        ('PDD', 'Producto Diferente/Defectuoso'),
        ('CS', 'Compra Cancelada'),
        ('OTHER', 'Otro'),
    ], string='Tipo Motivo', compute='_compute_reason_type', store=True)

    reason_detail = fields.Text(
        string='Detalle del Motivo',
        readonly=True
    )
    problem_description = fields.Text(
        string='Descripcion del Problema',
        readonly=True
    )

    # === PARTICIPANTES (PLAYERS) ===
    complainant_user_id = fields.Char(
        string='ID Comprador',
        readonly=True,
        help='ID del usuario que reclama (comprador)'
    )
    complainant_type = fields.Char(
        string='Tipo Comprador',
        readonly=True
    )
    respondent_user_id = fields.Char(
        string='ID Vendedor',
        readonly=True,
        help='ID del usuario respondiente (vendedor - nosotros)'
    )
    respondent_type = fields.Char(
        string='Tipo Vendedor',
        readonly=True
    )
    mediator_user_id = fields.Char(
        string='ID Mediador',
        readonly=True,
        help='ID del mediador de MercadoLibre'
    )

    # === RESOLUCION ===
    resolution_reason = fields.Char(
        string='Motivo Resolucion',
        readonly=True
    )
    resolution_benefited = fields.Char(
        string='Beneficiado',
        readonly=True,
        help='Quien fue beneficiado por la resolucion'
    )
    resolution_closed_by = fields.Char(
        string='Cerrado Por',
        readonly=True
    )
    resolution_date = fields.Datetime(
        string='Fecha Resolucion',
        readonly=True
    )
    applied_coverage = fields.Boolean(
        string='Cobertura Aplicada',
        readonly=True,
        help='Si MercadoLibre aplico cobertura'
    )

    # === FECHAS ===
    date_created = fields.Datetime(
        string='Fecha Creacion',
        readonly=True
    )
    date_last_updated = fields.Datetime(
        string='Ultima Actualizacion ML',
        readonly=True
    )
    due_date = fields.Datetime(
        string='Fecha Limite',
        readonly=True,
        help='Fecha limite para responder/resolver'
    )
    action_responsible = fields.Selection([
        ('seller', 'Vendedor'),
        ('buyer', 'Comprador'),
        ('mediator', 'Mediador'),
    ], string='Responsable Accion', readonly=True)

    # === DETALLES ADICIONALES ===
    title = fields.Char(
        string='Titulo',
        readonly=True
    )
    description = fields.Text(
        string='Descripcion Estado',
        readonly=True
    )

    # === ACCIONES DISPONIBLES ===
    available_actions = fields.Text(
        string='Acciones Disponibles (JSON)',
        readonly=True,
        help='JSON con las acciones disponibles para el vendedor'
    )
    can_refund = fields.Boolean(
        string='Puede Reembolsar',
        compute='_compute_available_actions',
        store=True
    )
    can_open_dispute = fields.Boolean(
        string='Puede Abrir Disputa',
        compute='_compute_available_actions',
        store=True
    )
    can_send_message = fields.Boolean(
        string='Puede Enviar Mensaje',
        compute='_compute_available_actions',
        store=True
    )
    can_add_evidence = fields.Boolean(
        string='Puede Agregar Evidencia',
        compute='_compute_available_actions',
        store=True
    )
    can_allow_return = fields.Boolean(
        string='Puede Permitir Devolucion',
        compute='_compute_available_actions',
        store=True
    )
    can_partial_refund = fields.Boolean(
        string='Puede Reembolso Parcial',
        compute='_compute_available_actions',
        store=True
    )

    # === RELACIONES ===
    message_ids = fields.One2many(
        'mercadolibre.claim.message',
        'claim_id',
        string='Mensajes'
    )
    message_count = fields.Integer(
        string='Num. Mensajes',
        compute='_compute_message_count'
    )
    evidence_ids = fields.One2many(
        'mercadolibre.claim.evidence',
        'claim_id',
        string='Evidencias'
    )
    resolution_ids = fields.One2many(
        'mercadolibre.claim.resolution',
        'claim_id',
        string='Resoluciones Esperadas'
    )
    action_log_ids = fields.One2many(
        'mercadolibre.claim.action.log',
        'claim_id',
        string='Historial de Acciones'
    )

    # === ENTIDADES RELACIONADAS ===
    has_return = fields.Boolean(
        string='Tiene Devolucion',
        readonly=True
    )
    return_id = fields.Char(
        string='Return ID',
        readonly=True
    )

    # === PROCESAMIENTO EN ODOO ===
    odoo_process_status = fields.Selection([
        ('pending', 'Pendiente'),
        ('processed', 'Procesado'),
        ('error', 'Error'),
        ('manual', 'Requiere Accion Manual'),
    ], string='Estado Procesamiento', default='pending', tracking=True)

    odoo_process_log = fields.Text(
        string='Log de Procesamiento',
        readonly=True
    )

    # === ESTADISTICAS Y EXTRAS ===
    affects_reputation = fields.Selection([
        ('affected', 'Afecta'),
        ('not_affected', 'No Afecta'),
        ('not_applies', 'No Aplica'),
    ], string='Afecta Reputacion', readonly=True)

    fulfilled = fields.Boolean(
        string='Entregado',
        readonly=True,
        help='Si el producto fue entregado antes del reclamo'
    )
    quantity_type = fields.Selection([
        ('total', 'Total'),
        ('partial', 'Parcial'),
    ], string='Tipo Cantidad', readonly=True)

    claimed_quantity = fields.Integer(
        string='Cantidad Reclamada',
        readonly=True
    )
    claim_version = fields.Char(
        string='Version Claim',
        readonly=True
    )
    site_id = fields.Char(
        string='Site ID',
        readonly=True,
        help='ID del sitio (MLM, MLA, etc.)'
    )
    parent_id_ml = fields.Char(
        string='Parent Claim ID',
        readonly=True,
        help='ID del claim padre si existe'
    )

    # === RAW DATA ===
    raw_data = fields.Text(
        string='Datos Crudos JSON',
        readonly=True
    )

    # === SINCRONIZACION ===
    last_sync_date = fields.Datetime(
        string='Ultima Sincronizacion',
        readonly=True
    )

    notes = fields.Text(string='Notas')

    _sql_constraints = [
        ('ml_claim_id_uniq', 'unique(ml_claim_id, account_id)',
         'Este reclamo ya existe para esta cuenta.')
    ]

    # =====================================================
    # CAMPOS COMPUTADOS
    # =====================================================

    @api.depends('ml_claim_id', 'type')
    def _compute_name(self):
        type_labels = {
            'mediations': 'MED',
            'returns': 'DEV',
            'fulfillment': 'FUL',
            'ml_case': 'CAS',
            'cancel_sale': 'CVT',
            'cancel_purchase': 'CCO',
            'change': 'CAM',
            'service': 'SRV',
        }
        for record in self:
            prefix = type_labels.get(record.type, 'CLM')
            record.name = f'{prefix}-{record.ml_claim_id}' if record.ml_claim_id else 'Nuevo Reclamo'

    @api.depends('reason_id')
    def _compute_reason_type(self):
        for record in self:
            if record.reason_id:
                if record.reason_id.startswith('PNR'):
                    record.reason_type = 'PNR'
                elif record.reason_id.startswith('PDD'):
                    record.reason_type = 'PDD'
                elif record.reason_id.startswith('CS'):
                    record.reason_type = 'CS'
                else:
                    record.reason_type = 'OTHER'
            else:
                record.reason_type = False

    @api.depends('available_actions')
    def _compute_available_actions(self):
        for record in self:
            actions = []
            if record.available_actions:
                try:
                    actions_data = json.loads(record.available_actions)
                    actions = [a.get('action', '') for a in actions_data]
                except (json.JSONDecodeError, TypeError):
                    actions = []

            record.can_refund = 'refund' in actions
            record.can_open_dispute = 'open_dispute' in actions
            record.can_send_message = any(a.startswith('send_message') for a in actions)
            record.can_add_evidence = 'add_shipping_evidence' in actions
            record.can_allow_return = 'allow_return' in actions or 'allow_return_label' in actions
            record.can_partial_refund = 'allow_partial_refund' in actions

    @api.depends('message_ids')
    def _compute_message_count(self):
        for record in self:
            record.message_count = len(record.message_ids)

    # =====================================================
    # METODOS DE CREACION/ACTUALIZACION
    # =====================================================

    @api.model
    def create_from_ml_data(self, data, account):
        """
        Crea o actualiza un claim desde los datos de MercadoLibre API.

        Args:
            data: dict con los datos del claim desde la API
            account: mercadolibre.account record

        Returns:
            tuple: (mercadolibre.claim record, bool is_new)
        """
        ml_claim_id = str(data.get('id', ''))

        if not ml_claim_id:
            _logger.error('No se encontro ID de claim en los datos')
            return False, False

        # Buscar claim existente
        existing = self.search([
            ('ml_claim_id', '=', ml_claim_id),
            ('account_id', '=', account.id)
        ], limit=1)

        # Extraer players
        players = data.get('players', []) or []
        complainant = next((p for p in players if p.get('role') == 'complainant'), {})
        respondent = next((p for p in players if p.get('role') == 'respondent'), {})
        mediator = next((p for p in players if p.get('role') == 'mediator'), {})

        # Extraer available_actions del respondent (vendedor)
        available_actions = respondent.get('available_actions', []) or []

        # Extraer resolucion
        resolution = data.get('resolution', {}) or {}

        # Extraer related_entities
        related_entities = data.get('related_entities', []) or []
        has_return = 'return' in related_entities

        # Preparar valores
        vals = {
            'account_id': account.id,
            'ml_claim_id': ml_claim_id,
            'resource': data.get('resource', ''),
            'resource_id': str(data.get('resource_id', '')),
            'status': data.get('status', ''),
            'stage': data.get('stage', ''),
            'type': data.get('type', ''),
            'reason_id': data.get('reason_id', ''),
            'fulfilled': data.get('fulfilled', False),
            'quantity_type': data.get('quantity_type', ''),
            'claimed_quantity': data.get('claimed_quantity', 0),
            'claim_version': str(data.get('claim_version', '')),
            'site_id': data.get('site_id', ''),
            'parent_id_ml': str(data.get('parent_id', '')) if data.get('parent_id') else '',
            # Players
            'complainant_user_id': str(complainant.get('user_id', '')),
            'complainant_type': complainant.get('type', ''),
            'respondent_user_id': str(respondent.get('user_id', '')),
            'respondent_type': respondent.get('type', ''),
            'mediator_user_id': str(mediator.get('user_id', '')) if mediator else '',
            # Acciones disponibles
            'available_actions': json.dumps(available_actions) if available_actions else '',
            # Resolucion
            'resolution_reason': resolution.get('reason', ''),
            'resolution_benefited': ','.join(resolution.get('benefited', [])) if resolution.get('benefited') else '',
            'resolution_closed_by': resolution.get('closed_by', ''),
            'resolution_date': self._parse_datetime(resolution.get('date_created')),
            'applied_coverage': resolution.get('applied_coverage', False),
            # Fechas
            'date_created': self._parse_datetime(data.get('date_created')),
            'date_last_updated': self._parse_datetime(data.get('last_updated')),
            # Entidades relacionadas
            'has_return': has_return,
            # Raw data
            'raw_data': json.dumps(data, indent=2, ensure_ascii=False),
            'last_sync_date': fields.Datetime.now(),
        }

        # Buscar order_id si el recurso es order
        if data.get('resource') == 'order':
            vals['ml_order_id'] = str(data.get('resource_id', ''))

        if existing:
            _logger.info('Actualizando claim existente: %s', ml_claim_id)
            existing.write(vals)
            claim = existing
            is_new = False
        else:
            _logger.info('Creando nuevo claim: %s', ml_claim_id)
            claim = self.create(vals)
            is_new = True

        # Vincular con pago si existe
        claim._link_to_payment()

        return claim, is_new

    def _link_to_payment(self):
        """Intenta vincular el claim con un pago existente"""
        self.ensure_one()

        if self.ml_payment_id:
            return  # Ya vinculado

        PaymentModel = self.env['mercadolibre.payment']

        # Buscar por order_id
        if self.ml_order_id:
            payment = PaymentModel.search([
                ('mp_order_id', '=', self.ml_order_id),
                ('account_id', '=', self.account_id.id)
            ], limit=1)

            if payment:
                self.ml_payment_id = payment.id
                _logger.info('Claim %s vinculado a pago %s por order_id',
                            self.ml_claim_id, payment.mp_payment_id)
                return

        # Buscar por external_reference (que suele ser el order_id)
        if self.resource_id and self.resource == 'order':
            payment = PaymentModel.search([
                ('mp_external_reference', '=', self.resource_id),
                ('account_id', '=', self.account_id.id)
            ], limit=1)

            if payment:
                self.ml_payment_id = payment.id
                _logger.info('Claim %s vinculado a pago %s por external_reference',
                            self.ml_claim_id, payment.mp_payment_id)

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

    # =====================================================
    # METODOS DE SINCRONIZACION
    # =====================================================

    def action_sync_claim(self):
        """Sincroniza este claim desde MercadoLibre"""
        self.ensure_one()
        return self._sync_from_api()

    def _sync_from_api(self):
        """Obtiene los datos actualizados del claim desde la API"""
        self.ensure_one()

        access_token = self.account_id.get_valid_token_with_retry()
        if not access_token:
            raise UserError(_('No se pudo obtener token valido'))

        url = f'https://api.mercadolibre.com/post-purchase/v1/claims/{self.ml_claim_id}'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        LogModel = self.env['mercadolibre.log'].sudo()
        start_time = time.time()

        try:
            response = requests.get(url, headers=headers, timeout=30)
            duration = time.time() - start_time

            headers_log = {k: v if k != 'Authorization' else 'Bearer ***' for k, v in headers.items()}
            LogModel.create({
                'log_type': 'api_request',
                'level': 'success' if response.status_code == 200 else 'error',
                'account_id': self.account_id.id,
                'message': f'Sync Claim {self.ml_claim_id}: GET /post-purchase/v1/claims - {response.status_code}',
                'request_url': url,
                'request_method': 'GET',
                'request_headers': json.dumps(headers_log, indent=2),
                'response_code': response.status_code,
                'response_body': response.text[:10000] if response.text else '',
                'duration': duration,
            })

            if response.status_code != 200:
                raise UserError(_('Error al obtener claim: %s') % response.text)

            data = response.json()
            self.create_from_ml_data(data, self.account_id)

            # Sincronizar datos relacionados
            self._sync_messages()
            self._sync_detail()

            return True

        except requests.exceptions.RequestException as e:
            _logger.error('Error sincronizando claim %s: %s', self.ml_claim_id, str(e))
            raise UserError(_('Error de conexion: %s') % str(e))

    def _sync_messages(self):
        """Sincroniza los mensajes del reclamo desde la API"""
        self.ensure_one()

        access_token = self.account_id.get_valid_token_with_retry()
        if not access_token:
            return False

        url = f'https://api.mercadolibre.com/post-purchase/v1/claims/{self.ml_claim_id}/messages'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code != 200:
                _logger.error('Error obteniendo mensajes: %s', response.text)
                return False

            messages_data = response.json()
            MessageModel = self.env['mercadolibre.claim.message']

            for msg_data in messages_data:
                msg_hash = msg_data.get('hash')
                if not msg_hash:
                    msg_hash = f"{self.ml_claim_id}_{msg_data.get('date_created')}_{msg_data.get('sender_role')}"

                existing = MessageModel.search([
                    ('claim_id', '=', self.id),
                    ('hash', '=', msg_hash)
                ], limit=1)

                moderation = msg_data.get('message_moderation', {}) or {}

                vals = {
                    'claim_id': self.id,
                    'sender_role': msg_data.get('sender_role'),
                    'receiver_role': msg_data.get('receiver_role'),
                    'message': msg_data.get('message'),
                    'translated_message': msg_data.get('translated_message'),
                    'message_date': self._parse_datetime(msg_data.get('message_date')),
                    'date_created': self._parse_datetime(msg_data.get('date_created')),
                    'date_read': self._parse_datetime(msg_data.get('date_read')),
                    'stage': msg_data.get('stage'),
                    'status': msg_data.get('status'),
                    'moderation_status': moderation.get('status'),
                    'moderation_reason': moderation.get('reason'),
                    'hash': msg_hash,
                }

                if existing:
                    existing.write(vals)
                    message = existing
                else:
                    message = MessageModel.create(vals)

                # Sincronizar adjuntos del mensaje
                self._sync_message_attachments(message, msg_data.get('attachments', []))

            return True

        except requests.exceptions.RequestException as e:
            _logger.error('Error sincronizando mensajes: %s', str(e))
            return False

    def _sync_message_attachments(self, message, attachments_data):
        """Sincroniza los adjuntos de un mensaje"""
        AttachmentModel = self.env['mercadolibre.claim.message.attachment']

        for att_data in attachments_data:
            filename = att_data.get('filename')

            existing = AttachmentModel.search([
                ('message_id', '=', message.id),
                ('filename', '=', filename)
            ], limit=1)

            vals = {
                'message_id': message.id,
                'filename': filename,
                'original_filename': att_data.get('original_filename'),
                'file_size': att_data.get('size'),
                'file_type': att_data.get('type'),
                'date_created': self._parse_datetime(att_data.get('date_created')),
            }

            if existing:
                existing.write(vals)
            else:
                AttachmentModel.create(vals)

    def _sync_detail(self):
        """Sincroniza los detalles adicionales del claim"""
        self.ensure_one()

        access_token = self.account_id.get_valid_token_with_retry()
        if not access_token:
            return False

        url = f'https://api.mercadolibre.com/post-purchase/v1/claims/{self.ml_claim_id}/detail'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                self.write({
                    'due_date': self._parse_datetime(data.get('due_date')),
                    'action_responsible': data.get('action_responsible'),
                    'title': data.get('title'),
                    'description': data.get('description'),
                    'problem_description': data.get('problem'),
                })

            return True

        except requests.exceptions.RequestException as e:
            _logger.error('Error sincronizando detalle: %s', str(e))
            return False

    def action_sync_messages(self):
        """Accion para sincronizar mensajes manualmente"""
        self.ensure_one()
        self._sync_messages()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Mensajes sincronizados correctamente'),
                'type': 'success',
                'sticky': False,
            }
        }

    # =====================================================
    # ACCIONES DEL CLAIM
    # =====================================================

    def action_send_message(self):
        """Abre wizard para enviar mensaje"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Enviar Mensaje'),
            'res_model': 'mercadolibre.claim.send.message.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_claim_id': self.id,
            },
        }

    def action_open_dispute(self):
        """Abre disputa/mediacion con MercadoLibre"""
        self.ensure_one()

        if not self.can_open_dispute:
            raise UserError(_('No es posible abrir disputa para este reclamo'))

        access_token = self.account_id.get_valid_token_with_retry()
        if not access_token:
            raise UserError(_('No se pudo obtener token valido'))

        url = f'https://api.mercadolibre.com/post-purchase/v1/claims/{self.ml_claim_id}/actions/open-dispute'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        try:
            response = requests.post(url, headers=headers, timeout=30)

            if response.status_code not in (200, 201):
                raise UserError(_('Error al abrir disputa: %s') % response.text)

            # Actualizar claim
            self._sync_from_api()

            # Registrar en log
            self._log_action('open_dispute', 'Disputa abierta exitosamente')

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('Disputa abierta correctamente. MercadoLibre intervendra.'),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except requests.exceptions.RequestException as e:
            raise UserError(_('Error de conexion: %s') % str(e))

    def action_refund(self):
        """Ejecuta reembolso total al comprador"""
        self.ensure_one()

        if not self.can_refund:
            raise UserError(_('No es posible realizar reembolso para este reclamo'))

        access_token = self.account_id.get_valid_token_with_retry()
        if not access_token:
            raise UserError(_('No se pudo obtener token valido'))

        url = f'https://api.mercadolibre.com/post-purchase/v1/claims/{self.ml_claim_id}/expected-resolutions/refund'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        try:
            response = requests.post(url, headers=headers, timeout=30)

            if response.status_code not in (200, 201):
                raise UserError(_('Error al procesar reembolso: %s') % response.text)

            # Actualizar claim
            self._sync_from_api()

            # Registrar en log
            self._log_action('refund', 'Reembolso total ejecutado')

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('Reembolso procesado correctamente'),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except requests.exceptions.RequestException as e:
            raise UserError(_('Error de conexion: %s') % str(e))

    def action_allow_return(self):
        """Permite devolucion del producto"""
        self.ensure_one()

        if not self.can_allow_return:
            raise UserError(_('No es posible permitir devolucion para este reclamo'))

        access_token = self.account_id.get_valid_token_with_retry()
        if not access_token:
            raise UserError(_('No se pudo obtener token valido'))

        url = f'https://api.mercadolibre.com/post-purchase/v1/claims/{self.ml_claim_id}/expected-resolutions/allow-return'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        try:
            response = requests.post(url, headers=headers, timeout=30)

            if response.status_code not in (200, 201):
                raise UserError(_('Error al permitir devolucion: %s') % response.text)

            # Actualizar claim
            self._sync_from_api()

            # Registrar en log
            self._log_action('allow_return', 'Devolucion permitida')

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('Devolucion permitida. Se generara etiqueta para el comprador.'),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except requests.exceptions.RequestException as e:
            raise UserError(_('Error de conexion: %s') % str(e))

    def _log_action(self, action, detail):
        """Registra una accion en el historial"""
        self.ensure_one()
        self.env['mercadolibre.claim.action.log'].create({
            'claim_id': self.id,
            'action_name': action,
            'detail': detail,
            'user_id': self.env.user.id,
        })

    # =====================================================
    # VISTAS Y ACCIONES DE NAVEGACION
    # =====================================================

    def action_view_messages(self):
        """Abre vista de mensajes"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Mensajes del Reclamo'),
            'res_model': 'mercadolibre.claim.message',
            'view_mode': 'tree,form',
            'domain': [('claim_id', '=', self.id)],
            'context': {'default_claim_id': self.id},
        }

    def action_view_payment(self):
        """Abre el pago asociado"""
        self.ensure_one()
        if not self.ml_payment_id:
            raise UserError(_('Este reclamo no tiene un pago asociado'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Pago MercadoLibre'),
            'res_model': 'mercadolibre.payment',
            'res_id': self.ml_payment_id.id,
            'view_mode': 'form',
        }

    def action_view_raw_data(self):
        """Muestra los datos crudos del claim"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Datos Crudos - {self.name}',
            'res_model': 'mercadolibre.claim',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('mercadolibre_claims.view_mercadolibre_claim_raw_form').id,
            'target': 'new',
        }

    # =====================================================
    # CRON JOBS
    # =====================================================

    @api.model
    def _cron_sync_messages(self):
        """
        Cron job para sincronizar mensajes de todos los claims abiertos.
        Se ejecuta periódicamente para mantener los mensajes actualizados.
        """
        _logger.info('Iniciando sincronizacion de mensajes de claims')

        # Buscar claims abiertos
        open_claims = self.search([
            ('status', '=', 'opened'),
        ])

        synced_count = 0
        error_count = 0

        for claim in open_claims:
            try:
                claim._sync_messages()
                synced_count += 1
            except Exception as e:
                error_count += 1
                _logger.error('Error sincronizando mensajes de claim %s: %s',
                            claim.ml_claim_id, str(e))

        _logger.info('Sincronizacion de mensajes completada: %d OK, %d errores',
                    synced_count, error_count)

        return True
