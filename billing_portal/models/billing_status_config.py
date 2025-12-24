# -*- coding: utf-8 -*-

from odoo import models, fields, api


class BillingStatusConfig(models.Model):
    _name = 'billing.status.config'
    _description = 'Configuración de Estados de Facturación'
    _order = 'sequence, id'

    name = fields.Char(
        string='Nombre',
        required=True
    )

    code = fields.Char(
        string='Código',
        required=True
    )

    description = fields.Text(
        string='Descripción'
    )

    sequence = fields.Integer(
        string='Secuencia',
        default=10
    )

    progress_min = fields.Integer(
        string='Progreso Mínimo',
        default=0
    )

    progress_max = fields.Integer(
        string='Progreso Máximo',
        default=100
    )

    color = fields.Char(
        string='Color',
        default='#3498db'
    )

    icon = fields.Char(
        string='Icono',
        default='fa-spinner',
        help='Clase de FontAwesome (ej: fa-check, fa-spinner)'
    )

    is_error = fields.Boolean(
        string='Es Error',
        default=False
    )

    is_final = fields.Boolean(
        string='Es Final',
        default=False
    )

    active = fields.Boolean(
        string='Activo',
        default=True
    )

    message_template = fields.Char(
        string='Plantilla de Mensaje',
        help='Mensaje a mostrar en este estado. Use {variables} para datos dinámicos.'
    )
