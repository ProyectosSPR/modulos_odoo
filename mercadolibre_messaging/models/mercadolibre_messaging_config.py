# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class MercadolibreMessagingConfig(models.Model):
    _name = 'mercadolibre.messaging.config'
    _description = 'Configuración de Mensajería ML'
    _order = 'sequence, id'

    name = fields.Char(
        string='Nombre',
        required=True,
        default='Configuración Principal'
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        required=True,
        ondelete='cascade'
    )
    company_id = fields.Many2one(
        related='account_id.company_id',
        store=True,
        readonly=True
    )

    # Horario de atención
    schedule_id = fields.Many2one(
        'mercadolibre.messaging.schedule',
        string='Horario de Atención',
        help='Horario en el que se pueden enviar mensajes automáticos'
    )

    # Límites de ejecución
    messages_per_cron = fields.Integer(
        string='Mensajes por Ejecución',
        default=50,
        help='Máximo de mensajes a procesar por ejecución del cron'
    )
    min_interval_minutes = fields.Integer(
        string='Intervalo Mínimo (min)',
        default=5,
        help='Minutos mínimos entre mensajes a un mismo cliente'
    )
    max_retries = fields.Integer(
        string='Reintentos Máximos',
        default=3,
        help='Número máximo de reintentos para mensajes fallidos'
    )
    retry_delay_minutes = fields.Integer(
        string='Delay Reintento (min)',
        default=15,
        help='Minutos a esperar antes de reintentar un mensaje fallido'
    )

    # Rate limiting (respetando límite ML de 500 rpm)
    rate_limit_per_minute = fields.Integer(
        string='Límite por Minuto',
        default=100,
        help='Máximo de mensajes por minuto (ML permite 500, recomendamos menos)'
    )

    # Intervalos de sincronización
    sync_conversations_interval = fields.Integer(
        string='Intervalo Sync Conversaciones (min)',
        default=15,
        help='Cada cuántos minutos sincronizar conversaciones'
    )
    sync_messages_interval = fields.Integer(
        string='Intervalo Sync Mensajes (min)',
        default=5,
        help='Cada cuántos minutos sincronizar mensajes nuevos'
    )

    # Configuración de logging
    log_level = fields.Selection([
        ('debug', 'Debug'),
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
    ], string='Nivel de Log', default='info')

    log_to_database = fields.Boolean(
        string='Log a Base de Datos',
        default=True,
        help='Guardar logs en mercadolibre.log además de consola'
    )
    log_api_requests = fields.Boolean(
        string='Log Requests API',
        default=False,
        help='Guardar request/response de API (puede generar muchos datos)'
    )

    # Funcionalidades habilitadas
    auto_messages_enabled = fields.Boolean(
        string='Mensajes Automáticos',
        default=True,
        help='Habilitar envío automático de mensajes por reglas'
    )
    manual_messages_enabled = fields.Boolean(
        string='Mensajes Manuales',
        default=True,
        help='Permitir envío manual de mensajes'
    )
    sync_to_chatter = fields.Boolean(
        string='Sincronizar a Chatter',
        default=True,
        help='Copiar mensajes recibidos al chatter de sale.order'
    )
    queue_out_of_hours = fields.Boolean(
        string='Encolar Fuera de Horario',
        default=True,
        help='Si está fuera de horario, encolar mensaje para envío posterior'
    )

    # =========================================================================
    # CONFIGURACIÓN DE PREGUNTAS
    # =========================================================================
    sync_questions = fields.Boolean(
        string='Sincronizar Preguntas',
        default=True,
        help='Habilitar sincronización automática de preguntas'
    )
    sync_questions_interval = fields.Integer(
        string='Intervalo Sync Preguntas (min)',
        default=10,
        help='Cada cuántos minutos sincronizar preguntas nuevas'
    )
    notify_new_questions = fields.Boolean(
        string='Notificar Preguntas Nuevas',
        default=True,
        help='Crear actividad cuando llegue una nueva pregunta'
    )
    question_notify_user_ids = fields.Many2many(
        'res.users',
        'mercadolibre_config_question_users_rel',
        'config_id',
        'user_id',
        string='Usuarios a Notificar',
        help='Usuarios que recibirán notificación de nuevas preguntas'
    )
    question_auto_assign_user_id = fields.Many2one(
        'res.users',
        string='Asignar Automáticamente a',
        help='Usuario al que se asignarán automáticamente las preguntas nuevas'
    )

    # Métricas de preguntas (desde ML API)
    question_response_time_total = fields.Integer(
        string='Tiempo Respuesta Promedio (min)',
        readonly=True,
        help='Tiempo promedio de respuesta según MercadoLibre'
    )
    question_response_time_weekdays = fields.Integer(
        string='T. Respuesta Días Hábiles (9-18h)',
        readonly=True
    )
    question_response_time_weekdays_extra = fields.Integer(
        string='T. Respuesta Fuera de Horario (18-24h)',
        readonly=True
    )
    question_response_time_weekend = fields.Integer(
        string='T. Respuesta Fin de Semana',
        readonly=True
    )
    question_sales_percent_increase = fields.Float(
        string='% Incremento Ventas',
        readonly=True,
        help='Porcentaje estimado de incremento de ventas si respondes en menos de 1 hora'
    )
    question_metrics_last_update = fields.Datetime(
        string='Métricas Actualizadas',
        readonly=True
    )

    # Reputación del vendedor (desde ML API)
    seller_reputation_level = fields.Char(
        string='Nivel de Reputación',
        readonly=True,
        help='Nivel actual de reputación en MercadoLibre'
    )
    seller_reputation_power_seller = fields.Char(
        string='MercadoLíder',
        readonly=True,
        help='Status de MercadoLíder (gold, platinum, etc.)'
    )
    seller_transactions_completed = fields.Integer(
        string='Ventas Completadas',
        readonly=True
    )
    seller_transactions_canceled = fields.Integer(
        string='Ventas Canceladas',
        readonly=True
    )
    seller_transactions_period = fields.Char(
        string='Período',
        readonly=True
    )
    seller_ratings_positive = fields.Float(
        string='% Positivas',
        readonly=True
    )
    seller_ratings_neutral = fields.Float(
        string='% Neutras',
        readonly=True
    )
    seller_ratings_negative = fields.Float(
        string='% Negativas',
        readonly=True
    )
    seller_claims_rate = fields.Float(
        string='Tasa Reclamos (%)',
        readonly=True
    )
    seller_delayed_handling_rate = fields.Float(
        string='Tasa Demoras (%)',
        readonly=True
    )
    seller_cancellations_rate = fields.Float(
        string='Tasa Cancelaciones (%)',
        readonly=True
    )
    seller_reputation_last_update = fields.Datetime(
        string='Reputación Actualizada',
        readonly=True
    )

    # Estadísticas de mensajes
    messages_sent_today = fields.Integer(
        string='Mensajes Hoy',
        compute='_compute_messages_stats'
    )
    messages_sent_week = fields.Integer(
        string='Mensajes Semana',
        compute='_compute_messages_stats'
    )
    last_sync_date = fields.Datetime(
        string='Última Sincronización'
    )

    # Estadísticas de preguntas
    questions_pending_count = fields.Integer(
        string='Preguntas Pendientes',
        compute='_compute_questions_stats'
    )
    questions_answered_today = fields.Integer(
        string='Respondidas Hoy',
        compute='_compute_questions_stats'
    )
    questions_avg_response_time = fields.Float(
        string='T. Respuesta Promedio (min)',
        compute='_compute_questions_stats'
    )

    @api.depends('account_id')
    def _compute_messages_stats(self):
        from datetime import datetime, timedelta
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)

        for record in self:
            if record.account_id:
                # Mensajes hoy
                record.messages_sent_today = self.env['mercadolibre.message'].search_count([
                    ('account_id', '=', record.account_id.id),
                    ('direction', '=', 'outgoing'),
                    ('create_date', '>=', today.strftime('%Y-%m-%d 00:00:00')),
                ])
                # Mensajes semana
                record.messages_sent_week = self.env['mercadolibre.message'].search_count([
                    ('account_id', '=', record.account_id.id),
                    ('direction', '=', 'outgoing'),
                    ('create_date', '>=', week_ago.strftime('%Y-%m-%d 00:00:00')),
                ])
            else:
                record.messages_sent_today = 0
                record.messages_sent_week = 0

    @api.depends('account_id')
    def _compute_questions_stats(self):
        from datetime import datetime
        today = datetime.now().date()

        for record in self:
            if record.account_id:
                Question = self.env['mercadolibre.question']

                # Preguntas pendientes
                record.questions_pending_count = Question.search_count([
                    ('account_id', '=', record.account_id.id),
                    ('state', '=', 'pending'),
                ])

                # Respondidas hoy
                record.questions_answered_today = Question.search_count([
                    ('account_id', '=', record.account_id.id),
                    ('state', '=', 'answered'),
                    ('answer_date', '>=', today.strftime('%Y-%m-%d 00:00:00')),
                ])

                # Tiempo promedio de respuesta (últimas 50 respondidas)
                answered = Question.search([
                    ('account_id', '=', record.account_id.id),
                    ('state', '=', 'answered'),
                    ('response_time_minutes', '>', 0),
                ], limit=50, order='answer_date desc')

                if answered:
                    total_time = sum(answered.mapped('response_time_minutes'))
                    record.questions_avg_response_time = total_time / len(answered)
                else:
                    record.questions_avg_response_time = 0
            else:
                record.questions_pending_count = 0
                record.questions_answered_today = 0
                record.questions_avg_response_time = 0

    @api.constrains('rate_limit_per_minute')
    def _check_rate_limit(self):
        for record in self:
            if record.rate_limit_per_minute > 500:
                raise ValidationError(_(
                    'El límite por minuto no puede exceder 500 (límite de MercadoLibre)'
                ))
            if record.rate_limit_per_minute < 1:
                raise ValidationError(_(
                    'El límite por minuto debe ser al menos 1'
                ))

    @api.constrains('messages_per_cron')
    def _check_messages_per_cron(self):
        for record in self:
            if record.messages_per_cron < 1:
                raise ValidationError(_('Mensajes por ejecución debe ser al menos 1'))
            if record.messages_per_cron > 500:
                raise ValidationError(_('Mensajes por ejecución no debe exceder 500'))

    def _log(self, message, level='info', log_type='messaging', **kwargs):
        """
        Sistema de logging dual (consola + BD).

        Args:
            message: Mensaje a registrar
            level: Nivel de log (debug, info, warning, error)
            log_type: Tipo de log para BD
            **kwargs: Campos adicionales para mercadolibre.log
        """
        self.ensure_one()

        # Determinar si debe loggear según nivel configurado
        levels = ['debug', 'info', 'warning', 'error']
        config_level_idx = levels.index(self.log_level)
        msg_level_idx = levels.index(level)

        if msg_level_idx < config_level_idx:
            return

        # Log a consola
        log_func = getattr(_logger, level)
        log_func(f"[ML Messaging {self.account_id.name}] {message}")

        # Log a base de datos si está habilitado
        if self.log_to_database:
            log_vals = {
                'account_id': self.account_id.id,
                'log_type': log_type,
                'level': level,
                'message': message,
                'model': kwargs.get('model'),
                'res_id': kwargs.get('res_id'),
                'conversation_id': kwargs.get('conversation_id'),
                'message_rule_id': kwargs.get('message_rule_id'),
                'ml_pack_id': kwargs.get('ml_pack_id'),
            }

            if self.log_api_requests:
                log_vals.update({
                    'request_url': kwargs.get('request_url'),
                    'request_method': kwargs.get('request_method'),
                    'request_data': kwargs.get('request_data'),
                    'response_data': kwargs.get('response_data'),
                    'response_code': kwargs.get('response_code'),
                })

            try:
                self.env['mercadolibre.log'].sudo().create(log_vals)
            except Exception as e:
                _logger.error(f"Error guardando log en BD: {e}")

    @api.model
    def get_config_for_account(self, account):
        """Obtiene o crea configuración para una cuenta."""
        config = self.search([
            ('account_id', '=', account.id),
            ('active', '=', True),
        ], limit=1)

        if not config:
            config = self.create({
                'name': f'Config {account.name}',
                'account_id': account.id,
            })

        return config

    def action_test_connection(self):
        """Prueba la conexión con API de mensajería."""
        self.ensure_one()
        # Implementar prueba de conexión
        return True

    def action_sync_questions(self):
        """Sincroniza preguntas pendientes desde MercadoLibre."""
        self.ensure_one()

        if not self.sync_questions:
            raise ValidationError(_('La sincronización de preguntas está deshabilitada.'))

        try:
            synced = self.env['mercadolibre.question'].sync_questions_for_account(
                self.account_id,
                status='UNANSWERED',
                limit=50
            )
            _logger.info(f"Sincronizadas {synced} preguntas para {self.account_id.name}")
        except Exception as e:
            _logger.error(f"Error sincronizando preguntas: {e}")
            raise ValidationError(_('Error sincronizando preguntas: %s') % str(e))

        return True

    def action_update_question_metrics(self):
        """Actualiza métricas de tiempo de respuesta desde MercadoLibre."""
        self.ensure_one()

        account = self.account_id
        _logger.info(f"Actualizando métricas de preguntas para {account.name}")

        try:
            # Endpoint: GET /users/{user_id}/questions/response_time
            endpoint = f'/users/{account.ml_user_id}/questions/response_time'
            response = account._make_request('GET', endpoint)

            if response:
                vals = {
                    'question_metrics_last_update': fields.Datetime.now(),
                }

                # Total response time
                if 'total' in response:
                    vals['question_response_time_total'] = response['total'].get('response_time', 0)

                # Weekdays working hours (9-18h)
                if 'weekdays_working_hours' in response:
                    vals['question_response_time_weekdays'] = response['weekdays_working_hours'].get('response_time', 0)

                # Weekdays extra hours (18-24h)
                if 'weekdays_extra_hours' in response:
                    vals['question_response_time_weekdays_extra'] = response['weekdays_extra_hours'].get('response_time', 0)

                # Weekend
                if 'weekend' in response:
                    vals['question_response_time_weekend'] = response['weekend'].get('response_time', 0)

                # Sales percent increase if answering in less than 1 hour
                if 'sales_percent_increase' in response:
                    vals['question_sales_percent_increase'] = response.get('sales_percent_increase', 0)

                self.write(vals)
                _logger.info(f"Métricas de preguntas actualizadas: {vals}")

        except Exception as e:
            _logger.error(f"Error obteniendo métricas de preguntas: {e}")
            raise ValidationError(_('Error obteniendo métricas: %s') % str(e))

        return True

    def action_update_seller_reputation(self):
        """Actualiza métricas de reputación del vendedor desde MercadoLibre."""
        self.ensure_one()

        account = self.account_id
        _logger.info(f"Actualizando reputación de vendedor para {account.name}")

        try:
            # Endpoint: GET /users/{user_id}
            endpoint = f'/users/{account.ml_user_id}'
            response = account._make_request('GET', endpoint)

            if response and 'seller_reputation' in response:
                rep = response.get('seller_reputation', {})
                transactions = rep.get('transactions', {})
                metrics = rep.get('metrics', {})

                vals = {
                    'seller_reputation_last_update': fields.Datetime.now(),
                    'seller_reputation_level': rep.get('level_id', ''),
                    'seller_reputation_power_seller': rep.get('power_seller_status', ''),
                    'seller_transactions_period': transactions.get('period', ''),
                    'seller_transactions_completed': transactions.get('completed', 0),
                    'seller_transactions_canceled': transactions.get('canceled', 0),
                }

                # Ratings
                ratings = transactions.get('ratings', {})
                if ratings:
                    vals['seller_ratings_positive'] = ratings.get('positive', 0)
                    vals['seller_ratings_neutral'] = ratings.get('neutral', 0)
                    vals['seller_ratings_negative'] = ratings.get('negative', 0)

                # Metrics
                if metrics:
                    # Claims rate
                    claims = metrics.get('claims', {})
                    if claims:
                        vals['seller_claims_rate'] = claims.get('rate', 0) * 100

                    # Delayed handling time
                    delayed = metrics.get('delayed_handling_time', {})
                    if delayed:
                        vals['seller_delayed_handling_rate'] = delayed.get('rate', 0) * 100

                    # Cancellations
                    cancellations = metrics.get('cancellations', {})
                    if cancellations:
                        vals['seller_cancellations_rate'] = cancellations.get('rate', 0) * 100

                self.write(vals)
                _logger.info(f"Reputación de vendedor actualizada: nivel={vals.get('seller_reputation_level')}")

        except Exception as e:
            _logger.error(f"Error obteniendo reputación de vendedor: {e}")
            raise ValidationError(_('Error obteniendo reputación: %s') % str(e))

        return True

    def action_update_all_metrics(self):
        """Actualiza todas las métricas (preguntas y reputación)."""
        self.ensure_one()
        self.action_update_question_metrics()
        self.action_update_seller_reputation()
        return True

    def action_view_pending_questions(self):
        """Abre vista de preguntas pendientes para esta cuenta."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Preguntas Pendientes'),
            'res_model': 'mercadolibre.question',
            'view_mode': 'kanban,tree,form',
            'domain': [
                ('account_id', '=', self.account_id.id),
                ('state', '=', 'pending'),
            ],
            'context': {'default_account_id': self.account_id.id},
        }
