# -*- coding: utf-8 -*-
"""
Configuración de campos de búsqueda para conciliación de pagos.
"""

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class BillingReconciliationField(models.Model):
    _name = 'billing.reconciliation.field'
    _description = 'Campo de búsqueda para conciliación'
    _order = 'sequence, id'

    name = fields.Char(
        string='Nombre del Campo',
        required=True,
        help='Nombre descriptivo del campo (ej: Número de Orden)'
    )

    # Campos de orden - Selection dinámico
    field_name = fields.Selection(
        selection='_get_sale_order_fields',
        string='Campo en Orden de Venta',
        required=True,
        help='Campo de la orden de venta a usar como referencia'
    )

    # Campos de pago - Selection dinámico
    payment_field = fields.Selection(
        selection='_get_payment_fields',
        string='Campo en Pago',
        required=True,
        default='ref',
        help='Campo del pago donde buscar la referencia'
    )

    search_mode = fields.Selection([
        ('exact', 'Coincidencia Exacta'),
        ('ilike', 'Contiene (sin distinguir mayúsculas)'),
        ('like', 'Contiene (distingue mayúsculas)'),
    ], string='Modo de Búsqueda', default='ilike',
        help='Cómo buscar la referencia en el campo de pago')

    sequence = fields.Integer(
        string='Secuencia',
        default=10,
        help='Orden de prioridad al buscar (menor = mayor prioridad)'
    )

    active = fields.Boolean(
        string='Activo',
        default=True
    )

    description = fields.Text(
        string='Descripción',
        help='Descripción del campo y cuándo usarlo'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company
    )

    _sql_constraints = [
        ('field_name_unique', 'UNIQUE(field_name, company_id)',
         'Ya existe una configuración para este campo en esta compañía.')
    ]

    @api.model
    def _get_sale_order_fields(self):
        """
        Obtiene los campos disponibles del modelo sale.order para selección.
        Incluye campos de tipo Char que son útiles para búsqueda.
        """
        # Campos comunes que siempre están disponibles
        common_fields = [
            ('name', 'Número de Orden (name)'),
            ('client_order_ref', 'Referencia del Cliente (client_order_ref)'),
        ]

        # Campos adicionales que pueden existir si hay módulos ML instalados
        additional_fields = [
            ('ml_order_id', 'ID Orden MercadoLibre (ml_order_id)'),
            ('ml_pack_id', 'ID Pack MercadoLibre (ml_pack_id)'),
            ('origin', 'Documento Origen (origin)'),
            ('reference', 'Referencia de Pago (reference)'),
        ]

        result = list(common_fields)

        # Verificar qué campos adicionales existen en el modelo
        try:
            sale_order_model = self.env['sale.order']
            for field_name, field_label in additional_fields:
                if field_name in sale_order_model._fields:
                    result.append((field_name, field_label))
        except Exception as e:
            _logger.warning(f"Error obteniendo campos de sale.order: {e}")

        return result

    @api.model
    def _get_payment_fields(self):
        """
        Obtiene los campos disponibles del modelo account.payment para selección.
        """
        # Campos comunes en account.payment
        common_fields = [
            ('ref', 'Referencia/Memo (ref)'),
            ('name', 'Nombre/Número (name)'),
        ]

        # Campos adicionales que pueden existir
        additional_fields = [
            ('ml_order_id', 'ID Orden MercadoLibre (ml_order_id)'),
            ('ml_pack_id', 'ID Pack MercadoLibre (ml_pack_id)'),
            ('mp_order_id', 'ID Orden MercadoPago (mp_order_id)'),
            ('mp_external_reference', 'Referencia Externa MP (mp_external_reference)'),
            ('communication', 'Comunicación (communication)'),
        ]

        result = list(common_fields)

        # Verificar qué campos adicionales existen en el modelo
        try:
            payment_model = self.env['account.payment']
            for field_name, field_label in additional_fields:
                if field_name in payment_model._fields:
                    result.append((field_name, field_label))
        except Exception as e:
            _logger.warning(f"Error obteniendo campos de account.payment: {e}")

        return result

    @api.model
    def get_active_fields(self, company_id=None):
        """
        Obtiene los campos activos para conciliación.
        """
        domain = [('active', '=', True)]
        if company_id:
            domain.append(('company_id', 'in', [company_id, False]))

        fields = self.search(domain, order='sequence')
        _logger.info(f"[RECONCILIATION] Campos de búsqueda activos: {fields.mapped('name')}")
        return fields

    def get_search_domain(self, search_value, partner_id):
        """
        Genera el dominio de búsqueda para account.payment.
        """
        self.ensure_one()
        if self.search_mode == 'exact':
            operator = '='
        elif self.search_mode == 'ilike':
            operator = 'ilike'
        else:
            operator = 'like'

        domain = [
            (self.payment_field, operator, search_value),
            ('partner_id', '=', partner_id),
            ('state', '=', 'posted'),
            ('payment_type', '=', 'inbound'),  # Solo pagos recibidos
        ]

        _logger.info(
            f"[RECONCILIATION] Dominio de búsqueda generado:\n"
            f"  - Campo pago: {self.payment_field}\n"
            f"  - Operador: {operator}\n"
            f"  - Valor búsqueda: {search_value}\n"
            f"  - Partner ID: {partner_id}\n"
            f"  - Dominio completo: {domain}"
        )

        return domain
