# -*- coding: utf-8 -*-
"""
Comparador Odoo-a-Odoo
Compara esquemas entre diferentes instancias/versiones de Odoo
Detecta diferencias y genera mapeos automáticos
"""

from odoo import models, api, _
from odoo.exceptions import UserError
import logging
import xmlrpc.client
from collections import defaultdict

_logger = logging.getLogger(__name__)


class OdooComparator(models.AbstractModel):
    _name = 'migration.odoo.comparator'
    _description = 'Comparador de Instancias Odoo'

    @api.model
    def connect_to_odoo(self, url, db, username, password):
        """
        Conectar a una instancia Odoo remota via XML-RPC
        Retorna objeto de conexión o error
        """
        try:
            # Normalizar URL
            url = url.rstrip('/')

            # Conectar al common endpoint
            common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')

            # Autenticar
            uid = common.authenticate(db, username, password, {})

            if not uid:
                return {
                    'success': False,
                    'error': _('Autenticación fallida. Verificar credenciales.'),
                }

            # Obtener versión
            version_info = common.version()

            # Crear objeto models
            models_proxy = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

            return {
                'success': True,
                'uid': uid,
                'db': db,
                'url': url,
                'models': models_proxy,
                'version': version_info.get('server_version', 'Unknown'),
                'version_info': version_info,
            }

        except xmlrpc.client.Fault as e:
            return {
                'success': False,
                'error': f'Error XML-RPC: {e.faultString}',
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Error de conexión: {str(e)}',
            }

    @api.model
    def get_remote_models(self, connection, model_filter=None):
        """
        Obtener lista de modelos de una instancia Odoo remota
        """
        if not connection.get('success'):
            return []

        try:
            models = connection['models']
            uid = connection['uid']
            db = connection['db']
            password = connection.get('password', '')

            # Buscar modelos
            domain = [('transient', '=', False)]
            if model_filter:
                domain.append(('model', 'ilike', model_filter))

            model_ids = models.execute_kw(
                db, uid, password,
                'ir.model', 'search',
                [domain],
                {'limit': 500}
            )

            if not model_ids:
                return []

            # Leer información de modelos
            model_data = models.execute_kw(
                db, uid, password,
                'ir.model', 'read',
                [model_ids],
                {'fields': ['model', 'name', 'state']}
            )

            return model_data

        except Exception as e:
            _logger.error(f'Error obteniendo modelos remotos: {e}')
            return []

    @api.model
    def get_remote_model_fields(self, connection, model_name):
        """
        Obtener campos de un modelo en instancia remota
        """
        if not connection.get('success'):
            return []

        try:
            models = connection['models']
            uid = connection['uid']
            db = connection['db']
            password = connection.get('password', '')

            # Buscar modelo
            model_ids = models.execute_kw(
                db, uid, password,
                'ir.model', 'search',
                [[('model', '=', model_name)]],
                {'limit': 1}
            )

            if not model_ids:
                return []

            # Buscar campos del modelo
            field_ids = models.execute_kw(
                db, uid, password,
                'ir.model.fields', 'search',
                [[('model_id', '=', model_ids[0]), ('store', '=', True)]],
            )

            if not field_ids:
                return []

            # Leer información de campos
            field_data = models.execute_kw(
                db, uid, password,
                'ir.model.fields', 'read',
                [field_ids],
                {'fields': ['name', 'field_description', 'ttype', 'relation',
                           'required', 'readonly', 'size', 'selection']}
            )

            return field_data

        except Exception as e:
            _logger.error(f'Error obteniendo campos remotos: {e}')
            return []

    @api.model
    def compare_models(self, source_conn, target_conn, model_name):
        """
        Comparar un modelo entre origen y destino
        Detecta: campos agregados, eliminados, modificados, renombrados
        """
        source_fields = self.get_remote_model_fields(source_conn, model_name)
        target_fields = self.get_remote_model_fields(target_conn, model_name)

        if not source_fields and not target_fields:
            return {
                'model': model_name,
                'status': 'not_found',
                'message': _('Modelo no encontrado en ninguna instancia'),
            }

        if not source_fields:
            return {
                'model': model_name,
                'status': 'target_only',
                'message': _('Modelo solo existe en destino (nuevo)'),
                'target_fields': target_fields,
            }

        if not target_fields:
            return {
                'model': model_name,
                'status': 'source_only',
                'message': _('Modelo solo existe en origen (eliminado en destino)'),
                'source_fields': source_fields,
            }

        # Crear índices por nombre de campo
        source_by_name = {f['name']: f for f in source_fields}
        target_by_name = {f['name']: f for f in target_fields}

        source_names = set(source_by_name.keys())
        target_names = set(target_by_name.keys())

        # Campos comunes, agregados, eliminados
        common = source_names & target_names
        added = target_names - source_names
        removed = source_names - target_names

        # Detectar campos modificados
        modified = []
        compatible = []

        for name in common:
            src = source_by_name[name]
            tgt = target_by_name[name]

            changes = []

            if src['ttype'] != tgt['ttype']:
                changes.append({
                    'attribute': 'type',
                    'source': src['ttype'],
                    'target': tgt['ttype'],
                    'breaking': True,
                })

            if src.get('relation') != tgt.get('relation'):
                changes.append({
                    'attribute': 'relation',
                    'source': src.get('relation'),
                    'target': tgt.get('relation'),
                    'breaking': True,
                })

            if src.get('required') != tgt.get('required'):
                changes.append({
                    'attribute': 'required',
                    'source': src.get('required'),
                    'target': tgt.get('required'),
                    'breaking': tgt.get('required', False),  # Breaking si ahora es required
                })

            if changes:
                modified.append({
                    'name': name,
                    'source': src,
                    'target': tgt,
                    'changes': changes,
                    'has_breaking_changes': any(c['breaking'] for c in changes),
                })
            else:
                compatible.append({
                    'name': name,
                    'source': src,
                    'target': tgt,
                })

        # Intentar detectar campos renombrados
        renamed = self._detect_renamed_fields(
            [source_by_name[n] for n in removed],
            [target_by_name[n] for n in added]
        )

        # Quitar los renombrados de added/removed
        for r in renamed:
            if r['source']['name'] in removed:
                removed.discard(r['source']['name'])
            if r['target']['name'] in added:
                added.discard(r['target']['name'])

        return {
            'model': model_name,
            'status': 'compared',
            'source_version': source_conn.get('version', 'Unknown'),
            'target_version': target_conn.get('version', 'Unknown'),
            'summary': {
                'total_source': len(source_fields),
                'total_target': len(target_fields),
                'compatible': len(compatible),
                'modified': len(modified),
                'added': len(added),
                'removed': len(removed),
                'renamed': len(renamed),
                'breaking_changes': sum(1 for m in modified if m['has_breaking_changes']),
            },
            'compatible_fields': compatible,
            'modified_fields': modified,
            'added_fields': [target_by_name[n] for n in added],
            'removed_fields': [source_by_name[n] for n in removed],
            'renamed_fields': renamed,
        }

    def _detect_renamed_fields(self, removed_fields, added_fields):
        """
        Detectar campos que fueron renombrados comparando tipo y relación
        """
        renamed = []
        used_added = set()

        for rem in removed_fields:
            for add in added_fields:
                if add['name'] in used_added:
                    continue

                # Mismo tipo y misma relación = probable renombre
                if (rem['ttype'] == add['ttype'] and
                    rem.get('relation') == add.get('relation')):

                    # Calcular similitud de nombre
                    similarity = self._name_similarity(rem['name'], add['name'])

                    if similarity > 0.5:  # 50% similitud mínima
                        renamed.append({
                            'source': rem,
                            'target': add,
                            'confidence': similarity * 100,
                            'reason': 'same_type_similar_name',
                        })
                        used_added.add(add['name'])
                        break

        return renamed

    def _name_similarity(self, name1, name2):
        """
        Calcular similitud entre dos nombres de campo
        """
        # Normalizar
        n1 = name1.lower().replace('_', '')
        n2 = name2.lower().replace('_', '')

        # Si uno contiene al otro
        if n1 in n2 or n2 in n1:
            return 0.8

        # Similitud por caracteres comunes
        common = set(n1) & set(n2)
        total = set(n1) | set(n2)

        if not total:
            return 0

        return len(common) / len(total)

    @api.model
    def compare_multiple_models(self, source_conn, target_conn, model_names):
        """
        Comparar múltiples modelos entre origen y destino
        """
        results = []

        for model_name in model_names:
            result = self.compare_models(source_conn, target_conn, model_name)
            results.append(result)

        # Resumen general
        summary = {
            'total_models': len(model_names),
            'compared': sum(1 for r in results if r['status'] == 'compared'),
            'source_only': sum(1 for r in results if r['status'] == 'source_only'),
            'target_only': sum(1 for r in results if r['status'] == 'target_only'),
            'not_found': sum(1 for r in results if r['status'] == 'not_found'),
            'with_breaking_changes': sum(
                1 for r in results
                if r['status'] == 'compared' and r['summary']['breaking_changes'] > 0
            ),
        }

        return {
            'summary': summary,
            'models': results,
            'source_version': source_conn.get('version', 'Unknown'),
            'target_version': target_conn.get('version', 'Unknown'),
        }

    @api.model
    def generate_migration_mapping(self, comparison_result):
        """
        Generar mapeo de migración basado en comparación
        """
        if comparison_result.get('status') != 'compared':
            return None

        mappings = []

        # Campos compatibles: mapeo directo
        for field in comparison_result.get('compatible_fields', []):
            mappings.append({
                'source_field': field['name'],
                'target_field': field['name'],
                'type': 'direct',
                'confidence': 100,
                'transform': None,
            })

        # Campos modificados: mapeo con transformación
        for field in comparison_result.get('modified_fields', []):
            transform = None
            confidence = 70

            # Si cambió el tipo, necesita transformación
            type_change = next(
                (c for c in field['changes'] if c['attribute'] == 'type'),
                None
            )

            if type_change:
                transform = self._get_type_transform(
                    type_change['source'],
                    type_change['target']
                )
                confidence = 50 if transform else 30

            mappings.append({
                'source_field': field['name'],
                'target_field': field['name'],
                'type': 'transform',
                'confidence': confidence,
                'transform': transform,
                'changes': field['changes'],
                'warning': field['has_breaking_changes'],
            })

        # Campos renombrados
        for field in comparison_result.get('renamed_fields', []):
            mappings.append({
                'source_field': field['source']['name'],
                'target_field': field['target']['name'],
                'type': 'rename',
                'confidence': field['confidence'],
                'transform': None,
            })

        # Campos nuevos en destino (necesitan valor por defecto)
        for field in comparison_result.get('added_fields', []):
            default_value = self._get_default_value(field)
            mappings.append({
                'source_field': None,
                'target_field': field['name'],
                'type': 'new',
                'confidence': 0,
                'default_value': default_value,
                'required': field.get('required', False),
            })

        # Campos eliminados en destino (se ignoran)
        for field in comparison_result.get('removed_fields', []):
            mappings.append({
                'source_field': field['name'],
                'target_field': None,
                'type': 'ignored',
                'confidence': 100,
                'reason': 'field_removed_in_target',
            })

        return {
            'model': comparison_result['model'],
            'mappings': mappings,
            'total_mappings': len(mappings),
            'direct_mappings': sum(1 for m in mappings if m['type'] == 'direct'),
            'transform_mappings': sum(1 for m in mappings if m['type'] == 'transform'),
            'warnings': sum(1 for m in mappings if m.get('warning')),
        }

    def _get_type_transform(self, source_type, target_type):
        """
        Obtener función de transformación entre tipos
        """
        transforms = {
            ('char', 'text'): 'direct',  # char -> text es directo
            ('text', 'char'): 'truncate',  # text -> char puede truncar
            ('integer', 'float'): 'to_float',
            ('float', 'integer'): 'to_int',
            ('char', 'integer'): 'parse_int',
            ('char', 'float'): 'parse_float',
            ('integer', 'char'): 'to_string',
            ('float', 'char'): 'to_string',
            ('date', 'datetime'): 'date_to_datetime',
            ('datetime', 'date'): 'datetime_to_date',
            ('many2one', 'integer'): 'relation_to_id',
            ('selection', 'char'): 'direct',
            ('char', 'selection'): 'validate_selection',
        }

        return transforms.get((source_type, target_type))

    def _get_default_value(self, field):
        """
        Obtener valor por defecto para un campo nuevo
        """
        defaults = {
            'char': '',
            'text': '',
            'integer': 0,
            'float': 0.0,
            'boolean': False,
            'date': None,
            'datetime': None,
            'many2one': None,
            'selection': None,
        }

        return defaults.get(field.get('ttype'))

    @api.model
    def get_local_model_info(self, model_name):
        """
        Obtener información de un modelo local de Odoo
        Para comparar con el mismo modelo en otra instancia
        """
        Analyzer = self.env['migration.odoo.model.analyzer']
        return Analyzer.get_model_info(model_name)

    @api.model
    def compare_with_local(self, remote_conn, model_name):
        """
        Comparar modelo remoto con el modelo local
        Útil para migrar HACIA esta instancia
        """
        # Obtener campos remotos
        remote_fields = self.get_remote_model_fields(remote_conn, model_name)

        # Obtener campos locales
        local_info = self.get_local_model_info(model_name)

        if not local_info:
            return {
                'model': model_name,
                'status': 'local_not_found',
                'message': _('Modelo no existe en instancia local'),
            }

        if not remote_fields:
            return {
                'model': model_name,
                'status': 'remote_not_found',
                'message': _('Modelo no existe en instancia remota'),
            }

        # Convertir campos locales al mismo formato
        local_fields = []
        for f in local_info['fields']['all']:
            local_fields.append({
                'name': f['name'],
                'field_description': f['string'],
                'ttype': f['type'],
                'relation': f['relation'],
                'required': f['required'],
            })

        # Crear conexión virtual para local
        local_conn = {
            'success': True,
            'version': self.env['ir.module.module'].sudo().search(
                [('name', '=', 'base')], limit=1
            ).installed_version or 'Local',
        }

        # Comparar
        source_by_name = {f['name']: f for f in remote_fields}
        target_by_name = {f['name']: f for f in local_fields}

        source_names = set(source_by_name.keys())
        target_names = set(target_by_name.keys())

        common = source_names & target_names
        added = target_names - source_names
        removed = source_names - target_names

        compatible = []
        modified = []

        for name in common:
            src = source_by_name[name]
            tgt = target_by_name[name]

            if src['ttype'] == tgt['ttype']:
                compatible.append({'name': name, 'source': src, 'target': tgt})
            else:
                modified.append({
                    'name': name,
                    'source': src,
                    'target': tgt,
                    'changes': [{'attribute': 'type', 'source': src['ttype'], 'target': tgt['ttype']}],
                })

        return {
            'model': model_name,
            'status': 'compared',
            'source_version': remote_conn.get('version', 'Remote'),
            'target_version': local_conn.get('version', 'Local'),
            'summary': {
                'total_source': len(remote_fields),
                'total_target': len(local_fields),
                'compatible': len(compatible),
                'modified': len(modified),
                'added': len(added),
                'removed': len(removed),
            },
            'compatible_fields': compatible,
            'modified_fields': modified,
            'added_fields': [target_by_name[n] for n in added],
            'removed_fields': [source_by_name[n] for n in removed],
        }

    @api.model
    def analyze_migration_complexity(self, comparison_results):
        """
        Analizar complejidad de migración basado en comparaciones
        """
        if not comparison_results:
            return {'complexity': 'unknown', 'score': 0}

        total_fields = 0
        breaking_changes = 0
        transforms_needed = 0
        new_required_fields = 0

        for result in comparison_results:
            if result.get('status') != 'compared':
                continue

            summary = result.get('summary', {})
            total_fields += summary.get('total_source', 0)
            breaking_changes += summary.get('breaking_changes', 0)
            transforms_needed += len(result.get('modified_fields', []))

            for field in result.get('added_fields', []):
                if field.get('required'):
                    new_required_fields += 1

        # Calcular score (0-100, mayor = más complejo)
        score = 0

        if total_fields > 0:
            # Penalizar por cambios breaking
            score += (breaking_changes / total_fields) * 40

            # Penalizar por transformaciones
            score += (transforms_needed / total_fields) * 30

            # Penalizar por campos requeridos nuevos
            score += min(new_required_fields * 5, 30)

        # Determinar nivel de complejidad
        if score < 20:
            complexity = 'low'
            description = _('Migración sencilla, mayoría de campos compatibles')
        elif score < 50:
            complexity = 'medium'
            description = _('Migración moderada, algunas transformaciones necesarias')
        elif score < 80:
            complexity = 'high'
            description = _('Migración compleja, varios cambios breaking')
        else:
            complexity = 'critical'
            description = _('Migración crítica, requiere intervención manual significativa')

        return {
            'complexity': complexity,
            'score': round(score, 1),
            'description': description,
            'metrics': {
                'total_fields': total_fields,
                'breaking_changes': breaking_changes,
                'transforms_needed': transforms_needed,
                'new_required_fields': new_required_fields,
            },
        }
