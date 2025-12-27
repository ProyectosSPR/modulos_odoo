# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)


class MigrationTopic(models.Model):
    _name = 'migration.topic'
    _description = 'Tópico de Migración'
    _order = 'sequence, name'

    name = fields.Char(
        string='Nombre',
        required=True,
        translate=True,
    )
    icon = fields.Char(
        string='Icono',
        default='📦',
        help='Emoji o icono para identificar el tópico',
    )
    description = fields.Text(
        string='Descripción',
        translate=True,
    )
    color = fields.Integer(string='Color')

    # Modelos de Odoo asociados a este tópico
    model_ids = fields.Many2many(
        'ir.model',
        'migration_topic_model_rel',
        'topic_id',
        'model_id',
        string='Modelos Odoo',
        domain=[('transient', '=', False)],
        help='Modelos de Odoo que pertenecen a este tópico',
    )

    # Palabras clave para que la IA identifique este tópico
    keywords = fields.Char(
        string='Palabras Clave',
        help='Palabras separadas por coma que ayudan a la IA a identificar este tópico',
    )
    keywords_list = fields.Text(
        string='Lista de Keywords',
        compute='_compute_keywords_list',
        inverse='_inverse_keywords_list',
    )

    # Tipo de tópico
    is_system_template = fields.Boolean(
        string='Plantilla del Sistema',
        default=False,
        help='Las plantillas del sistema no pueden ser eliminadas',
    )

    # Secuencia para orden de migración
    sequence = fields.Integer(
        string='Secuencia',
        default=10,
        help='Orden en que se deben migrar los tópicos (menor = primero)',
    )

    # Dependencias
    depends_on_topic_ids = fields.Many2many(
        'migration.topic',
        'migration_topic_dependency_rel',
        'topic_id',
        'depends_on_id',
        string='Depende de',
        help='Tópicos que deben migrarse antes que este',
    )

    # Configuración avanzada
    batch_size = fields.Integer(
        string='Tamaño de Lote',
        default=100,
        help='Cantidad de registros a procesar por lote',
    )
    priority = fields.Selection([
        ('low', 'Baja'),
        ('medium', 'Media'),
        ('high', 'Alta'),
    ], string='Prioridad', default='medium')

    # Compañía (para multi-company)
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        help='Dejar vacío para que sea global',
    )

    # Estadísticas
    model_count = fields.Integer(
        string='Cantidad de Modelos',
        compute='_compute_model_count',
    )

    @api.depends('keywords')
    def _compute_keywords_list(self):
        for record in self:
            if record.keywords:
                keywords = [k.strip() for k in record.keywords.split(',')]
                record.keywords_list = json.dumps(keywords)
            else:
                record.keywords_list = '[]'

    def _inverse_keywords_list(self):
        for record in self:
            if record.keywords_list:
                try:
                    keywords = json.loads(record.keywords_list)
                    record.keywords = ', '.join(keywords)
                except json.JSONDecodeError:
                    pass

    @api.depends('model_ids')
    def _compute_model_count(self):
        for record in self:
            record.model_count = len(record.model_ids)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_system_template(self):
        for record in self:
            if record.is_system_template:
                raise UserError(_(
                    'No puede eliminar la plantilla del sistema "%s". '
                    'Puede desactivarla o crear una personalizada.'
                ) % record.name)

    def get_models_info(self):
        """Obtener información detallada de los modelos del tópico"""
        self.ensure_one()
        result = []
        for model in self.model_ids:
            # Obtener campos del modelo
            fields_info = self.env['ir.model.fields'].search([
                ('model_id', '=', model.id),
                ('store', '=', True),
            ])

            result.append({
                'id': model.id,
                'model': model.model,
                'name': model.name,
                'field_count': len(fields_info),
                'fields': [{
                    'name': f.name,
                    'type': f.ttype,
                    'relation': f.relation,
                    'required': f.required,
                } for f in fields_info[:20]],  # Limitar a 20 campos
            })

        return result

    def match_keywords(self, text):
        """Verificar si el texto coincide con las keywords del tópico"""
        self.ensure_one()
        if not self.keywords:
            return 0

        text_lower = text.lower()
        keywords = [k.strip().lower() for k in self.keywords.split(',')]

        matches = sum(1 for kw in keywords if kw in text_lower)
        return matches / len(keywords) * 100 if keywords else 0

    @api.model
    def get_topics_for_portal(self, company_id=None):
        """Obtener tópicos disponibles para el portal"""
        domain = ['|', ('company_id', '=', False), ('company_id', '=', company_id)]
        topics = self.search(domain, order='sequence')

        return [{
            'id': t.id,
            'name': t.name,
            'icon': t.icon,
            'description': t.description,
            'model_count': t.model_count,
            'is_system': t.is_system_template,
            'models': [{'id': m.id, 'name': m.name, 'model': m.model} for m in t.model_ids],
        } for t in topics]

    @api.model
    def suggest_topic_for_table(self, table_name, column_names):
        """Sugerir el tópico más adecuado para una tabla basándose en keywords"""
        # Crear texto para búsqueda
        search_text = f"{table_name} {' '.join(column_names)}"

        topics = self.search([])
        best_match = None
        best_score = 0

        for topic in topics:
            score = topic.match_keywords(search_text)
            if score > best_score:
                best_score = score
                best_match = topic

        if best_match and best_score > 20:  # Umbral mínimo 20%
            return {
                'topic_id': best_match.id,
                'topic_name': best_match.name,
                'confidence': best_score,
            }

        return None

    def action_auto_populate_models(self):
        """Poblar automáticamente los modelos basado en el analizador"""
        self.ensure_one()
        Analyzer = self.env['migration.odoo.model.analyzer']
        IrModel = self.env['ir.model']

        # Obtener modelos de la categoría
        category_data = Analyzer.get_category_models(self.name)

        if not category_data:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin datos'),
                    'message': _('No se encontró configuración para "%s"') % self.name,
                    'type': 'warning',
                }
            }

        # Buscar y agregar modelos
        added_models = []
        for model_info in category_data['models']:
            model = IrModel.search([('model', '=', model_info['model'])], limit=1)
            if model and model not in self.model_ids:
                self.model_ids = [(4, model.id)]
                added_models.append(model_info['model'])

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Modelos agregados'),
                'message': _('Se agregaron %d modelos: %s') % (len(added_models), ', '.join(added_models[:5])),
                'type': 'success',
            }
        }

    def get_dependency_tree(self):
        """Obtener árbol de dependencias del tópico"""
        self.ensure_one()
        Analyzer = self.env['migration.odoo.model.analyzer']

        model_names = [m.model for m in self.model_ids]
        if not model_names:
            return {'models': [], 'migration_order': []}

        return Analyzer.get_model_dependencies_graph(model_names)

    def get_models_with_dependencies(self):
        """Obtener modelos con información de dependencias"""
        self.ensure_one()
        Analyzer = self.env['migration.odoo.model.analyzer']

        result = []
        for model in self.model_ids:
            info = Analyzer.get_model_info(model.model)
            if info:
                result.append({
                    'id': model.id,
                    'model': model.model,
                    'name': model.name,
                    'table': info['table'],
                    'field_count': info['field_count'],
                    'dependencies': info['dependencies'],
                    'dependents': info['dependents'],
                    'many2one_fields': info['fields']['many2one'],
                    'one2many_fields': info['fields']['one2many'],
                })

        return result

    @api.model
    def action_refresh_all_topics(self):
        """Actualizar todos los tópicos con modelos del analizador"""
        Analyzer = self.env['migration.odoo.model.analyzer']
        IrModel = self.env['ir.model']

        for category_name, category_config in Analyzer.CORE_MODELS.items():
            # Buscar o crear tópico
            topic = self.search([('name', '=', category_name)], limit=1)

            if not topic:
                continue  # Solo actualizar existentes, no crear nuevos

            # Agregar modelos
            all_models = [category_config['main']] + category_config.get('related', [])

            for model_name in all_models:
                model = IrModel.search([('model', '=', model_name)], limit=1)
                if model and model not in topic.model_ids:
                    topic.model_ids = [(4, model.id)]

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Tópicos actualizados'),
                'message': _('Se actualizaron los modelos de todos los tópicos'),
                'type': 'success',
            }
        }


class MigrationTopicModelInfo(models.Model):
    """Información adicional de modelos en un tópico"""
    _name = 'migration.topic.model.info'
    _description = 'Información de Modelo en Tópico'

    topic_id = fields.Many2one(
        'migration.topic',
        string='Tópico',
        required=True,
        ondelete='cascade',
    )
    model_id = fields.Many2one(
        'ir.model',
        string='Modelo',
        required=True,
        ondelete='cascade',
    )
    model_name = fields.Char(
        related='model_id.model',
        string='Nombre Técnico',
    )

    # Configuración específica del modelo en este tópico
    is_primary = fields.Boolean(
        string='Es Primario',
        default=False,
        help='El modelo principal del tópico',
    )
    sequence = fields.Integer(
        string='Secuencia',
        default=10,
    )

    # Campos clave para identificar
    key_fields = fields.Char(
        string='Campos Clave',
        help='Campos importantes para identificar registros (separados por coma)',
    )

    # Dependencias específicas
    depends_on_model_ids = fields.Many2many(
        'ir.model',
        'migration_topic_model_dep_rel',
        'info_id',
        'model_id',
        string='Depende de Modelos',
    )
