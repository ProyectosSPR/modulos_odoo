# -*- coding: utf-8 -*-

from odoo import models, api, fields, _
from odoo.exceptions import UserError
import logging
import json
import requests

_logger = logging.getLogger(__name__)

# Constantes para Claude API
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = "claude-sonnet-4-20250514"
ANTHROPIC_VERSION = "2023-06-01"


class MigrationAIAnalyzer(models.AbstractModel):
    _name = 'migration.ai.analyzer'
    _description = 'Analizador con IA para Sugerencias de Mapeo'

    @api.model
    def get_ai_config(self):
        """Obtener configuración de IA"""
        ICP = self.env['ir.config_parameter'].sudo()
        return {
            'provider': ICP.get_param('migration_hub.ai_provider', 'heuristic'),
            'claude_api_key': ICP.get_param('migration_hub.claude_api_key', ''),
            'openai_api_key': ICP.get_param('migration_hub.openai_api_key', ''),
            'claude_model': ICP.get_param('migration_hub.claude_model', CLAUDE_MODEL),
        }

    @api.model
    def test_claude_connection(self, api_key=None):
        """Probar conexión con Claude API - Información detallada"""
        result = {
            'success': False,
            'message': '',
            'details': {},
            'steps': [],
        }

        if not api_key:
            api_key = self.get_ai_config().get('claude_api_key')

        if not api_key:
            result['steps'].append({
                'step': 'API Key',
                'status': 'error',
                'detail': 'No configurada'
            })
            result['message'] = 'API Key de Claude no configurada'
            return result

        # Validar formato de API Key
        result['steps'].append({
            'step': 'Validar API Key',
            'status': 'pending',
            'detail': 'Verificando formato...'
        })

        if api_key.startswith('sk-ant-'):
            result['steps'][-1]['status'] = 'ok'
            result['steps'][-1]['detail'] = f"Formato válido: {api_key[:12]}...{api_key[-4:]}"
        else:
            result['steps'][-1]['status'] = 'warning'
            result['steps'][-1]['detail'] = 'Formato no estándar (debería empezar con sk-ant-)'

        try:
            result['steps'].append({
                'step': 'Conectar API',
                'status': 'pending',
                'detail': 'Enviando solicitud de prueba...'
            })

            headers = {
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json"
            }

            # Solicitud mínima para validar la key
            data = {
                "model": CLAUDE_MODEL,
                "max_tokens": 50,
                "messages": [
                    {"role": "user", "content": "Responde exactamente: API_OK"}
                ]
            }

            response = requests.post(
                CLAUDE_API_URL,
                headers=headers,
                json=data,
                timeout=30
            )

            if response.status_code == 200:
                response_data = response.json()
                content = response_data.get('content', [{}])[0].get('text', '')
                model_used = response_data.get('model', CLAUDE_MODEL)
                usage = response_data.get('usage', {})

                result['steps'][-1]['status'] = 'ok'
                result['steps'][-1]['detail'] = 'Conexión establecida'

                result['steps'].append({
                    'step': 'Modelo',
                    'status': 'ok',
                    'detail': model_used
                })

                result['steps'].append({
                    'step': 'Respuesta',
                    'status': 'ok',
                    'detail': f"Tokens: {usage.get('input_tokens', 0)} entrada, {usage.get('output_tokens', 0)} salida"
                })

                result['success'] = True
                result['message'] = f"Claude API conectada correctamente. Modelo: {model_used}"
                result['details'] = {
                    'model': model_used,
                    'api_version': ANTHROPIC_VERSION,
                    'usage': usage,
                    'response_preview': content[:50] if content else '',
                    'key_hint': f"{api_key[:12]}...{api_key[-4:]}",
                }

            elif response.status_code == 401:
                result['steps'][-1]['status'] = 'error'
                result['steps'][-1]['detail'] = 'API Key inválida o expirada'
                result['message'] = 'Error 401: API Key inválida. Verifica que la key sea correcta y esté activa.'

            elif response.status_code == 403:
                result['steps'][-1]['status'] = 'error'
                result['steps'][-1]['detail'] = 'Acceso denegado'
                result['message'] = 'Error 403: Acceso denegado. La API Key no tiene permisos suficientes.'

            elif response.status_code == 429:
                result['steps'][-1]['status'] = 'warning'
                result['steps'][-1]['detail'] = 'Rate limit alcanzado'
                result['message'] = 'Error 429: Límite de solicitudes alcanzado. La API Key funciona pero hay que esperar.'
                result['success'] = True  # La key es válida, solo hay rate limit

            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get('error', {}).get('message', 'Error desconocido')
                result['steps'][-1]['status'] = 'error'
                result['steps'][-1]['detail'] = f"HTTP {response.status_code}"
                result['message'] = f"Error {response.status_code}: {error_msg}"

            return result

        except requests.exceptions.Timeout:
            result['steps'][-1]['status'] = 'error'
            result['steps'][-1]['detail'] = 'Timeout - sin respuesta'
            result['message'] = 'Error: Timeout. Claude API no responde en 30 segundos.'
            return result

        except requests.exceptions.ConnectionError:
            result['steps'][-1]['status'] = 'error'
            result['steps'][-1]['detail'] = 'Error de conexión'
            result['message'] = 'Error: No se puede conectar a api.anthropic.com. Verificar conexión a internet.'
            return result

        except Exception as e:
            result['steps'][-1]['status'] = 'error'
            result['steps'][-1]['detail'] = str(e)[:100]
            result['message'] = f'Error: {str(e)}'
            return result

    @api.model
    def validate_and_save_api_key(self, api_key):
        """Validar y guardar API Key de Claude"""
        # Primero probar la conexión
        test_result = self.test_claude_connection(api_key)

        if test_result.get('success'):
            # Guardar la key
            self.env['ir.config_parameter'].sudo().set_param(
                'migration_hub.claude_api_key', api_key
            )
            self.env['ir.config_parameter'].sudo().set_param(
                'migration_hub.ai_provider', 'claude'
            )
            test_result['saved'] = True
            test_result['message'] += ' - API Key guardada correctamente.'
        else:
            test_result['saved'] = False

        return test_result

    @api.model
    def analyze_and_suggest(self, project):
        """
        Analizar el proyecto y generar sugerencias usando IA.
        Puede usar OpenAI, Claude, o heurísticas locales.
        """
        config = self.get_ai_config()
        ai_provider = config.get('provider', 'heuristic')

        if ai_provider == 'openai' and config.get('openai_api_key'):
            return self._analyze_with_openai(project)
        elif ai_provider == 'claude' and config.get('claude_api_key'):
            return self._analyze_with_claude(project)
        else:
            return self._analyze_with_heuristics(project)

    def _analyze_with_heuristics(self, project):
        """Análisis usando heurísticas locales (sin IA externa)"""
        suggestions = []
        topics = self.env['migration.topic'].search([])

        for table_mapping in project.table_mapping_ids:
            # Obtener información de la tabla
            table_name = table_mapping.source_table
            columns = table_mapping.get_columns()
            column_names = [c.get('name', '') for c in columns]

            # Buscar mejor tópico usando keywords
            best_topic = None
            best_score = 0

            # Texto para búsqueda
            search_text = f"{table_name} {' '.join(column_names)}"

            for topic in topics:
                score = topic.match_keywords(search_text)
                if score > best_score:
                    best_score = score
                    best_topic = topic

            if best_topic and best_score > 20:
                # Sugerir el modelo principal del tópico
                suggested_model = None
                if best_topic.model_ids:
                    suggested_model = best_topic.model_ids[0].model

                suggestions.append({
                    'source_table': table_name,
                    'topic_id': best_topic.id,
                    'odoo_model': suggested_model,
                    'confidence': min(best_score, 95),  # Cap en 95%
                    'reason': f'Coincidencia por keywords: {best_topic.keywords[:50]}...',
                })
            else:
                # Intentar inferir por nombre de tabla
                suggestion = self._infer_from_table_name(table_name, topics)
                if suggestion:
                    suggestions.append(suggestion)

        return suggestions

    def _infer_from_table_name(self, table_name, topics):
        """Inferir tópico basándose en el nombre de la tabla"""
        table_lower = table_name.lower()

        # Mapeos comunes de nombres de tabla a modelos Odoo
        common_mappings = {
            # Clientes/Contactos
            ('customer', 'client', 'vendor', 'supplier', 'partner'): ('res.partner', 'Contactos'),
            # Productos
            ('product', 'item', 'material', 'article'): ('product.template', 'Productos'),
            # Ventas
            ('sale', 'order', 'so_'): ('sale.order', 'Ventas'),
            # Compras
            ('purchase', 'po_', 'procurement'): ('purchase.order', 'Compras'),
            # Facturas
            ('invoice', 'bill', 'factura'): ('account.move', 'Facturación'),
            # Inventario
            ('stock', 'inventory', 'warehouse'): ('stock.quant', 'Inventario'),
            # Empleados
            ('employee', 'staff', 'worker'): ('hr.employee', 'Recursos Humanos'),
        }

        for keywords, (model, topic_name) in common_mappings.items():
            if any(kw in table_lower for kw in keywords):
                # Buscar el tópico correspondiente
                topic = topics.filtered(lambda t: t.name == topic_name)
                if topic:
                    return {
                        'source_table': table_name,
                        'topic_id': topic[0].id,
                        'odoo_model': model,
                        'confidence': 70,
                        'reason': f'Inferido por nombre de tabla ({keywords[0]})',
                    }

        return None

    def _analyze_with_openai(self, project):
        """Análisis usando OpenAI GPT"""
        api_key = self.env['ir.config_parameter'].sudo().get_param(
            'migration_hub.openai_api_key'
        )

        if not api_key:
            _logger.warning('OpenAI API key no configurada, usando heurísticas')
            return self._analyze_with_heuristics(project)

        try:
            import openai
            openai.api_key = api_key

            # Preparar datos para el prompt
            tables_info = []
            for tm in project.table_mapping_ids:
                tables_info.append({
                    'table': tm.source_table,
                    'columns': [c.get('name') for c in tm.get_columns()[:10]],
                    'row_count': tm.row_count,
                })

            # Obtener tópicos disponibles
            topics = self.env['migration.topic'].search([])
            topics_info = [{
                'id': t.id,
                'name': t.name,
                'models': [m.model for m in t.model_ids],
            } for t in topics]

            prompt = self._build_analysis_prompt(tables_info, topics_info)

            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Eres un experto en migración de datos ERP a Odoo."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
            )

            result = response.choices[0].message.content
            return self._parse_ai_response(result)

        except Exception as e:
            _logger.error(f'Error con OpenAI: {str(e)}')
            return self._analyze_with_heuristics(project)

    def _analyze_with_claude(self, project):
        """Análisis usando Claude de Anthropic (API REST directa)"""
        config = self.get_ai_config()
        api_key = config.get('claude_api_key')

        if not api_key:
            _logger.warning('Claude API key no configurada, usando heurísticas')
            return self._analyze_with_heuristics(project)

        try:
            # Preparar datos del esquema
            tables_info = []
            for tm in project.table_mapping_ids:
                columns = tm.get_columns() if hasattr(tm, 'get_columns') else []
                tables_info.append({
                    'table': tm.source_table,
                    'columns': [c.get('name') for c in columns[:15]],
                    'column_types': [c.get('type', 'unknown') for c in columns[:15]],
                    'row_count': tm.row_count,
                    'primary_key': tm.primary_key or 'id',
                    'foreign_keys': self._detect_foreign_keys(columns),
                })

            # Obtener tópicos disponibles con sus modelos
            topics = self.env['migration.topic'].search([])
            topics_info = [{
                'id': t.id,
                'name': t.name,
                'description': t.description or '',
                'models': [m.model for m in t.model_ids],
                'keywords': t.keywords or '',
            } for t in topics]

            # Obtener modelos Odoo disponibles
            odoo_models = self._get_available_odoo_models()

            prompt = self._build_claude_analysis_prompt(tables_info, topics_info, odoo_models)

            # Llamar a Claude API
            headers = {
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json"
            }

            data = {
                "model": config.get('claude_model', CLAUDE_MODEL),
                "max_tokens": 4096,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "system": """Eres un experto en migración de datos ERP a Odoo.
Tu tarea es analizar esquemas de bases de datos y sugerir mapeos óptimos a modelos de Odoo.
Considera relaciones entre tablas, tipos de datos, y mejores prácticas de Odoo.
Responde SIEMPRE en formato JSON válido."""
            }

            response = requests.post(
                CLAUDE_API_URL,
                headers=headers,
                json=data,
                timeout=120
            )

            if response.status_code != 200:
                error_msg = response.json().get('error', {}).get('message', 'Error desconocido')
                _logger.error(f'Error Claude API: {error_msg}')
                return self._analyze_with_heuristics(project)

            result_data = response.json()
            result_text = result_data.get('content', [{}])[0].get('text', '')

            return self._parse_ai_response(result_text)

        except requests.exceptions.Timeout:
            _logger.error('Timeout llamando a Claude API')
            return self._analyze_with_heuristics(project)
        except Exception as e:
            _logger.error(f'Error con Claude: {str(e)}')
            return self._analyze_with_heuristics(project)

    def _detect_foreign_keys(self, columns):
        """Detectar posibles llaves foráneas por convención de nombres"""
        fks = []
        for col in columns:
            name = col.get('name', '').lower()
            if name.endswith('_id') and name != 'id':
                fks.append({
                    'column': col.get('name'),
                    'references': name[:-3]  # Quitar _id
                })
        return fks

    def _get_available_odoo_models(self):
        """Obtener modelos Odoo más comunes para migración"""
        common_models = [
            'res.partner', 'res.users', 'res.company', 'res.country', 'res.currency',
            'product.template', 'product.product', 'product.category',
            'sale.order', 'sale.order.line',
            'purchase.order', 'purchase.order.line',
            'account.move', 'account.move.line', 'account.account',
            'stock.picking', 'stock.move', 'stock.quant', 'stock.warehouse',
            'hr.employee', 'hr.department',
            'crm.lead', 'project.project', 'project.task',
        ]

        models_info = []
        for model_name in common_models:
            model = self.env['ir.model'].search([('model', '=', model_name)], limit=1)
            if model:
                fields = self.env['ir.model.fields'].search([
                    ('model_id', '=', model.id),
                    ('store', '=', True),
                    ('name', 'not in', ['create_uid', 'write_uid', 'create_date', 'write_date', '__last_update'])
                ], limit=20)

                models_info.append({
                    'model': model_name,
                    'name': model.name,
                    'fields': [{'name': f.name, 'type': f.ttype, 'required': f.required} for f in fields]
                })

        return models_info

    def _build_claude_analysis_prompt(self, tables_info, topics_info, odoo_models):
        """Construir prompt optimizado para Claude"""
        return f"""
Analiza las siguientes tablas de una base de datos origen y genera mapeos a Odoo.

## TABLAS ORIGEN (a migrar):
```json
{json.dumps(tables_info, indent=2, ensure_ascii=False)}
```

## TÓPICOS DISPONIBLES EN ODOO:
```json
{json.dumps(topics_info, indent=2, ensure_ascii=False)}
```

## MODELOS ODOO DISPONIBLES:
```json
{json.dumps(odoo_models[:10], indent=2, ensure_ascii=False)}
```

## INSTRUCCIONES:
1. Para cada tabla origen, identifica el mejor modelo Odoo destino
2. Considera las relaciones (foreign keys) entre tablas
3. Sugiere el tópico más apropiado para agrupar
4. Calcula un porcentaje de confianza (0-100)

## RESPUESTA (JSON):
Responde ÚNICAMENTE con un JSON array válido, sin texto adicional:
```json
[
    {{
        "source_table": "nombre_tabla_origen",
        "topic_id": id_numerico_del_topico,
        "odoo_model": "modelo.odoo.sugerido",
        "confidence": 85,
        "reason": "explicación breve del mapeo",
        "field_mappings": [
            {{"source": "columna_origen", "target": "campo_odoo", "transform": null}},
            {{"source": "customer_id", "target": "partner_id", "transform": "lookup"}}
        ],
        "dependencies": ["tabla_padre_si_existe"],
        "priority": 1
    }}
]
```

Considera:
- Nombres que terminan en _id son llaves foráneas
- Tablas con pocos registros suelen ser catálogos
- Prioriza tablas maestras (partners, products) antes que transaccionales (orders, invoices)
"""

    def _build_analysis_prompt(self, tables_info, topics_info):
        """Construir prompt para análisis de IA"""
        return f"""
Analiza las siguientes tablas de una base de datos origen y clasifícalas
según los tópicos de Odoo disponibles.

TABLAS ORIGEN:
{json.dumps(tables_info, indent=2)}

TÓPICOS DISPONIBLES EN ODOO:
{json.dumps(topics_info, indent=2)}

Para cada tabla, responde en JSON con este formato:
[
    {{
        "source_table": "nombre_tabla",
        "topic_id": id_del_topico,
        "odoo_model": "modelo.odoo.sugerido",
        "confidence": 0-100,
        "reason": "explicación breve"
    }}
]

Considera:
- Nombres de tablas y columnas
- Patrones comunes de ERP (customers, invoices, orders, etc.)
- Relaciones implícitas (columnas que terminan en _id)
- Cantidad de registros como indicador de importancia

Responde SOLO con el JSON, sin explicaciones adicionales.
"""

    def _parse_ai_response(self, response_text):
        """Parsear respuesta de la IA"""
        try:
            # Intentar extraer JSON de la respuesta
            import re
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            if json_match:
                return json.loads(json_match.group())
            return []
        except json.JSONDecodeError:
            _logger.error('Error parseando respuesta de IA')
            return []

    @api.model
    def suggest_field_mappings(self, table_mapping):
        """Sugerir mapeos de campos para una tabla específica"""
        suggestions = []

        source_columns = table_mapping.get_columns()
        if not table_mapping.target_model_id:
            return suggestions

        # Obtener campos del modelo destino
        target_fields = self.env['ir.model.fields'].search([
            ('model_id', '=', table_mapping.target_model_id.id),
            ('store', '=', True),
        ])

        target_field_dict = {f.name: f for f in target_fields}

        # Mapeos conocidos comunes
        known_mappings = {
            'customer_name': 'name',
            'client_name': 'name',
            'nombre': 'name',
            'description': 'name',
            'tax_id': 'vat',
            'tax_number': 'vat',
            'rfc': 'vat',
            'nit': 'vat',
            'email_address': 'email',
            'mail': 'email',
            'correo': 'email',
            'phone_number': 'phone',
            'telephone': 'phone',
            'telefono': 'phone',
            'mobile_phone': 'mobile',
            'celular': 'mobile',
            'address': 'street',
            'address_line_1': 'street',
            'direccion': 'street',
            'address_line_2': 'street2',
            'city_name': 'city',
            'ciudad': 'city',
            'zip_code': 'zip',
            'postal_code': 'zip',
            'codigo_postal': 'zip',
            'country_code': 'country_id',
            'pais': 'country_id',
            'state_code': 'state_id',
            'provincia': 'state_id',
            'is_active': 'active',
            'enabled': 'active',
            'activo': 'active',
            'created_at': 'create_date',
            'created_date': 'create_date',
            'fecha_creacion': 'create_date',
            'updated_at': 'write_date',
            'modified_at': 'write_date',
            'product_code': 'default_code',
            'sku': 'default_code',
            'codigo': 'default_code',
            'product_name': 'name',
            'item_name': 'name',
            'unit_price': 'list_price',
            'price': 'list_price',
            'precio': 'list_price',
            'quantity': 'product_uom_qty',
            'qty': 'product_uom_qty',
            'cantidad': 'product_uom_qty',
        }

        for col in source_columns:
            col_name = col.get('name', '')
            col_name_lower = col_name.lower().replace(' ', '_')

            # Buscar en mapeos conocidos
            if col_name_lower in known_mappings:
                target_name = known_mappings[col_name_lower]
                if target_name in target_field_dict:
                    suggestions.append({
                        'source_column': col_name,
                        'target_field': target_name,
                        'confidence': 90,
                        'mapping_type': 'direct',
                        'reason': 'Mapeo conocido',
                    })
                    continue

            # Buscar coincidencia exacta
            if col_name_lower.replace('_', '') in [f.name.replace('_', '') for f in target_fields]:
                for f in target_fields:
                    if col_name_lower.replace('_', '') == f.name.replace('_', ''):
                        suggestions.append({
                            'source_column': col_name,
                            'target_field': f.name,
                            'confidence': 85,
                            'mapping_type': 'direct',
                            'reason': 'Coincidencia de nombre',
                        })
                        break
                continue

            # Buscar coincidencia parcial
            best_match = None
            best_score = 0
            for f in target_fields:
                score = self._name_similarity(col_name_lower, f.name)
                if score > best_score:
                    best_score = score
                    best_match = f

            if best_match and best_score > 0.5:
                suggestions.append({
                    'source_column': col_name,
                    'target_field': best_match.name,
                    'confidence': int(best_score * 100),
                    'mapping_type': 'direct',
                    'reason': f'Similitud: {best_score:.0%}',
                })

        return suggestions

    def _name_similarity(self, name1, name2):
        """Calcular similitud entre dos nombres"""
        n1 = set(name1.lower().replace('_', ''))
        n2 = set(name2.lower().replace('_', ''))

        if not n1 or not n2:
            return 0

        intersection = n1 & n2
        union = n1 | n2

        return len(intersection) / len(union)
