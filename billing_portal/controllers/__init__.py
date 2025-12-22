# -*- coding: utf-8 -*-
"""
Controladores del Portal de Facturación.

- public.py: Rutas públicas (búsqueda sin login)
- portal.py: Rutas privadas (facturación requiere login Odoo)
- portal_customer.py: Extensión de CustomerPortal para integración con /my/*
"""

from . import public
from . import portal
from . import portal_customer
