# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import json

_logger = logging.getLogger(__name__)


class AIMappingWizard(models.TransientModel):
    """Wizard para asistencia de IA en mapeo"""
    _name = 'migration.ai.mapping.wizard'
    _description = 'Wizard de Mapeo con IA'

    project_id = fields.Many2one(
        'migration.project',
        string='Proyecto',
        required=True,
        ondelete='cascade'
    )

    # Configuración IA
    ai_provider = fields.Selection([
        ('openai', 'OpenAI (GPT-4)'),
        ('claude', 'Anthropic (Claude)'),
        ('heuristic', 'Heurísticas (Sin IA)')
    ], default='heuristic', string='Proveedor IA')

    api_key = fields.Char(string='API Key')

    # Opciones de análisis
    analyze_tables = fields.Boolean(
        default=True,
        string='Analizar Tablas',
        help='Sugerir tópicos para cada tabla'
    )
    analyze_fields = fields.Boolean(
        default=True,
        string='Analizar Campos',
        help='Sugerir mapeo de campos'
    )
    analyze_relationships = fields.Boolean(
        default=True,
        string='Analizar Relaciones',
        help='Detectar y mapear llaves foráneas'
    )
    min_confidence = fields.Float(
        default=0.6,
        string='Confianza Mínima',
        help='Solo mostrar sugerencias con confianza mayor a este valor'
    )

    # Estado del proceso
    state = fields.Selection([
        ('config', 'Configuración'),
        ('analyzing', 'Analizando'),
        ('results', 'Resultados'),
        ('applying', 'Aplicando'),
        ('done', 'Completado')
    ], default='config', string='Estado')

    progress = fields.Float(string='Progreso', default=0)
    current_step = fields.Char(string='Paso Actual')

    # Resultados
    suggestions_count = fields.Integer(string='Sugerencias Generadas')
    tables_analyzed = fields.Integer(string='Tablas Analizadas')
    fields_mapped = fields.Integer(string='Campos Mapeados')
    high_confidence_count = fields.Integer(
        string='Alta Confianza',
        help='Sugerencias con confianza > 80%'
    )
    medium_confidence_count = fields.Integer(
        string='Media Confianza',
        help='Sugerencias con confianza 60-80%'
    )
    low_confidence_count = fields.Integer(
        string='Baja Confianza',
        help='Sugerencias con confianza < 60%'
    )

    # Líneas de sugerencia
    suggestion_ids = fields.One2many(
        'migration.ai.suggestion.line',
        'wizard_id',
        string='Sugerencias'
    )

    results_html = fields.Html(string='Resumen de Resultados')

    def action_start_analysis(self):
        """Iniciar análisis con IA"""
        self.ensure_one()

        self.state = 'analyzing'
        self.progress = 0
        self.current_step = _('Iniciando análisis...')

        try:
            # Obtener servicio de IA
            AIAnalyzer = self.env['migration.ai.analyzer']

            # Configurar proveedor
            if self.ai_provider != 'heuristic' and self.api_key:
                # Guardar API key temporalmente en parámetros
                param_name = f'{self.ai_provider}_api_key'
                self.env['ir.config_parameter'].sudo().set_param(
                    f'migration_hub.{param_name}',
                    self.api_key
                )

            # Obtener mapeos de tabla del proyecto
            table_mappings = self.project_id.table_mapping_ids

            if not table_mappings:
                raise UserError(_('No hay tablas para analizar. Primero debe analizar el esquema.'))

            total_tables = len(table_mappings)
            suggestions_created = 0

            for idx, mapping in enumerate(table_mappings):
                self.progress = (idx / total_tables) * 100
                self.current_step = _('Analizando tabla: %s') % mapping.source_table

                # Analizar tabla
                if self.analyze_tables:
                    topic_suggestion = AIAnalyzer.suggest_topic_for_table(
                        self.project_id,
                        mapping.source_table,
                        mapping.source_schema or {}
                    )

                    if topic_suggestion and topic_suggestion.get('confidence', 0) >= self.min_confidence:
                        self._create_table_suggestion(mapping, topic_suggestion)
                        suggestions_created += 1

                # Analizar campos
                if self.analyze_fields and mapping.topic_id:
                    field_suggestions = AIAnalyzer.suggest_field_mappings(
                        mapping,
                        mapping.source_schema or {}
                    )

                    for field_sug in field_suggestions:
                        if field_sug.get('confidence', 0) >= self.min_confidence:
                            self._create_field_suggestion(mapping, field_sug)
                            suggestions_created += 1

            # Actualizar contadores
            self._compute_statistics()

            self.state = 'results'
            self.progress = 100
            self.current_step = _('Análisis completado')
            self.suggestions_count = suggestions_created

            # Generar HTML de resultados
            self._generate_results_html()

        except Exception as e:
            self.state = 'config'
            _logger.exception("Error en análisis IA")
            raise UserError(_('Error durante el análisis: %s') % str(e))

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _create_table_suggestion(self, mapping, suggestion):
        """Crear sugerencia de tabla"""
        topic = self.env['migration.topic'].browse(suggestion.get('topic_id'))

        self.env['migration.ai.suggestion.line'].create({
            'wizard_id': self.id,
            'suggestion_type': 'table',
            'table_mapping_id': mapping.id,
            'source_name': mapping.source_table,
            'suggested_topic_id': topic.id if topic else False,
            'suggested_value': topic.name if topic else suggestion.get('topic_name', ''),
            'confidence': suggestion.get('confidence', 0),
            'reason': suggestion.get('reason', ''),
            'selected': suggestion.get('confidence', 0) >= 0.8,  # Auto-seleccionar alta confianza
        })

    def _create_field_suggestion(self, mapping, suggestion):
        """Crear sugerencia de campo"""
        self.env['migration.ai.suggestion.line'].create({
            'wizard_id': self.id,
            'suggestion_type': 'field',
            'table_mapping_id': mapping.id,
            'source_name': suggestion.get('source_column', ''),
            'suggested_value': suggestion.get('target_field', ''),
            'suggested_target_field_id': suggestion.get('target_field_id'),
            'confidence': suggestion.get('confidence', 0),
            'reason': suggestion.get('reason', ''),
            'transform_function': suggestion.get('transform', ''),
            'selected': suggestion.get('confidence', 0) >= 0.8,
        })

    def _compute_statistics(self):
        """Calcular estadísticas de sugerencias"""
        suggestions = self.suggestion_ids

        self.tables_analyzed = len(self.project_id.table_mapping_ids)
        self.fields_mapped = len(suggestions.filtered(lambda s: s.suggestion_type == 'field'))

        self.high_confidence_count = len(suggestions.filtered(lambda s: s.confidence >= 0.8))
        self.medium_confidence_count = len(suggestions.filtered(
            lambda s: 0.6 <= s.confidence < 0.8
        ))
        self.low_confidence_count = len(suggestions.filtered(lambda s: s.confidence < 0.6))

    def _generate_results_html(self):
        """Generar HTML con resumen de resultados"""
        high = self.high_confidence_count
        medium = self.medium_confidence_count
        low = self.low_confidence_count
        total = high + medium + low

        self.results_html = f"""
        <div class="o_ai_results">
            <div class="row">
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <h2 class="text-primary">{total}</h2>
                            <p>Total Sugerencias</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <h2 class="text-success">{high}</h2>
                            <p>Alta Confianza (&gt;80%)</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <h2 class="text-warning">{medium}</h2>
                            <p>Media Confianza (60-80%)</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <h2 class="text-danger">{low}</h2>
                            <p>Baja Confianza (&lt;60%)</p>
                        </div>
                    </div>
                </div>
            </div>
            <hr/>
            <p class="text-muted">
                Las sugerencias con alta confianza han sido pre-seleccionadas.
                Revise y ajuste las sugerencias antes de aplicarlas.
            </p>
        </div>
        """

    def action_apply_selected(self):
        """Aplicar sugerencias seleccionadas"""
        self.ensure_one()

        self.state = 'applying'
        selected = self.suggestion_ids.filtered(lambda s: s.selected)

        if not selected:
            raise UserError(_('No hay sugerencias seleccionadas para aplicar'))

        applied_count = 0

        for sug in selected:
            try:
                if sug.suggestion_type == 'table':
                    self._apply_table_suggestion(sug)
                else:
                    self._apply_field_suggestion(sug)
                applied_count += 1
            except Exception as e:
                _logger.warning(f"Error aplicando sugerencia {sug.id}: {e}")

        self.state = 'done'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sugerencias Aplicadas'),
                'message': _('%d sugerencias aplicadas exitosamente') % applied_count,
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def _apply_table_suggestion(self, suggestion):
        """Aplicar sugerencia de tabla"""
        mapping = suggestion.table_mapping_id
        if suggestion.suggested_topic_id:
            mapping.write({
                'suggested_topic_id': suggestion.suggested_topic_id.id,
                'ai_confidence': suggestion.confidence,
                'ai_reason': suggestion.reason,
            })

    def _apply_field_suggestion(self, suggestion):
        """Aplicar sugerencia de campo"""
        mapping = suggestion.table_mapping_id

        # Buscar o crear mapeo de campo
        field_mapping = self.env['migration.field.mapping'].search([
            ('table_mapping_id', '=', mapping.id),
            ('source_column', '=', suggestion.source_name)
        ], limit=1)

        values = {
            'target_field_id': suggestion.suggested_target_field_id,
            'ai_confidence': suggestion.confidence,
            'ai_reason': suggestion.reason,
        }

        if suggestion.transform_function:
            values['mapping_type'] = 'transform'
            values['transform_function'] = suggestion.transform_function

        if field_mapping:
            field_mapping.write(values)
        else:
            values.update({
                'table_mapping_id': mapping.id,
                'source_column': suggestion.source_name,
            })
            self.env['migration.field.mapping'].create(values)

    def action_select_all_high(self):
        """Seleccionar todas las sugerencias de alta confianza"""
        self.suggestion_ids.filtered(lambda s: s.confidence >= 0.8).write({'selected': True})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_deselect_all(self):
        """Deseleccionar todas las sugerencias"""
        self.suggestion_ids.write({'selected': False})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class AISuggestionLine(models.TransientModel):
    """Línea de sugerencia de IA"""
    _name = 'migration.ai.suggestion.line'
    _description = 'Línea de Sugerencia IA'
    _order = 'confidence desc'

    wizard_id = fields.Many2one(
        'migration.ai.mapping.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )

    suggestion_type = fields.Selection([
        ('table', 'Tabla/Tópico'),
        ('field', 'Campo')
    ], required=True, string='Tipo')

    table_mapping_id = fields.Many2one(
        'migration.table.mapping',
        string='Mapeo de Tabla'
    )

    source_name = fields.Char(string='Origen', required=True)
    suggested_value = fields.Char(string='Sugerencia')

    suggested_topic_id = fields.Many2one(
        'migration.topic',
        string='Tópico Sugerido'
    )

    suggested_target_field_id = fields.Many2one(
        'ir.model.fields',
        string='Campo Destino Sugerido'
    )

    transform_function = fields.Char(string='Transformación')

    confidence = fields.Float(string='Confianza')
    confidence_display = fields.Char(
        string='Confianza',
        compute='_compute_confidence_display'
    )

    reason = fields.Text(string='Razón')
    selected = fields.Boolean(default=False, string='Aplicar')

    @api.depends('confidence')
    def _compute_confidence_display(self):
        for rec in self:
            pct = int(rec.confidence * 100)
            if pct >= 80:
                rec.confidence_display = f"🟢 {pct}%"
            elif pct >= 60:
                rec.confidence_display = f"🟡 {pct}%"
            else:
                rec.confidence_display = f"🔴 {pct}%"
