# -*- coding: utf-8 -*-
"""
Wizard para sincronizar preguntas de MercadoLibre.
"""

import logging
from datetime import datetime, timedelta
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

    sync_mode = fields.Selection([
        ('recent', 'Preguntas Recientes'),
        ('history', 'Descargar Historial'),
    ], string='Modo', default='recent', required=True,
        help='Recientes: Últimas preguntas. Historial: Descarga masiva con paginación.')

    status_filter = fields.Selection([
        ('UNANSWERED', 'Sin Responder'),
        ('ANSWERED', 'Respondidas'),
        ('ALL', 'Todas'),
    ], string='Estado', default='UNANSWERED', required=True)

    limit = fields.Integer(
        string='Límite por página',
        default=50,
        help='Máximo de preguntas por consulta (máx 50)'
    )

    # Opciones para historial
    max_pages = fields.Integer(
        string='Páginas máximas',
        default=10,
        help='Número máximo de páginas a descargar (cada página = hasta 50 preguntas)'
    )

    date_from = fields.Date(
        string='Desde',
        default=lambda self: fields.Date.today() - timedelta(days=30),
        help='Filtrar preguntas desde esta fecha (filtrado local después de descargar)'
    )

    date_to = fields.Date(
        string='Hasta',
        default=lambda self: fields.Date.today(),
        help='Filtrar preguntas hasta esta fecha (filtrado local después de descargar)'
    )

    use_date_filter = fields.Boolean(
        string='Filtrar por fecha',
        default=False,
        help='Aplicar filtro de fechas (se descargan todas y se filtran localmente)'
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
    questions_filtered = fields.Integer(
        string='Preguntas en Rango de Fecha',
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

        _logger.info("=" * 60)
        _logger.info("=== INICIO SINCRONIZACIÓN DE PREGUNTAS ===")
        _logger.info(f"Cuenta: {self.account_id.name}")
        _logger.info(f"Modo: {self.sync_mode}")
        _logger.info(f"Filtro estado: {self.status_filter}")
        _logger.info(f"Límite por página: {self.limit}")

        if self.sync_mode == 'history':
            _logger.info(f"Páginas máximas: {self.max_pages}")
            if self.use_date_filter:
                _logger.info(f"Filtro fechas: {self.date_from} a {self.date_to}")

        account = self.account_id
        total_synced = 0
        total_filtered = 0
        messages = []

        try:
            if self.sync_mode == 'recent':
                # Modo simple: solo preguntas recientes
                total_synced, messages = self._sync_recent(account)
            else:
                # Modo historial: paginación completa
                total_synced, total_filtered, messages = self._sync_history(account)

            result_msg = f"Sincronización completada para {account.name}:\n\n"
            result_msg += "\n".join(messages)

            if self.sync_mode == 'history' and self.use_date_filter:
                result_msg += f"\n\nTotal descargadas: {total_synced}"
                result_msg += f"\nEn rango de fechas: {total_filtered}"
            else:
                result_msg += f"\n\nTotal: {total_synced} preguntas sincronizadas"

            _logger.info(f"=== FIN SINCRONIZACIÓN: {total_synced} preguntas ===")
            _logger.info("=" * 60)

            self.write({
                'state': 'done',
                'result_message': result_msg,
                'questions_synced': total_synced,
                'questions_filtered': total_filtered if self.sync_mode == 'history' else total_synced,
            })

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'mercadolibre.question.sync',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }

        except Exception as e:
            _logger.error(f"Error en sincronización de preguntas: {e}", exc_info=True)
            raise UserError(_('Error sincronizando preguntas: %s') % str(e))

    def _sync_recent(self, account):
        """Sincroniza preguntas recientes (modo simple)."""
        Question = self.env['mercadolibre.question']
        total_synced = 0
        messages = []

        if self.status_filter == 'ALL':
            for status in ['UNANSWERED', 'ANSWERED']:
                _logger.info(f"Sincronizando preguntas {status}...")
                synced = Question.sync_questions_for_account(
                    account,
                    status=status,
                    limit=self.limit
                )
                total_synced += synced
                messages.append(f"• {status}: {synced} preguntas")
        else:
            synced = Question.sync_questions_for_account(
                account,
                status=self.status_filter,
                limit=self.limit
            )
            total_synced = synced
            messages.append(f"• {self.status_filter}: {synced} preguntas")

        return total_synced, messages

    def _sync_history(self, account):
        """Sincroniza historial completo con paginación."""
        Question = self.env['mercadolibre.question']
        total_synced = 0
        total_filtered = 0
        messages = []

        statuses = ['UNANSWERED', 'ANSWERED'] if self.status_filter == 'ALL' else [self.status_filter]

        for status in statuses:
            _logger.info(f"Descargando historial {status}...")
            synced, filtered = self._sync_status_with_pagination(account, status, Question)
            total_synced += synced
            total_filtered += filtered

            if self.use_date_filter:
                messages.append(f"• {status}: {synced} descargadas, {filtered} en rango")
            else:
                messages.append(f"• {status}: {synced} preguntas")

        return total_synced, total_filtered, messages

    def _sync_status_with_pagination(self, account, status, Question):
        """Sincroniza un estado específico con paginación."""
        synced = 0
        filtered = 0
        offset = 0
        limit = min(self.limit, 50)  # ML max es 50
        page = 0

        while page < self.max_pages:
            page += 1
            _logger.info(f"Página {page}/{self.max_pages} - Offset: {offset}")

            try:
                endpoint = (
                    f'/questions/search?seller_id={account.ml_user_id}'
                    f'&status={status}&api_version=4'
                    f'&sort_fields=date_created&sort_types=DESC'
                    f'&limit={limit}&offset={offset}'
                )
                _logger.info(f"Endpoint: {endpoint}")

                response = account._make_request('GET', endpoint)

                if not response:
                    _logger.warning(f"Respuesta vacía en página {page}")
                    break

                questions = response.get('questions', [])
                total_api = response.get('total', 0)

                _logger.info(f"Página {page}: {len(questions)} preguntas (total en API: {total_api})")

                if not questions:
                    _logger.info("No hay más preguntas, terminando paginación")
                    break

                # Procesar cada pregunta
                for q_data in questions:
                    try:
                        # Verificar filtro de fecha si aplica
                        if self.use_date_filter:
                            date_str = q_data.get('date_created')
                            if date_str:
                                q_date = self._parse_date(date_str)
                                if q_date:
                                    if q_date.date() < self.date_from:
                                        # Ya pasamos el rango, podemos terminar si ordenamos DESC
                                        _logger.info(f"Pregunta {q_data.get('id')} fuera de rango (anterior), terminando")
                                        # No terminamos porque podría haber más en rango
                                        continue
                                    if q_date.date() > self.date_to:
                                        # Aún no llegamos al rango
                                        continue
                                    filtered += 1

                        Question._process_question_from_api(account, q_data)
                        synced += 1

                    except Exception as e:
                        _logger.warning(f"Error procesando pregunta {q_data.get('id')}: {e}")

                # Verificar si hay más páginas
                if len(questions) < limit:
                    _logger.info("Última página (menos resultados que el límite)")
                    break

                offset += limit

            except Exception as e:
                _logger.error(f"Error en página {page}: {e}")
                break

        _logger.info(f"Historial {status}: {synced} sincronizadas, {filtered} en rango de fechas")
        return synced, filtered if self.use_date_filter else synced

    def _parse_date(self, date_str):
        """Parsea una fecha ISO de ML."""
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except Exception:
            return None

    def action_view_questions(self):
        """Abre la vista de preguntas sincronizadas."""
        self.ensure_one()

        domain = [('account_id', '=', self.account_id.id)]

        # Si usamos filtro de fechas, aplicarlo al dominio
        if self.sync_mode == 'history' and self.use_date_filter:
            domain.append(('date_created', '>=', self.date_from))
            domain.append(('date_created', '<=', self.date_to))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Preguntas'),
            'res_model': 'mercadolibre.question',
            'view_mode': 'kanban,tree,form',
            'domain': domain,
            'context': {},
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
