# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re
import logging

_logger = logging.getLogger(__name__)


class CSFFieldConfig(models.Model):
    _name = 'billing.csf.field.config'
    _description = 'Configuración de Campos CSF'
    _order = 'sequence, id'

    name = fields.Char(
        string='Nombre del Campo',
        required=True,
        help='Nombre descriptivo del campo (ej: RFC, Razón Social)'
    )

    technical_name = fields.Char(
        string='Nombre Técnico',
        required=True,
        help='Nombre interno usado en el código (ej: rfc, razon_social)'
    )

    active = fields.Boolean(
        string='Activo',
        default=True,
        help='Si está activo, este campo se extraerá del CSF'
    )

    required = fields.Boolean(
        string='Requerido',
        default=False,
        help='Si es requerido, la validación fallará si no se encuentra'
    )

    sequence = fields.Integer(
        string='Secuencia',
        default=10,
        help='Orden de extracción y visualización'
    )

    # Configuración de extracción
    regex_pattern = fields.Char(
        string='Patrón Regex',
        help='Expresión regular para extraer el campo del texto'
    )

    regex_group = fields.Integer(
        string='Grupo Regex',
        default=1,
        help='Número del grupo de captura a usar (1 = primer grupo)'
    )

    regex_flags = fields.Selection([
        ('none', 'Sin flags'),
        ('i', 'Ignorar mayúsculas (IGNORECASE)'),
        ('m', 'Multilínea (MULTILINE)'),
        ('im', 'IGNORECASE + MULTILINE'),
    ], string='Flags Regex', default='i')

    alternative_patterns = fields.Text(
        string='Patrones Alternativos',
        help='Un patrón regex por línea. Se prueban en orden si el principal falla.'
    )

    # Mapeo a Odoo
    odoo_field = fields.Char(
        string='Campo Odoo (res.partner)',
        help='Campo de res.partner donde se guardará el valor (ej: vat, name, zip)'
    )

    odoo_model = fields.Char(
        string='Modelo de Búsqueda',
        help='Si el campo necesita buscar en otro modelo (ej: catalogo.regimen.fiscal)'
    )

    odoo_search_field = fields.Char(
        string='Campo de Búsqueda',
        help='Campo del modelo donde buscar (ej: code)'
    )

    # Validación
    validation_type = fields.Selection([
        ('none', 'Sin validación'),
        ('regex', 'Validar con Regex'),
        ('length', 'Validar longitud'),
        ('numeric', 'Solo números'),
        ('alpha', 'Solo letras'),
        ('alphanumeric', 'Alfanumérico'),
    ], string='Tipo de Validación', default='none')

    validation_pattern = fields.Char(
        string='Patrón de Validación',
        help='Regex para validar el valor extraído'
    )

    validation_min_length = fields.Integer(
        string='Longitud Mínima',
        default=0
    )

    validation_max_length = fields.Integer(
        string='Longitud Máxima',
        default=0
    )

    validation_error_message = fields.Char(
        string='Mensaje de Error',
        help='Mensaje a mostrar si la validación falla'
    )

    # Transformación
    transform_type = fields.Selection([
        ('none', 'Sin transformación'),
        ('upper', 'Mayúsculas'),
        ('lower', 'Minúsculas'),
        ('title', 'Capitalizar'),
        ('strip', 'Quitar espacios'),
    ], string='Transformación', default='strip')

    # Para IA
    ai_json_path = fields.Char(
        string='Ruta JSON (IA)',
        help='Ruta en el JSON de respuesta de la IA (ej: contribuyente.rfc)'
    )

    # Categoría
    category = fields.Selection([
        ('contribuyente', 'Datos del Contribuyente'),
        ('domicilio', 'Domicilio Fiscal'),
        ('regimen', 'Régimen Fiscal'),
        ('documento', 'Datos del Documento'),
        ('otro', 'Otros'),
    ], string='Categoría', default='contribuyente')

    # UI Portal
    show_in_form = fields.Boolean(
        string='Mostrar en Formulario',
        default=True,
        help='Si se muestra en el formulario del portal'
    )

    editable_by_user = fields.Boolean(
        string='Editable por Usuario',
        default=False,
        help='Si el usuario puede modificar el valor extraído'
    )

    help_text = fields.Char(
        string='Texto de Ayuda',
        help='Texto de ayuda mostrado al usuario en el formulario'
    )

    # Notas
    notes = fields.Text(
        string='Notas',
        help='Notas internas sobre este campo'
    )

    @api.constrains('regex_pattern')
    def _check_regex_pattern(self):
        """Valida que el patrón regex sea válido"""
        for record in self:
            if record.regex_pattern:
                try:
                    re.compile(record.regex_pattern)
                except re.error as e:
                    raise ValidationError(
                        _('Patrón regex inválido para "%s": %s') % (record.name, str(e))
                    )

    @api.constrains('technical_name')
    def _check_technical_name(self):
        """Valida el nombre técnico"""
        for record in self:
            if record.technical_name:
                if not re.match(r'^[a-z_][a-z0-9_]*$', record.technical_name):
                    raise ValidationError(
                        _('El nombre técnico debe ser snake_case (ej: razon_social)')
                    )

    def extract_value(self, text):
        """Extrae el valor de este campo del texto dado"""
        self.ensure_one()

        if not self.regex_pattern:
            return None

        # Compilar flags
        flags = 0
        if self.regex_flags and 'i' in self.regex_flags:
            flags |= re.IGNORECASE
        if self.regex_flags and 'm' in self.regex_flags:
            flags |= re.MULTILINE

        # Intentar patrón principal
        match = re.search(self.regex_pattern, text, flags)

        # Si falla, intentar alternativos
        if not match and self.alternative_patterns:
            for alt_pattern in self.alternative_patterns.strip().split('\n'):
                alt_pattern = alt_pattern.strip()
                if alt_pattern:
                    try:
                        match = re.search(alt_pattern, text, flags)
                        if match:
                            break
                    except re.error:
                        continue

        if not match:
            return None

        # Extraer grupo
        try:
            value = match.group(self.regex_group or 1)
        except IndexError:
            value = match.group(0)

        # Aplicar transformación
        value = self._apply_transform(value)

        # Validar
        is_valid, error_msg = self._validate_value(value)
        if not is_valid:
            _logger.warning(f"Validación fallida para {self.name}: {error_msg}")
            return None

        return value

    def _apply_transform(self, value):
        """Aplica la transformación configurada al valor"""
        if not value:
            return value

        if self.transform_type == 'upper':
            return value.upper()
        elif self.transform_type == 'lower':
            return value.lower()
        elif self.transform_type == 'title':
            return value.title()
        elif self.transform_type == 'strip':
            return value.strip()

        return value

    def _validate_value(self, value):
        """Valida el valor según la configuración"""
        if not value:
            return True, None

        if self.validation_type == 'none':
            return True, None

        if self.validation_type == 'regex' and self.validation_pattern:
            if not re.match(self.validation_pattern, value):
                return False, self.validation_error_message or _('Formato inválido')

        if self.validation_type == 'length':
            if self.validation_min_length and len(value) < self.validation_min_length:
                return False, _('Muy corto (mín: %d)') % self.validation_min_length
            if self.validation_max_length and len(value) > self.validation_max_length:
                return False, _('Muy largo (máx: %d)') % self.validation_max_length

        if self.validation_type == 'numeric':
            if not value.isdigit():
                return False, _('Debe contener solo números')

        if self.validation_type == 'alpha':
            if not value.replace(' ', '').isalpha():
                return False, _('Debe contener solo letras')

        if self.validation_type == 'alphanumeric':
            if not value.replace(' ', '').isalnum():
                return False, _('Debe ser alfanumérico')

        return True, None

    def action_test_regex(self):
        """Acción para probar el regex con un texto de ejemplo"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Probar Regex'),
            'res_model': 'billing.csf.field.test.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_field_config_id': self.id,
            }
        }
