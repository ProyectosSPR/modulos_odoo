# -*- coding: utf-8 -*-

import logging
import requests
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MercadolibreShipmentSync(models.TransientModel):
    _name = 'mercadolibre.shipment.sync'
    _description = 'Asistente de Sincronizacion de Envios'

    state = fields.Selection([
        ('draft', 'Configuracion'),
        ('done', 'Completado'),
        ('error', 'Error'),
    ], string='Estado', default='draft')

    account_id = fields.Many2one(
        'mercadolibre.account',
        string='Cuenta MercadoLibre',
        required=True,
        default=lambda self: self._default_account_id()
    )

    # Tipo de sincronizacion
    sync_type = fields.Selection([
        ('all_orders', 'Todos los envios de ordenes'),
        ('pending_only', 'Solo ordenes sin envio sincronizado'),
        ('specific', 'Envio especifico'),
        ('by_status', 'Por estado de envio'),
    ], string='Tipo de Sincronizacion', default='pending_only', required=True)

    specific_shipment_id = fields.Char(
        string='ID de Envio',
        help='ID del envio en MercadoLibre'
    )

    status_filter = fields.Selection([
        ('all', 'Todos'),
        ('pending', 'Pendientes'),
        ('ready_to_ship', 'Listos para enviar'),
        ('shipped', 'Enviados'),
        ('in_transit', 'En transito'),
        ('delivered', 'Entregados'),
    ], string='Estado', default='all')

    # Rango de fechas (para filtrar ordenes)
    date_from = fields.Date(
        string='Desde',
        default=lambda self: fields.Date.today() - timedelta(days=30)
    )
    date_to = fields.Date(
        string='Hasta',
        default=fields.Date.today
    )

    limit = fields.Integer(
        string='Limite',
        default=100,
        help='Maximo de envios a sincronizar'
    )

    update_logistic_type = fields.Boolean(
        string='Actualizar tipo logistico',
        default=True,
        help='Actualiza el tipo logistico en las ordenes ML'
    )

    # Resultados
    sync_count = fields.Integer(
        string='Envios Sincronizados',
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
    sync_log = fields.Text(
        string='Log de Sincronizacion',
        readonly=True
    )

    def _default_account_id(self):
        """Obtiene la cuenta por defecto"""
        account = self.env['mercadolibre.account'].search([
            ('state', '=', 'connected')
        ], limit=1)
        return account.id if account else False

    def action_sync(self):
        """Ejecuta la sincronizacion de envios"""
        self.ensure_one()

        if self.sync_type == 'specific':
            return self._sync_specific_shipment()
        else:
            return self._sync_orders_shipments()

    def _sync_specific_shipment(self):
        """Sincroniza un envio especifico"""
        self.ensure_one()

        if not self.specific_shipment_id:
            raise UserError(_('Debe especificar el ID del envio'))

        Shipment = self.env['mercadolibre.shipment']
        shipment = Shipment.sync_shipment_by_id(
            self.specific_shipment_id,
            self.account_id
        )

        if shipment:
            self.write({
                'state': 'done',
                'sync_count': 1,
                'created_count': 1 if not shipment.create_date else 0,
                'updated_count': 1 if shipment.create_date else 0,
                'sync_log': f'Envio {shipment.name} sincronizado exitosamente.\n'
                           f'Estado: {dict(shipment._fields["status"].selection).get(shipment.status, "")}\n'
                           f'Tipo logistico: {dict(shipment._fields["logistic_type"].selection).get(shipment.logistic_type, "") or "No especificado"}'
            })
        else:
            self.write({
                'state': 'error',
                'sync_log': f'No se pudo sincronizar el envio {self.specific_shipment_id}'
            })

        return self._return_wizard()

    def _sync_orders_shipments(self):
        """Sincroniza envios de las ordenes"""
        self.ensure_one()

        Shipment = self.env['mercadolibre.shipment']
        Order = self.env['mercadolibre.order']

        # Construir dominio de busqueda de ordenes
        domain = [
            ('account_id', '=', self.account_id.id),
            ('ml_shipment_id', '!=', False),
            ('ml_shipment_id', '!=', ''),
        ]

        if self.date_from:
            domain.append(('date_closed', '>=', self.date_from))
        if self.date_to:
            domain.append(('date_closed', '<=', self.date_to))

        if self.sync_type == 'pending_only':
            # Solo ordenes sin shipment sincronizado
            domain.append(('shipment_id', '=', False))

        orders = Order.search(domain, limit=self.limit, order='date_closed desc')

        sync_count = 0
        created_count = 0
        updated_count = 0
        error_count = 0
        log_lines = []

        for order in orders:
            try:
                shipment = Shipment.sync_shipment_by_id(
                    order.ml_shipment_id,
                    self.account_id
                )

                if shipment:
                    # Vincular shipment con orden
                    if not shipment.order_id:
                        shipment.order_id = order.id

                    # Actualizar logistic_type si está habilitado
                    if self.update_logistic_type and shipment.logistic_type:
                        if order.logistic_type != shipment.logistic_type:
                            order.write({'logistic_type': shipment.logistic_type})

                    sync_count += 1
                    if shipment.create_date == shipment.write_date:
                        created_count += 1
                        log_lines.append(f'+ Creado: {shipment.name} (Orden: {order.ml_order_id})')
                    else:
                        updated_count += 1
                        log_lines.append(f'= Actualizado: {shipment.name} (Orden: {order.ml_order_id})')
                else:
                    error_count += 1
                    log_lines.append(f'! Error: No se pudo sincronizar envio {order.ml_shipment_id}')

            except Exception as e:
                error_count += 1
                log_lines.append(f'! Error en orden {order.ml_order_id}: {str(e)}')
                _logger.error('Error sincronizando shipment de orden %s: %s',
                            order.ml_order_id, str(e))

        self.write({
            'state': 'done' if error_count == 0 else 'error',
            'sync_count': sync_count,
            'created_count': created_count,
            'updated_count': updated_count,
            'error_count': error_count,
            'sync_log': '\n'.join(log_lines) if log_lines else 'No se encontraron ordenes para sincronizar'
        })

        return self._return_wizard()

    def _return_wizard(self):
        """Retorna la vista del wizard con los resultados"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sincronizacion de Envios'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_view_shipments(self):
        """Ver envios sincronizados"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Envios Sincronizados'),
            'res_model': 'mercadolibre.shipment',
            'view_mode': 'tree,form',
            'domain': [('account_id', '=', self.account_id.id)],
            'context': {'default_account_id': self.account_id.id},
        }

    def action_new_sync(self):
        """Iniciar nueva sincronizacion"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sincronizar Envios'),
            'res_model': self._name,
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_account_id': self.account_id.id},
        }
