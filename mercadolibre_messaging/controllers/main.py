# -*- coding: utf-8 -*-
"""
Controllers del módulo mercadolibre_messaging.

NOTA: Las notificaciones de mensajes se reciben a través del endpoint central
en mercadolibre_connector (/mercadolibre/notifications).

El modelo mercadolibre.conversation implementa el método process_notification()
que es llamado automáticamente por el router de notificaciones.

Este archivo se mantiene para posibles endpoints adicionales específicos
del módulo de mensajería.
"""

import logging
from odoo import http

_logger = logging.getLogger(__name__)


class MercadolibreMessagingController(http.Controller):
    """
    Controller para funcionalidades específicas de mensajería.

    Las notificaciones de ML (topic: 'messages') son manejadas por:
    - Endpoint central: /mercadolibre/notifications (mercadolibre_connector)
    - Handler: mercadolibre.conversation.process_notification()
    """
    pass
