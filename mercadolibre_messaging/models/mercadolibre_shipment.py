# -*- coding: utf-8 -*-

import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class MercadolibreShipmentMessaging(models.Model):
    """
    Extensión de mercadolibre.shipment para mensajería automática.

    Esta herencia permite disparar reglas de mensajes automáticos
    cuando cambia el estado del envío vía webhook.
    """
    _inherit = 'mercadolibre.shipment'

    @api.model
    def process_notification(self, account, data):
        """
        Extiende el procesamiento de notificaciones para disparar reglas de mensajes.

        Después de procesar el webhook de shipments, verifica si hay reglas
        de mensajes automáticos que deban ejecutarse según el nuevo estado.
        """
        # Obtener el estado anterior antes de procesar (si el shipment existe)
        resource = data.get('resource', '')
        shipment_id = None
        old_status = None

        if '/shipments/' in resource:
            try:
                shipment_id = resource.split('/shipments/')[-1].split('/')[0].split('?')[0]
                existing = self.search([
                    ('ml_shipment_id', '=', shipment_id),
                    ('account_id', '=', account.id)
                ], limit=1)
                if existing:
                    old_status = existing.status
            except Exception as e:
                _logger.debug(f"[MESSAGING] Error obteniendo estado anterior: {e}")

        # Procesar la notificación original
        result = super().process_notification(account, data)

        # Si fue exitoso, verificar reglas de mensajes
        if result.get('status') == 'ok' and result.get('shipment_id'):
            try:
                shipment = self.browse(result['shipment_id'])
                new_status = shipment.status

                # Solo disparar si el estado cambió
                if new_status and new_status != old_status:
                    _logger.info(
                        f"[MESSAGING] Shipment {shipment_id} cambió de "
                        f"'{old_status}' a '{new_status}', verificando reglas..."
                    )
                    self._trigger_message_rules_for_shipment(shipment, old_status, new_status)

            except Exception as e:
                _logger.error(f"[MESSAGING] Error verificando reglas de mensajes: {e}")

        return result

    def _trigger_message_rules_for_shipment(self, shipment, old_status, new_status):
        """
        Dispara reglas de mensajes automáticos por cambio de estado de envío.

        Args:
            shipment: mercadolibre.shipment record
            old_status: estado anterior del envío
            new_status: nuevo estado del envío
        """
        if not shipment.order_id:
            _logger.debug(f"[MESSAGING] Shipment {shipment.ml_shipment_id} sin orden asociada")
            return

        ml_order = shipment.order_id

        # Verificar si mensajería automática está habilitada
        config = self.env['mercadolibre.messaging.config'].get_config_for_account(
            ml_order.account_id
        )
        if not config.auto_messages_enabled:
            _logger.debug(f"[MESSAGING] Mensajes automáticos deshabilitados para cuenta")
            return

        # Obtener reglas que aplican para shipment_status
        MessageRule = self.env['mercadolibre.message.rule']
        matching_rules = MessageRule.get_matching_rules(
            ml_order,
            trigger_type='shipment_status'
        )

        # También buscar reglas con trigger_type='both'
        both_rules = MessageRule.get_matching_rules(
            ml_order,
            trigger_type='both'
        )
        matching_rules |= both_rules

        _logger.info(
            f"[MESSAGING] Encontradas {len(matching_rules)} reglas para "
            f"shipment_status={new_status}"
        )

        for rule in matching_rules:
            try:
                _logger.info(f"[MESSAGING] Ejecutando regla '{rule.name}' para orden {ml_order.ml_order_id}")
                rule.execute_rule(ml_order)
            except Exception as e:
                _logger.error(
                    f"[MESSAGING] Error ejecutando regla {rule.name} "
                    f"para orden {ml_order.ml_order_id}: {e}"
                )
                config._log(
                    f'Error ejecutando regla {rule.name}: {str(e)}',
                    level='error',
                    log_type='message_error',
                    message_rule_id=rule.id,
                    ml_pack_id=ml_order.ml_pack_id,
                )

    def write(self, vals):
        """
        Override para detectar cambios de estado y ejecutar reglas.

        Esto complementa el disparo por webhook, cubriendo casos donde
        el estado cambia por sincronización manual o cron.
        """
        # Guardar estados anteriores
        old_statuses = {rec.id: rec.status for rec in self}

        result = super().write(vals)

        # Si cambió el status, verificar reglas
        if 'status' in vals:
            for record in self:
                old_status = old_statuses.get(record.id)
                new_status = record.status

                if old_status != new_status:
                    try:
                        self._trigger_message_rules_for_shipment(
                            record, old_status, new_status
                        )
                    except Exception as e:
                        _logger.error(
                            f"[MESSAGING] Error en write() verificando reglas: {e}"
                        )

        return result
