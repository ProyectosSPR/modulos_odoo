# -*- coding: utf-8 -*-
"""
Modelo para gestionar preguntas y respuestas de MercadoLibre.

Permite sincronizar, visualizar y responder preguntas de productos
desde Odoo, con alertas a usuarios y métricas de tiempo de respuesta.
"""

import logging
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Límite de caracteres para respuestas en ML
ML_ANSWER_CHAR_LIMIT = 2000


class MercadolibreQuestion(models.Model):
    _name = 'mercadolibre.question'
    _description = 'Pregunta MercadoLibre'
    _order = 'date_created desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Identificadores
    ml_question_id = fields.Char(
        string='ID Pregunta ML',
        required=True,
        index=True,
        readonly=True,
        copy=False
    )
    name = fields.Char(
        string='Pregunta',
        compute='_compute_name',
        store=True
    )

    # Relaciones
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        required=True,
        ondelete='cascade',
        index=True
    )
    company_id = fields.Many2one(
        related='account_id.company_id',
        store=True
    )
    item_id = fields.Char(
        string='ID Producto ML',
        index=True,
        readonly=True
    )
    ml_product_id = fields.Many2one(
        'mercadolibre.product',
        string='Producto ML',
        ondelete='set null',
        compute='_compute_ml_product',
        store=True
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto Odoo',
        related='ml_product_id.product_id',
        store=True
    )

    # Datos del producto (para referencia rápida)
    item_title = fields.Char(
        string='Título Producto',
        readonly=True
    )
    item_price = fields.Float(
        string='Precio',
        readonly=True
    )
    item_thumbnail = fields.Char(
        string='Imagen',
        readonly=True
    )

    # Contenido de la pregunta
    text = fields.Text(
        string='Pregunta',
        readonly=True
    )
    text_preview = fields.Char(
        string='Vista Previa',
        compute='_compute_text_preview',
        store=True
    )

    # Datos del comprador que pregunta
    from_id = fields.Char(
        string='ID Usuario',
        readonly=True,
        index=True
    )
    from_nickname = fields.Char(
        string='Nickname',
        readonly=True
    )
    from_answered_questions = fields.Integer(
        string='Preguntas Respondidas',
        readonly=True,
        help='Cantidad de preguntas que este usuario ha hecho y fueron respondidas'
    )

    # Estado
    status = fields.Selection([
        ('UNANSWERED', 'Sin Responder'),
        ('ANSWERED', 'Respondida'),
        ('CLOSED_UNANSWERED', 'Cerrada Sin Respuesta'),
        ('UNDER_REVIEW', 'En Revisión'),
        ('BANNED', 'Prohibida'),
        ('DELETED', 'Eliminada'),
        ('DISABLED', 'Deshabilitada'),
    ], string='Estado ML', default='UNANSWERED', readonly=True, tracking=True)

    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('answered', 'Respondida'),
        ('closed', 'Cerrada'),
    ], string='Estado', compute='_compute_state', store=True)

    # Respuesta
    answer_text = fields.Text(
        string='Respuesta',
        tracking=True
    )
    answer_draft = fields.Text(
        string='Borrador Respuesta',
        help='Escribe aquí tu respuesta antes de enviarla'
    )
    answer_status = fields.Selection([
        ('ACTIVE', 'Activa'),
        ('DISABLED', 'Deshabilitada'),
        ('BANNED', 'Prohibida'),
    ], string='Estado Respuesta', readonly=True)
    answer_date = fields.Datetime(
        string='Fecha Respuesta',
        readonly=True
    )
    answer_char_count = fields.Integer(
        string='Caracteres',
        compute='_compute_answer_char_count'
    )

    # Fechas
    date_created = fields.Datetime(
        string='Fecha Pregunta',
        readonly=True,
        index=True
    )

    # Tiempo de respuesta
    response_time_minutes = fields.Integer(
        string='Tiempo Respuesta (min)',
        compute='_compute_response_time',
        store=True,
        help='Tiempo en minutos que tardó en responderse'
    )
    response_time_display = fields.Char(
        string='Tiempo Respuesta',
        compute='_compute_response_time',
        store=True
    )
    is_late = fields.Boolean(
        string='Respuesta Tardía',
        compute='_compute_response_time',
        store=True,
        help='La respuesta tardó más de 1 hora'
    )

    # Flags
    hold = fields.Boolean(
        string='En Espera',
        readonly=True,
        help='La pregunta está en espera por algún motivo'
    )
    deleted_from_listing = fields.Boolean(
        string='Eliminada del Listado',
        readonly=True
    )

    # Usuario asignado para responder
    user_id = fields.Many2one(
        'res.users',
        string='Asignado a',
        tracking=True,
        help='Usuario responsable de responder esta pregunta'
    )

    # Etiquetas para clasificación
    tag_ids = fields.Many2many(
        'mercadolibre.question.tag',
        string='Etiquetas'
    )

    _sql_constraints = [
        ('ml_question_id_unique', 'unique(ml_question_id, account_id)',
         'Ya existe una pregunta con este ID para esta cuenta.')
    ]

    @api.depends('text', 'item_title')
    def _compute_name(self):
        for record in self:
            text = (record.text or '')[:50]
            if len(record.text or '') > 50:
                text += '...'
            record.name = f"{record.item_title or 'Producto'}: {text}"

    @api.depends('text')
    def _compute_text_preview(self):
        for record in self:
            text = (record.text or '')[:100]
            if len(record.text or '') > 100:
                text += '...'
            record.text_preview = text

    @api.depends('item_id')
    def _compute_ml_product(self):
        """Busca el producto ML asociado al item_id."""
        for record in self:
            if record.item_id:
                ml_product = self.env['mercadolibre.product'].search([
                    ('ml_id', '=', record.item_id),
                    ('account_id', '=', record.account_id.id),
                ], limit=1)
                record.ml_product_id = ml_product.id if ml_product else False
            else:
                record.ml_product_id = False

    @api.depends('status')
    def _compute_state(self):
        for record in self:
            if record.status == 'ANSWERED':
                record.state = 'answered'
            elif record.status in ('CLOSED_UNANSWERED', 'BANNED', 'DELETED', 'DISABLED'):
                record.state = 'closed'
            else:
                record.state = 'pending'

    @api.depends('answer_draft')
    def _compute_answer_char_count(self):
        for record in self:
            record.answer_char_count = len(record.answer_draft or '')

    @api.depends('date_created', 'answer_date', 'status')
    def _compute_response_time(self):
        for record in self:
            if record.status == 'ANSWERED' and record.date_created and record.answer_date:
                delta = record.answer_date - record.date_created
                minutes = int(delta.total_seconds() / 60)
                record.response_time_minutes = minutes
                record.is_late = minutes > 60

                # Formato legible
                if minutes < 60:
                    record.response_time_display = f"{minutes} min"
                elif minutes < 1440:  # menos de 24 horas
                    hours = minutes // 60
                    mins = minutes % 60
                    record.response_time_display = f"{hours}h {mins}m"
                else:
                    days = minutes // 1440
                    hours = (minutes % 1440) // 60
                    record.response_time_display = f"{days}d {hours}h"
            else:
                record.response_time_minutes = 0
                record.response_time_display = ''
                record.is_late = False

    def action_answer(self):
        """Envía la respuesta a MercadoLibre."""
        self.ensure_one()

        if self.status == 'ANSWERED':
            raise UserError(_('Esta pregunta ya fue respondida.'))

        if not self.answer_draft or not self.answer_draft.strip():
            raise UserError(_('Debes escribir una respuesta.'))

        if len(self.answer_draft) > ML_ANSWER_CHAR_LIMIT:
            raise UserError(_(
                'La respuesta no puede exceder %s caracteres. '
                'Actualmente tiene %s caracteres.'
            ) % (ML_ANSWER_CHAR_LIMIT, len(self.answer_draft)))

        self._send_answer_to_ml()
        return True

    def _send_answer_to_ml(self):
        """Envía la respuesta a la API de MercadoLibre."""
        self.ensure_one()

        account = self.account_id
        answer_text = self.answer_draft.strip()

        _logger.info(f"=== ENVIANDO RESPUESTA ===")
        _logger.info(f"Pregunta ID: {self.ml_question_id}")
        _logger.info(f"Respuesta: {answer_text[:100]}...")

        try:
            endpoint = '/answers'
            payload = {
                'question_id': int(self.ml_question_id),
                'text': answer_text
            }

            response = account._make_request('POST', endpoint, data=payload)

            if response:
                # Éxito - actualizar registro
                self.write({
                    'status': 'ANSWERED',
                    'answer_text': answer_text,
                    'answer_draft': False,
                    'answer_date': fields.Datetime.now(),
                    'answer_status': 'ACTIVE',
                })

                _logger.info(f"Respuesta enviada exitosamente para pregunta {self.ml_question_id}")
                return True
            else:
                raise Exception('Respuesta vacía de la API')

        except Exception as e:
            _logger.error(f"Error enviando respuesta: {e}")
            raise UserError(_('Error al enviar respuesta: %s') % str(e))

    def action_view_item(self):
        """Abre el producto en MercadoLibre."""
        self.ensure_one()
        if self.item_id:
            # Determinar el sitio según la cuenta
            site_id = self.account_id.site_id or 'MLM'
            sites = {
                'MLA': 'mercadolibre.com.ar',
                'MLB': 'mercadolibre.com.br',
                'MLM': 'mercadolibre.com.mx',
                'MLC': 'mercadolibre.cl',
                'MCO': 'mercadolibre.com.co',
                'MLU': 'mercadolibre.com.uy',
                'MPE': 'mercadolibre.com.pe',
            }
            domain = sites.get(site_id, 'mercadolibre.com.mx')
            url = f"https://www.{domain}/p/{self.item_id}"
            return {
                'type': 'ir.actions.act_url',
                'url': url,
                'target': 'new',
            }

    def action_assign_to_me(self):
        """Asigna la pregunta al usuario actual."""
        self.write({'user_id': self.env.user.id})

    def action_unassign(self):
        """Desasigna la pregunta."""
        self.write({'user_id': False})

    @api.model
    def sync_questions_for_account(self, account, status='UNANSWERED', limit=50):
        """
        Sincroniza preguntas desde MercadoLibre para una cuenta.

        Args:
            account: mercadolibre.account record
            status: Estado de preguntas a sincronizar (UNANSWERED, ANSWERED, etc.)
            limit: Máximo de preguntas a sincronizar

        Returns:
            int: Cantidad de preguntas sincronizadas
        """
        _logger.info(f"Sincronizando preguntas {status} para cuenta {account.name}")

        try:
            # Endpoint con api_version=4 para mejor estructura
            endpoint = f'/questions/search?seller_id={account.ml_user_id}&status={status}&api_version=4&sort_fields=date_created&sort_types=DESC&limit={limit}'
            response = account._make_request('GET', endpoint)

            if not response or 'questions' not in response:
                _logger.info(f"Sin preguntas {status} para sincronizar")
                return 0

            questions = response.get('questions', [])
            synced = 0

            for q_data in questions:
                try:
                    self._process_question_from_api(account, q_data)
                    synced += 1
                except Exception as e:
                    _logger.warning(f"Error procesando pregunta {q_data.get('id')}: {e}")

            _logger.info(f"Sincronizadas {synced} preguntas para cuenta {account.name}")
            return synced

        except Exception as e:
            _logger.error(f"Error sincronizando preguntas: {e}")
            raise

    def _process_question_from_api(self, account, q_data):
        """
        Procesa una pregunta desde la API y la guarda/actualiza.

        Args:
            account: mercadolibre.account record
            q_data: dict con datos de la pregunta de la API
        """
        ml_question_id = str(q_data.get('id'))

        # Buscar si ya existe
        existing = self.search([
            ('ml_question_id', '=', ml_question_id),
            ('account_id', '=', account.id),
        ], limit=1)

        # Parsear fecha
        date_created = None
        date_str = q_data.get('date_created')
        if date_str:
            try:
                date_created = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except:
                pass

        # Datos de la respuesta
        answer_data = q_data.get('answer') or {}
        answer_date = None
        if answer_data.get('date_created'):
            try:
                answer_date = datetime.fromisoformat(
                    answer_data['date_created'].replace('Z', '+00:00')
                )
            except:
                pass

        # Datos del usuario que pregunta
        from_data = q_data.get('from') or {}

        vals = {
            'ml_question_id': ml_question_id,
            'account_id': account.id,
            'item_id': q_data.get('item_id'),
            'text': q_data.get('text', ''),
            'status': q_data.get('status', 'UNANSWERED'),
            'date_created': date_created,
            'from_id': str(from_data.get('id', '')),
            'from_answered_questions': from_data.get('answered_questions', 0),
            'hold': q_data.get('hold', False),
            'deleted_from_listing': q_data.get('deleted_from_listing', False),
            'answer_text': answer_data.get('text', ''),
            'answer_status': answer_data.get('status'),
            'answer_date': answer_date,
        }

        if existing:
            # Actualizar solo si hay cambios relevantes
            if existing.status != vals['status'] or existing.answer_text != vals['answer_text']:
                existing.write(vals)
            return existing
        else:
            # Crear nueva pregunta
            question = self.create(vals)

            # Obtener info del item para mostrar
            question._fetch_item_info()

            # Notificar si está configurado
            question._notify_new_question()

            return question

    def _fetch_item_info(self):
        """Obtiene información del producto desde ML."""
        self.ensure_one()

        if not self.item_id:
            return

        try:
            endpoint = f'/items/{self.item_id}'
            response = self.account_id._make_request('GET', endpoint)

            if response:
                self.write({
                    'item_title': response.get('title', ''),
                    'item_price': response.get('price', 0),
                    'item_thumbnail': response.get('thumbnail', ''),
                })
        except Exception as e:
            _logger.warning(f"Error obteniendo info de item {self.item_id}: {e}")

    def _notify_new_question(self):
        """Envía notificación de nueva pregunta a usuarios configurados."""
        self.ensure_one()

        config = self.env['mercadolibre.messaging.config'].get_config_for_account(self.account_id)

        if not config.notify_new_questions:
            return

        # Obtener usuarios a notificar
        users = config.question_notify_user_ids
        if not users:
            return

        # Crear actividad para cada usuario
        for user in users:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=user.id,
                summary=_('Nueva pregunta en MercadoLibre'),
                note=_(
                    '<p><strong>Producto:</strong> %s</p>'
                    '<p><strong>Pregunta:</strong> %s</p>'
                ) % (self.item_title or self.item_id, self.text or ''),
            )

        _logger.info(f"Notificación enviada para pregunta {self.ml_question_id}")

    @api.model
    def cron_sync_questions(self):
        """Cron para sincronizar preguntas pendientes desde ML."""
        accounts = self.env['mercadolibre.account'].search([('active', '=', True)])

        for account in accounts:
            config = self.env['mercadolibre.messaging.config'].get_config_for_account(account)

            if not config.sync_questions:
                continue

            try:
                # Sincronizar preguntas sin responder
                self.sync_questions_for_account(account, status='UNANSWERED', limit=50)
            except Exception as e:
                _logger.error(f"Error en cron de preguntas para {account.name}: {e}")

    # =========================================================================
    # NOTIFICACIONES WEBHOOK
    # =========================================================================

    @api.model
    def process_notification(self, account, data):
        """
        Procesa una notificación de preguntas desde el webhook central.

        Este método es llamado por el controller de mercadolibre_connector
        cuando recibe una notificación con topic='questions'.

        Args:
            account: mercadolibre.account record
            data: dict con la notificación de ML
                {
                    "resource": "/questions/5036111111",
                    "user_id": 123456789,
                    "topic": "questions",
                    "application_id": 89745685555,
                    "attempts": 1,
                    "sent": "2024-01-15T10:30:00.000Z",
                    "received": "2024-01-15T10:30:01.000Z"
                }

        Returns:
            dict con resultado del procesamiento
        """
        resource = data.get('resource', '')  # /questions/12345

        _logger.info(f"Procesando notificación pregunta - Resource: {resource}")

        # Extraer question_id del resource
        question_id = None
        if resource.startswith('/questions/'):
            question_id = resource.replace('/questions/', '')

        if not question_id:
            _logger.warning(f"Resource de pregunta inválido: {resource}")
            return {'status': 'error', 'reason': 'invalid resource'}

        return self._handle_question_notification(account, question_id)

    def _handle_question_notification(self, account, question_id):
        """
        Procesa una notificación de pregunta.

        Args:
            account: mercadolibre.account record
            question_id: ID de la pregunta en ML
        """
        try:
            # Obtener detalles de la pregunta desde la API
            endpoint = f'/questions/{question_id}?api_version=4'
            question_data = account._make_request('GET', endpoint)

            if not question_data:
                _logger.error(f"No se pudo obtener pregunta {question_id}")
                return {'status': 'error', 'reason': 'could not fetch question'}

            # Verificar que la pregunta es para este vendedor
            seller_id = str(question_data.get('seller_id', ''))
            if seller_id != account.ml_user_id:
                _logger.debug(f"Pregunta {question_id} no es para cuenta {account.name}")
                return {'status': 'ignored', 'reason': 'not for this seller'}

            # Procesar la pregunta
            question = self._process_question_from_api(account, question_data)

            if question:
                return {
                    'status': 'ok',
                    'action': 'processed',
                    'question_id': question.id,
                    'ml_question_id': question_id
                }

            return {'status': 'error', 'reason': 'could not process question'}

        except Exception as e:
            _logger.error(f"Error procesando notificación de pregunta {question_id}: {e}")
            return {'status': 'error', 'message': str(e)}


class MercadolibreQuestionTag(models.Model):
    """Etiquetas para clasificar preguntas."""
    _name = 'mercadolibre.question.tag'
    _description = 'Etiqueta de Pregunta ML'

    name = fields.Char(string='Nombre', required=True)
    color = fields.Integer(string='Color')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'El nombre de la etiqueta debe ser único.')
    ]
