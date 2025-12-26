# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MercadolibreBillingSyncChargeTypes(models.TransientModel):
    _name = 'mercadolibre.billing.sync.charge.types'
    _description = 'Sincronizar Tipos de Cargos ML/MP'

    sync_source = fields.Selection([
        ('details', 'Desde Detalles Descargados'),
        ('api', 'Desde API de MercadoLibre')
    ], string='Fuente', default='details', required=True,
       help='Desde dónde extraer los tipos de cargos')

    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML/MP',
        help='Si se especifica, sincroniza solo para esta cuenta. Si está vacío, sincroniza todos.'
    )
    period_key = fields.Date(
        string='Periodo',
        default=lambda self: fields.Date.today().replace(day=1),
        help='Mes a consultar (solo para sincronización desde API)'
    )

    def action_sync(self):
        """Ejecuta la sincronización de tipos de cargos"""
        self.ensure_one()

        Mapping = self.env['mercadolibre.billing.product.mapping']

        if self.sync_source == 'details':
            # Sincronizar desde detalles ya descargados
            result = Mapping.sync_charge_types_from_details(
                account_id=self.account_id.id if self.account_id else None
            )
        else:
            # Sincronizar desde API
            if not self.account_id:
                raise UserError(_('Debe seleccionar una cuenta para sincronizar desde la API'))

            result = Mapping.sync_charge_types_from_api(
                account_id=self.account_id.id,
                period_key=self.period_key
            )

        # Preparar mensaje
        message = _(
            'Tipos nuevos: %(created)s | Ya existentes: %(existing)s | Total: %(total)s'
        ) % result

        # Retornar acción para abrir la lista de mapeos con mensaje
        return {
            'type': 'ir.actions.act_window',
            'name': _('Mapeo de Cargos - %s') % message,
            'res_model': 'mercadolibre.billing.product.mapping',
            'view_mode': 'tree,form',
            'target': 'current',
            'context': {'search_default_no_product': 1 if result['created'] > 0 else 0}
        }
