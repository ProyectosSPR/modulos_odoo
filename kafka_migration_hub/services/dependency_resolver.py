# -*- coding: utf-8 -*-

from odoo import models, api
from collections import defaultdict, deque
import logging

_logger = logging.getLogger(__name__)


class MigrationDependencyResolver(models.AbstractModel):
    _name = 'migration.dependency.resolver'
    _description = 'Resolutor de Dependencias para Migración'

    @api.model
    def build_dependency_graph(self, project):
        """
        Construir grafo de dependencias para las tablas mapeadas.
        Retorna un orden topológico para la migración.
        """
        graph = defaultdict(list)  # modelo -> [dependencias]
        in_degree = defaultdict(int)  # modelo -> cantidad de dependencias entrantes

        # Obtener todos los mapeos del proyecto
        mappings = project.table_mapping_ids.filtered(lambda m: m.state == 'mapped')

        if not mappings:
            return []

        # Modelos involucrados
        models_in_project = set()
        for mapping in mappings:
            if mapping.target_model:
                models_in_project.add(mapping.target_model)

        # Construir grafo basándose en campos Many2one
        for mapping in mappings:
            target_model = mapping.target_model
            if not target_model:
                continue

            # Obtener dependencias (campos Many2one)
            dependencies = self._get_model_dependencies(target_model)

            for dep in dependencies:
                dep_model = dep['relation']

                # Solo considerar dependencias que están en el proyecto
                if dep_model in models_in_project:
                    graph[dep_model].append(target_model)
                    in_degree[target_model] += 1

            # Asegurar que el modelo está en el grafo
            if target_model not in in_degree:
                in_degree[target_model] = 0

        # Ordenamiento topológico (Kahn's algorithm)
        order = []
        queue = deque([m for m in models_in_project if in_degree[m] == 0])

        while queue:
            model = queue.popleft()
            order.append(model)

            for dependent in graph[model]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # Verificar ciclos
        if len(order) != len(models_in_project):
            _logger.warning('Ciclo detectado en dependencias, usando orden parcial')
            # Agregar modelos faltantes al final
            remaining = models_in_project - set(order)
            order.extend(remaining)

        # Convertir a lista de mapeos ordenados
        ordered_mappings = []
        for model in order:
            mapping = mappings.filtered(lambda m: m.target_model == model)
            if mapping:
                ordered_mappings.append(mapping[0])

        return ordered_mappings

    def _get_model_dependencies(self, model_name):
        """Obtener dependencias de un modelo (campos Many2one requeridos)"""
        fields_data = self.env['ir.model.fields'].search([
            ('model', '=', model_name),
            ('ttype', '=', 'many2one'),
            ('store', '=', True),
        ])

        dependencies = []
        for f in fields_data:
            if f.relation:
                dependencies.append({
                    'field': f.name,
                    'relation': f.relation,
                    'required': f.required,
                })

        return dependencies

    @api.model
    def get_migration_order(self, project):
        """
        Obtener orden de migración optimizado.
        Retorna lista de diccionarios con información de cada paso.
        """
        ordered_mappings = self.build_dependency_graph(project)

        migration_order = []
        for idx, mapping in enumerate(ordered_mappings, 1):
            dependencies = []
            if mapping.target_model:
                deps = self._get_model_dependencies(mapping.target_model)
                # Solo mostrar dependencias que están en el proyecto
                project_models = set(project.table_mapping_ids.mapped('target_model'))
                dependencies = [d for d in deps if d['relation'] in project_models]

            migration_order.append({
                'sequence': idx,
                'mapping_id': mapping.id,
                'source_table': mapping.source_table,
                'target_model': mapping.target_model,
                'row_count': mapping.row_count,
                'dependencies': dependencies,
                'topic': mapping.topic_id.name if mapping.topic_id else None,
            })

        return migration_order

    @api.model
    def validate_dependencies(self, project):
        """
        Validar que todas las dependencias pueden ser resueltas.
        Retorna lista de problemas encontrados.
        """
        issues = []
        mappings = project.table_mapping_ids.filtered(lambda m: m.state == 'mapped')
        project_models = set(mappings.mapped('target_model'))

        for mapping in mappings:
            if not mapping.target_model:
                continue

            deps = self._get_model_dependencies(mapping.target_model)

            for dep in deps:
                if dep['required'] and dep['relation'] not in project_models:
                    # Verificar si el modelo ya tiene datos en Odoo
                    try:
                        count = self.env[dep['relation']].search_count([])
                        if count == 0:
                            issues.append({
                                'type': 'missing_dependency',
                                'mapping_id': mapping.id,
                                'source_table': mapping.source_table,
                                'target_model': mapping.target_model,
                                'missing_model': dep['relation'],
                                'field': dep['field'],
                                'message': f"El modelo {dep['relation']} es requerido por {mapping.target_model}.{dep['field']} pero no está en el proyecto y no tiene datos en Odoo",
                            })
                    except Exception:
                        pass

        return issues

    @api.model
    def suggest_missing_dependencies(self, project):
        """
        Sugerir tablas adicionales a migrar basándose en dependencias.
        """
        suggestions = []
        mappings = project.table_mapping_ids.filtered(lambda m: m.state == 'mapped')
        project_models = set(mappings.mapped('target_model'))

        analyzed_models = set()

        for mapping in mappings:
            if not mapping.target_model:
                continue

            deps = self._get_model_dependencies(mapping.target_model)

            for dep in deps:
                if dep['relation'] in project_models:
                    continue  # Ya está en el proyecto
                if dep['relation'] in analyzed_models:
                    continue  # Ya analizado

                analyzed_models.add(dep['relation'])

                # Verificar si podemos encontrar una tabla origen para esta dependencia
                # Buscar en el catálogo de tópicos
                topic = self.env['migration.topic'].search([
                    ('model_ids.model', '=', dep['relation'])
                ], limit=1)

                suggestions.append({
                    'required_by': mapping.target_model,
                    'field': dep['field'],
                    'required': dep['required'],
                    'missing_model': dep['relation'],
                    'suggested_topic': topic.name if topic else None,
                    'topic_id': topic.id if topic else None,
                })

        return suggestions
