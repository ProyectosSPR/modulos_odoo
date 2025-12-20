# -*- coding: utf-8 -*-
"""
Controllers del módulo mercadolibre_messaging.

NOTA: Las notificaciones de mensajes se reciben a través del endpoint central
en mercadolibre_connector (/mercadolibre/notifications).

El modelo mercadolibre.conversation implementa el método process_notification()
que es llamado automáticamente por el router de notificaciones.
"""
