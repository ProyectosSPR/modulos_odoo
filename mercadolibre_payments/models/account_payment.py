# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    # =====================================================
    # CAMPOS DE MERCADOPAGO
    # =====================================================
    ml_payment_id = fields.Many2one(
        'mercadolibre.payment',
        string='Pago MercadoPago',
        readonly=True,
        help='Referencia al pago de MercadoPago que origino este pago'
    )

    # Campos de informacion ML (readonly, se llenan automaticamente)
    ml_payment_mp_id = fields.Char(
        string='ID Pago MP',
        readonly=True,
        help='ID del pago en MercadoPago'
    )
    ml_order_id = fields.Char(
        string='Order ID',
        readonly=True,
        help='ID de la orden en MercadoLibre'
    )
    ml_pack_id = fields.Char(
        string='Pack ID',
        readonly=True,
        help='ID del pack en MercadoLibre (envios con multiples ordenes)'
    )

    # Estado de pago MercadoPago
    ml_status = fields.Selection([
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
        ('authorized', 'Autorizado'),
        ('in_process', 'En Proceso'),
        ('in_mediation', 'En Mediacion'),
        ('rejected', 'Rechazado'),
        ('cancelled', 'Cancelado'),
        ('refunded', 'Reembolsado'),
        ('charged_back', 'Contracargo'),
    ], string='Estado MP', readonly=True)

    ml_status_detail = fields.Char(
        string='Detalle Estado',
        readonly=True
    )

    # Estado de liberacion/acreditacion
    ml_release_status = fields.Selection([
        ('released', 'Liberado'),
        ('pending', 'Pendiente'),
        ('not_released', 'No Liberado'),
        ('unavailable', 'No Disponible'),
    ], string='Estado Acreditacion', readonly=True,
       help='Estado de liberacion del dinero en MercadoPago')

    ml_release_status_display = fields.Char(
        string='Acreditacion',
        compute='_compute_release_status_display',
        store=False
    )

    # Metodo de pago
    ml_payment_method = fields.Char(
        string='Metodo Pago MP',
        readonly=True
    )

    # Referencia de orden de venta
    ml_sale_order_id = fields.Many2one(
        'sale.order',
        string='Orden de Venta',
        readonly=True,
        help='Orden de venta relacionada encontrada por client_order_ref'
    )
    ml_sale_order_name = fields.Char(
        string='Nombre Orden',
        readonly=True,
        help='Nombre de la orden de venta (ej: DML06557)'
    )

    # Indica si es pago de ML
    is_ml_payment = fields.Boolean(
        string='Es Pago ML',
        compute='_compute_is_ml_payment',
        store=True
    )

    # Usuario responsable del registro (campo propio, almacenado)
    # NOTA: user_id de account.payment base NO se almacena (store=False)
    ml_responsible_user_id = fields.Many2one(
        'res.users',
        string='Registrado por',
        help='Usuario que registro este pago desde MercadoLibre'
    )

    @api.depends('ml_payment_id')
    def _compute_is_ml_payment(self):
        for record in self:
            record.is_ml_payment = bool(record.ml_payment_id)

    @api.depends('ml_release_status')
    def _compute_release_status_display(self):
        """Traduce el estado de acreditacion a texto legible"""
        status_map = {
            'released': 'Acreditado',
            'pending': 'Pendiente de Acreditar',
            'not_released': 'No Acreditado',
            'unavailable': 'No Disponible',
        }
        for record in self:
            record.ml_release_status_display = status_map.get(record.ml_release_status, '')

    def _build_ml_ref(self, ml_payment, sale_order_name=None):
        """
        Construye la referencia del pago con la estructura:
        [Nombre Orden Venta] - [pack_id o order_id] - [payment_id]

        Args:
            ml_payment: mercadolibre.payment record
            sale_order_name: nombre de la orden de venta (opcional)

        Returns:
            str con la referencia formateada
        """
        parts = []

        # Parte 1: Nombre de la orden de venta
        if sale_order_name:
            parts.append(sale_order_name)

        # Parte 2: pack_id (prioridad) o order_id
        if ml_payment.mp_order_id:
            # mp_order_id puede contener el order_id
            order_ref = ml_payment.mp_order_id
        else:
            order_ref = ''

        # Buscar pack_id en raw_data si existe
        pack_id = ''
        if ml_payment.raw_data:
            import json
            try:
                raw = json.loads(ml_payment.raw_data)
                # Buscar en order.id y en metadata
                order_data = raw.get('order', {}) or {}
                pack_id = str(order_data.get('pack_id', '')) if order_data.get('pack_id') else ''

                # Si no hay order_ref, intentar obtener de order.id
                if not order_ref:
                    order_ref = str(order_data.get('id', '')) if order_data.get('id') else ''
            except (json.JSONDecodeError, TypeError):
                pass

        # Prioridad: pack_id > order_id
        ml_ref_id = pack_id if pack_id else order_ref
        if ml_ref_id:
            parts.append(ml_ref_id)

        # Parte 3: Payment ID
        if ml_payment.mp_payment_id:
            parts.append(ml_payment.mp_payment_id)

        return ' - '.join(parts) if parts else f'ML-{ml_payment.mp_payment_id}'

    def _find_sale_order_by_ml_ref(self, ml_payment):
        """
        Busca la orden de venta basandose en el pack_id u order_id
        en el campo client_order_ref.

        Args:
            ml_payment: mercadolibre.payment record

        Returns:
            tuple (sale.order record or False, pack_id, order_id)
        """
        SaleOrder = self.env['sale.order']

        pack_id = ''
        order_id = ml_payment.mp_order_id or ''

        # Extraer pack_id de raw_data
        if ml_payment.raw_data:
            import json
            try:
                raw = json.loads(ml_payment.raw_data)
                order_data = raw.get('order', {}) or {}
                pack_id = str(order_data.get('pack_id', '')) if order_data.get('pack_id') else ''
                if not order_id:
                    order_id = str(order_data.get('id', '')) if order_data.get('id') else ''
            except (json.JSONDecodeError, TypeError):
                pass

        # Buscar por pack_id primero (prioridad)
        sale_order = False
        search_ref = pack_id if pack_id else order_id

        if search_ref:
            # Buscar en client_order_ref
            sale_order = SaleOrder.search([
                ('client_order_ref', 'ilike', search_ref),
                ('company_id', '=', self.env.company.id)
            ], limit=1)

            # Si no encuentra, buscar exacto
            if not sale_order:
                sale_order = SaleOrder.search([
                    ('client_order_ref', '=', search_ref),
                ], limit=1)

            # Buscar tambien si el ref contiene el ID
            if not sale_order:
                sale_order = SaleOrder.search([
                    '|',
                    ('name', 'ilike', search_ref),
                    ('client_order_ref', 'ilike', search_ref),
                ], limit=1)

        return sale_order, pack_id, order_id

    @api.model
    def create_from_ml_payment(self, ml_payment, payment_vals):
        """
        Crea un pago de Odoo desde un pago de MercadoPago,
        llenando automaticamente los campos de ML y construyendo el ref.

        Args:
            ml_payment: mercadolibre.payment record
            payment_vals: dict con valores base del pago

        Returns:
            account.payment record
        """
        # Buscar orden de venta
        sale_order, pack_id, order_id = self._find_sale_order_by_ml_ref(ml_payment)
        sale_order_name = sale_order.name if sale_order else ''

        # Construir referencia
        ref = self._build_ml_ref(ml_payment, sale_order_name)

        # Agregar campos de ML
        payment_vals.update({
            'ref': ref,
            'ml_payment_id': ml_payment.id,
            'ml_payment_mp_id': ml_payment.mp_payment_id,
            'ml_order_id': order_id,
            'ml_pack_id': pack_id,
            'ml_status': ml_payment.status,
            'ml_status_detail': ml_payment.status_detail,
            'ml_release_status': ml_payment.money_release_status,
            'ml_payment_method': ml_payment.payment_method_name or ml_payment.payment_type,
            'ml_sale_order_id': sale_order.id if sale_order else False,
            'ml_sale_order_name': sale_order_name,
        })

        payment = self.create(payment_vals)

        _logger.info('Pago Odoo creado desde ML: %s (ref: %s)', payment.name, ref)

        return payment

    def action_view_ml_payment(self):
        """Abre el pago de MercadoPago relacionado"""
        self.ensure_one()
        if not self.ml_payment_id:
            return False

        return {
            'type': 'ir.actions.act_window',
            'name': _('Pago MercadoPago'),
            'res_model': 'mercadolibre.payment',
            'res_id': self.ml_payment_id.id,
            'view_mode': 'form',
        }

    def action_view_sale_order(self):
        """Abre la orden de venta relacionada"""
        self.ensure_one()
        if not self.ml_sale_order_id:
            return False

        return {
            'type': 'ir.actions.act_window',
            'name': _('Orden de Venta'),
            'res_model': 'sale.order',
            'res_id': self.ml_sale_order_id.id,
            'view_mode': 'form',
        }
