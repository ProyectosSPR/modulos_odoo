# -*- coding: utf-8 -*-

from odoo import api, models, _
import json
import requests
import base64
import logging
import re

_logger = logging.getLogger(__name__)

# Intentar importar PyMuPDF
try:
    import fitz
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    _logger.warning("PyMuPDF no está instalado. La extracción local de PDF no funcionará.")


class CSFValidator(models.AbstractModel):
    _name = 'billing.csf.validator'
    _description = 'Validador Dinámico de CSF'

    def validate_csf(self, pdf_content):
        """
        Valida CSF usando la configuración dinámica de campos.

        Args:
            pdf_content: bytes del PDF

        Returns:
            dict con success, method, data, errors, warnings
        """
        result = {
            'success': False,
            'method': None,
            'data': {},
            'errors': [],
            'warnings': [],
            'fields_extracted': []
        }

        # Verificar si debemos usar solo IA
        use_ai_only = self.env['ir.config_parameter'].sudo().get_param(
            'billing_portal.ai_only', 'False'
        ) == 'True'

        if use_ai_only:
            return self._extract_with_ai(pdf_content, result)

        # 1. Validar PDF
        if not self._is_valid_pdf(pdf_content):
            result['errors'].append(_('El archivo no es un PDF válido'))
            return result

        # 2. Extraer texto con OCR local
        text = self._extract_text(pdf_content)
        if not text:
            _logger.info("No se pudo extraer texto, intentando con IA")
            return self._extract_with_ai(pdf_content, result)

        # 3. Verificar que es CSF
        if not self._is_csf_document(text):
            result['errors'].append(
                _('El documento no parece ser una Constancia de Situación Fiscal. '
                  'Por favor suba el documento correcto del SAT.')
            )
            return result

        # 4. Obtener campos configurados activos
        fields_config = self.env['billing.csf.field.config'].search([
            ('active', '=', True)
        ], order='sequence')

        if not fields_config:
            result['errors'].append(_('No hay campos CSF configurados'))
            return result

        # 5. Extraer cada campo
        for field_config in fields_config:
            try:
                value = field_config.extract_value(text)

                if value:
                    result['data'][field_config.technical_name] = value
                    result['fields_extracted'].append(field_config.name)

                    # Si tiene modelo de búsqueda, buscar ID en Odoo
                    if field_config.odoo_model and field_config.odoo_search_field:
                        odoo_record = self._search_odoo_record(
                            field_config.odoo_model,
                            field_config.odoo_search_field,
                            value
                        )
                        if odoo_record:
                            result['data'][f'{field_config.technical_name}_id'] = odoo_record.id
                            result['data'][f'{field_config.technical_name}_display'] = odoo_record.display_name

                elif field_config.required:
                    result['warnings'].append(
                        _('No se pudo extraer: %s') % field_config.name
                    )
            except Exception as e:
                _logger.warning(f"Error extrayendo campo {field_config.name}: {e}")

        # 6. Verificar si necesitamos IA como fallback
        required_fields = fields_config.filtered(lambda f: f.required)
        missing_required = [
            f for f in required_fields
            if not result['data'].get(f.technical_name)
        ]

        use_ai_fallback = self.env['ir.config_parameter'].sudo().get_param(
            'billing_portal.use_ai_fallback', 'True'
        ) == 'True'

        if missing_required and use_ai_fallback:
            _logger.info(f"Campos requeridos faltantes: {[f.name for f in missing_required]}. Usando IA.")
            result['warnings'].append(
                _('Extracción local incompleta. Usando IA para completar.')
            )
            return self._extract_with_ai(pdf_content, result, result['data'])

        if missing_required and not use_ai_fallback:
            result['errors'].append(
                _('No se pudieron extraer todos los campos requeridos: %s') %
                ', '.join(f.name for f in missing_required)
            )
            return result

        result['success'] = True
        result['method'] = 'local'
        return result

    def _is_valid_pdf(self, content):
        """Verifica que el contenido sea un PDF válido"""
        if not content:
            return False

        try:
            # Verificar magic bytes
            if isinstance(content, str):
                content = content.encode()

            if not content.startswith(b'%PDF'):
                return False

            if HAS_PYMUPDF:
                doc = fitz.open(stream=content, filetype="pdf")
                page_count = len(doc)
                doc.close()
                return page_count > 0

            return True
        except Exception as e:
            _logger.warning(f"Error validando PDF: {e}")
            return False

    def _extract_text(self, pdf_content):
        """Extrae texto del PDF usando PyMuPDF"""
        if not HAS_PYMUPDF:
            _logger.warning("PyMuPDF no disponible para extracción de texto")
            return ""

        try:
            doc = fitz.open(stream=pdf_content, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text.strip()
        except Exception as e:
            _logger.error(f"Error extrayendo texto del PDF: {e}")
            return ""

    def _is_csf_document(self, text):
        """Verifica si el texto corresponde a una CSF"""
        if not text:
            return False

        text_lower = text.lower()
        indicators = [
            'constancia de situación fiscal',
            'constancia de situacion fiscal',
            'servicio de administración tributaria',
            'servicio de administracion tributaria',
            'régimen fiscal',
            'regimen fiscal',
            'cédula de identificación fiscal',
            'cedula de identificacion fiscal',
        ]
        matches = sum(1 for ind in indicators if ind in text_lower)
        return matches >= 2

    def _search_odoo_record(self, model_name, search_field, value):
        """Busca un registro en Odoo por un campo"""
        try:
            Model = self.env[model_name].sudo()

            # Búsqueda exacta primero
            record = Model.search([
                (search_field, '=', value)
            ], limit=1)

            if not record:
                # Búsqueda parcial
                record = Model.search([
                    (search_field, 'ilike', value)
                ], limit=1)

            # Para regímenes fiscales, extraer solo el código numérico
            if not record and model_name == 'catalogo.regimen.fiscal':
                code_match = re.search(r'\d{3}', str(value))
                if code_match:
                    record = Model.search([
                        (search_field, '=', code_match.group())
                    ], limit=1)

            return record
        except Exception as e:
            _logger.warning(f"Error buscando en {model_name}: {e}")
            return None

    def _extract_with_ai(self, pdf_content, result, partial_data=None):
        """Usa Google Gemini como fallback para extracción"""

        gemini_key = self.env['ir.config_parameter'].sudo().get_param(
            'billing_portal.gemini_api_key'
        )

        if not gemini_key:
            result['errors'].append(
                _('Extracción local incompleta y la IA no está configurada. '
                  'Configure la API Key de Gemini en Ajustes.')
            )
            return result

        gemini_model = self.env['ir.config_parameter'].sudo().get_param(
            'billing_portal.gemini_model', 'gemini-2.0-flash'
        )

        # Obtener campos activos para construir prompt dinámico
        fields_config = self.env['billing.csf.field.config'].search([
            ('active', '=', True)
        ])

        # Construir estructura JSON esperada
        json_structure = self._build_ai_json_structure(fields_config)

        prompt = f"""Eres un asistente especializado en documentos fiscales mexicanos.
Analiza este PDF y determina si es una Constancia de Situación Fiscal (CSF) del SAT.

IMPORTANTE:
- Si NO es una CSF, responde SOLO: {{"estatus": "error", "mensaje": "No es una Constancia de Situación Fiscal"}}
- Si ES una CSF, extrae los datos en el formato JSON especificado abajo.

Reglas de extracción:
- El RFC debe tener 12-13 caracteres (3-4 letras + 6 dígitos + 3 homoclave)
- El código postal debe tener 5 dígitos
- Para el régimen fiscal, extrae el código de 3 dígitos y la descripción
- Para entidad federativa, usa el nombre completo (ej: "Guanajuato", "Ciudad de México")

Estructura JSON a devolver si es CSF válida:

{json.dumps(json_structure, indent=2, ensure_ascii=False)}

Responde SOLO con el JSON, sin explicaciones adicionales."""

        try:
            # Codificar PDF a base64
            if isinstance(pdf_content, str):
                pdf_base64 = pdf_content
            else:
                pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')

            # Llamar a Gemini
            response = requests.post(
                f'https://generativelanguage.googleapis.com/v1/models/{gemini_model}:generateContent',
                headers={'Content-Type': 'application/json'},
                params={'key': gemini_key},
                json={
                    'contents': [{
                        'parts': [
                            {'text': prompt},
                            {
                                'inline_data': {
                                    'mime_type': 'application/pdf',
                                    'data': pdf_base64
                                }
                            }
                        ]
                    }],
                    'generationConfig': {
                        'temperature': 0.1,
                        'maxOutputTokens': 2048,
                    }
                },
                timeout=60
            )

            if response.status_code == 200:
                ai_response = response.json()

                # Extraer texto de respuesta
                text_response = ai_response.get('candidates', [{}])[0].get(
                    'content', {}
                ).get('parts', [{}])[0].get('text', '')

                # Limpiar markdown si existe
                text_response = text_response.strip()
                if text_response.startswith('```'):
                    text_response = re.sub(r'^```(?:json)?\n?', '', text_response)
                    text_response = re.sub(r'\n?```$', '', text_response)

                ai_data = json.loads(text_response)

                if ai_data.get('estatus') == 'error':
                    result['errors'].append(
                        ai_data.get('mensaje', _('El documento no es una CSF válida'))
                    )
                    return result

                # Mapear respuesta de IA usando configuración
                for field_config in fields_config:
                    if field_config.ai_json_path:
                        value = self._get_json_path(ai_data, field_config.ai_json_path)
                        if value:
                            # Aplicar transformación
                            if field_config.transform_type == 'upper' and isinstance(value, str):
                                value = value.upper()
                            elif field_config.transform_type == 'strip' and isinstance(value, str):
                                value = value.strip()

                            result['data'][field_config.technical_name] = value
                            result['fields_extracted'].append(field_config.name)

                            # Buscar en Odoo si aplica
                            if field_config.odoo_model and field_config.odoo_search_field:
                                search_value = value
                                # Para regímenes, usar el código
                                if isinstance(value, list) and len(value) > 0:
                                    search_value = value[0].get('codigo', value[0].get('code', ''))
                                elif isinstance(value, dict):
                                    search_value = value.get('codigo', value.get('code', ''))

                                odoo_record = self._search_odoo_record(
                                    field_config.odoo_model,
                                    field_config.odoo_search_field,
                                    search_value
                                )
                                if odoo_record:
                                    result['data'][f'{field_config.technical_name}_id'] = odoo_record.id
                                    result['data'][f'{field_config.technical_name}_display'] = odoo_record.display_name

                # Combinar con datos locales si existen
                if partial_data:
                    for key, value in partial_data.items():
                        if value and not result['data'].get(key):
                            result['data'][key] = value

                result['success'] = True
                result['method'] = 'ai'

            else:
                error_detail = response.json().get('error', {}).get('message', response.status_code)
                result['errors'].append(_('Error de API Gemini: %s') % error_detail)
                _logger.error(f"Error Gemini API: {response.text}")

        except json.JSONDecodeError as e:
            result['errors'].append(_('Error parseando respuesta de IA'))
            _logger.error(f"Error JSON: {e}")
        except requests.exceptions.Timeout:
            result['errors'].append(_('Timeout conectando con servicio de IA'))
        except Exception as e:
            result['errors'].append(_('Error procesando con IA: %s') % str(e))
            _logger.exception("Error en extracción con IA")

        return result

    def _build_ai_json_structure(self, fields_config):
        """Construye la estructura JSON esperada para el prompt de IA"""
        structure = {'estatus': 'ok'}

        for field in fields_config:
            if field.ai_json_path:
                parts = field.ai_json_path.split('.')
                current = structure

                for i, part in enumerate(parts[:-1]):
                    if part not in current:
                        current[part] = {}
                    current = current[part]

                # Valor de ejemplo según el tipo
                example_value = f"EXTRAER_{field.name.upper().replace(' ', '_')}"

                # Para regímenes, indicar que es una lista
                if field.technical_name == 'regimen_fiscal':
                    current[parts[-1]] = [{"codigo": "000", "descripcion": "DESCRIPCION_REGIMEN"}]
                else:
                    current[parts[-1]] = example_value

        return structure

    def _get_json_path(self, data, path):
        """Obtiene valor de un JSON dado una ruta tipo 'contribuyente.rfc'"""
        if not data or not path:
            return None

        parts = path.split('.')
        current = data

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, list) and part.isdigit():
                idx = int(part)
                if idx < len(current):
                    current = current[idx]
                else:
                    return None
            else:
                return None

        return current
