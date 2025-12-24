{
    'name': 'Sale Order Invoice Payment Info',
    'version': '16.0.1.0.0',
    'summary': 'Extender Sale Order con información de facturas, pagos, comisiones y proyecciones de ventas',
    'description': """
        Este módulo extiende el modelo sale.order para mostrar información detallada por vendedores
        de las facturas relacionadas y los pagos aplicados a esas facturas.

        Características:
        - Muestra facturas relacionadas a la orden de venta
        - Información de pagos aplicados a cada factura
        - Campos de fecha de factura, importes, cliente
        - Líneas de producto de las facturas
        - Información de conciliación de pagos

        Sistema de Comisiones:
        - Configuración de equipos de ventas unificados con porcentajes de comisión
        - Reglas configurables de alcance de meta vs recompensa
        - Metas de ventas por vendedor y periodo
        - Cálculo automático de comisiones basado en ventas
        - Histórico de comisiones pagadas
        - Opción de calcular comisión sobre subtotal o total

        Sistema de Proyecciones y Reportes:
        - Proyecciones de ventas mensuales por equipo
        - Versiones de proyecciones editables
        - Cálculo de temporalidad (% vs proyección anterior)
        - Reportes por cuatrimestre con comparativa objetivo/estimado/real
        - Análisis de diferencias y porcentajes de cumplimiento
        - Vistas pivot y gráficas para análisis detallado
    """,
    'author': 'Tu Empresa',
    'category': 'Sales',
    'depends': [
        'sale',
        'account',
        'sales_team',
    ],
    'data': [
        'security/commission_security.xml',
        'security/ir.model.access.csv',
        'views/sale_order_views.xml',
        'views/commission_views.xml',
        'views/commission_menus.xml',
        'views/sales_projection_views.xml',
        'views/quarterly_report_views.xml',
        'views/sales_projection_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
