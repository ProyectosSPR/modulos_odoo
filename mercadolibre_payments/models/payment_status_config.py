# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class MercadolibrePaymentStatusConfigExtend(models.Model):
    """
    Extiende mercadolibre.payment.status.config para agregar:
    - Estados de Money Release (released, pending, not_released)

    Esto permite configurar tags basados en si el dinero ya fue liberado o no.
    """
    _inherit = 'mercadolibre.payment.status.config'

    # =========================================================================
    # ESTADOS DE LIBERACIÓN DE DINERO (Money Release)
    # =========================================================================
    status_money_released = fields.Boolean(
        string='Dinero Liberado',
        help='El dinero ya está disponible en tu cuenta MercadoPago'
    )
    status_money_pending = fields.Boolean(
        string='Dinero Pendiente',
        help='El dinero aún está retenido por MercadoLibre (ej: 21 días)'
    )
    status_money_not_released = fields.Boolean(
        string='Dinero No Liberado',
        help='El dinero no será liberado (orden cancelada, contracargo, etc.)'
    )

    def get_status_list(self):
        """
        Override para incluir estados de money release.
        """
        # Obtener estados base de la clase padre (estados de orden ML)
        statuses = super().get_status_list()

        # Agregar estados de money release como identificadores únicos
        if self.status_money_released:
            statuses.append('money_released')
        if self.status_money_pending:
            statuses.append('money_pending')
        if self.status_money_not_released:
            statuses.append('money_not_released')

        return statuses

    def get_money_release_status_list(self):
        """Retorna lista de estados de money release seleccionados"""
        self.ensure_one()
        statuses = []

        if self.status_money_released:
            statuses.append('released')
        if self.status_money_pending:
            statuses.append('pending')
        if self.status_money_not_released:
            statuses.append('not_released')

        return statuses

    @api.model
    def get_tags_for_money_release_status(self, money_release_status, account_id=None, company_id=None):
        """
        Obtiene las etiquetas correspondientes a un estado de liberación de dinero.

        Args:
            money_release_status: Estado de liberación (released, pending, not_released)
            account_id: ID de la cuenta ML (opcional)
            company_id: ID de la compania (opcional)

        Returns:
            recordset de crm.tag
        """
        domain = [('active', '=', True)]
        if account_id:
            domain.append(('account_id', 'in', [account_id, False]))
        if company_id:
            domain.append(('company_id', 'in', [company_id, False]))

        configs = self.search(domain)

        _logger.info(
            '[MONEY_RELEASE_TAGS] Buscando tags para status=%s: encontradas %d configs',
            money_release_status, len(configs)
        )

        for config in configs:
            money_statuses = config.get_money_release_status_list()

            if money_release_status in money_statuses:
                _logger.info(
                    '[MONEY_RELEASE_TAGS] Match! Config "%s" -> Tags: %s',
                    config.name, config.tag_ids.mapped('name')
                )
                return config.tag_ids

        _logger.info('[MONEY_RELEASE_TAGS] No se encontró config para status=%s', money_release_status)
        return self.env['crm.tag']
