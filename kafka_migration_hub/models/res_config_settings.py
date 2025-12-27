# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ==========================================
    # Configuración de Kafka
    # ==========================================
    migration_kafka_servers = fields.Char(
        string='Servidores Kafka',
        config_parameter='migration_hub.kafka_servers',
        help='Lista de servidores Kafka (bootstrap servers). Ej: kafka:9092'
    )
    migration_kafka_security = fields.Selection([
        ('PLAINTEXT', 'Sin autenticación (PLAINTEXT)'),
        ('SSL', 'SSL/TLS'),
        ('SASL_PLAINTEXT', 'SASL (usuario/contraseña)'),
        ('SASL_SSL', 'SASL + SSL'),
    ], string='Protocolo de Seguridad',
        config_parameter='migration_hub.kafka_security_protocol',
        default='PLAINTEXT'
    )
    migration_kafka_sasl_mechanism = fields.Selection([
        ('', 'Ninguno'),
        ('PLAIN', 'PLAIN'),
        ('SCRAM-SHA-256', 'SCRAM-SHA-256'),
        ('SCRAM-SHA-512', 'SCRAM-SHA-512'),
    ], string='Mecanismo SASL',
        config_parameter='migration_hub.kafka_sasl_mechanism',
        default=''
    )
    migration_kafka_username = fields.Char(
        string='Usuario Kafka',
        config_parameter='migration_hub.kafka_sasl_username'
    )
    migration_kafka_password = fields.Char(
        string='Contraseña Kafka',
        config_parameter='migration_hub.kafka_sasl_password'
    )

    # ==========================================
    # Configuración de IA
    # ==========================================
    migration_ai_provider = fields.Selection([
        ('heuristic', 'Heurísticas (Sin IA externa)'),
        ('claude', 'Claude (Anthropic)'),
        ('openai', 'OpenAI (GPT-4)'),
    ], string='Proveedor de IA',
        config_parameter='migration_hub.ai_provider',
        default='heuristic',
        help='Seleccione el proveedor de IA para sugerencias de mapeo automático'
    )

    # Claude (Anthropic)
    migration_claude_api_key = fields.Char(
        string='Claude API Key',
        config_parameter='migration_hub.claude_api_key',
        help='API Key de Anthropic (empieza con sk-ant-...)'
    )
    migration_claude_model = fields.Selection([
        ('claude-sonnet-4-20250514', 'Claude Sonnet 4 (Recomendado)'),
        ('claude-3-5-sonnet-20241022', 'Claude 3.5 Sonnet'),
        ('claude-3-haiku-20240307', 'Claude 3 Haiku (Rápido)'),
        ('claude-3-opus-20240229', 'Claude 3 Opus (Más potente)'),
    ], string='Modelo Claude',
        config_parameter='migration_hub.claude_model',
        default='claude-sonnet-4-20250514'
    )
    migration_claude_status = fields.Char(
        string='Estado de Claude',
        compute='_compute_claude_status'
    )

    # OpenAI
    migration_openai_api_key = fields.Char(
        string='OpenAI API Key',
        config_parameter='migration_hub.openai_api_key',
        help='API Key de OpenAI (empieza con sk-...)'
    )
    migration_openai_model = fields.Selection([
        ('gpt-4', 'GPT-4'),
        ('gpt-4-turbo', 'GPT-4 Turbo'),
        ('gpt-3.5-turbo', 'GPT-3.5 Turbo (Económico)'),
    ], string='Modelo OpenAI',
        config_parameter='migration_hub.openai_model',
        default='gpt-4'
    )

    # ==========================================
    # Configuración de Migración
    # ==========================================
    migration_batch_size = fields.Integer(
        string='Tamaño de Lote',
        config_parameter='migration_hub.default_batch_size',
        default=100,
        help='Cantidad de registros a procesar por lote'
    )
    migration_max_retries = fields.Integer(
        string='Reintentos Máximos',
        config_parameter='migration_hub.max_retries',
        default=3,
        help='Número máximo de reintentos para registros con error'
    )
    migration_retry_delay = fields.Integer(
        string='Delay entre Reintentos (seg)',
        config_parameter='migration_hub.retry_delay',
        default=30
    )

    @api.depends('migration_claude_api_key')
    def _compute_claude_status(self):
        for record in self:
            if record.migration_claude_api_key:
                record.migration_claude_status = 'API Key configurada'
            else:
                record.migration_claude_status = 'No configurado'

    def action_test_claude_connection(self):
        """Probar conexión con Claude API - Mostrar resultados detallados"""
        self.ensure_one()

        if not self.migration_claude_api_key:
            raise UserError(_('Primero ingrese la API Key de Claude'))

        AIAnalyzer = self.env['migration.ai.analyzer']
        result = AIAnalyzer.test_claude_connection(self.migration_claude_api_key)

        # Construir mensaje detallado con los pasos
        steps_html = self._format_test_steps(result.get('steps', []))
        details = result.get('details', {})

        if result.get('success'):
            message = f"""
<div style="font-family: monospace;">
<h4 style="color: #28a745;">✓ Conexión Exitosa</h4>
<p><strong>{result.get('message')}</strong></p>
<hr/>
<h5>Pasos de Verificación:</h5>
{steps_html}
<hr/>
<h5>Detalles:</h5>
<ul>
<li><strong>Modelo:</strong> {details.get('model', 'N/A')}</li>
<li><strong>API Version:</strong> {details.get('api_version', 'N/A')}</li>
<li><strong>Key:</strong> {details.get('key_hint', 'N/A')}</li>
</ul>
</div>
"""
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Claude API - Test Exitoso'),
                    'message': result.get('message'),
                    'type': 'success',
                    'sticky': True,
                }
            }
        else:
            msg = result.get('message', '')

            # Mensaje específico para créditos insuficientes
            if 'credit balance' in msg.lower() or 'purchase credits' in msg.lower():
                error_message = _("""
══════════════════════════════════════
   CLAUDE API - SIN CRÉDITOS
══════════════════════════════════════

Tu API Key es VÁLIDA pero no tienes créditos.

→ Ve a: console.anthropic.com/settings/plans
→ Agrega créditos o actualiza tu plan

API Key: %s
""") % result.get('details', {}).get('key_hint', 'N/A')
            else:
                error_message = _("""
══════════════════════════════════════
   CLAUDE API - ERROR
══════════════════════════════════════

%s

Verifica en: console.anthropic.com/settings/keys
""") % msg

            raise UserError(error_message)

    def action_test_kafka_connection(self):
        """Probar conexión con Kafka - Mostrar resultados detallados"""
        self.ensure_one()

        if not self.migration_kafka_servers:
            raise UserError(_('Primero configure los servidores Kafka'))

        try:
            KafkaService = self.env['migration.kafka.service']
            result = KafkaService.test_connection(self.migration_kafka_servers)

            steps_html = self._format_test_steps(result.get('steps', []))
            details = result.get('details', {})

            if result.get('success'):
                # Construir lista de topics
                topics_list = details.get('migration_topics', [])
                topics_text = ', '.join(topics_list[:5]) if topics_list else 'Ninguno'

                brokers = details.get('brokers', [])
                brokers_text = ', '.join([f"{b['host']}:{b['port']}" for b in brokers]) if brokers else 'N/A'

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Kafka - Conexión Exitosa'),
                        'message': f"{result.get('message')}\nBrokers: {brokers_text}\nTopics migración: {topics_text}",
                        'type': 'success',
                        'sticky': True,
                    }
                }
            else:
                error_message = _("""
══════════════════════════════════════
   KAFKA - ERROR DE CONEXIÓN
══════════════════════════════════════

%s

Servidor: %s

Verificar:
  kubectl get pods | grep kafka
  kubectl get svc | grep kafka
""") % (result.get('message'), self.migration_kafka_servers)
                raise UserError(error_message)

        except UserError:
            raise
        except Exception as e:
            raise UserError(f'Error inesperado: {str(e)}')

    def _format_test_steps(self, steps):
        """Formatear pasos como HTML"""
        html_parts = ['<ul style="list-style: none; padding: 0;">']
        for step in steps:
            status = step.get('status', 'pending')
            icon = '✓' if status == 'ok' else ('⚠' if status == 'warning' else ('✗' if status == 'error' else '○'))
            color = '#28a745' if status == 'ok' else ('#ffc107' if status == 'warning' else ('#dc3545' if status == 'error' else '#6c757d'))
            html_parts.append(f'<li style="color: {color};"><strong>{icon} {step.get("step")}:</strong> {step.get("detail")}</li>')
        html_parts.append('</ul>')
        return '\n'.join(html_parts)

    def _format_test_steps_text(self, steps):
        """Formatear pasos como texto plano"""
        lines = []
        for step in steps:
            status = step.get('status', 'pending')
            icon = '[OK]' if status == 'ok' else ('[!]' if status == 'warning' else ('[X]' if status == 'error' else '[ ]'))
            lines.append(f"  {icon} {step.get('step')}: {step.get('detail')}")
        return '\n'.join(lines)
