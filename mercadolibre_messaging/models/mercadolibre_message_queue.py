# -*- coding: utf-8 -*-

import logging
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MercadolibreMessageQueue(models.Model):
    _name = 'mercadolibre.message.queue'
    _description = 'Cola de Mensajes ML'
    _order = 'scheduled_time asc'

    # Relaciones
    conversation_id = fields.Many2one(
        'mercadolibre.conversation',
        string='Conversación',
        required=True,
        ondelete='cascade',
        index=True
    )
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
    ml_order_id = fields.Many2one(
        'mercadolibre.order',
        string='Orden ML',
        ondelete='set null'
    )

    # Contenido
    body = fields.Text(
        string='Mensaje',
        required=True
    )

    # Plantilla/Regla
    template_id = fields.Many2one(
        'mercadolibre.message.template',
        string='Plantilla',
        ondelete='set null'
    )
    rule_id = fields.Many2one(
        'mercadolibre.message.rule',
        string='Regla',
        ondelete='set null'
    )

    # Opción ML
    ml_option_id = fields.Selection([
        ('REQUEST_BILLING_INFO', 'Solicitar Datos de Facturación'),
        ('REQUEST_VARIANTS', 'Solicitar Variantes'),
        ('SEND_INVOICE_LINK', 'Enviar Link de Factura'),
        ('DELIVERY_PROMISE', 'Promesa de Entrega'),
        ('OTHER', 'Otro'),
    ], string='Opción ML', default='OTHER')

    # Programación
    scheduled_time = fields.Datetime(
        string='Programado Para',
        required=True,
        default=fields.Datetime.now,
        index=True
    )
    priority = fields.Integer(
        string='Prioridad',
        default=10,
        help='Menor número = mayor prioridad'
    )

    # Estado
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('processing', 'Procesando'),
        ('sent', 'Enviado'),
        ('failed', 'Fallido'),
        ('cancelled', 'Cancelado'),
    ], string='Estado', default='pending', index=True)

    # Resultado
    message_id = fields.Many2one(
        'mercadolibre.message',
        string='Mensaje Creado',
        readonly=True,
        ondelete='set null'
    )
    error_message = fields.Text(
        string='Error',
        readonly=True
    )
    retry_count = fields.Integer(
        string='Reintentos',
        default=0
    )

    # Fechas
    processed_date = fields.Datetime(
        string='Fecha Procesado',
        readonly=True
    )

    # Motivo de encolado
    queue_reason = fields.Selection([
        ('schedule', 'Fuera de Horario'),
        ('delay', 'Delay de Regla'),
        ('rate_limit', 'Límite de Tasa'),
        ('manual', 'Programación Manual'),
    ], string='Motivo', default='manual')

    def action_send_now(self):
        """Envía el mensaje inmediatamente."""
        for record in self:
            if record.state not in ('pending', 'failed'):
                raise UserError(_('Solo se pueden enviar mensajes pendientes o fallidos'))

            record._process_queue_item()

    def action_cancel(self):
        """Cancela el mensaje encolado."""
        self.filtered(lambda r: r.state == 'pending').write({
            'state': 'cancelled'
        })

    def action_reschedule(self):
        """Reprograma el mensaje."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reprogramar Mensaje'),
            'res_model': 'mercadolibre.message.queue.reschedule',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_ids': self.ids}
        }

    def _process_queue_item(self):
        """Procesa un elemento de la cola."""
        self.ensure_one()

        if self.state not in ('pending', 'failed'):
            return

        self.write({'state': 'processing'})

        config = self.env['mercadolibre.messaging.config'].get_config_for_account(self.account_id)

        # Verificar horario si corresponde
        if self.queue_reason == 'schedule' and config.schedule_id:
            if not config.schedule_id.is_within_schedule():
                # Reprogramar para próxima apertura
                schedule_status = config.schedule_id.get_schedule_status()
                _logger.info(f"Cola {self.id}: aún fuera de horario, reprogramando")
                self.write({
                    'state': 'pending',
                    # Se procesará en el próximo cron
                })
                return

        try:
            # Crear y enviar mensaje
            message = self.env['mercadolibre.message'].create({
                'conversation_id': self.conversation_id.id,
                'account_id': self.account_id.id,
                'body': self.body,
                'direction': 'outgoing',
                'template_id': self.template_id.id if self.template_id else False,
                'rule_id': self.rule_id.id if self.rule_id else False,
                'ml_order_id': self.ml_order_id.id if self.ml_order_id else False,
                'ml_option_id': self.ml_option_id,
                'state': 'pending',
            })

            # Intentar enviar
            success = message._send_to_ml()

            if success:
                self.write({
                    'state': 'sent',
                    'message_id': message.id,
                    'processed_date': fields.Datetime.now(),
                    'error_message': False,
                })

                config._log(
                    f'Cola procesada: mensaje {message.id} enviado',
                    level='info',
                    log_type='auto_message',
                    conversation_id=self.conversation_id.id,
                )
            else:
                self.write({
                    'state': 'failed',
                    'message_id': message.id,
                    'error_message': message.error_message,
                    'retry_count': self.retry_count + 1,
                })

        except Exception as e:
            error_msg = str(e)
            self.write({
                'state': 'failed',
                'error_message': error_msg,
                'retry_count': self.retry_count + 1,
                'processed_date': fields.Datetime.now(),
            })

            config._log(
                f'Error procesando cola {self.id}: {error_msg}',
                level='error',
                log_type='message_error',
                conversation_id=self.conversation_id.id,
            )

    @api.model
    def cron_process_queue(self):
        """Cron para procesar la cola de mensajes."""
        now = fields.Datetime.now()

        # Obtener elementos pendientes cuya hora programada ya pasó
        pending_items = self.search([
            ('state', '=', 'pending'),
            ('scheduled_time', '<=', now),
        ], order='priority asc, scheduled_time asc', limit=100)

        if not pending_items:
            return

        # Agrupar por cuenta para respetar rate limits
        by_account = {}
        for item in pending_items:
            account_id = item.account_id.id
            if account_id not in by_account:
                by_account[account_id] = []
            by_account[account_id].append(item)

        # Procesar por cuenta
        for account_id, items in by_account.items():
            account = self.env['mercadolibre.account'].browse(account_id)
            config = self.env['mercadolibre.messaging.config'].get_config_for_account(account)

            # Verificar horario
            if config.schedule_id and not config.schedule_id.is_within_schedule():
                _logger.info(f"Cuenta {account.name}: fuera de horario, omitiendo cola")
                continue

            # Limitar por rate limit
            items_to_process = items[:config.messages_per_cron]

            for item in items_to_process:
                try:
                    item._process_queue_item()
                except Exception as e:
                    _logger.error(f"Error procesando cola {item.id}: {e}")

    @api.model
    def cron_retry_failed_queue(self):
        """Cron para reintentar elementos fallidos de la cola."""
        failed_items = self.search([
            ('state', '=', 'failed'),
        ])

        for item in failed_items:
            config = self.env['mercadolibre.messaging.config'].get_config_for_account(item.account_id)

            # Verificar máximo de reintentos
            if item.retry_count >= config.max_retries:
                continue

            # Verificar delay
            if item.processed_date:
                min_retry_time = item.processed_date + timedelta(minutes=config.retry_delay_minutes)
                if datetime.now() < min_retry_time:
                    continue

            # Reprogramar
            item.write({
                'state': 'pending',
                'scheduled_time': fields.Datetime.now(),
            })

    @api.model
    def cron_cleanup_old_queue(self):
        """Cron para limpiar elementos antiguos de la cola."""
        cutoff_date = datetime.now() - timedelta(days=30)

        old_items = self.search([
            ('state', 'in', ('sent', 'cancelled')),
            ('processed_date', '<', cutoff_date),
        ])

        if old_items:
            _logger.info(f"Limpiando {len(old_items)} elementos antiguos de cola")
            old_items.unlink()
