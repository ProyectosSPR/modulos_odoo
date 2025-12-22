# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re
import unicodedata
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
        compute='_compute_technical_name',
        store=True,
        help='Nombre interno usado en el código (ej: rfc, razon_social)'
    )

    field_type = fields.Selection([
        ('text', 'Texto'),
        ('rfc', 'RFC'),
        ('postal_code', 'Código Postal'),
        ('date', 'Fecha'),
        ('catalog', 'Catálogo'),
        ('numeric', 'Numérico'),
    ], string='Tipo de Campo', default='text')

    active = fields.Boolean(
        string='Activo',
        default=True,
        help='Si está activo, este campo se extraerá del CSF'
    )

    is_required = fields.Boolean(
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
    ], string='Flags Regex', default='im')

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
    validation_regex = fields.Char(
        string='Regex de Validación',
        help='Regex para validar el valor extraído'
    )

    error_message = fields.Char(
        string='Mensaje de Error',
        help='Mensaje a mostrar si la validación falla'
    )

    # Transformación
    transformation = fields.Selection([
        ('none', 'Sin transformación'),
        ('uppercase', 'Mayúsculas'),
        ('lowercase', 'Minúsculas'),
        ('title', 'Capitalizar'),
        ('strip', 'Quitar espacios'),
        ('digits_only', 'Solo dígitos'),
    ], string='Transformación', default='strip')

    # Para IA
    use_ai_extraction = fields.Boolean(
        string='Usar Extracción IA',
        default=True,
        help='Si se debe usar IA como fallback para extraer este campo'
    )

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

    @api.depends('name')
    def _compute_technical_name(self):
        """Genera nombre técnico automáticamente desde el nombre"""
        for record in self:
            if record.name:
                # Normalizar y quitar acentos
                nfkd = unicodedata.normalize('NFKD', record.name)
                ascii_str = nfkd.encode('ASCII', 'ignore').decode('ASCII')
                # Convertir a snake_case
                technical = ascii_str.lower().replace(' ', '_').replace('/', '_')
                technical = re.sub(r'[^a-z0-9_]', '', technical)
                technical = re.sub(r'_+', '_', technical).strip('_')
                record.technical_name = technical or 'field'
            else:
                record.technical_name = 'field'

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

    def extract_value(self, text):
        """Extrae el valor de este campo del texto dado"""
        self.ensure_one()

        if not self.regex_pattern:
            return None

        # Compilar flags
        flags = re.IGNORECASE | re.MULTILINE
        if self.regex_flags == 'none':
            flags = 0
        elif self.regex_flags == 'i':
            flags = re.IGNORECASE
        elif self.regex_flags == 'm':
            flags = re.MULTILINE

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

        if self.transformation == 'uppercase':
            return value.upper().strip()
        elif self.transformation == 'lowercase':
            return value.lower().strip()
        elif self.transformation == 'title':
            return value.title().strip()
        elif self.transformation == 'strip':
            return value.strip()
        elif self.transformation == 'digits_only':
            return re.sub(r'\D', '', value)

        return value

    def _validate_value(self, value):
        """Valida el valor según la configuración"""
        if not value:
            return True, None

        if self.validation_regex:
            try:
                if not re.match(self.validation_regex, value):
                    return False, self.error_message or _('Formato inválido')
            except re.error:
                pass

        # Validaciones por tipo de campo
        if self.field_type == 'rfc':
            # RFC: 12-13 caracteres alfanuméricos
            if not re.match(r'^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$', value.upper()):
                return False, self.error_message or _('RFC inválido')

        elif self.field_type == 'postal_code':
            if not re.match(r'^\d{5}$', value):
                return False, self.error_message or _('Código postal inválido')

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
