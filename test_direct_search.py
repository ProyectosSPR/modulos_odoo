#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de prueba DIRECTA de búsqueda en Odoo
Sin XML-RPC, accede directamente al método Python
"""

import sys
import os

# Configurar path para importar desde Odoo
sys.path.insert(0, '/usr/lib/python3/dist-packages')

def test_direct_search():
    """Prueba la búsqueda directamente en el ORM de Odoo"""
    print("=" * 80)
    print("TEST DIRECTO DE BÚSQUEDA (sin XML-RPC)")
    print("=" * 80)

    try:
        # Importar Odoo
        import odoo
        from odoo import registry

        # Conectar a la base de datos
        db_name = 'odoo16c'
        print(f"\n1. Conectando a base de datos: {db_name}")

        reg = registry(db_name)
        with reg.cursor() as cr:
            # Obtener environment
            from odoo.api import Environment
            uid = 1  # Usuario admin
            env = Environment(cr, uid, {})

            print(f"✓ Conectado como usuario ID: {uid}")

            # Obtener modelo sale.order
            SaleOrder = env['sale.order']

            # Prueba 1: Buscar órdenes con client_order_ref
            print("\n2. Buscando órdenes con client_order_ref...")
            orders_with_ref = SaleOrder.search([
                ('client_order_ref', '!=', False)
            ], limit=5)

            print(f"✓ Órdenes con client_order_ref: {len(orders_with_ref)}")
            for order in orders_with_ref:
                print(f"  - ID: {order.id}, Name: {order.name}, Ref: {order.client_order_ref}")

            # Prueba 2: Verificar si el método search_for_billing_portal existe
            print("\n3. Verificando método search_for_billing_portal...")
            if hasattr(SaleOrder, 'search_for_billing_portal'):
                print("✓ Método search_for_billing_portal existe")

                # Prueba 3: Llamar al método con un término de búsqueda
                search_term = "2000005480906007"
                print(f"\n4. Llamando a search_for_billing_portal('{search_term}')...")

                result = SaleOrder.search_for_billing_portal(
                    search_term,
                    receiver_id=None,
                    limit=10
                )

                print(f"\n5. Resultado:")
                print(f"   Tipo: {type(result)}")
                print(f"   Cantidad: {len(result) if isinstance(result, list) else 'N/A'}")

                if isinstance(result, list) and len(result) > 0:
                    print(f"\n   Primera orden:")
                    for key, value in result[0].items():
                        print(f"     {key}: {value}")
                else:
                    print("\n   ❌ No se encontraron órdenes")

                # Prueba 4: Búsqueda con término más corto
                print(f"\n6. Buscando con término corto '2000005'...")
                result2 = SaleOrder.search_for_billing_portal("2000005", None, 10)
                print(f"   Órdenes encontradas: {len(result2) if isinstance(result2, list) else 0}")

            else:
                print("❌ Método search_for_billing_portal NO existe")
                print("   El módulo billing_portal no está instalado o no se cargó correctamente")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("✓ Test completado")
    print("=" * 80)


if __name__ == '__main__':
    test_direct_search()
