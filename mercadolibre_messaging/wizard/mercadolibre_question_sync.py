# -*- coding: utf-8 -*-
"""
Wizard para sincronizar preguntas de MercadoLibre.
"""

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MercadolibreQuestionSync(models.TransientModel):
    _name = 'mercadolibre.question.sync'
    _description = 'Sincronizar Preguntas MercadoLibre'

    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta MercadoLibre',
        required=True,
        default=lambda self: self._default_account_id()
    )

    status_filter = fields.Selection([
        ('UNANSWERED', 'Sin Responder'),
        ('ANSWERED', 'Respondidas'),
        ('ALL', 'Todas'),
    ], string='Estado', default='UNANSWERED', required=True)

    limit = fields.Integer(
        string='Límite',
        default=50,
        help='Máximo de preguntas a sincronizar'
    )

    # Resultados
    result_message = fields.Text(
        string='Resultado',
        readonly=True
    )
    questions_synced = fields.Integer(
        string='Preguntas Sincronizadas',
        readonly=True
    )
    state = fields.Selection([
        ('draft', 'Configurar'),
        ('done', 'Completado'),
    ], default='draft')

    def _default_account_id(self):
        """Obtiene la cuenta por defecto."""
        return self.env['mercadolibre.account'].search([('active', '=', True)], limit=1).id

    def action_sync(self):
        """Ejecuta la sincronización de preguntas."""
        self.ensure_one()

        _logger.info(f"=== INICIO SINCRONIZACIÓN DE PREGUNTAS ===")
        _logger.info(f"Cuenta: {self.account_id.name}")
        _logger.info(f"Filtro estado: {self.status_filter}")
        _logger.info(f"Límite: {self.limit}")

        account = self.account_id
        Question = self.env['mercadolibre.question']
        total_synced = 0
        messages = []

        try:
            if self.status_filter == 'ALL':
                # Sincronizar todos los estados
                for status in ['UNANSWERED', 'ANSWERED']:
                    _logger.info(f"Sincronizando preguntas con estado: {status}")
                    synced = Question.sync_questions_for_account(
                        account,
                        status=status,
                        limit=self.limit
                    )
                    total_synced += synced
                    messages.append(f"- {status}: {synced} preguntas")
                    _logger.info(f"Sincronizadas {synced} preguntas {status}")
            else:
                _logger.info(f"Sincronizando preguntas con estado: {self.status_filter}")
                total_synced = Question.sync_questions_for_account(
                    account,
                    status=self.status_filter,
                    limit=self.limit
                )
                messages.append(f"- {self.status_filter}: {total_synced} preguntas")
                _logger.info(f"Sincronizadas {total_synced} preguntas {self.status_filter}")

            result_msg = f"Sincronización completada para {account.name}:\n"
            result_msg += "\n".join(messages)
            result_msg += f"\n\nTotal: {total_synced} preguntas sincronizadas"

            _logger.info(f"=== FIN SINCRONIZACIÓN: {total_synced} preguntas ===")

            self.write({
                'state': 'done',
                'result_message': result_msg,
                'questions_synced': total_synced,
            })

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'mercadolibre.question.sync',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }

        except Exception as e:
            _logger.error(f"Error en sincronización de preguntas: {e}")
            raise UserError(_('Error sincronizando preguntas: %s') % str(e))

    def action_view_questions(self):
        """Abre la vista de preguntas sincronizadas."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Preguntas'),
            'res_model': 'mercadolibre.question',
            'view_mode': 'kanban,tree,form',
            'domain': [('account_id', '=', self.account_id.id)],
            'context': {'search_default_pending': 1},
        }

    def action_new_sync(self):
        """Reinicia el wizard para nueva sincronización."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sincronizar Preguntas'),
            'res_model': 'mercadolibre.question.sync',
            'view_mode': 'form',
            'target': 'new',
        }
