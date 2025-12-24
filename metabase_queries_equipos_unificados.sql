-- ========================================
-- CONSULTAS SQL PARA METABASE - DASHBOARD DE VENTAS
-- Con EQUIPOS UNIFICADOS y Filtros de Metabase
-- Base de datos: odoo16c
-- ========================================

-- ========================================
-- CONSULTA 1: COMPARATIVA DE VENTAS CON EQUIPOS UNIFICADOS
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
        so.team_id AS equipo_venta_id
    FROM sale_order so
    WHERE
        so.date_order IS NOT NULL
        AND so.state IN ('sale', 'done')  -- Solo órdenes confirmadas
        [[AND {{rango_fecha}}]]
),

ordenes_con_equipo_unificado AS (
    SELECT
        ob.*,
        -- Obtener el equipo unificado
        ctu.id AS equipo_unificado_id,
        ctu.name AS equipo_unificado,
        ct.name ->> 'es_MX' AS equipo_venta_nombre
    FROM ordenes_base ob
    LEFT JOIN crm_team ct ON ct.id = ob.equipo_venta_id
    LEFT JOIN commission_team_unified_crm_team_rel rel ON rel.team_id = ob.equipo_venta_id
    LEFT JOIN commission_team_unified ctu ON ctu.id = rel.unified_id
    WHERE 1=1
        -- Filtro por equipo unificado (permite seleccionar múltiples)
        [[AND ctu.id IN ({{equipo_unificado_id}})]]
),

ordenes_con_estados AS (
    SELECT
        oeu.*,

        -- Estado de facturación
        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = oeu.orden_id
                AND soi.invoice_name IS NOT NULL
                AND soi.invoice_state = 'posted'
            ) THEN 'Facturado'
            ELSE 'No Facturado'
        END AS estado_facturacion,

        -- Estado de pago
        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = oeu.orden_id
                AND soi.payment_name IS NOT NULL
            ) THEN 'Pagado'
            ELSE 'No Pagado'
        END AS estado_pago,

        -- Estado de conciliación
        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = oeu.orden_id
                AND soi.reconcile_date IS NOT NULL
            ) THEN 'Conciliado'
            ELSE 'No Conciliado'
        END AS estado_conciliacion

    FROM ordenes_con_equipo_unificado oeu
)

SELECT
    oce.anio,
    oce.mes,
    oce.fecha_orden,
    oce.equipo_unificado,
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
GROUP BY oce.anio, oce.mes, oce.fecha_orden, oce.equipo_unificado
ORDER BY oce.fecha_orden DESC;


-- ========================================
-- CONSULTA 2: RESUMEN CONSOLIDADO POR AÑO Y EQUIPO UNIFICADO
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
        so.team_id AS equipo_venta_id
    FROM sale_order so
    WHERE
        so.date_order IS NOT NULL
        AND so.state IN ('sale', 'done')
        [[AND {{rango_fecha}}]]
),

ordenes_con_equipo_unificado AS (
    SELECT
        ob.*,
        ctu.id AS equipo_unificado_id,
        ctu.name AS equipo_unificado
    FROM ordenes_base ob
    LEFT JOIN commission_team_unified_crm_team_rel rel ON rel.team_id = ob.equipo_venta_id
    LEFT JOIN commission_team_unified ctu ON ctu.id = rel.unified_id
    WHERE 1=1
        [[AND ctu.id IN ({{equipo_unificado_id}})]]
),

ordenes_con_estados AS (
    SELECT
        oeu.*,

        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = oeu.orden_id
                AND soi.invoice_name IS NOT NULL
                AND soi.invoice_state = 'posted'
            ) THEN 'Facturado'
            ELSE 'No Facturado'
        END AS estado_facturacion,

        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = oeu.orden_id
                AND soi.payment_name IS NOT NULL
            ) THEN 'Pagado'
            ELSE 'No Pagado'
        END AS estado_pago,

        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = oeu.orden_id
                AND soi.reconcile_date IS NOT NULL
            ) THEN 'Conciliado'
            ELSE 'No Conciliado'
        END AS estado_conciliacion

    FROM ordenes_con_equipo_unificado oeu
)

SELECT
    oce.anio,
    oce.equipo_unificado,
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
GROUP BY oce.anio, oce.equipo_unificado
ORDER BY oce.anio DESC, oce.equipo_unificado;


-- ========================================
-- CONSULTA 3: DETALLE DE ÓRDENES CON EQUIPOS UNIFICADOS
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
        so.team_id AS equipo_venta_id
    FROM sale_order so
    LEFT JOIN res_partner rp ON rp.id = so.partner_id
    WHERE
        so.date_order IS NOT NULL
        AND so.state IN ('sale', 'done')
        [[AND {{rango_fecha}}]]
),

ordenes_con_equipo_unificado AS (
    SELECT
        ob.*,
        ctu.id AS equipo_unificado_id,
        ctu.name AS equipo_unificado,
        ct.name ->> 'es_MX' AS equipo_venta_nombre
    FROM ordenes_base ob
    LEFT JOIN crm_team ct ON ct.id = ob.equipo_venta_id
    LEFT JOIN commission_team_unified_crm_team_rel rel ON rel.team_id = ob.equipo_venta_id
    LEFT JOIN commission_team_unified ctu ON ctu.id = rel.unified_id
    WHERE 1=1
        [[AND ctu.id IN ({{equipo_unificado_id}})]]
),

ordenes_con_info_facturacion AS (
    SELECT
        oeu.*,

        -- Estado de facturación
        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = oeu.orden_id
                AND soi.invoice_name IS NOT NULL
                AND soi.invoice_state = 'posted'
            ) THEN 'Facturado'
            ELSE 'No Facturado'
        END AS estado_facturacion,

        -- Estado de pago
        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = oeu.orden_id
                AND soi.payment_name IS NOT NULL
            ) THEN 'Pagado'
            ELSE 'No Pagado'
        END AS estado_pago,

        -- Estado de conciliación
        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = oeu.orden_id
                AND soi.reconcile_date IS NOT NULL
            ) THEN 'Conciliado'
            ELSE 'No Conciliado'
        END AS estado_conciliacion,

        -- Estado general combinado
        CASE
            WHEN NOT EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = oeu.orden_id
                AND soi.invoice_name IS NOT NULL
                AND soi.invoice_state = 'posted'
            ) THEN 'Orden sin Factura'
            WHEN NOT EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = oeu.orden_id
                AND soi.payment_name IS NOT NULL
            ) THEN 'Factura sin Pago'
            WHEN NOT EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = oeu.orden_id
                AND soi.reconcile_date IS NOT NULL
            ) THEN 'Pago sin Conciliar'
            ELSE 'Completo'
        END AS estado_general,

        -- Información de factura
        (SELECT soi.invoice_name
         FROM sale_order_invoice_payment_info soi
         WHERE soi.order_id = oeu.orden_id
         AND soi.invoice_name IS NOT NULL
         AND soi.invoice_state = 'posted'
         ORDER BY soi.invoice_date DESC
         LIMIT 1) AS nombre_factura,

        (SELECT soi.invoice_date
         FROM sale_order_invoice_payment_info soi
         WHERE soi.order_id = oeu.orden_id
         AND soi.invoice_name IS NOT NULL
         AND soi.invoice_state = 'posted'
         ORDER BY soi.invoice_date DESC
         LIMIT 1) AS fecha_factura,

        -- Información de pago
        (SELECT soi.payment_name
         FROM sale_order_invoice_payment_info soi
         WHERE soi.order_id = oeu.orden_id
         AND soi.payment_name IS NOT NULL
         ORDER BY soi.payment_date DESC
         LIMIT 1) AS nombre_pago,

        (SELECT soi.payment_date
         FROM sale_order_invoice_payment_info soi
         WHERE soi.order_id = oeu.orden_id
         AND soi.payment_name IS NOT NULL
         ORDER BY soi.payment_date DESC
         LIMIT 1) AS fecha_pago,

        -- Información de conciliación
        (SELECT soi.reconcile_date
         FROM sale_order_invoice_payment_info soi
         WHERE soi.order_id = oeu.orden_id
         AND soi.reconcile_date IS NOT NULL
         ORDER BY soi.reconcile_date DESC
         LIMIT 1) AS fecha_conciliacion

    FROM ordenes_con_equipo_unificado oeu
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
    equipo_unificado,
    equipo_venta_nombre,
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
-- Con equipos unificados
-- ========================================

WITH ordenes_base AS (
    SELECT
        so.id AS orden_id,
        EXTRACT(YEAR FROM so.date_order) AS anio,
        EXTRACT(MONTH FROM so.date_order) AS mes,
        so.amount_total AS total,
        so.team_id AS equipo_venta_id
    FROM sale_order so
    WHERE
        so.date_order IS NOT NULL
        AND so.state IN ('sale', 'done')
        AND EXTRACT(YEAR FROM so.date_order) IN (
            EXTRACT(YEAR FROM CURRENT_DATE),
            EXTRACT(YEAR FROM CURRENT_DATE) - 1
        )
),

ordenes_con_equipo_unificado AS (
    SELECT
        ob.*,
        ctu.id AS equipo_unificado_id,
        ctu.name AS equipo_unificado
    FROM ordenes_base ob
    LEFT JOIN commission_team_unified_crm_team_rel rel ON rel.team_id = ob.equipo_venta_id
    LEFT JOIN commission_team_unified ctu ON ctu.id = rel.unified_id
    WHERE 1=1
        [[AND ctu.id IN ({{equipo_unificado_id}})]]
),

ordenes_con_estados AS (
    SELECT
        oeu.*,

        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = oeu.orden_id
                AND soi.invoice_name IS NOT NULL
                AND soi.invoice_state = 'posted'
            ) THEN 'Facturado'
            ELSE 'No Facturado'
        END AS estado_facturacion,

        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = oeu.orden_id
                AND soi.payment_name IS NOT NULL
            ) THEN 'Pagado'
            ELSE 'No Pagado'
        END AS estado_pago,

        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_invoice_payment_info soi
                WHERE soi.order_id = oeu.orden_id
                AND soi.reconcile_date IS NOT NULL
            ) THEN 'Conciliado'
            ELSE 'No Conciliado'
        END AS estado_conciliacion

    FROM ordenes_con_equipo_unificado oeu
),

ventas_por_mes AS (
    SELECT
        anio,
        mes,
        equipo_unificado,
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
    GROUP BY anio, mes, equipo_unificado
)

SELECT
    m.mes,
    TO_CHAR(TO_DATE(m.mes::text, 'MM'), 'Month') AS nombre_mes,
    COALESCE(actual.equipo_unificado, anterior.equipo_unificado) AS equipo_unificado,

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
CROSS JOIN (
    SELECT DISTINCT equipo_unificado
    FROM ventas_por_mes
) equipos
LEFT JOIN ventas_por_mes actual
    ON actual.mes = m.mes
    AND actual.anio = EXTRACT(YEAR FROM CURRENT_DATE)
    AND actual.equipo_unificado = equipos.equipo_unificado
LEFT JOIN ventas_por_mes anterior
    ON anterior.mes = m.mes
    AND anterior.anio = EXTRACT(YEAR FROM CURRENT_DATE) - 1
    AND anterior.equipo_unificado = equipos.equipo_unificado
ORDER BY equipos.equipo_unificado, m.mes;


-- ========================================
-- CONSULTA ADICIONAL: LISTA DE EQUIPOS UNIFICADOS
-- Para poblar el filtro dropdown en Metabase
-- ========================================

SELECT
    ctu.id AS equipo_unificado_id,
    ctu.name AS equipo_unificado_nombre,
    ARRAY_AGG(ct.name ->> 'es_MX' ORDER BY ct.name ->> 'es_MX') AS equipos_incluidos,
    COUNT(DISTINCT rel.team_id) AS cantidad_equipos
FROM commission_team_unified ctu
LEFT JOIN commission_team_unified_crm_team_rel rel ON rel.unified_id = ctu.id
LEFT JOIN crm_team ct ON ct.id = rel.team_id
WHERE ctu.active = true
GROUP BY ctu.id, ctu.name
ORDER BY ctu.name;


-- ========================================
-- GUÍA DE CONFIGURACIÓN DE FILTROS EN METABASE
-- ========================================
/*
FILTROS DISPONIBLES:

1. {{rango_fecha}}
   - Tipo: Field Filter
   - Widget: Date Filter
   - Configuración: Permitir rangos personalizados

2. {{equipo_unificado_id}}
   - Tipo: Number
   - Widget: Dropdown list
   - Source: From another model/question
   - Usar la "CONSULTA ADICIONAL" para poblar los valores
   - Permite múltiples selecciones
   - Valores: IDs de commission_team_unified

   IMPORTANTE: Este filtro permite seleccionar múltiples equipos unificados.
   Por ejemplo, si seleccionas "Mercado libre" (ID 1), automáticamente
   filtrará todas las órdenes de los equipos:
   - Mercado Libre (team_id 5)
   - Mercado Libre Full (team_id 10)
   - Mercado Libre Agencia (team_id 11)

3. {{estado_facturacion}}
   - Tipo: Text
   - Widget: Dropdown list
   - Valores: "Facturado", "No Facturado"
   - Permite múltiples selecciones

4. {{estado_pago}}
   - Tipo: Text
   - Widget: Dropdown list
   - Valores: "Pagado", "No Pagado"
   - Permite múltiples selecciones

5. {{estado_conciliacion}}
   - Tipo: Text
   - Widget: Dropdown list
   - Valores: "Conciliado", "No Conciliado"
   - Permite múltiples selecciones

6. {{estado_general}}
   - Tipo: Text
   - Widget: Dropdown list
   - Valores: "Orden sin Factura", "Factura sin Pago", "Pago sin Conciliar", "Completo"
   - Permite múltiples selecciones

EJEMPLO DE CONFIGURACIÓN DEL FILTRO DE EQUIPOS UNIFICADOS:
1. Crear primero una pregunta con la "CONSULTA ADICIONAL"
2. En el filtro {{equipo_unificado_id}}, seleccionar:
   - Field to map to: No mapear (usar el ID directamente)
   - Filter widget type: Dropdown list
   - How should people filter on this column?: Dropdown list
   - Limit list values: Yes
   - Source: From another model or question
   - Seleccionar la pregunta de "Lista de Equipos Unificados"
   - Value: equipo_unificado_id
   - Label: equipo_unificado_nombre
*/
