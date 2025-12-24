# -*- coding: utf-8 -*-

import logging
import re
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Límite de caracteres de MercadoLibre
ML_MESSAGE_CHAR_LIMIT = 350


class MercadolibreMessageTemplate(models.Model):
    _name = 'mercadolibre.message.template'
    _description = 'Plantilla de Mensaje ML'
    _order = 'sequence, name'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre identificativo de la plantilla'
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # Clasificación
    template_type = fields.Selection([
        ('greeting', 'Saludo Inicial'),
        ('billing_request', 'Solicitud de Facturación'),
        ('shipping_info', 'Información de Envío'),
        ('delivery_confirm', 'Confirmación de Entrega'),
        ('out_of_hours', 'Fuera de Horario'),
        ('follow_up', 'Seguimiento'),
        ('thanks', 'Agradecimiento'),
        ('custom', 'Personalizado'),
    ], string='Tipo', default='custom', required=True)

    # Contenido
    body = fields.Text(
        string='Contenido',
        required=True,
        help='Mensaje a enviar. Máximo 350 caracteres. '
             'Variables disponibles: {buyer_name}, {order_number}, {tracking_number}, '
             '{delivery_date}, {product_name}, {seller_name}'
    )
    body_char_count = fields.Integer(
        string='Caracteres',
        compute='_compute_body_char_count',
        store=True
    )
    body_preview = fields.Text(
        string='Vista Previa',
        compute='_compute_body_preview'
    )

    # Opción de mensaje ML
    ml_option_id = fields.Selection([
        ('REQUEST_BILLING_INFO', 'Solicitar Datos de Facturación'),
        ('REQUEST_VARIANTS', 'Solicitar Variantes'),
        ('SEND_INVOICE_LINK', 'Enviar Link de Factura'),
        ('DELIVERY_PROMISE', 'Promesa de Entrega'),
        ('OTHER', 'Otro'),
    ], string='Opción ML', default='OTHER',
       help='Opción de mensaje requerida por MercadoLibre')

    # Restricciones
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company
    )
    account_ids = fields.Many2many(
        'mercadolibre.account',
        'ml_template_account_rel',
        'template_id',
        'account_id',
        string='Cuentas',
        help='Cuentas donde está disponible. Vacío = Todas'
    )

    # Uso
    use_count = fields.Integer(
        string='Veces Usado',
        compute='_compute_use_count'
    )
    last_used = fields.Datetime(string='Último Uso')

    @api.depends('body')
    def _compute_body_char_count(self):
        for record in self:
            record.body_char_count = len(record.body or '')

    @api.depends('body')
    def _compute_body_preview(self):
        """Genera vista previa con datos de ejemplo."""
        example_data = {
            'buyer_name': 'Juan Pérez',
            'order_number': 'ML-123456789',
            'tracking_number': 'TRK789456123',
            'delivery_date': '25/12/2024',
            'product_name': 'Producto Ejemplo',
            'seller_name': 'Tu Tienda',
        }
        for record in self:
            if record.body:
                try:
                    record.body_preview = record._render_template(example_data)
                except Exception:
                    record.body_preview = record.body
            else:
                record.body_preview = ''

    def _compute_use_count(self):
        for record in self:
            record.use_count = self.env['mercadolibre.message'].search_count([
                ('template_id', '=', record.id)
            ])

    @api.constrains('body')
    def _check_body_length(self):
        for record in self:
            if record.body and len(record.body) > ML_MESSAGE_CHAR_LIMIT:
                raise ValidationError(_(
                    'El mensaje no puede exceder %s caracteres. '
                    'Actualmente tiene %s caracteres.'
                ) % (ML_MESSAGE_CHAR_LIMIT, len(record.body)))

    @api.constrains('body')
    def _check_body_variables(self):
        """Valida que las variables usadas sean válidas."""
        valid_vars = {
            'buyer_name', 'order_number', 'tracking_number',
            'delivery_date', 'product_name', 'seller_name',
            'billing_url', 'store_name'
        }
        var_pattern = re.compile(r'\{(\w+)\}')

        for record in self:
            if record.body:
                found_vars = set(var_pattern.findall(record.body))
                invalid_vars = found_vars - valid_vars
                if invalid_vars:
                    raise ValidationError(_(
                        'Variables no válidas en el mensaje: %s\n'
                        'Variables permitidas: %s'
                    ) % (', '.join(invalid_vars), ', '.join(valid_vars)))

    def _render_template(self, data):
        """
        Renderiza la plantilla con los datos proporcionados.

        Args:
            data: dict con valores para las variables

        Returns:
            str: Mensaje renderizado
        """
        self.ensure_one()
        message = self.body or ''

        for key, value in data.items():
            message = message.replace('{%s}' % key, str(value or ''))

        # Limpiar variables no reemplazadas
        message = re.sub(r'\{(\w+)\}', '', message)

        return message[:ML_MESSAGE_CHAR_LIMIT]

    def render_for_order(self, ml_order):
        """
        Renderiza plantilla con datos de una orden ML.

        Args:
            ml_order: mercadolibre.order record

        Returns:
            str: Mensaje renderizado
        """
        self.ensure_one()

        data = {
            'buyer_name': ml_order.buyer_nickname or ml_order.buyer_first_name or 'Cliente',
            'order_number': ml_order.ml_order_id or '',
            'seller_name': ml_order.account_id.name or '',
            'store_name': ml_order.account_id.name or '',
        }

        # Datos de envío si existe
        if ml_order.shipment_id:
            shipment = ml_order.shipment_id
            data['tracking_number'] = shipment.tracking_number or ''
            if shipment.date_delivered:
                data['delivery_date'] = shipment.date_delivered.strftime('%d/%m/%Y')
            else:
                data['delivery_date'] = ''

        # Nombre del producto (primero de la orden)
        if ml_order.order_line_ids:
            data['product_name'] = ml_order.order_line_ids[0].title or ''
        else:
            data['product_name'] = ''

        return self._render_template(data)

    @api.model
    def get_templates_for_account(self, account, template_type=None):
        """
        Obtiene plantillas disponibles para una cuenta.

        Args:
            account: mercadolibre.account
            template_type: str opcional para filtrar por tipo

        Returns:
            recordset de plantillas
        """
        domain = [
            ('active', '=', True),
            '|',
            ('account_ids', '=', False),
            ('account_ids', 'in', account.id),
        ]

        if template_type:
            domain.append(('template_type', '=', template_type))

        return self.search(domain, order='sequence, name')

    def action_preview(self):
        """Abre wizard de vista previa."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vista Previa de Plantilla'),
            'res_model': 'mercadolibre.message.template',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
