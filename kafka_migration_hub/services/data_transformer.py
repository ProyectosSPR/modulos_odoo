# -*- coding: utf-8 -*-

from odoo import models, api, _
from odoo.exceptions import ValidationError
import logging
import json

_logger = logging.getLogger(__name__)


class MigrationDataTransformer(models.AbstractModel):
    _name = 'migration.data.transformer'
    _description = 'Transformador de Datos para Migración'

    @api.model
    def transform_and_insert(self, table_mapping, source_data):
        """
        Transformar datos del origen y insertar en Odoo.

        Args:
            table_mapping: migration.table.mapping record
            source_data: dict con datos del registro origen

        Returns:
            dict con resultado {'success': bool, 'odoo_id': int, 'error': str}
        """
        if not table_mapping.target_model:
            return {'success': False, 'error': 'No hay modelo destino configurado'}

        try:
            # Transformar datos
            transformed_data = self._transform_record(table_mapping, source_data)

            if not transformed_data:
                return {'success': False, 'error': 'No se pudieron transformar los datos'}

            # Insertar en Odoo
            target_model = self.env[table_mapping.target_model]

            # Verificar si ya existe (por external ID o campos únicos)
            existing_id = self._find_existing_record(table_mapping, source_data, transformed_data)

            if existing_id:
                # Actualizar registro existente
                record = target_model.browse(existing_id)
                record.write(transformed_data)
                odoo_id = existing_id
                action = 'updated'
            else:
                # Crear nuevo registro
                record = target_model.create(transformed_data)
                odoo_id = record.id
                action = 'created'

            # Guardar mapeo de IDs
            self._save_id_mapping(table_mapping, source_data, odoo_id)

            return {
                'success': True,
                'odoo_id': odoo_id,
                'action': action,
            }

        except ValidationError as e:
            error_msg = str(e)
            self._log_error(table_mapping, source_data, 'validation', error_msg)
            return {'success': False, 'error': error_msg, 'error_type': 'validation'}

        except Exception as e:
            error_msg = str(e)
            self._log_error(table_mapping, source_data, 'unknown', error_msg)
            return {'success': False, 'error': error_msg, 'error_type': 'unknown'}

    def _transform_record(self, table_mapping, source_data):
        """Transformar un registro usando los mapeos de campos"""
        result = {}

        for field_mapping in table_mapping.field_mapping_ids:
            if field_mapping.state == 'ignored' or field_mapping.mapping_type == 'ignore':
                continue

            source_column = field_mapping.source_column
            source_value = source_data.get(source_column)

            # Aplicar transformación
            try:
                transformed_value = field_mapping.transform_value(source_value, source_data)

                if transformed_value is not None and field_mapping.target_field_name:
                    # Manejar campos relacionales
                    if field_mapping.target_field_type == 'many2one':
                        transformed_value = self._resolve_many2one(
                            field_mapping, transformed_value, table_mapping
                        )
                    elif field_mapping.target_field_type in ('many2many', 'one2many'):
                        transformed_value = self._resolve_x2many(
                            field_mapping, transformed_value, table_mapping
                        )

                    if transformed_value is not None:
                        result[field_mapping.target_field_name] = transformed_value

            except Exception as e:
                _logger.warning(
                    f'Error transformando campo {source_column}: {e}'
                )
                continue

        return result

    def _resolve_many2one(self, field_mapping, value, table_mapping):
        """Resolver campo Many2one"""
        if not value:
            return False

        # Si ya es un ID numérico, verificar que existe
        if isinstance(value, int):
            return value

        # Buscar en mapeo de IDs
        if field_mapping.source_is_fk and field_mapping.source_fk_table:
            id_mapping = self.env['migration.id.mapping'].get_target_id(
                table_mapping.project_id.id,
                field_mapping.source_fk_table,
                value,
            )
            if id_mapping:
                return id_mapping

        # Buscar en modelo destino
        if field_mapping.target_relation:
            model = self.env[field_mapping.target_relation]

            # Intentar búsquedas comunes
            search_fields = ['name', 'code', 'ref', 'external_id']
            for search_field in search_fields:
                if search_field in model._fields:
                    record = model.search([(search_field, '=', value)], limit=1)
                    if record:
                        return record.id

        return False

    def _resolve_x2many(self, field_mapping, value, table_mapping):
        """Resolver campos Many2many o One2many"""
        if not value:
            return [(5, 0, 0)]  # Clear

        if isinstance(value, list):
            ids = []
            for v in value:
                resolved_id = self._resolve_many2one(field_mapping, v, table_mapping)
                if resolved_id:
                    ids.append(resolved_id)
            return [(6, 0, ids)] if ids else False

        return False

    def _find_existing_record(self, table_mapping, source_data, transformed_data):
        """Buscar si ya existe un registro equivalente en Odoo"""
        project = table_mapping.project_id

        # Buscar en mapeo de IDs
        pk_columns = []
        for fm in table_mapping.field_mapping_ids:
            if fm.source_is_pk:
                pk_columns.append(fm.source_column)

        for pk_col in pk_columns:
            pk_value = source_data.get(pk_col)
            if pk_value:
                existing = self.env['migration.id.mapping'].get_target_id(
                    project.id,
                    table_mapping.source_table,
                    pk_value,
                )
                if existing:
                    return existing

        return None

    def _save_id_mapping(self, table_mapping, source_data, odoo_id):
        """Guardar mapeo de IDs"""
        project = table_mapping.project_id

        # Encontrar columna PK
        pk_value = None
        for fm in table_mapping.field_mapping_ids:
            if fm.source_is_pk:
                pk_value = source_data.get(fm.source_column)
                break

        if pk_value is None:
            pk_value = source_data.get('id', source_data.get('ID'))

        if pk_value:
            self.env['migration.id.mapping'].create_mapping(
                project_id=project.id,
                source_table=table_mapping.source_table,
                source_id=pk_value,
                target_model=table_mapping.target_model,
                target_id=odoo_id,
                table_mapping_id=table_mapping.id,
            )

    def _log_error(self, table_mapping, source_data, error_type, error_message):
        """Registrar error en la cola DLQ"""
        self.env['migration.error'].create({
            'project_id': table_mapping.project_id.id,
            'table_mapping_id': table_mapping.id,
            'source_table': table_mapping.source_table,
            'source_record_id': str(source_data.get('id', '')),
            'source_data': json.dumps(source_data, default=str),
            'error_type': error_type,
            'error_message': error_message,
        })

    @api.model
    def batch_transform_and_insert(self, table_mapping, records, batch_size=100):
        """
        Procesar múltiples registros en lote.
        Más eficiente que procesar uno por uno.
        """
        results = {
            'success': 0,
            'errors': 0,
            'created': 0,
            'updated': 0,
        }

        batch = []
        for record in records:
            transformed = self._transform_record(table_mapping, record)
            if transformed:
                batch.append({
                    'source': record,
                    'transformed': transformed,
                })

            if len(batch) >= batch_size:
                batch_results = self._insert_batch(table_mapping, batch)
                results['success'] += batch_results['success']
                results['errors'] += batch_results['errors']
                results['created'] += batch_results['created']
                results['updated'] += batch_results['updated']
                batch = []

        # Procesar batch final
        if batch:
            batch_results = self._insert_batch(table_mapping, batch)
            results['success'] += batch_results['success']
            results['errors'] += batch_results['errors']
            results['created'] += batch_results['created']
            results['updated'] += batch_results['updated']

        return results

    def _insert_batch(self, table_mapping, batch):
        """Insertar un lote de registros"""
        results = {'success': 0, 'errors': 0, 'created': 0, 'updated': 0}
        target_model = self.env[table_mapping.target_model]

        for item in batch:
            try:
                existing_id = self._find_existing_record(
                    table_mapping,
                    item['source'],
                    item['transformed'],
                )

                if existing_id:
                    record = target_model.browse(existing_id)
                    record.write(item['transformed'])
                    results['updated'] += 1
                else:
                    record = target_model.create(item['transformed'])
                    results['created'] += 1

                self._save_id_mapping(
                    table_mapping,
                    item['source'],
                    record.id if not existing_id else existing_id,
                )
                results['success'] += 1

            except Exception as e:
                results['errors'] += 1
                self._log_error(
                    table_mapping,
                    item['source'],
                    'unknown',
                    str(e),
                )

        return results
