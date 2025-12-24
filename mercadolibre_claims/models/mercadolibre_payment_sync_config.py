# -*- coding: utf-8 -*-

import json
import logging
import requests
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class MercadolibrePaymentSyncConfigClaims(models.Model):
    """
    Extiende la configuración de sincronización de pagos para incluir
    la sincronización automática de claims/reclamos.
    """
    _inherit = 'mercadolibre.payment.sync.config'

    # =====================================================
    # CONFIGURACION DE SINCRONIZACION DE CLAIMS
    # =====================================================
    sync_claims = fields.Boolean(
        string='Sincronizar Reclamos',
        default=False,
        help='Sincronizar reclamos de MercadoLibre junto con los pagos'
    )

    claims_status_filter = fields.Selection([
        ('all', 'Todos'),
        ('opened', 'Solo Abiertos'),
        ('closed', 'Solo Cerrados'),
    ], string='Estado de Reclamos', default='opened',
       help='Filtrar reclamos por estado')

    claims_type_filter = fields.Selection([
        ('all', 'Todos los Tipos'),
        ('mediations', 'Solo Mediaciones'),
        ('returns', 'Solo Devoluciones'),
    ], string='Tipo de Reclamo', default='all')

    claims_limit = fields.Integer(
        string='Limite de Reclamos',
        default=50,
        help='Número máximo de reclamos a sincronizar por ejecución'
    )

    sync_claim_messages = fields.Boolean(
        string='Sincronizar Mensajes',
        default=True,
        help='También sincronizar los mensajes de cada reclamo'
    )

    # Estadísticas de claims
    last_claims_synced = fields.Integer(
        string='Últimos Reclamos Sincronizados',
        readonly=True
    )
    last_claims_created = fields.Integer(
        string='Últimos Reclamos Nuevos',
        readonly=True
    )
    last_claims_updated = fields.Integer(
        string='Últimos Reclamos Actualizados',
        readonly=True
    )
    total_claims_synced = fields.Integer(
        string='Total Reclamos Sincronizados',
        readonly=True,
        default=0
    )

    # =====================================================
    # ACCIONES AUTOMATICAS PARA MEDIACIONES
    # =====================================================
    auto_process_mediation = fields.Boolean(
        string='Procesar Mediaciones Automáticamente',
        default=False,
        help='Ejecutar acciones automáticas cuando un pago entra en mediación'
    )

    mediation_action = fields.Selection([
        ('none', 'Solo Notificar'),
        ('cancel_payment', 'Cancelar Pago Odoo'),
        ('create_cancelled', 'Crear Pago No Confirmado'),
        ('reverse_payment', 'Revertir Pago'),
    ], string='Acción en Mediación', default='none',
       help='Qué hacer cuando un pago entra en mediación')

    mediation_notify_user_ids = fields.Many2many(
        'res.users',
        'payment_sync_config_mediation_notify_rel',
        'config_id',
        'user_id',
        string='Notificar Usuarios',
        help='Usuarios a notificar cuando un pago entre en mediación'
    )

    create_mediation_activity = fields.Boolean(
        string='Crear Actividad',
        default=True,
        help='Crear una actividad pendiente cuando haya un nuevo reclamo'
    )

    mediation_activity_user_id = fields.Many2one(
        'res.users',
        string='Responsable Actividad',
        help='Usuario responsable de la actividad creada'
    )

    def _execute_sync(self):
        """Sobrescribe para agregar sincronización de claims"""
        # Ejecutar sync de pagos original
        result = super()._execute_sync()

        # Si está habilitada la sincronización de claims, ejecutarla
        if self.sync_claims:
            self._execute_claims_sync()

        return result

    def _execute_claims_sync(self):
        """Ejecuta la sincronización de claims"""
        self.ensure_one()

        _logger.info('SYNC CLAIMS: Iniciando para "%s"', self.name)

        access_token = self.account_id.get_valid_token_with_retry()
        if not access_token:
            _logger.error('No se pudo obtener token para sync de claims')
            return False

        # Construir parámetros
        params = {
            'limit': self.claims_limit,
        }

        if self.claims_status_filter and self.claims_status_filter != 'all':
            params['status'] = self.claims_status_filter

        if self.claims_type_filter and self.claims_type_filter != 'all':
            params['type'] = self.claims_type_filter

        url = 'https://api.mercadolibre.com/post-purchase/v1/claims/search'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        try:
            response = requests.get(url, params=params, headers=headers, timeout=60)

            if response.status_code != 200:
                _logger.error('Error API claims: %s', response.text)
                return False

            data = response.json()

        except requests.exceptions.RequestException as e:
            _logger.error('Error de conexión sync claims: %s', str(e))
            return False

        results = data.get('data', [])
        ClaimModel = self.env['mercadolibre.claim']

        synced_count = 0
        created_count = 0
        updated_count = 0
        error_count = 0

        for claim_data in results:
            try:
                claim, is_new = ClaimModel.create_from_ml_data(claim_data, self.account_id)
                synced_count += 1

                if is_new:
                    created_count += 1
                    # Crear actividad si está configurado
                    if self.create_mediation_activity and self.mediation_activity_user_id:
                        self._create_claim_activity(claim)
                else:
                    updated_count += 1

                # Sincronizar mensajes si está habilitado
                if self.sync_claim_messages and claim:
                    claim._sync_messages()

            except Exception as e:
                error_count += 1
                _logger.error('Error procesando claim %s: %s', claim_data.get('id'), str(e))

        # Actualizar estadísticas
        self.write({
            'last_claims_synced': synced_count,
            'last_claims_created': created_count,
            'last_claims_updated': updated_count,
            'total_claims_synced': self.total_claims_synced + synced_count,
        })

        # Actualizar log
        claims_log = f'\n\n  CLAIMS SYNC:\n  Sincronizados: {synced_count} (Nuevos: {created_count}, Actualizados: {updated_count}, Errores: {error_count})'
        if self.last_sync_log:
            self.last_sync_log = self.last_sync_log + claims_log

        _logger.info('SYNC CLAIMS completada: %d sincronizados', synced_count)

        return True

    def _create_claim_activity(self, claim):
        """Crea una actividad para un nuevo claim"""
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            return

        claim.activity_schedule(
            activity_type_id=activity_type.id,
            summary=f'Nuevo reclamo: {claim.name}',
            note=f'Se ha recibido un nuevo reclamo de MercadoLibre.\nTipo: {claim.type}\nEtapa: {claim.stage}',
            user_id=self.mediation_activity_user_id.id,
        )

    def action_sync_claims_now(self):
        """Ejecuta sincronización de claims manualmente"""
        self.ensure_one()
        self._execute_claims_sync()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Sincronización de reclamos completada'),
                'type': 'success',
                'sticky': False,
            }
        }
