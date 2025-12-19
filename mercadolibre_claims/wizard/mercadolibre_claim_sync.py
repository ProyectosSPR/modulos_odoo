# -*- coding: utf-8 -*-

import json
import logging
import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MercadolibreClaimSyncWizard(models.TransientModel):
    _name = 'mercadolibre.claim.sync.wizard'
    _description = 'Wizard Sincronizacion de Reclamos'

    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML',
        required=True,
        domain="[('state', '=', 'connected')]"
    )

    status_filter = fields.Selection([
        ('all', 'Todos'),
        ('opened', 'Solo Abiertos'),
        ('closed', 'Solo Cerrados'),
    ], string='Filtrar por Estado', default='opened')

    type_filter = fields.Selection([
        ('all', 'Todos los Tipos'),
        ('mediations', 'Solo Mediaciones'),
        ('returns', 'Solo Devoluciones'),
    ], string='Filtrar por Tipo', default='all')

    limit = fields.Integer(
        string='Limite',
        default=50,
        help='Numero maximo de reclamos a sincronizar'
    )

    # Resultados
    sync_result = fields.Text(
        string='Resultado',
        readonly=True
    )
    synced_count = fields.Integer(
        string='Sincronizados',
        readonly=True
    )
    created_count = fields.Integer(
        string='Nuevos',
        readonly=True
    )
    updated_count = fields.Integer(
        string='Actualizados',
        readonly=True
    )
    error_count = fields.Integer(
        string='Errores',
        readonly=True
    )

    state = fields.Selection([
        ('config', 'Configuracion'),
        ('done', 'Completado'),
    ], default='config')

    def action_sync(self):
        """Ejecuta la sincronizacion"""
        self.ensure_one()

        access_token = self.account_id.get_valid_token_with_retry()
        if not access_token:
            raise UserError(_('No se pudo obtener token valido para la cuenta'))

        params = {
            'limit': self.limit,
        }

        if self.status_filter and self.status_filter != 'all':
            params['status'] = self.status_filter

        if self.type_filter and self.type_filter != 'all':
            params['type'] = self.type_filter

        url = 'https://api.mercadolibre.com/post-purchase/v1/claims/search'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        try:
            response = requests.get(url, params=params, headers=headers, timeout=60)

            if response.status_code != 200:
                raise UserError(_('Error API: %s') % response.text)

            data = response.json()

        except requests.exceptions.RequestException as e:
            raise UserError(_('Error de conexion: %s') % str(e))

        results = data.get('data', [])
        ClaimModel = self.env['mercadolibre.claim']

        synced_count = 0
        created_count = 0
        updated_count = 0
        error_count = 0
        log_lines = []

        for claim_data in results:
            try:
                claim, is_new = ClaimModel.create_from_ml_data(claim_data, self.account_id)
                synced_count += 1

                if is_new:
                    created_count += 1
                    log_lines.append(f'[NUEVO] {claim.name} - {claim.type}')
                else:
                    updated_count += 1
                    log_lines.append(f'[ACTUALIZADO] {claim.name}')

            except Exception as e:
                error_count += 1
                log_lines.append(f'[ERROR] Claim {claim_data.get("id")}: {str(e)}')
                _logger.error('Error procesando claim %s: %s', claim_data.get('id'), str(e))

        log_lines.insert(0, f'Total procesados: {synced_count}')
        log_lines.insert(1, f'Nuevos: {created_count}, Actualizados: {updated_count}, Errores: {error_count}')
        log_lines.insert(2, '-' * 40)

        self.write({
            'state': 'done',
            'sync_result': '\n'.join(log_lines),
            'synced_count': synced_count,
            'created_count': created_count,
            'updated_count': updated_count,
            'error_count': error_count,
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_view_claims(self):
        """Abre la lista de claims sincronizados"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reclamos Sincronizados'),
            'res_model': 'mercadolibre.claim',
            'view_mode': 'tree,form',
            'domain': [('account_id', '=', self.account_id.id)],
            'context': {'search_default_filter_opened': 1},
        }
