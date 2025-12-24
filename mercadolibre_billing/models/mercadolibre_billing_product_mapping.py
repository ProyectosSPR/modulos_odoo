# -*- coding: utf-8 -*-

import logging
import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MercadolibreBillingProductMapping(models.Model):
    _name = 'mercadolibre.billing.product.mapping'
    _description = 'Mapeo de Cargos ML/MP a Productos'
    _order = 'charge_type, id'
    _rec_name = 'charge_type'

    charge_type = fields.Char(
        string='Tipo de Cargo ML/MP',
        required=True,
        index=True,
        help='Texto del cargo como viene de MercadoLibre (transaction_detail)'
    )
    charge_code = fields.Char(
        string='Código de Cargo',
        index=True,
        help='Código o subtipo del cargo (detail_sub_type)'
    )
    billing_group = fields.Selection([
        ('ML', 'MercadoLibre'),
        ('MP', 'MercadoPago'),
        ('both', 'Ambos')
    ], string='Grupo', default='both', required=True,
       help='Aplica a MercadoLibre, MercadoPago o ambos')

    product_id = fields.Many2one(
        'product.product',
        string='Producto Odoo',
        domain=[('purchase_ok', '=', True)],
        help='Producto a usar en las órdenes de compra para este tipo de cargo'
    )
    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML/MP',
        ondelete='cascade',
        help='Si se especifica, este mapeo aplica solo para esta cuenta. Si está vacío, aplica globalmente.'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        required=True
    )
    active = fields.Boolean(
        string='Activo',
        default=True
    )
    usage_count = fields.Integer(
        string='Veces Usado',
        compute='_compute_usage_count',
        help='Cantidad de detalles que usan este tipo de cargo'
    )
    notes = fields.Text(
        string='Notas',
        help='Notas internas sobre este tipo de cargo'
    )

    _sql_constraints = [
        ('charge_type_account_uniq', 'unique(charge_type, account_id, company_id)',
         'Ya existe un mapeo para este tipo de cargo en esta cuenta/compañía.')
    ]

    def _compute_usage_count(self):
        """Calcula cuántos detalles usan este tipo de cargo"""
        Detail = self.env['mercadolibre.billing.detail']
        for record in self:
            record.usage_count = Detail.search_count([
                ('transaction_detail', '=', record.charge_type),
                ('company_id', '=', record.company_id.id)
            ])

    @api.model
    def get_product_for_charge(self, transaction_detail, account_id=None, billing_group=None):
        """
        Obtiene el producto mapeado para un tipo de cargo específico.

        Prioridad de búsqueda:
        1. Mapeo específico para la cuenta
        2. Mapeo global (sin cuenta específica)
        3. None si no hay mapeo

        Args:
            transaction_detail: Texto del tipo de cargo
            account_id: ID de la cuenta ML/MP (opcional)
            billing_group: 'ML' o 'MP' (opcional)

        Returns:
            product.product record o False
        """
        if not transaction_detail:
            return False

        domain = [
            ('charge_type', '=', transaction_detail),
            ('company_id', '=', self.env.company.id),
            ('product_id', '!=', False)
        ]

        # Primero buscar mapeo específico para la cuenta
        if account_id:
            specific_mapping = self.search(domain + [('account_id', '=', account_id)], limit=1)
            if specific_mapping:
                return specific_mapping.product_id

        # Buscar mapeo global (sin cuenta específica)
        global_domain = domain + [('account_id', '=', False)]

        # Filtrar por grupo si se especifica
        if billing_group:
            global_domain.append(('billing_group', 'in', [billing_group, 'both']))

        global_mapping = self.search(global_domain, limit=1)
        if global_mapping:
            return global_mapping.product_id

        return False

    @api.model
    def sync_charge_types_from_details(self, account_id=None):
        """
        Sincroniza tipos de cargos desde los detalles ya descargados.
        Crea registros de mapeo vacíos para los tipos que no existen.

        Args:
            account_id: ID de cuenta específica o None para todas

        Returns:
            dict: Resultado con nuevos y existentes
        """
        Detail = self.env['mercadolibre.billing.detail']

        # Obtener todos los tipos de cargo únicos
        domain = [('transaction_detail', '!=', False)]
        if account_id:
            domain.append(('account_id', '=', account_id))

        details = Detail.search(domain)

        # Extraer tipos únicos con su información
        charge_types = {}
        for detail in details:
            key = detail.transaction_detail
            if key and key not in charge_types:
                charge_types[key] = {
                    'charge_type': detail.transaction_detail,
                    'charge_code': detail.detail_sub_type,
                    'billing_group': detail.billing_group or 'both',
                }

        created = []
        existing = []

        for charge_type, data in charge_types.items():
            # Verificar si ya existe
            existing_mapping = self.search([
                ('charge_type', '=', charge_type),
                ('company_id', '=', self.env.company.id)
            ], limit=1)

            if existing_mapping:
                existing.append(charge_type)
            else:
                # Crear nuevo mapeo vacío (sin producto)
                self.create({
                    'charge_type': data['charge_type'],
                    'charge_code': data['charge_code'],
                    'billing_group': data['billing_group'],
                    'company_id': self.env.company.id,
                })
                created.append(charge_type)

        return {
            'created': len(created),
            'existing': len(existing),
            'total': len(charge_types),
            'created_types': created,
        }

    @api.model
    def sync_charge_types_from_api(self, account_id, period_key=None):
        """
        Sincroniza tipos de cargos directamente desde la API de MercadoLibre.
        Descarga detalles del mes actual (o especificado) y extrae tipos únicos.

        Args:
            account_id: ID de la cuenta ML/MP
            period_key: Fecha del periodo (opcional, default: mes actual)

        Returns:
            dict: Resultado con nuevos y existentes
        """
        account = self.env['mercadolibre.account'].browse(account_id)
        if not account:
            raise UserError(_('Cuenta no encontrada'))

        token = account.get_valid_token()
        if not token:
            raise UserError(_('No se pudo obtener un token válido'))

        # Usar mes actual si no se especifica
        if not period_key:
            period_key = fields.Date.today().replace(day=1)

        period_key_str = period_key.strftime('%Y-%m-%d') if hasattr(period_key, 'strftime') else str(period_key)

        charge_types = {}

        # Sincronizar para ML y MP
        for group in ['ML', 'MP']:
            url = f'https://api.mercadolibre.com/billing/integration/periods/key/{period_key_str}/group/{group}/details'

            offset = 0
            limit = 50
            display = None

            while display != 'complete':
                try:
                    params = {
                        'document_type': 'BILL',
                        'limit': limit,
                        'offset': offset
                    }
                    headers = {'Authorization': f'Bearer {token}'}

                    response = requests.get(url, headers=headers, params=params, timeout=60)

                    if response.status_code != 200:
                        _logger.warning(f'Error al obtener tipos de cargo para {group}: {response.status_code}')
                        break

                    data = response.json()
                    results = data.get('results', [])
                    display = data.get('display', 'complete')

                    # Extraer tipos únicos
                    for result in results:
                        charge_info = result.get('charge_info', {})
                        transaction_detail = charge_info.get('transaction_detail')

                        if transaction_detail and transaction_detail not in charge_types:
                            charge_types[transaction_detail] = {
                                'charge_type': transaction_detail,
                                'charge_code': charge_info.get('detail_sub_type'),
                                'billing_group': group,
                            }

                    offset += limit

                except Exception as e:
                    _logger.error(f'Error sincronizando tipos de cargo: {e}')
                    break

        # Crear mapeos para tipos nuevos
        created = []
        existing = []

        for charge_type, data in charge_types.items():
            existing_mapping = self.search([
                ('charge_type', '=', charge_type),
                ('company_id', '=', self.env.company.id)
            ], limit=1)

            if existing_mapping:
                existing.append(charge_type)
            else:
                self.create({
                    'charge_type': data['charge_type'],
                    'charge_code': data['charge_code'],
                    'billing_group': data['billing_group'],
                    'company_id': self.env.company.id,
                    'account_id': account_id,
                })
                created.append(charge_type)

        return {
            'created': len(created),
            'existing': len(existing),
            'total': len(charge_types),
            'created_types': created,
        }

    def action_view_details(self):
        """Ver detalles que usan este tipo de cargo"""
        self.ensure_one()
        return {
            'name': _('Detalles con "%s"') % self.charge_type,
            'type': 'ir.actions.act_window',
            'res_model': 'mercadolibre.billing.detail',
            'view_mode': 'tree,form',
            'domain': [
                ('transaction_detail', '=', self.charge_type),
                ('company_id', '=', self.company_id.id)
            ],
        }
