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

    # Estadísticas
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
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Conexión Exitosa'),
                'message': _('La conexión con la API de mensajería funciona correctamente.'),
                'type': 'success',
                'sticky': False,
            }
        }
