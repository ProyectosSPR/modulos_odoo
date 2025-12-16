-- ========================================
-- CONSULTAS SQL PARA METABASE - DASHBOARD DE VENTAS
-- Con sintaxis de filtros de Metabase [[AND {{variable}}]]
-- Base de datos: odoo16c
-- ========================================

-- ========================================
-- CONSULTA 1: COMPARATIVA DE VENTAS AÑO ACTUAL VS AÑO ANTERIOR
-- Con filtros opcionales de Metabase
-- ========================================

WITH ordenes_base AS (
    SELECT
        so.id AS orden_id,
        so.name AS orden_nombre,
        (so.date_order AT TIME ZONE 'UTC' AT TIME ZONE 'America/Mexico_City')::date AS fecha_orden,
        EXTRACT(YEAR FROM so.date_order) AS anio,
        EXTRACT(MONTH FROM so.date_order) AS mes,
        so.state AS estado_orden,
        so.invoice_status,
        so.amount_untaxed AS subtotal,
        so.amount_total AS total,
        so.partner_id AS cliente_id,
        so.user_id AS vendedor_id,
        so.team_id AS equipo_id
    FROM sale_order so
    WHERE
        so.date_order IS NOT NULL
        AND so.state IN ('sale', 'done')  -- Solo órdenes confirmadas
        [[AND {{rango_fecha}}]]
        [[AND so.user_id IN ({{vendedor_id}})]]
        [[AND so.team_id IN ({{equipo_id}})]]
),

ordenes_con_estados AS (
    SELECT
        ob.*,

        -- Estado de facturación
        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = ob.orden_id
                AND soi.invoice_name IS NOT NULL
                AND soi.invoice_state = 'posted'
            ) THEN 'Facturado'
            ELSE 'No Facturado'
        END AS estado_facturacion,

        -- Estado de pago
        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = ob.orden_id
                AND soi.payment_name IS NOT NULL
            ) THEN 'Pagado'
            ELSE 'No Pagado'
        END AS estado_pago,

        -- Estado de conciliación
        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = ob.orden_id
                AND soi.reconcile_date IS NOT NULL
            ) THEN 'Conciliado'
            ELSE 'No Conciliado'
        END AS estado_conciliacion,

        -- Nombre de factura
        (SELECT soi.invoice_name
         FROM sale_order_invoice_payment_info soi
         WHERE soi.order_id = ob.orden_id
         AND soi.invoice_name IS NOT NULL
         AND soi.invoice_state = 'posted'
         LIMIT 1) AS nombre_factura,

        -- Nombre de pago
        (SELECT soi.payment_name
         FROM sale_order_invoice_payment_info soi
         WHERE soi.order_id = ob.orden_id
         AND soi.payment_name IS NOT NULL
         LIMIT 1) AS nombre_pago

    FROM ordenes_base ob
)

SELECT
    oce.anio,
    oce.mes,
    oce.fecha_orden,
    COUNT(DISTINCT oce.orden_id) AS cantidad_ordenes,
    SUM(oce.subtotal) AS total_subtotal,
    SUM(oce.total) AS total_con_impuestos,
    ROUND(AVG(oce.total), 2) AS ticket_promedio,

    -- Totales por estado de facturación
    SUM(CASE WHEN oce.estado_facturacion = 'Facturado' THEN oce.total ELSE 0 END) AS total_facturado,
    SUM(CASE WHEN oce.estado_facturacion = 'No Facturado' THEN oce.total ELSE 0 END) AS total_no_facturado,

    -- Totales por estado de pago
    SUM(CASE WHEN oce.estado_pago = 'Pagado' THEN oce.total ELSE 0 END) AS total_pagado,
    SUM(CASE WHEN oce.estado_pago = 'No Pagado' THEN oce.total ELSE 0 END) AS total_no_pagado,

    -- Totales por estado de conciliación
    SUM(CASE WHEN oce.estado_conciliacion = 'Conciliado' THEN oce.total ELSE 0 END) AS total_conciliado,
    SUM(CASE WHEN oce.estado_conciliacion = 'No Conciliado' THEN oce.total ELSE 0 END) AS total_no_conciliado,

    -- Conteos
    COUNT(DISTINCT CASE WHEN oce.estado_facturacion = 'Facturado' THEN oce.orden_id END) AS ordenes_facturadas,
    COUNT(DISTINCT CASE WHEN oce.estado_pago = 'Pagado' THEN oce.orden_id END) AS ordenes_pagadas,
    COUNT(DISTINCT CASE WHEN oce.estado_conciliacion = 'Conciliado' THEN oce.orden_id END) AS ordenes_conciliadas

FROM ordenes_con_estados oce
WHERE 1=1
    [[AND oce.estado_facturacion IN ({{estado_facturacion}})]]
    [[AND oce.estado_pago IN ({{estado_pago}})]]
    [[AND oce.estado_conciliacion IN ({{estado_conciliacion}})]]
GROUP BY oce.anio, oce.mes, oce.fecha_orden
ORDER BY oce.fecha_orden DESC;


-- ========================================
-- CONSULTA 2: RESUMEN CONSOLIDADO POR AÑO
-- Ideal para KPIs y métricas principales
-- ========================================

WITH ordenes_base AS (
    SELECT
        so.id AS orden_id,
        so.name AS orden_nombre,
        (so.date_order AT TIME ZONE 'UTC' AT TIME ZONE 'America/Mexico_City')::date AS fecha_orden,
        EXTRACT(YEAR FROM so.date_order) AS anio,
        so.state AS estado_orden,
        so.amount_untaxed AS subtotal,
        so.amount_total AS total,
        so.user_id AS vendedor_id,
        so.team_id AS equipo_id
    FROM sale_order so
    WHERE
        so.date_order IS NOT NULL
        AND so.state IN ('sale', 'done')
        [[AND {{rango_fecha}}]]
        [[AND so.user_id IN ({{vendedor_id}})]]
        [[AND so.team_id IN ({{equipo_id}})]]
),

ordenes_con_estados AS (
    SELECT
        ob.*,

        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = ob.orden_id
                AND soi.invoice_name IS NOT NULL
                AND soi.invoice_state = 'posted'
            ) THEN 'Facturado'
            ELSE 'No Facturado'
        END AS estado_facturacion,

        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = ob.orden_id
                AND soi.payment_name IS NOT NULL
            ) THEN 'Pagado'
            ELSE 'No Pagado'
        END AS estado_pago,

        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = ob.orden_id
                AND soi.reconcile_date IS NOT NULL
            ) THEN 'Conciliado'
            ELSE 'No Conciliado'
        END AS estado_conciliacion

    FROM ordenes_base ob
)

SELECT
    oce.anio,
    COUNT(DISTINCT oce.orden_id) AS total_ordenes,
    SUM(oce.total) AS total_ventas,
    ROUND(AVG(oce.total), 2) AS ticket_promedio,

    -- Ventas facturadas
    COUNT(DISTINCT CASE WHEN oce.estado_facturacion = 'Facturado' THEN oce.orden_id END) AS ordenes_facturadas,
    SUM(CASE WHEN oce.estado_facturacion = 'Facturado' THEN oce.total ELSE 0 END) AS monto_facturado,
    ROUND((SUM(CASE WHEN oce.estado_facturacion = 'Facturado' THEN oce.total ELSE 0 END) / NULLIF(SUM(oce.total), 0) * 100)::numeric, 2) AS porcentaje_facturado,

    -- Ventas NO facturadas
    COUNT(DISTINCT CASE WHEN oce.estado_facturacion = 'No Facturado' THEN oce.orden_id END) AS ordenes_no_facturadas,
    SUM(CASE WHEN oce.estado_facturacion = 'No Facturado' THEN oce.total ELSE 0 END) AS monto_no_facturado,

    -- Ventas pagadas
    COUNT(DISTINCT CASE WHEN oce.estado_pago = 'Pagado' THEN oce.orden_id END) AS ordenes_pagadas,
    SUM(CASE WHEN oce.estado_pago = 'Pagado' THEN oce.total ELSE 0 END) AS monto_pagado,
    ROUND((SUM(CASE WHEN oce.estado_pago = 'Pagado' THEN oce.total ELSE 0 END) / NULLIF(SUM(oce.total), 0) * 100)::numeric, 2) AS porcentaje_pagado,

    -- Ventas NO pagadas
    COUNT(DISTINCT CASE WHEN oce.estado_pago = 'No Pagado' THEN oce.orden_id END) AS ordenes_no_pagadas,
    SUM(CASE WHEN oce.estado_pago = 'No Pagado' THEN oce.total ELSE 0 END) AS monto_no_pagado,

    -- Ventas conciliadas
    COUNT(DISTINCT CASE WHEN oce.estado_conciliacion = 'Conciliado' THEN oce.orden_id END) AS ordenes_conciliadas,
    SUM(CASE WHEN oce.estado_conciliacion = 'Conciliado' THEN oce.total ELSE 0 END) AS monto_conciliado,
    ROUND((SUM(CASE WHEN oce.estado_conciliacion = 'Conciliado' THEN oce.total ELSE 0 END) / NULLIF(SUM(oce.total), 0) * 100)::numeric, 2) AS porcentaje_conciliado,

    -- Ventas NO conciliadas
    COUNT(DISTINCT CASE WHEN oce.estado_conciliacion = 'No Conciliado' THEN oce.orden_id END) AS ordenes_no_conciliadas,
    SUM(CASE WHEN oce.estado_conciliacion = 'No Conciliado' THEN oce.total ELSE 0 END) AS monto_no_conciliado

FROM ordenes_con_estados oce
WHERE 1=1
    [[AND oce.estado_facturacion IN ({{estado_facturacion}})]]
    [[AND oce.estado_pago IN ({{estado_pago}})]]
    [[AND oce.estado_conciliacion IN ({{estado_conciliacion}})]]
GROUP BY oce.anio
ORDER BY oce.anio DESC;


-- ========================================
-- CONSULTA 3: DETALLE DE ÓRDENES
-- Para tablas detalladas con toda la información
-- ========================================

WITH ordenes_base AS (
    SELECT
        so.id AS orden_id,
        so.name AS orden_nombre,
        (so.date_order AT TIME ZONE 'UTC' AT TIME ZONE 'America/Mexico_City')::date AS fecha_orden,
        EXTRACT(YEAR FROM so.date_order) AS anio,
        EXTRACT(MONTH FROM so.date_order) AS mes,
        so.state AS estado_orden,
        so.invoice_status,
        so.amount_untaxed AS subtotal,
        so.amount_total AS total,
        so.partner_id AS cliente_id,
        rp.name AS nombre_cliente,
        so.user_id AS vendedor_id,
        ru.login AS nombre_vendedor,
        so.team_id AS equipo_id,
        ct.name ->> 'es_MX' AS nombre_equipo
    FROM sale_order so
    LEFT JOIN res_partner rp ON rp.id = so.partner_id
    LEFT JOIN res_users ru ON ru.id = so.user_id
    LEFT JOIN crm_team ct ON ct.id = so.team_id
    WHERE
        so.date_order IS NOT NULL
        AND so.state IN ('sale', 'done')
        [[AND {{rango_fecha}}]]
        [[AND so.user_id IN ({{vendedor_id}})]]
        [[AND so.team_id IN ({{equipo_id}})]]
),

ordenes_con_info_facturacion AS (
    SELECT
        ob.*,

        -- Estado de facturación
        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = ob.orden_id
                AND soi.invoice_name IS NOT NULL
                AND soi.invoice_state = 'posted'
            ) THEN 'Facturado'
            ELSE 'No Facturado'
        END AS estado_facturacion,

        -- Estado de pago
        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = ob.orden_id
                AND soi.payment_name IS NOT NULL
            ) THEN 'Pagado'
            ELSE 'No Pagado'
        END AS estado_pago,

        -- Estado de conciliación
        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = ob.orden_id
                AND soi.reconcile_date IS NOT NULL
            ) THEN 'Conciliado'
            ELSE 'No Conciliado'
        END AS estado_conciliacion,

        -- Estado general combinado
        CASE
            WHEN NOT EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = ob.orden_id
                AND soi.invoice_name IS NOT NULL
                AND soi.invoice_state = 'posted'
            ) THEN 'Orden sin Factura'
            WHEN NOT EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = ob.orden_id
                AND soi.payment_name IS NOT NULL
            ) THEN 'Factura sin Pago'
            WHEN NOT EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = ob.orden_id
                AND soi.reconcile_date IS NOT NULL
            ) THEN 'Pago sin Conciliar'
            ELSE 'Completo'
        END AS estado_general,

        -- Información de factura
        (SELECT soi.invoice_name
         FROM sale_order_invoice_payment_info soi
         WHERE soi.order_id = ob.orden_id
         AND soi.invoice_name IS NOT NULL
         AND soi.invoice_state = 'posted'
         ORDER BY soi.invoice_date DESC
         LIMIT 1) AS nombre_factura,

        (SELECT soi.invoice_date
         FROM sale_order_invoice_payment_info soi
         WHERE soi.order_id = ob.orden_id
         AND soi.invoice_name IS NOT NULL
         AND soi.invoice_state = 'posted'
         ORDER BY soi.invoice_date DESC
         LIMIT 1) AS fecha_factura,

        -- Información de pago
        (SELECT soi.payment_name
         FROM sale_order_invoice_payment_info soi
         WHERE soi.order_id = ob.orden_id
         AND soi.payment_name IS NOT NULL
         ORDER BY soi.payment_date DESC
         LIMIT 1) AS nombre_pago,

        (SELECT soi.payment_date
         FROM sale_order_invoice_payment_info soi
         WHERE soi.order_id = ob.orden_id
         AND soi.payment_name IS NOT NULL
         ORDER BY soi.payment_date DESC
         LIMIT 1) AS fecha_pago,

        -- Información de conciliación
        (SELECT soi.reconcile_date
         FROM sale_order_invoice_payment_info soi
         WHERE soi.order_id = ob.orden_id
         AND soi.reconcile_date IS NOT NULL
         ORDER BY soi.reconcile_date DESC
         LIMIT 1) AS fecha_conciliacion

    FROM ordenes_base ob
)

SELECT
    orden_id,
    orden_nombre,
    fecha_orden,
    anio,
    mes,
    estado_orden,
    invoice_status,
    nombre_cliente,
    nombre_vendedor,
    nombre_equipo,
    subtotal,
    total,
    estado_facturacion,
    estado_pago,
    estado_conciliacion,
    estado_general,
    nombre_factura,
    fecha_factura,
    nombre_pago,
    fecha_pago,
    fecha_conciliacion
FROM ordenes_con_info_facturacion
WHERE 1=1
    [[AND estado_facturacion IN ({{estado_facturacion}})]]
    [[AND estado_pago IN ({{estado_pago}})]]
    [[AND estado_conciliacion IN ({{estado_conciliacion}})]]
    [[AND estado_general IN ({{estado_general}})]]
ORDER BY fecha_orden DESC;


-- ========================================
-- CONSULTA 4: COMPARATIVA MENSUAL AÑO ACTUAL VS AÑO ANTERIOR
-- Ideal para gráficas de líneas
-- ========================================

WITH ordenes_base AS (
    SELECT
        so.id AS orden_id,
        EXTRACT(YEAR FROM so.date_order) AS anio,
        EXTRACT(MONTH FROM so.date_order) AS mes,
        so.amount_total AS total,
        so.user_id AS vendedor_id,
        so.team_id AS equipo_id
    FROM sale_order so
    WHERE
        so.date_order IS NOT NULL
        AND so.state IN ('sale', 'done')
        AND EXTRACT(YEAR FROM so.date_order) IN (
            EXTRACT(YEAR FROM CURRENT_DATE),
            EXTRACT(YEAR FROM CURRENT_DATE) - 1
        )
        [[AND so.user_id IN ({{vendedor_id}})]]
        [[AND so.team_id IN ({{equipo_id}})]]
),

ordenes_con_estados AS (
    SELECT
        ob.*,

        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = ob.orden_id
                AND soi.invoice_name IS NOT NULL
                AND soi.invoice_state = 'posted'
            ) THEN 'Facturado'
            ELSE 'No Facturado'
        END AS estado_facturacion,

        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = ob.orden_id
                AND soi.payment_name IS NOT NULL
            ) THEN 'Pagado'
            ELSE 'No Pagado'
        END AS estado_pago,

        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = ob.orden_id
                AND soi.reconcile_date IS NOT NULL
            ) THEN 'Conciliado'
            ELSE 'No Conciliado'
        END AS estado_conciliacion

    FROM ordenes_base ob
),

ventas_por_mes AS (
    SELECT
        anio,
        mes,
        COUNT(DISTINCT orden_id) AS cantidad_ordenes,
        SUM(total) AS total_ventas,
        SUM(CASE WHEN estado_facturacion = 'Facturado' THEN total ELSE 0 END) AS total_facturado,
        SUM(CASE WHEN estado_pago = 'Pagado' THEN total ELSE 0 END) AS total_pagado,
        SUM(CASE WHEN estado_conciliacion = 'Conciliado' THEN total ELSE 0 END) AS total_conciliado
    FROM ordenes_con_estados
    WHERE 1=1
        [[AND estado_facturacion IN ({{estado_facturacion}})]]
        [[AND estado_pago IN ({{estado_pago}})]]
        [[AND estado_conciliacion IN ({{estado_conciliacion}})]]
    GROUP BY anio, mes
)

SELECT
    m.mes,
    TO_CHAR(TO_DATE(m.mes::text, 'MM'), 'Month') AS nombre_mes,

    -- Año actual
    COALESCE(actual.cantidad_ordenes, 0) AS ordenes_anio_actual,
    COALESCE(actual.total_ventas, 0) AS ventas_anio_actual,
    COALESCE(actual.total_facturado, 0) AS facturado_anio_actual,
    COALESCE(actual.total_pagado, 0) AS pagado_anio_actual,
    COALESCE(actual.total_conciliado, 0) AS conciliado_anio_actual,

    -- Año anterior
    COALESCE(anterior.cantidad_ordenes, 0) AS ordenes_anio_anterior,
    COALESCE(anterior.total_ventas, 0) AS ventas_anio_anterior,
    COALESCE(anterior.total_facturado, 0) AS facturado_anio_anterior,
    COALESCE(anterior.total_pagado, 0) AS pagado_anio_anterior,
    COALESCE(anterior.total_conciliado, 0) AS conciliado_anio_anterior,

    -- Variaciones
    COALESCE(actual.total_ventas, 0) - COALESCE(anterior.total_ventas, 0) AS diferencia_ventas,

    CASE
        WHEN COALESCE(anterior.total_ventas, 0) > 0 THEN
            ROUND(((COALESCE(actual.total_ventas, 0) - COALESCE(anterior.total_ventas, 0))
                   / anterior.total_ventas * 100)::numeric, 2)
        ELSE NULL
    END AS porcentaje_variacion

FROM generate_series(1, 12) m(mes)
LEFT JOIN ventas_por_mes actual
    ON actual.mes = m.mes
    AND actual.anio = EXTRACT(YEAR FROM CURRENT_DATE)
LEFT JOIN ventas_por_mes anterior
    ON anterior.mes = m.mes
    AND anterior.anio = EXTRACT(YEAR FROM CURRENT_DATE) - 1
ORDER BY m.mes;


-- ========================================
-- GUÍA DE CONFIGURACIÓN DE FILTROS EN METABASE
-- ========================================
/*
Para configurar los filtros en Metabase, usa los siguientes parámetros:

1. {{rango_fecha}}
   - Tipo: Field Filter
   - Widget: Date Filter
   - Campo: date_order (de sale_order)
   - Opciones: All Options, Relative dates, etc.

2. {{estado_facturacion}}
   - Tipo: Field Filter
   - Widget: String
   - Valores permitidos: "Facturado", "No Facturado"
   - Permite múltiples valores

3. {{estado_pago}}
   - Tipo: Field Filter
   - Widget: String
   - Valores permitidos: "Pagado", "No Pagado"
   - Permite múltiples valores

4. {{estado_conciliacion}}
   - Tipo: Field Filter
   - Widget: String
   - Valores permitidos: "Conciliado", "No Conciliado"
   - Permite múltiples valores

5. {{estado_general}}
   - Tipo: Field Filter
   - Widget: String
   - Valores permitidos: "Orden sin Factura", "Factura sin Pago", "Pago sin Conciliar", "Completo"
   - Permite múltiples valores

6. {{vendedor_id}}
   - Tipo: Field Filter
   - Widget: ID
   - Campo: user_id (de sale_order)
   - Permite múltiples valores

7. {{equipo_id}}
   - Tipo: Field Filter
   - Widget: ID
   - Campo: team_id (de sale_order)
   - Permite múltiples valores

IMPORTANTE:
- Los filtros con sintaxis [[AND {{filtro}}]] son opcionales
- Si no se selecciona ningún valor, el filtro se ignora
- Todos los filtros pueden combinarse entre sí
*/
