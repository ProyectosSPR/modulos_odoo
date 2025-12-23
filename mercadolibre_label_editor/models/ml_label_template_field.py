# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MlLabelTemplateField(models.Model):
    _name = 'ml.label.template.field'
    _description = 'Campo de Texto en Plantilla de Etiqueta'
    _order = 'sequence, id'

    template_id = fields.Many2one(
        'ml.label.template',
        string='Plantilla',
        required=True,
        ondelete='cascade'
    )
    sequence = fields.Integer(
        string='Secuencia',
        default=10,
        help='Orden de procesamiento de campos'
    )
    name = fields.Char(
        string='Descripción',
        required=True,
        help='Descripción del campo (ej: "Número de Orden", "Cliente")'
    )

    # Tipo de campo
    field_type = fields.Selection([
        ('static', 'Texto Estático'),
        ('dynamic', 'Variable Dinámica'),
    ], string='Tipo', required=True, default='dynamic',
       help='Estático: texto fijo. Dinámico: usa variables como ${sale_order.name}')

    # Valor
    value = fields.Char(
        string='Valor',
        required=True,
        help='Texto estático o variable dinámica con formato ${modelo.campo}'
    )

    # Posición (en píxeles desde esquina superior izquierda)
    position_x = fields.Integer(
        string='Posición X (px)',
        required=True,
        default=0,
        help='Posición horizontal en píxeles desde la esquina superior izquierda'
    )
    position_y = fields.Integer(
        string='Posición Y (px)',
        required=True,
        default=0,
        help='Posición vertical en píxeles desde la esquina superior izquierda'
    )

    # Estilo
    font_size = fields.Integer(
        string='Tamaño Fuente',
        default=12,
        help='Tamaño de la fuente en puntos (pt)'
    )
    font_family = fields.Selection([
        ('Helvetica', 'Helvetica'),
        ('Helvetica-Bold', 'Helvetica Bold'),
        ('Helvetica-Oblique', 'Helvetica Italic'),
        ('Helvetica-BoldOblique', 'Helvetica Bold Italic'),
        ('Times-Roman', 'Times New Roman'),
        ('Times-Bold', 'Times Bold'),
        ('Times-Italic', 'Times Italic'),
        ('Times-BoldItalic', 'Times Bold Italic'),
        ('Courier', 'Courier'),
        ('Courier-Bold', 'Courier Bold'),
        ('Courier-Oblique', 'Courier Italic'),
        ('Courier-BoldOblique', 'Courier Bold Italic'),
    ], string='Fuente', default='Helvetica',
       help='Familia de fuente a usar')

    color = fields.Char(
        string='Color',
        default='#000000',
        help='Color del texto en formato hexadecimal (ej: #000000 para negro)'
    )
    rotation = fields.Float(
        string='Rotación (°)',
        default=0.0,
        help='Ángulo de rotación del texto (0-360 grados, sentido antihorario)'
    )

    # Alineación
    align = fields.Selection([
        ('left', 'Izquierda'),
        ('center', 'Centro'),
        ('right', 'Derecha'),
    ], string='Alineación', default='left',
       help='Alineación del texto')

    active = fields.Boolean(
        string='Activo',
        default=True
    )

    # Campos relacionados para mostrar en el editor
    template_pdf_width = fields.Integer(
        related='template_id.pdf_width',
        string='Ancho PDF',
        readonly=True
    )
    template_pdf_height = fields.Integer(
        related='template_id.pdf_height',
        string='Alto PDF',
        readonly=True
    )

    @api.constrains('position_x', 'position_y')
    def _check_position(self):
        """Validar que las posiciones sean positivas"""
        for record in self:
            if record.position_x < 0:
                raise ValidationError(_('La posición X no puede ser negativa.'))
            if record.position_y < 0:
                raise ValidationError(_('La posición Y no puede ser negativa.'))

    @api.constrains('font_size')
    def _check_font_size(self):
        """Validar tamaño de fuente razonable"""
        for record in self:
            if record.font_size < 1 or record.font_size > 200:
                raise ValidationError(_('El tamaño de fuente debe estar entre 1 y 200 puntos.'))

    @api.constrains('rotation')
    def _check_rotation(self):
        """Normalizar rotación entre 0-360"""
        for record in self:
            if record.rotation < 0 or record.rotation > 360:
                raise ValidationError(_('La rotación debe estar entre 0 y 360 grados.'))

    @api.constrains('color')
    def _check_color(self):
        """Validar formato de color hexadecimal"""
        import re
        for record in self:
            if record.color and not re.match(r'^#[0-9A-Fa-f]{6}$', record.color):
                raise ValidationError(_(
                    'El color debe estar en formato hexadecimal (ej: #000000)'
                ))

    @api.constrains('value', 'field_type')
    def _check_value_format(self):
        """Validar formato de variables dinámicas"""
        import re
        for record in self:
            if record.field_type == 'dynamic' and record.value:
                # Buscar variables ${...}
                variables = re.findall(r'\$\{([^}]+)\}', record.value)
                if not variables and '${' not in record.value:
                    # Advertir si parece dinámico pero no tiene variables
                    _logger = self.env['ir.logging']
                    _logger.sudo().create({
                        'name': 'ml.label.template.field',
                        'type': 'server',
                        'level': 'warning',
                        'message': f'Campo "{record.name}" marcado como dinámico pero no contiene variables ${{...}}',
                        'path': 'ml_label_template_field',
                        'func': '_check_value_format',
                        'line': '1',
                    })

    def get_available_variables_info(self):
        """
        Retorna información sobre variables disponibles para usar en campos dinámicos.
        Útil para mostrar ayuda al usuario.
        """
        return {
            'sale_order': {
                'description': 'Orden de Venta',
                'fields': {
                    'name': 'Número de Orden (SO001)',
                    'partner_id.name': 'Nombre del Cliente',
                    'partner_id.phone': 'Teléfono del Cliente',
                    'date_order': 'Fecha de Orden',
                    'amount_total': 'Total',
                    'warehouse_id.name': 'Almacén',
                }
            },
            'ml_order': {
                'description': 'Orden MercadoLibre',
                'fields': {
                    'ml_order_id': 'ID Orden ML',
                    'ml_pack_id': 'Pack ID',
                    'ml_shipment_id': 'Shipment ID',
                    'logistic_type': 'Tipo Logístico',
                }
            },
            'special': {
                'description': 'Variables Especiales',
                'fields': {
                    'today': 'Fecha de Hoy',
                    'now': 'Fecha y Hora Actual',
                    'company.name': 'Nombre Compañía',
                }
            }
        }

    @api.model
    def get_variables_help_text(self):
        """Retorna texto de ayuda formateado para mostrar al usuario"""
        info = self.get_available_variables_info()
        help_text = "Variables disponibles:\n\n"

        for category, data in info.items():
            help_text += f"{data['description']}:\n"
            for var, desc in data['fields'].items():
                help_text += f"  ${{{category}.{var}}} - {desc}\n"
            help_text += "\n"

        return help_text
