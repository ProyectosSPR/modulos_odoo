#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de prueba para búsqueda de órdenes usando XML-RPC
"""

import xmlrpc.client
import sys
import getpass
import argparse

# Configuración por defecto
DEFAULT_URL = 'http://localhost:8069'
DEFAULT_DB = 'odoo16c'
DEFAULT_USERNAME = 'admin'
DEFAULT_SEARCH = '2000005480906007'

# Parse argumentos de línea de comandos
parser = argparse.ArgumentParser(
    description='Test de búsqueda de órdenes en Odoo via XML-RPC',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Ejemplos de uso:
  # Modo interactivo (por defecto)
  python3 test_search_xmlrpc.py

  # Con parámetros
  python3 test_search_xmlrpc.py --url http://192.168.1.100:8069 --db odoo16c --user admin --search "2000005"

  # Búsqueda directa (sin interacción)
  python3 test_search_xmlrpc.py -u http://localhost:8069 -d odoo16c -U admin -p admin123 -s "DML00007"
    """
)
parser.add_argument('-u', '--url', help=f'URL de Odoo (default: {DEFAULT_URL})')
parser.add_argument('-d', '--db', help=f'Base de datos (default: {DEFAULT_DB})')
parser.add_argument('-U', '--user', help=f'Usuario (default: {DEFAULT_USERNAME})')
parser.add_argument('-p', '--password', help='Contraseña (se solicitará si no se proporciona)')
parser.add_argument('-s', '--search', help=f'Término de búsqueda (default: {DEFAULT_SEARCH})')
parser.add_argument('-q', '--quiet', action='store_true', help='Modo silencioso (sin prompts)')

args = parser.parse_args()

print("=" * 60)
print("CONFIGURACIÓN DE CONEXIÓN A ODOO")
print("=" * 60)

# Usar parámetros de línea de comandos o solicitar interactivamente
if args.quiet or (args.url and args.db and args.user and args.password and args.search):
    # Modo no interactivo
    URL = args.url or DEFAULT_URL
    DB = args.db or DEFAULT_DB
    USERNAME = args.user or DEFAULT_USERNAME
    PASSWORD = args.password or 'admin'
    SEARCH_TERM = args.search or DEFAULT_SEARCH
    print(f"\n✓ Modo no interactivo")
    print(f"  URL: {URL}")
    print(f"  DB: {DB}")
    print(f"  Usuario: {USERNAME}")
    print(f"  Búsqueda: {SEARCH_TERM}")
else:
    # Modo interactivo
    URL = args.url or input(f"\nURL de Odoo [{DEFAULT_URL}]: ").strip() or DEFAULT_URL
    DB = args.db or input(f"Base de datos [{DEFAULT_DB}]: ").strip() or DEFAULT_DB
    USERNAME = args.user or input(f"Usuario [{DEFAULT_USERNAME}]: ").strip() or DEFAULT_USERNAME
    PASSWORD = args.password or getpass.getpass("Contraseña: ") or 'admin'
    SEARCH_TERM = args.search or input(f"\nTérmino de búsqueda [{DEFAULT_SEARCH}]: ").strip() or DEFAULT_SEARCH

print("=" * 60)
print("TEST: Búsqueda de órdenes con XML-RPC")
print("=" * 60)

try:
    # Conectar a Odoo
    common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')

    # Autenticar
    print(f"\n1. Autenticando como '{USERNAME}' en BD '{DB}'...")
    uid = common.authenticate(DB, USERNAME, PASSWORD, {})

    if not uid:
        print("❌ Error: Autenticación fallida")
        exit(1)

    print(f"✓ Autenticado con UID: {uid}")

    # Conectar a modelos
    models = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object')

    # Probar método search_for_billing_portal
    print(f"\n2. Llamando a search_for_billing_portal con término: '{SEARCH_TERM}'")

    result = models.execute_kw(
        DB, uid, PASSWORD,
        'sale.order', 'search_for_billing_portal',
        [SEARCH_TERM],  # search_term
        {'receiver_id': None, 'limit': 50}  # kwargs
    )

    print(f"\n3. Resultado:")
    print(f"   - Tipo: {type(result)}")
    print(f"   - Cantidad de órdenes: {len(result) if isinstance(result, list) else 'N/A'}")

    if isinstance(result, list) and len(result) > 0:
        print(f"\n4. Primera orden encontrada:")
        for key, value in result[0].items():
            print(f"   - {key}: {value}")
    else:
        print("\n❌ No se encontraron órdenes")

    # Probar búsqueda directa con dominio
    print(f"\n5. Búsqueda directa con search() y dominio:")
    domain = [
        '|', '|', '|',
        ('client_order_ref', 'ilike', SEARCH_TERM),
        ('name', 'ilike', SEARCH_TERM),
        ('ml_order_id', 'ilike', SEARCH_TERM),
        ('ml_pack_id', 'ilike', SEARCH_TERM),
    ]

    order_ids = models.execute_kw(
        DB, uid, PASSWORD,
        'sale.order', 'search',
        [domain],
        {'limit': 10}
    )

    print(f"   - IDs encontrados: {order_ids}")

    if order_ids:
        # Leer datos de la primera orden
        order_data = models.execute_kw(
            DB, uid, PASSWORD,
            'sale.order', 'read',
            [order_ids[0:1]],
            {'fields': ['name', 'client_order_ref', 'state', 'invoice_status']}
        )
        print(f"   - Datos primera orden: {order_data}")

    print("\n" + "=" * 60)
    print("✓ Test completado")
    print("=" * 60)

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
