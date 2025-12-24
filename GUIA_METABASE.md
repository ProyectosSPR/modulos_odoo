# Guía de Configuración Dashboard de Ventas en Metabase

## Información de Conexión

**Datos de conexión a PostgreSQL:**
- Host: `192.168.80.232`
- Puerto: `30432`
- Base de datos: `odoo16c`
- Usuario: `dml`
- Contraseña: `Sergio55`

## Archivos Disponibles

1. **metabase_queries_filtros.sql** - Contiene 4 consultas SQL optimizadas para Metabase con filtros

## Estructura del Dashboard

### CONSULTA 1: Comparativa de Ventas con Filtros Detallados
**Propósito:** Análisis diario/mensual de ventas con filtros múltiples

**Campos devueltos:**
- `anio`, `mes`, `fecha_orden`
- `cantidad_ordenes`, `total_subtotal`, `total_con_impuestos`, `ticket_promedio`
- `total_facturado`, `total_no_facturado`
- `total_pagado`, `total_no_pagado`
- `total_conciliado`, `total_no_conciliado`
- Contadores de órdenes por estado

**Filtros disponibles:**
- `{{rango_fecha}}` - Filtro de rango de fechas
- `{{vendedor_id}}` - Filtro por vendedor
- `{{equipo_id}}` - Filtro por equipo de ventas
- `{{estado_facturacion}}` - "Facturado" o "No Facturado"
- `{{estado_pago}}` - "Pagado" o "No Pagado"
- `{{estado_conciliacion}}` - "Conciliado" o "No Conciliado"

**Uso recomendado:**
- Tablas de resumen diario/mensual
- Gráficas de barras apiladas
- Filtros interactivos para usuarios

---

### CONSULTA 2: Resumen Consolidado por Año
**Propósito:** KPIs principales y métricas anuales

**Campos devueltos:**
- `anio`
- `total_ordenes`, `total_ventas`, `ticket_promedio`
- Desglose completo de facturación (cantidad, monto, porcentaje)
- Desglose completo de pagos (cantidad, monto, porcentaje)
- Desglose completo de conciliación (cantidad, monto, porcentaje)

**Filtros disponibles:**
- `{{rango_fecha}}`
- `{{vendedor_id}}`
- `{{equipo_id}}`
- `{{estado_facturacion}}`
- `{{estado_pago}}`
- `{{estado_conciliacion}}`

**Uso recomendado:**
- Tarjetas de KPIs principales
- Gráficas de dona/pie para distribución de estados
- Comparativa anual en formato tabla

---

### CONSULTA 3: Detalle de Órdenes
**Propósito:** Vista detallada de cada orden con toda su información

**Campos devueltos:**
- Información básica: `orden_id`, `orden_nombre`, `fecha_orden`, `anio`, `mes`
- Estados: `estado_orden`, `invoice_status`
- Cliente y vendedor: `nombre_cliente`, `nombre_vendedor`, `nombre_equipo`
- Montos: `subtotal`, `total`
- Estados calculados: `estado_facturacion`, `estado_pago`, `estado_conciliacion`, `estado_general`
- Información detallada: `nombre_factura`, `fecha_factura`, `nombre_pago`, `fecha_pago`, `fecha_conciliacion`

**Filtros disponibles:**
- `{{rango_fecha}}`
- `{{vendedor_id}}`
- `{{equipo_id}}`
- `{{estado_facturacion}}`
- `{{estado_pago}}`
- `{{estado_conciliacion}}`
- `{{estado_general}}` - "Orden sin Factura", "Factura sin Pago", "Pago sin Conciliar", "Completo"

**Uso recomendado:**
- Tabla de detalle principal del dashboard
- Exportación de datos
- Drill-down desde otras visualizaciones

---

### CONSULTA 4: Comparativa Mensual Año Actual vs Año Anterior
**Propósito:** Gráfica de tendencias comparando años

**Campos devueltos:**
- `mes`, `nombre_mes`
- Métricas año actual: `ordenes_anio_actual`, `ventas_anio_actual`, `facturado_anio_actual`, `pagado_anio_actual`, `conciliado_anio_actual`
- Métricas año anterior: `ordenes_anio_anterior`, `ventas_anio_anterior`, `facturado_anio_anterior`, `pagado_anio_anterior`, `conciliado_anio_anterior`
- Variaciones: `diferencia_ventas`, `porcentaje_variacion`

**Filtros disponibles:**
- `{{vendedor_id}}`
- `{{equipo_id}}`
- `{{estado_facturacion}}`
- `{{estado_pago}}`
- `{{estado_conciliacion}}`

**Uso recomendado:**
- Gráfica de líneas comparativa
- Análisis de tendencias mes a mes
- Identificación de estacionalidad

---

## Configuración de Filtros en Metabase

### Paso 1: Crear la Pregunta SQL

1. En Metabase, ir a "New" → "SQL Query"
2. Seleccionar la conexión a la base de datos `odoo16c`
3. Copiar y pegar una de las consultas del archivo `metabase_queries_filtros.sql`
4. Click en "Save"

### Paso 2: Configurar Variables/Filtros

Para cada variable en la consulta (por ejemplo `{{rango_fecha}}`), Metabase detectará automáticamente que es un filtro. Configura cada uno así:

#### {{rango_fecha}}
- **Tipo:** Field Filter
- **Widget:** Date Filter
- **Campo:** No es necesario mapear (la consulta ya maneja esto)
- **Tipo de campo:** Date
- **Display name:** "Rango de Fecha"
- **Opciones:** Habilitar "All Options" para permitir rangos personalizados

#### {{estado_facturacion}}
- **Tipo:** Field Filter
- **Widget:** String contains
- **Display name:** "Estado de Facturación"
- **Valores por defecto:** Ninguno (opcional)
- **Nota:** Los usuarios pueden escribir "Facturado" o "No Facturado"

**Mejor opción - Crear filtro con valores predefinidos:**
Para mejorar la experiencia, puedes cambiar la consulta para usar un filtro de lista:
```sql
-- En lugar de: [[AND estado_facturacion IN ({{estado_facturacion}})]]
-- Usar: [[AND estado_facturacion = {{estado_facturacion}}]]
```
Luego configurar como:
- **Tipo:** Text
- **Widget:** Dropdown list
- **Source:** Custom list
- **Valores:** "Facturado", "No Facturado"

#### {{estado_pago}}
- **Tipo:** Field Filter / Text
- **Widget:** Dropdown list (si usas Custom list)
- **Display name:** "Estado de Pago"
- **Valores:** "Pagado", "No Pagado"

#### {{estado_conciliacion}}
- **Tipo:** Field Filter / Text
- **Widget:** Dropdown list
- **Display name:** "Estado de Conciliación"
- **Valores:** "Conciliado", "No Conciliado"

#### {{estado_general}}
- **Tipo:** Field Filter / Text
- **Widget:** Dropdown list
- **Display name:** "Estado General"
- **Valores:**
  - "Orden sin Factura"
  - "Factura sin Pago"
  - "Pago sin Conciliar"
  - "Completo"

#### {{vendedor_id}}
- **Tipo:** Number
- **Widget:** Number
- **Display name:** "ID Vendedor"
- **Nota:** Permite múltiples valores separados por coma

#### {{equipo_id}}
- **Tipo:** Number
- **Widget:** Number
- **Display name:** "ID Equipo"

### Paso 3: Crear el Dashboard

1. Ir a "New" → "Dashboard"
2. Nombre: "Dashboard de Ventas - Comparativa Anual"
3. Click en "Add a question" y selecciona las preguntas que creaste

### Diseño Recomendado del Dashboard

```
┌─────────────────────────────────────────────────────────────┐
│ FILTROS (Superior)                                          │
│ [Rango Fecha] [Vendedor] [Equipo] [Estado Fact] [Estado P] │
└─────────────────────────────────────────────────────────────┘

┌──────────────┬──────────────┬──────────────┬──────────────┐
│ KPI: Total   │ KPI: Total   │ KPI: Total   │ KPI: Ticket  │
│ Órdenes      │ Ventas       │ Facturado    │ Promedio     │
│ (Consulta 2) │ (Consulta 2) │ (Consulta 2) │ (Consulta 2) │
└──────────────┴──────────────┴──────────────┴──────────────┘

┌─────────────────────────────┬─────────────────────────────┐
│ Gráfica de Líneas:          │ Gráfica de Dona:            │
│ Comparativa Mensual         │ Distribución por Estado     │
│ (Consulta 4)                │ (Consulta 2)                │
│                             │                             │
└─────────────────────────────┴─────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Tabla Detallada de Órdenes                                  │
│ (Consulta 3)                                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Interpretación de los Estados

### Estado de Facturación
- **Facturado:** La orden tiene al menos una factura en estado 'posted' en `sale_order_invoice_payment_info`
- **No Facturado:** No se encontró ninguna factura válida para la orden

### Estado de Pago
- **Pagado:** La orden tiene al menos un pago registrado en `sale_order_invoice_payment_info`
- **No Pagado:** No se encontró ningún pago para la orden

### Estado de Conciliación
- **Conciliado:** La orden tiene al menos un registro con `reconcile_date` en `sale_order_invoice_payment_info`
- **No Conciliado:** No hay fecha de conciliación registrada

### Estado General (solo Consulta 3)
- **Orden sin Factura:** La orden no tiene ninguna factura
- **Factura sin Pago:** La orden está facturada pero no tiene pagos
- **Pago sin Conciliar:** La orden está facturada y pagada pero no conciliada
- **Completo:** La orden está facturada, pagada y conciliada

---

## Datos Importantes a Considerar

### Resultado de Prueba (2024-2025)

**Año 2025:**
- Total órdenes: 3,426
- Total ventas: $18,635,154.63
- ⚠️ Solo 3 órdenes con información de facturación
- ⚠️ Solo 2 órdenes con información de pago
- ⚠️ Solo 2 órdenes conciliadas

**Año 2024:**
- Total órdenes: 1,239
- Total ventas: $10,089,035.41
- ⚠️ 0 órdenes con información de facturación/pago/conciliación

### Advertencia Importante

La tabla `sale_order_invoice_payment_info` parece tener muy pocos registros comparado con el total de órdenes. Esto puede significar:

1. **Es una tabla nueva:** Puede que solo se haya empezado a usar recientemente
2. **Se llena manualmente:** Requiere un proceso específico para poblarla
3. **Solo para casos específicos:** Se usa solo para ciertos tipos de órdenes

**Recomendación:** Verificar con el equipo técnico:
- ¿Cómo se llena esta tabla?
- ¿Por qué solo tiene tan pocos registros?
- ¿Deberían usar otra fuente de datos para determinar estados de facturación/pago?

### Fuentes Alternativas de Datos

Si `sale_order_invoice_payment_info` no es confiable, considera:

1. **Para facturación:** Usar la tabla `account_move` directamente
2. **Para pagos:** Usar `account_payment` y `account_partial_reconcile`
3. **Para conciliación:** Verificar `account_move_line` con `reconciled = true`

---

## Próximos Pasos

1. **Validar los datos:** Confirmar que la tabla `sale_order_invoice_payment_info` es la fuente correcta
2. **Poblar datos faltantes:** Si es necesario, ejecutar proceso para llenar la tabla
3. **Crear consultas alternativas:** Si la tabla no es adecuada, usar las tablas de contabilidad directamente
4. **Testear en Metabase:** Importar las consultas y probar los filtros
5. **Ajustar visualizaciones:** Configurar las gráficas según preferencias

---

## Soporte y Consultas

Si necesitas modificar las consultas o agregar más funcionalidad, considera:
- Agregar más filtros (cliente, producto, categoría)
- Crear drill-downs entre consultas
- Agregar métricas calculadas (margen, comisión)
- Integrar con otras tablas (productos, categorías, etc.)
