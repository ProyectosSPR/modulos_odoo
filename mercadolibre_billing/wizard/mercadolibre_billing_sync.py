# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class MercadoliBillingSync(models.TransientModel):
    _name = 'mercadolibre.billing.sync'
    _description = 'Wizard de Sincronización de Facturación'

    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta ML/MP',
        required=True
    )
    period_from = fields.Date(
        string='Desde',
        required=True,
        help='Fecha de inicio del periodo a sincronizar'
    )
    period_to = fields.Date(
        string='Hasta',
        required=True,
        default=fields.Date.today,
        help='Fecha de fin del periodo a sincronizar'
    )
    billing_group = fields.Selection([
        ('ML', 'MercadoLibre'),
        ('MP', 'MercadoPago'),
        ('both', 'Ambos')
    ], string='Grupo', required=True, default='both')

    document_types = fields.Selection([
        ('bill', 'Solo Facturas'),
        ('both', 'Facturas y Notas de Crédito')
    ], string='Tipos de Documentos', default='both', required=True)

    auto_create_pos = fields.Boolean(
        string='Crear POs Automáticamente',
        default=False,
        help='Crear órdenes de compra después de la sincronización'
    )
    auto_validate_pos = fields.Boolean(
        string='Confirmar POs Automáticamente',
        default=False,
        help='Confirmar las órdenes de compra creadas'
    )

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('done', 'Completado')
    ], string='Estado', default='draft')

    sync_log = fields.Text(
        string='Log de Sincronización',
        readonly=True
    )
    periods_created = fields.Integer(
        string='Periodos Creados',
        readonly=True,
        default=0
    )
    details_synced = fields.Integer(
        string='Detalles Sincronizados',
        readonly=True,
        default=0
    )
    error_count = fields.Integer(
        string='Errores',
        readonly=True,
        default=0
    )
    period_ids = fields.Many2many(
        'mercadolibre.billing.period',
        string='Periodos Procesados',
        readonly=True
    )

    @api.constrains('period_from', 'period_to')
    def _check_dates(self):
        for record in self:
            if record.period_from > record.period_to:
                raise ValidationError(_(
                    'La fecha "Desde" debe ser anterior a la fecha "Hasta".'
                ))

    def action_sync(self):
        """
        Ejecuta la sincronización
        """
        self.ensure_one()

        log_lines = []
        periods_created = 0
        details_synced = 0
        error_count = 0
        period_ids = []

        log_lines.append(f'[INFO] Iniciando sincronización')
        log_lines.append(f'[INFO] Cuenta: {self.account_id.name}')
        log_lines.append(f'[INFO] Periodo: {self.period_from} - {self.period_to}')
        log_lines.append(f'[INFO] Grupo: {self.billing_group}')

        # Generar period_keys
        period_keys = self.env['mercadolibre.billing.period']._generate_period_keys(
            self.period_from, self.period_to
        )

        log_lines.append(f'[INFO] Periodos a procesar: {len(period_keys)}')

        # Determinar qué grupos sincronizar
        groups_to_sync = []
        if self.billing_group == 'both':
            groups_to_sync = ['ML', 'MP']
        else:
            groups_to_sync = [self.billing_group]

        try:
            for group in groups_to_sync:
                for period_key in period_keys:
                    try:
                        log_lines.append(f'\n[INFO] Procesando {group} - {period_key.strftime("%B %Y")}')

                        # Buscar o crear periodo
                        period = self.env['mercadolibre.billing.period'].search([
                            ('period_key', '=', period_key),
                            ('account_id', '=', self.account_id.id),
                            ('billing_group', '=', group)
                        ], limit=1)

                        if not period:
                            period = self.env['mercadolibre.billing.period'].create({
                                'period_key': period_key,
                                'account_id': self.account_id.id,
                                'billing_group': group,
                            })
                            periods_created += 1
                            log_lines.append(f'  [SUCCESS] Periodo creado')
                        else:
                            log_lines.append(f'  [INFO] Periodo ya existe')

                        # Sincronizar detalles
                        if period.state in ('draft', 'error'):
                            period.action_sync_details()
                            details_count = len(period.detail_ids)
                            details_synced += details_count
                            log_lines.append(f'  [SUCCESS] {details_count} detalles sincronizados')

                            # Crear POs si está configurado
                            if self.auto_create_pos:
                                period.action_create_purchase_orders()
                                pos_count = len(period.purchase_order_ids)
                                log_lines.append(f'  [SUCCESS] {pos_count} POs creadas')
                        else:
                            log_lines.append(f'  [INFO] Periodo ya sincronizado (estado: {period.state})')

                        period_ids.append(period.id)

                    except Exception as e:
                        error_count += 1
                        error_msg = f'  [ERROR] {str(e)}'
                        log_lines.append(error_msg)
                        _logger.error(f'Error sincronizando periodo {period_key} ({group}): {e}')
                        continue

            log_lines.append(f'\n[SUCCESS] Sincronización completada')
            log_lines.append(f'  - Periodos creados: {periods_created}')
            log_lines.append(f'  - Detalles sincronizados: {details_synced}')
            log_lines.append(f'  - Errores: {error_count}')

            self.write({
                'state': 'done',
                'sync_log': '\n'.join(log_lines),
                'periods_created': periods_created,
                'details_synced': details_synced,
                'error_count': error_count,
                'period_ids': [(6, 0, period_ids)]
            })

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'mercadolibre.billing.sync',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }

        except Exception as e:
            error_msg = str(e)
            log_lines.append(f'\n[ERROR] Error fatal: {error_msg}')

            self.write({
                'state': 'done',
                'sync_log': '\n'.join(log_lines),
                'periods_created': periods_created,
                'details_synced': details_synced,
                'error_count': error_count + 1,
                'period_ids': [(6, 0, period_ids)]
            })

            raise ValidationError(_(
                'Error al sincronizar:\n%s'
            ) % error_msg)

    def action_view_periods(self):
        """Ver periodos procesados"""
        self.ensure_one()

        return {
            'name': _('Periodos de Facturación'),
            'type': 'ir.actions.act_window',
            'res_model': 'mercadolibre.billing.period',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.period_ids.ids)],
        }

    def action_new_sync(self):
        """Nueva sincronización"""
        return {
            'name': _('Sincronizar Facturación'),
            'type': 'ir.actions.act_window',
            'res_model': 'mercadolibre.billing.sync',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_account_id': self.account_id.id}
        }
