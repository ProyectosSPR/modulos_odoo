# -*- coding: utf-8 -*-
"""
Analizador de Modelos Odoo
Detecta automáticamente relaciones, dependencias y orden de migración
"""

from odoo import models, api, _
from collections import defaultdict
import logging

_logger = logging.getLogger(__name__)


class OdooModelAnalyzer(models.AbstractModel):
    _name = 'migration.odoo.model.analyzer'
    _description = 'Analizador de Modelos y Relaciones de Odoo'

    # Modelos principales por categoría
    CORE_MODELS = {
        'Contactos': {
            'main': 'res.partner',
            'related': ['res.partner.category', 'res.partner.title', 'res.partner.bank'],
        },
        'Productos': {
            'main': 'product.template',
            'related': ['product.product', 'product.category', 'product.pricelist',
                       'product.pricelist.item', 'uom.uom', 'uom.category'],
        },
        'Ventas': {
            'main': 'sale.order',
            'related': ['sale.order.line', 'sale.order.template', 'sale.order.template.line'],
        },
        'Compras': {
            'main': 'purchase.order',
            'related': ['purchase.order.line'],
        },
        'Facturación': {
            'main': 'account.move',
            'related': ['account.move.line', 'account.payment', 'account.payment.term'],
        },
        'Contabilidad': {
            'main': 'account.account',
            'related': ['account.journal', 'account.tax', 'account.tax.group',
                       'account.fiscal.position', 'account.analytic.account'],
        },
        'Inventario': {
            'main': 'stock.quant',
            'related': ['stock.warehouse', 'stock.location', 'stock.picking',
                       'stock.picking.type', 'stock.move', 'stock.move.line'],
        },
        'CRM': {
            'main': 'crm.lead',
            'related': ['crm.stage', 'crm.tag', 'crm.team'],
        },
        'Recursos Humanos': {
            'main': 'hr.employee',
            'related': ['hr.department', 'hr.job', 'hr.contract'],
        },
        'Configuración': {
            'main': 'res.company',
            'related': ['res.country', 'res.country.state', 'res.currency',
                       'res.users', 'res.groups', 'res.lang'],
        },
    }

    @api.model
    def get_model_info(self, model_name):
        """
        Obtener información completa de un modelo Odoo
        Incluye campos, relaciones y dependencias
        """
        IrModel = self.env['ir.model']
        IrModelFields = self.env['ir.model.fields']

        model = IrModel.search([('model', '=', model_name)], limit=1)
        if not model:
            return None

        # Obtener campos
        fields = IrModelFields.search([
            ('model_id', '=', model.id),
            ('store', '=', True),
        ])

        # Clasificar campos
        field_info = {
            'all': [],
            'many2one': [],      # FK salientes (este modelo depende de...)
            'one2many': [],      # FK entrantes (otros modelos dependen de este)
            'many2many': [],     # Relaciones M2M
            'regular': [],       # Campos normales
        }

        dependencies = set()     # Modelos de los que depende
        dependents = set()       # Modelos que dependen de este

        for field in fields:
            field_data = {
                'name': field.name,
                'type': field.ttype,
                'string': field.field_description,
                'required': field.required,
                'relation': field.relation,
                'relation_field': field.relation_field,
            }
            field_info['all'].append(field_data)

            if field.ttype == 'many2one' and field.relation:
                field_info['many2one'].append(field_data)
                dependencies.add(field.relation)

            elif field.ttype == 'one2many' and field.relation:
                field_info['one2many'].append(field_data)
                dependents.add(field.relation)

            elif field.ttype == 'many2many' and field.relation:
                field_info['many2many'].append(field_data)

            else:
                field_info['regular'].append(field_data)

        # Buscar modelos que tienen FK hacia este modelo
        reverse_fks = IrModelFields.search([
            ('ttype', '=', 'many2one'),
            ('relation', '=', model_name),
            ('store', '=', True),
        ])

        for fk in reverse_fks:
            dependents.add(fk.model)

        return {
            'model': model_name,
            'name': model.name,
            'table': model.model.replace('.', '_'),
            'fields': field_info,
            'field_count': len(field_info['all']),
            'dependencies': list(dependencies - {model_name}),  # Excluir self-references
            'dependents': list(dependents - {model_name}),
            'has_dependencies': len(dependencies) > 0,
        }

    @api.model
    def get_model_dependencies_graph(self, model_names):
        """
        Construir grafo de dependencias para una lista de modelos
        Retorna orden de migración óptimo
        """
        graph = {}
        all_models = set(model_names)

        # Construir grafo
        for model_name in model_names:
            info = self.get_model_info(model_name)
            if info:
                # Solo incluir dependencias que están en nuestra lista
                deps = [d for d in info['dependencies'] if d in all_models]
                graph[model_name] = {
                    'dependencies': deps,
                    'info': info,
                }

        # Ordenamiento topológico
        order = self._topological_sort(graph)

        return {
            'graph': graph,
            'migration_order': order,
            'total_models': len(model_names),
        }

    def _topological_sort(self, graph):
        """Ordenamiento topológico para determinar orden de migración"""
        from collections import deque

        # Calcular in-degree
        in_degree = {node: 0 for node in graph}
        for node, data in graph.items():
            for dep in data['dependencies']:
                if dep in in_degree:
                    in_degree[dep] = in_degree.get(dep, 0)

        for node, data in graph.items():
            for dep in data['dependencies']:
                if dep in graph:
                    in_degree[node] += 1

        # Cola con nodos sin dependencias
        queue = deque([n for n in graph if in_degree[n] == 0])
        order = []
        priority = 1

        while queue:
            node = queue.popleft()
            order.append({
                'model': node,
                'priority': priority,
                'dependencies': graph[node]['dependencies'],
            })
            priority += 1

            # Reducir in-degree de dependientes
            for other_node, data in graph.items():
                if node in data['dependencies']:
                    in_degree[other_node] -= 1
                    if in_degree[other_node] == 0:
                        queue.append(other_node)

        # Agregar nodos con ciclos al final
        remaining = set(graph.keys()) - {o['model'] for o in order}
        for node in remaining:
            order.append({
                'model': node,
                'priority': priority,
                'dependencies': graph[node]['dependencies'],
                'has_cycle': True,
            })
            priority += 1

        return order

    @api.model
    def get_category_models(self, category_name):
        """
        Obtener todos los modelos de una categoría con sus relaciones
        """
        if category_name not in self.CORE_MODELS:
            return None

        category = self.CORE_MODELS[category_name]
        models_list = [category['main']] + category.get('related', [])

        result = {
            'category': category_name,
            'main_model': category['main'],
            'models': [],
        }

        for model_name in models_list:
            info = self.get_model_info(model_name)
            if info:
                result['models'].append(info)

        # Obtener orden de migración
        dep_graph = self.get_model_dependencies_graph(models_list)
        result['migration_order'] = dep_graph['migration_order']

        return result

    @api.model
    def analyze_all_categories(self):
        """
        Analizar todas las categorías y sus modelos
        Retorna estructura completa para poblar tópicos
        """
        analysis = []

        for category_name in self.CORE_MODELS.keys():
            category_data = self.get_category_models(category_name)
            if category_data:
                analysis.append(category_data)

        return analysis

    @api.model
    def compare_schemas(self, source_tables, target_model):
        """
        Comparar esquema de tablas origen con modelo Odoo destino
        Sugiere mapeos de campos
        """
        target_info = self.get_model_info(target_model)
        if not target_info:
            return None

        target_fields = {f['name'].lower(): f for f in target_info['fields']['all']}

        mappings = []
        for source_table in source_tables:
            table_mappings = {
                'source_table': source_table['name'],
                'target_model': target_model,
                'field_mappings': [],
                'unmapped_source': [],
                'unmapped_target': list(target_fields.keys()),
            }

            for source_col in source_table.get('columns', []):
                source_name = source_col.get('name', '').lower()

                # Buscar coincidencia exacta
                if source_name in target_fields:
                    table_mappings['field_mappings'].append({
                        'source': source_col['name'],
                        'target': target_fields[source_name]['name'],
                        'confidence': 100,
                        'match_type': 'exact',
                    })
                    if source_name in table_mappings['unmapped_target']:
                        table_mappings['unmapped_target'].remove(source_name)

                # Buscar coincidencia sin guiones bajos
                elif source_name.replace('_', '') in [k.replace('_', '') for k in target_fields]:
                    for target_name, target_field in target_fields.items():
                        if source_name.replace('_', '') == target_name.replace('_', ''):
                            table_mappings['field_mappings'].append({
                                'source': source_col['name'],
                                'target': target_field['name'],
                                'confidence': 90,
                                'match_type': 'similar',
                            })
                            if target_name in table_mappings['unmapped_target']:
                                table_mappings['unmapped_target'].remove(target_name)
                            break

                # Buscar por palabras clave comunes
                else:
                    mapped = self._find_keyword_match(source_name, target_fields)
                    if mapped:
                        table_mappings['field_mappings'].append({
                            'source': source_col['name'],
                            'target': mapped['name'],
                            'confidence': mapped['confidence'],
                            'match_type': 'keyword',
                        })
                        if mapped['name'].lower() in table_mappings['unmapped_target']:
                            table_mappings['unmapped_target'].remove(mapped['name'].lower())
                    else:
                        table_mappings['unmapped_source'].append(source_col['name'])

            mappings.append(table_mappings)

        return mappings

    def _find_keyword_match(self, source_name, target_fields):
        """Buscar coincidencia por palabras clave comunes"""
        keyword_mappings = {
            # Nombres/Descripciones
            ('nombre', 'name', 'descripcion', 'description', 'titulo', 'title'): 'name',
            # Email
            ('email', 'correo', 'mail', 'e_mail'): 'email',
            # Teléfono
            ('telefono', 'phone', 'tel', 'fono'): 'phone',
            ('celular', 'mobile', 'movil', 'cel'): 'mobile',
            # Dirección
            ('direccion', 'address', 'calle', 'street'): 'street',
            ('ciudad', 'city', 'localidad'): 'city',
            ('codigo_postal', 'zip', 'cp', 'postal'): 'zip',
            # Identificación
            ('rfc', 'vat', 'nit', 'ruc', 'tax_id', 'cuit'): 'vat',
            # Fechas
            ('fecha_creacion', 'created', 'create_date', 'fecha_alta'): 'create_date',
            ('fecha_modificacion', 'updated', 'write_date', 'fecha_mod'): 'write_date',
            # Precios
            ('precio', 'price', 'costo', 'cost', 'importe'): 'list_price',
            ('cantidad', 'qty', 'quantity', 'cant'): 'product_uom_qty',
            # Referencias
            ('codigo', 'code', 'sku', 'referencia', 'ref'): 'default_code',
            # Estado
            ('activo', 'active', 'enabled', 'habilitado'): 'active',
        }

        source_lower = source_name.lower().replace('_', '')

        for keywords, target_name in keyword_mappings.items():
            for kw in keywords:
                if kw in source_lower or source_lower in kw:
                    if target_name in target_fields:
                        return {
                            'name': target_name,
                            'confidence': 70,
                        }

        return None

    @api.model
    def get_full_dependency_tree(self, model_name, depth=3, visited=None):
        """
        Obtener árbol completo de dependencias de un modelo
        """
        if visited is None:
            visited = set()

        if model_name in visited or depth <= 0:
            return None

        visited.add(model_name)
        info = self.get_model_info(model_name)

        if not info:
            return None

        tree = {
            'model': model_name,
            'name': info['name'],
            'field_count': info['field_count'],
            'depends_on': [],
            'required_by': [],
        }

        # Dependencias (modelos que necesito migrar primero)
        for dep in info['dependencies'][:10]:  # Limitar para no explotar
            dep_tree = self.get_full_dependency_tree(dep, depth - 1, visited.copy())
            if dep_tree:
                tree['depends_on'].append(dep_tree)

        # Dependientes (modelos que me necesitan)
        for dep in info['dependents'][:10]:
            tree['required_by'].append({
                'model': dep,
                'name': self.get_model_info(dep)['name'] if self.get_model_info(dep) else dep,
            })

        return tree
