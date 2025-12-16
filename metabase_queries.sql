-- ========================================
-- CONSULTAS SQL PARA METABASE - DASHBOARD DE VENTAS
-- Base de datos: odoo16c
-- ========================================

-- ========================================
-- CONSULTA 1: COMPARATIVA DE VENTAS AÑO ACTUAL VS AÑO ANTERIOR
-- ========================================
-- Esta consulta compara las ventas del año actual con el año anterior
-- Incluye filtros para: estado de facturación, estado de pago, y conciliación
-- Variables de Metabase: {{year}}, {{invoice_filter}}, {{payment_filter}}, {{reconciliation_filter}}

WITH sales_data AS (
    SELECT
        so.id,
        so.name as order_name,
        so.date_order,
        EXTRACT(YEAR FROM so.date_order) as year,
        EXTRACT(MONTH FROM so.date_order) as month,
        so.amount_total,
        so.state as order_state,
        so.invoice_status,
        -- Determinar si tiene factura (basado en sale_order_invoice_payment_info)
        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = so.id
                AND soi.invoice_name IS NOT NULL
                AND soi.invoice_state = 'posted'
            ) THEN 'Facturado'
            ELSE 'No Facturado'
        END as invoice_filter_status,
        -- Determinar si tiene pago
        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = so.id
                AND soi.payment_name IS NOT NULL
            ) THEN 'Pagado'
            ELSE 'No Pagado'
        END as payment_filter_status,
        -- Determinar si está conciliado
        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = so.id
                AND soi.reconcile_date IS NOT NULL
            ) THEN 'Conciliado'
            ELSE 'No Conciliado'
        END as reconciliation_status
    FROM sale_order so
    WHERE so.date_order IS NOT NULL
    AND so.state IN ('sale', 'done')  -- Solo órdenes confirmadas
    AND EXTRACT(YEAR FROM so.date_order) IN (
        EXTRACT(YEAR FROM CURRENT_DATE),
        EXTRACT(YEAR FROM CURRENT_DATE) - 1
    )
)
SELECT
    year,
    month,
    COUNT(DISTINCT id) as total_orders,
    SUM(amount_total) as total_sales,
    SUM(CASE WHEN invoice_filter_status = 'Facturado' THEN amount_total ELSE 0 END) as invoiced_sales,
    SUM(CASE WHEN payment_filter_status = 'Pagado' THEN amount_total ELSE 0 END) as paid_sales,
    SUM(CASE WHEN reconciliation_status = 'Conciliado' THEN amount_total ELSE 0 END) as reconciled_sales,
    -- Conteo por estado
    COUNT(DISTINCT CASE WHEN invoice_filter_status = 'Facturado' THEN id END) as invoiced_orders,
    COUNT(DISTINCT CASE WHEN payment_filter_status = 'Pagado' THEN id END) as paid_orders,
    COUNT(DISTINCT CASE WHEN reconciliation_status = 'Conciliado' THEN id END) as reconciled_orders
FROM sales_data
WHERE
    -- Filtros opcionales de Metabase (comentar/descomentar según necesites)
    -- invoice_filter_status = COALESCE({{invoice_filter}}, invoice_filter_status)
    -- AND payment_filter_status = COALESCE({{payment_filter}}, payment_filter_status)
    -- AND reconciliation_status = COALESCE({{reconciliation_filter}}, reconciliation_status)
    1=1  -- Placeholder para facilitar agregar filtros
GROUP BY year, month
ORDER BY year DESC, month DESC;


-- ========================================
-- CONSULTA 2: RESUMEN ANUAL CONSOLIDADO
-- ========================================
-- Esta consulta muestra un resumen por año con todos los estados

SELECT
    EXTRACT(YEAR FROM so.date_order) as year,
    COUNT(DISTINCT so.id) as total_orders,
    SUM(so.amount_total) as total_sales,

    -- Ventas facturadas
    COUNT(DISTINCT CASE
        WHEN EXISTS (
            SELECT 1 FROM sale_order_invoice_payment_info soi
            WHERE soi.order_id = so.id
            AND soi.invoice_name IS NOT NULL
            AND soi.invoice_state = 'posted'
        ) THEN so.id
    END) as invoiced_orders_count,

    SUM(CASE
        WHEN EXISTS (
            SELECT 1 FROM sale_order_invoice_payment_info soi
            WHERE soi.order_id = so.id
            AND soi.invoice_name IS NOT NULL
            AND soi.invoice_state = 'posted'
        ) THEN so.amount_total
        ELSE 0
    END) as invoiced_amount,

    -- Ventas pagadas
    COUNT(DISTINCT CASE
        WHEN EXISTS (
            SELECT 1 FROM sale_order_invoice_payment_info soi
            WHERE soi.order_id = so.id
            AND soi.payment_name IS NOT NULL
        ) THEN so.id
    END) as paid_orders_count,

    SUM(CASE
        WHEN EXISTS (
            SELECT 1 FROM sale_order_invoice_payment_info soi
            WHERE soi.order_id = so.id
            AND soi.payment_name IS NOT NULL
        ) THEN so.amount_total
        ELSE 0
    END) as paid_amount,

    -- Ventas conciliadas
    COUNT(DISTINCT CASE
        WHEN EXISTS (
            SELECT 1 FROM sale_order_invoice_payment_info soi
            WHERE soi.order_id = so.id
            AND soi.reconcile_date IS NOT NULL
        ) THEN so.id
    END) as reconciled_orders_count,

    SUM(CASE
        WHEN EXISTS (
            SELECT 1 FROM sale_order_invoice_payment_info soi
            WHERE soi.order_id = so.id
            AND soi.reconcile_date IS NOT NULL
        ) THEN so.amount_total
        ELSE 0
    END) as reconciled_amount,

    -- Ventas NO facturadas
    COUNT(DISTINCT CASE
        WHEN NOT EXISTS (
            SELECT 1 FROM sale_order_invoice_payment_info soi
            WHERE soi.order_id = so.id
            AND soi.invoice_name IS NOT NULL
            AND soi.invoice_state = 'posted'
        ) THEN so.id
    END) as not_invoiced_orders_count,

    SUM(CASE
        WHEN NOT EXISTS (
            SELECT 1 FROM sale_order_invoice_payment_info soi
            WHERE soi.order_id = so.id
            AND soi.invoice_name IS NOT NULL
            AND soi.invoice_state = 'posted'
        ) THEN so.amount_total
        ELSE 0
    END) as not_invoiced_amount

FROM sale_order so
WHERE so.date_order IS NOT NULL
AND so.state IN ('sale', 'done')
GROUP BY EXTRACT(YEAR FROM so.date_order)
ORDER BY year DESC;


-- ========================================
-- CONSULTA 3: DETALLE DE ÓRDENES CON FILTROS
-- ========================================
-- Esta consulta muestra el detalle de órdenes con todos los estados
-- Útil para tablas detalladas en Metabase

SELECT
    so.id,
    so.name as order_name,
    so.date_order::date as order_date,
    EXTRACT(YEAR FROM so.date_order) as year,
    EXTRACT(MONTH FROM so.date_order) as month,
    so.partner_id,
    so.amount_total,
    so.state as order_state,
    so.invoice_status,

    -- Estado de facturación
    CASE
        WHEN EXISTS (
            SELECT 1 FROM sale_order_invoice_payment_info soi
            WHERE soi.order_id = so.id
            AND soi.invoice_name IS NOT NULL
            AND soi.invoice_state = 'posted'
        ) THEN 'Facturado'
        ELSE 'No Facturado'
    END as invoice_status_detailed,

    -- Estado de pago
    CASE
        WHEN EXISTS (
            SELECT 1 FROM sale_order_invoice_payment_info soi
            WHERE soi.order_id = so.id
            AND soi.payment_name IS NOT NULL
        ) THEN 'Pagado'
        ELSE 'No Pagado'
    END as payment_status_detailed,

    -- Estado de conciliación
    CASE
        WHEN EXISTS (
            SELECT 1 FROM sale_order_invoice_payment_info soi
            WHERE soi.order_id = so.id
            AND soi.reconcile_date IS NOT NULL
        ) THEN 'Conciliado'
        ELSE 'No Conciliado'
    END as reconciliation_status_detailed,

    -- Información de factura (primera factura encontrada)
    (SELECT soi.invoice_name
     FROM sale_order_invoice_payment_info soi
     WHERE soi.order_id = so.id
     AND soi.invoice_name IS NOT NULL
     AND soi.invoice_state = 'posted'
     LIMIT 1) as invoice_name,

    -- Información de pago (primer pago encontrado)
    (SELECT soi.payment_name
     FROM sale_order_invoice_payment_info soi
     WHERE soi.order_id = so.id
     AND soi.payment_name IS NOT NULL
     LIMIT 1) as payment_name,

    -- Fecha de conciliación (primera encontrada)
    (SELECT soi.reconcile_date
     FROM sale_order_invoice_payment_info soi
     WHERE soi.order_id = so.id
     AND soi.reconcile_date IS NOT NULL
     LIMIT 1) as reconcile_date

FROM sale_order so
WHERE so.date_order IS NOT NULL
AND so.state IN ('sale', 'done')
-- Filtros opcionales para Metabase (agregar según necesites)
-- AND EXTRACT(YEAR FROM so.date_order) = {{year}}
-- AND EXTRACT(MONTH FROM so.date_order) = {{month}}
ORDER BY so.date_order DESC;


-- ========================================
-- CONSULTA 4: COMPARATIVA MENSUAL AÑO ACTUAL VS AÑO ANTERIOR
-- ========================================
-- Esta consulta es ideal para gráficas de líneas comparando mes a mes

WITH monthly_sales AS (
    SELECT
        EXTRACT(YEAR FROM so.date_order) as year,
        EXTRACT(MONTH FROM so.date_order) as month,
        COUNT(DISTINCT so.id) as total_orders,
        SUM(so.amount_total) as total_sales,

        -- Ventas facturadas
        SUM(CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = so.id
                AND soi.invoice_name IS NOT NULL
                AND soi.invoice_state = 'posted'
            ) THEN so.amount_total
            ELSE 0
        END) as invoiced_sales,

        -- Ventas pagadas
        SUM(CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = so.id
                AND soi.payment_name IS NOT NULL
            ) THEN so.amount_total
            ELSE 0
        END) as paid_sales,

        -- Ventas conciliadas
        SUM(CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = so.id
                AND soi.reconcile_date IS NOT NULL
            ) THEN so.amount_total
            ELSE 0
        END) as reconciled_sales

    FROM sale_order so
    WHERE so.date_order IS NOT NULL
    AND so.state IN ('sale', 'done')
    AND EXTRACT(YEAR FROM so.date_order) IN (
        EXTRACT(YEAR FROM CURRENT_DATE),
        EXTRACT(YEAR FROM CURRENT_DATE) - 1
    )
    GROUP BY EXTRACT(YEAR FROM so.date_order), EXTRACT(MONTH FROM so.date_order)
)
SELECT
    m.month,
    TO_CHAR(TO_DATE(m.month::text, 'MM'), 'Month') as month_name,

    -- Año actual
    COALESCE(current_year.total_orders, 0) as current_year_orders,
    COALESCE(current_year.total_sales, 0) as current_year_sales,
    COALESCE(current_year.invoiced_sales, 0) as current_year_invoiced,
    COALESCE(current_year.paid_sales, 0) as current_year_paid,
    COALESCE(current_year.reconciled_sales, 0) as current_year_reconciled,

    -- Año anterior
    COALESCE(previous_year.total_orders, 0) as previous_year_orders,
    COALESCE(previous_year.total_sales, 0) as previous_year_sales,
    COALESCE(previous_year.invoiced_sales, 0) as previous_year_invoiced,
    COALESCE(previous_year.paid_sales, 0) as previous_year_paid,
    COALESCE(previous_year.reconciled_sales, 0) as previous_year_reconciled,

    -- Variación
    COALESCE(current_year.total_sales, 0) - COALESCE(previous_year.total_sales, 0) as sales_variance,
    CASE
        WHEN COALESCE(previous_year.total_sales, 0) > 0 THEN
            ROUND(((COALESCE(current_year.total_sales, 0) - COALESCE(previous_year.total_sales, 0))
            / previous_year.total_sales * 100)::numeric, 2)
        ELSE NULL
    END as sales_variance_percentage

FROM generate_series(1, 12) m(month)
LEFT JOIN monthly_sales current_year
    ON current_year.month = m.month
    AND current_year.year = EXTRACT(YEAR FROM CURRENT_DATE)
LEFT JOIN monthly_sales previous_year
    ON previous_year.month = m.month
    AND previous_year.year = EXTRACT(YEAR FROM CURRENT_DATE) - 1
ORDER BY m.month;


-- ========================================
-- NOTAS PARA METABASE:
-- ========================================
-- 1. Para crear variables/filtros en Metabase, usa la sintaxis: {{variable_name}}
-- 2. Tipos de variables recomendadas:
--    - {{year}}: Field Filter sobre date_order (Year)
--    - {{month}}: Field Filter sobre date_order (Month)
--    - {{invoice_filter}}: Text con opciones: "Facturado", "No Facturado"
--    - {{payment_filter}}: Text con opciones: "Pagado", "No Pagado"
--    - {{reconciliation_filter}}: Text con opciones: "Conciliado", "No Conciliado"
--
-- 3. Para crear el dashboard:
--    - Consulta 1: Usar para métricas principales con filtros
--    - Consulta 2: Usar para KPIs y resumen anual
--    - Consulta 3: Usar para tablas de detalle
--    - Consulta 4: Usar para gráficas de comparación mensual
--
-- 4. Conexión a la base de datos en Metabase:
--    - Host: 192.168.80.232
--    - Puerto: 30432
--    - Database: odoo16c
--    - Usuario: dml
--    - Contraseña: Sergio55
