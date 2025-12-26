# -*- coding: utf-8 -*-

from odoo import models, api, fields
import logging

_logger = logging.getLogger(__name__)


class MigrationOdooCatalog(models.AbstractModel):
    _name = 'migration.odoo.catalog'
    _description = 'Catálogo Dinámico de Estructura Odoo'

    @api.model
    def get_odoo_version(self):
        """Obtener versión de Odoo actual"""
        base_module = self.env['ir.module.module'].search([
            ('name', '=', 'base')
        ], limit=1)
        return base_module.latest_version if base_module else 'Unknown'

    @api.model
    def get_installed_modules(self):
        """Obtener lista de módulos instalados"""
        modules = self.env['ir.module.module'].search([
            ('state', '=', 'installed')
        ])
        return [{
            'name': m.name,
            'shortdesc': m.shortdesc,
            'version': m.latest_version,
        } for m in modules]

    @api.model
    def get_all_models(self, include_transient=False):
        """Obtener todos los modelos de Odoo"""
        domain = []
        if not include_transient:
            domain.append(('transient', '=', False))

        models = self.env['ir.model'].search(domain, order='model')

        return [{
            'id': m.id,
            'model': m.model,
            'name': m.name,
            'transient': m.transient,
            'field_count': len(m.field_id),
        } for m in models]

    @api.model
    def get_model_fields(self, model_name):
        """Obtener campos de un modelo específico"""
        model = self.env['ir.model'].search([('model', '=', model_name)], limit=1)
        if not model:
            return []

        fields_data = self.env['ir.model.fields'].search([
            ('model_id', '=', model.id),
            ('store', '=', True),
        ], order='name')

        return [{
            'id': f.id,
            'name': f.name,
            'field_description': f.field_description,
            'ttype': f.ttype,
            'relation': f.relation,
            'required': f.required,
            'readonly': f.readonly,
            'selection': f.selection if f.ttype == 'selection' else None,
        } for f in fields_data]

    @api.model
    def get_model_dependencies(self, model_name):
        """Obtener dependencias de un modelo (campos Many2one)"""
        fields_data = self.env['ir.model.fields'].search([
            ('model', '=', model_name),
            ('ttype', '=', 'many2one'),
            ('store', '=', True),
        ])

        dependencies = []
        for f in fields_data:
            if f.relation and f.relation not in ('res.users',):  # Excluir algunos modelos comunes
                dependencies.append({
                    'field': f.name,
                    'relation': f.relation,
                    'required': f.required,
                })

        return dependencies

    @api.model
    def get_models_by_app(self):
        """Agrupar modelos por aplicación/módulo"""
        models = self.env['ir.model'].search([
            ('transient', '=', False)
        ])

        apps = {}
        for m in models:
            # Determinar la app basándose en el nombre del modelo
            parts = m.model.split('.')
            app = parts[0] if parts else 'base'

            if app not in apps:
                apps[app] = []
            apps[app].append({
                'id': m.id,
                'model': m.model,
                'name': m.name,
            })

        return apps

    @api.model
    def scan_and_update_structure(self):
        """
        Escanear la estructura de Odoo y actualizar los tópicos.
        Llamado al instalar el módulo o manualmente.
        """
        _logger.info('Escaneando estructura de Odoo...')

        version = self.get_odoo_version()
        models_count = len(self.get_all_models())
        modules = self.get_installed_modules()

        _logger.info(f'Odoo {version} - {models_count} modelos - {len(modules)} módulos')

        # Crear/actualizar tópicos predefinidos basados en módulos instalados
        self._create_default_topics()

        return {
            'version': version,
            'models_count': models_count,
            'modules_count': len(modules),
        }

    def _create_default_topics(self):
        """Crear tópicos predefinidos basados en módulos instalados"""
        topic_model = self.env['migration.topic']

        # Definición de tópicos base
        default_topics = [
            {
                'name': 'Contactos',
                'icon': '👥',
                'keywords': 'customer,client,vendor,supplier,contact,partner,cliente,proveedor,contacto',
                'models': ['res.partner', 'res.partner.category', 'res.partner.bank'],
                'sequence': 1,
            },
            {
                'name': 'Productos',
                'icon': '📦',
                'keywords': 'product,item,article,producto,articulo,sku,material',
                'models': ['product.template', 'product.product', 'product.category'],
                'sequence': 2,
            },
            {
                'name': 'Ventas',
                'icon': '🛒',
                'keywords': 'sale,order,quote,venta,pedido,cotizacion,presupuesto',
                'models': ['sale.order', 'sale.order.line'],
                'sequence': 3,
            },
            {
                'name': 'Compras',
                'icon': '🛍️',
                'keywords': 'purchase,compra,procurement,orden compra,po',
                'models': ['purchase.order', 'purchase.order.line'],
                'sequence': 4,
            },
            {
                'name': 'Facturación',
                'icon': '🧾',
                'keywords': 'invoice,bill,factura,nota,credit,debit,documento,comprobante',
                'models': ['account.move', 'account.move.line', 'account.payment'],
                'sequence': 5,
            },
            {
                'name': 'Contabilidad',
                'icon': '💰',
                'keywords': 'account,ledger,cuenta,puc,chart,journal,diario,tax,impuesto',
                'models': ['account.account', 'account.journal', 'account.tax'],
                'sequence': 6,
            },
            {
                'name': 'Inventario',
                'icon': '📋',
                'keywords': 'stock,inventory,warehouse,almacen,existencia,bodega',
                'models': ['stock.warehouse', 'stock.location', 'stock.quant', 'stock.move'],
                'sequence': 7,
            },
            {
                'name': 'CRM',
                'icon': '📊',
                'keywords': 'lead,opportunity,crm,oportunidad,prospecto,pipeline',
                'models': ['crm.lead', 'crm.stage'],
                'sequence': 8,
            },
            {
                'name': 'Recursos Humanos',
                'icon': '👔',
                'keywords': 'employee,hr,rrhh,empleado,nomina,payroll',
                'models': ['hr.employee', 'hr.department', 'hr.job'],
                'sequence': 9,
            },
        ]

        for topic_data in default_topics:
            # Verificar si ya existe
            existing = topic_model.search([
                ('name', '=', topic_data['name']),
                ('is_system_template', '=', True),
            ], limit=1)

            if existing:
                continue  # Ya existe, no duplicar

            # Buscar modelos que existen en esta instalación
            model_ids = []
            for model_name in topic_data['models']:
                model = self.env['ir.model'].search([('model', '=', model_name)], limit=1)
                if model:
                    model_ids.append(model.id)

            if model_ids:  # Solo crear si hay al menos un modelo
                topic_model.create({
                    'name': topic_data['name'],
                    'icon': topic_data['icon'],
                    'keywords': topic_data['keywords'],
                    'model_ids': [(6, 0, model_ids)],
                    'sequence': topic_data['sequence'],
                    'is_system_template': True,
                })
                _logger.info(f'Tópico creado: {topic_data["name"]}')

    @api.model
    def compare_with_source(self, source_model_name, source_fields):
        """
        Comparar un modelo origen con modelos de Odoo para encontrar el mejor match.
        Usado para migraciones Odoo→Odoo.
        """
        best_match = None
        best_score = 0

        # Buscar modelo con mismo nombre
        exact_match = self.env['ir.model'].search([
            ('model', '=', source_model_name)
        ], limit=1)

        if exact_match:
            target_fields = self.get_model_fields(source_model_name)
            score, field_mappings = self._compare_fields(source_fields, target_fields)

            return {
                'model_id': exact_match.id,
                'model': exact_match.model,
                'name': exact_match.name,
                'confidence': score,
                'field_mappings': field_mappings,
                'is_exact_match': True,
            }

        # Buscar modelos similares si no hay coincidencia exacta
        all_models = self.get_all_models()
        for model_info in all_models:
            target_fields = self.get_model_fields(model_info['model'])
            score, field_mappings = self._compare_fields(source_fields, target_fields)

            if score > best_score:
                best_score = score
                best_match = {
                    'model_id': model_info['id'],
                    'model': model_info['model'],
                    'name': model_info['name'],
                    'confidence': score,
                    'field_mappings': field_mappings,
                    'is_exact_match': False,
                }

        return best_match

    def _compare_fields(self, source_fields, target_fields):
        """Comparar campos y calcular score de similitud"""
        if not source_fields or not target_fields:
            return 0, []

        target_field_names = {f['name']: f for f in target_fields}
        mappings = []
        matches = 0

        for source_field in source_fields:
            source_name = source_field.get('name', '')

            if source_name in target_field_names:
                # Coincidencia exacta
                mappings.append({
                    'source': source_name,
                    'target': source_name,
                    'confidence': 100,
                })
                matches += 1
            else:
                # Buscar coincidencia parcial
                best_target = None
                best_similarity = 0

                for target_name in target_field_names:
                    similarity = self._field_similarity(source_name, target_name)
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_target = target_name

                if best_target and best_similarity > 50:
                    mappings.append({
                        'source': source_name,
                        'target': best_target,
                        'confidence': best_similarity,
                    })
                    matches += 0.5

        score = (matches / len(source_fields)) * 100 if source_fields else 0
        return score, mappings

    def _field_similarity(self, name1, name2):
        """Calcular similitud entre nombres de campos"""
        n1 = name1.lower().replace('_', '')
        n2 = name2.lower().replace('_', '')

        if n1 == n2:
            return 100
        if n1 in n2 or n2 in n1:
            return 70

        # Calcular similitud por caracteres comunes
        common = set(n1) & set(n2)
        total = set(n1) | set(n2)
        return (len(common) / len(total)) * 100 if total else 0
