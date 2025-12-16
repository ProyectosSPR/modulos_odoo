# Guía de Configuración Dashboard de Ventas con Equipos Unificados

## Información de Conexión

**Datos de conexión a PostgreSQL:**
- Host: `192.168.80.232`
- Puerto: `30432`
- Base de datos: `odoo16c`
- Usuario: `dml`
- Contraseña: `Sergio55`

## ¿Qué son los Equipos Unificados?

Los **equipos unificados** agrupan múltiples equipos de venta individuales para facilitar el análisis. Por ejemplo:

| Equipo Unificado | Equipos de Venta Incluidos |
|------------------|----------------------------|
| **Mercado libre** | • Mercado Libre<br>• Mercado Libre Full<br>• Mercado Libre Agencia |
| **Amazon** | • Amazon<br>• Amazon FBA |
| **Google** | • Google<br>• Sitio web |
| **Meta** | • Meta |
| **Ventas Directas** | • Ventas Directas |
| **Distribuidores** | • Distribución |

Cuando filtras por un **equipo unificado**, automáticamente incluye todas las órdenes de los equipos individuales asociados.

## Estructura de Datos

### Tablas Involucradas

1. **sale_order** - Órdenes de venta
2. **sale_order_invoice_payment_info** - Información de facturación y pagos
3. **commission_team_unified** - Equipos unificados
4. **commission_team_unified_crm_team_rel** - Relación entre equipos unificados y equipos de venta
5. **crm_team** - Equipos de venta individuales

## Archivos Disponibles

### 1. metabase_queries_equipos_unificados.sql

Contiene **5 consultas SQL** optimizadas:

#### CONSULTA 1: Comparativa de Ventas con Equipos Unificados
**Propósito:** Análisis diario/mensual con desglose por equipo unificado y estados

**Campos principales:**
- `anio`, `mes`, `fecha_orden`
- `equipo_unificado` - Nombre del equipo unificado
- `cantidad_ordenes`, `total_subtotal`, `total_con_impuestos`, `ticket_promedio`
- Totales y conteos por estados (facturado, pagado, conciliado)

**Filtros:**
- `{{rango_fecha}}` - Rango de fechas
- `{{equipo_unificado_id}}` - Uno o varios equipos unificados
- `{{estado_facturacion}}` - "Facturado" / "No Facturado"
- `{{estado_pago}}` - "Pagado" / "No Pagado"
- `{{estado_conciliacion}}` - "Conciliado" / "No Conciliado"

**Uso:**
- Gráficas de barras apiladas por equipo
- Análisis de tendencias por canal de venta

---

#### CONSULTA 2: Resumen Consolidado por Año y Equipo Unificado
**Propósito:** KPIs principales por año y equipo unificado

**Campos principales:**
- `anio`, `equipo_unificado`
- `total_ordenes`, `total_ventas`, `ticket_promedio`
- Desglose completo con porcentajes de facturación, pago y conciliación

**Filtros:**
- `{{rango_fecha}}`
- `{{equipo_unificado_id}}`
- `{{estado_facturacion}}`
- `{{estado_pago}}`
- `{{estado_conciliacion}}`

**Uso:**
- Tarjetas de KPIs por equipo
- Comparación entre equipos unificados
- Análisis de eficiencia por canal

---

#### CONSULTA 3: Detalle de Órdenes con Equipos Unificados
**Propósito:** Vista detallada de cada orden con equipo unificado y equipo individual

**Campos principales:**
- Información básica de orden
- `equipo_unificado` - Equipo unificado
- `equipo_venta_nombre` - Equipo de venta individual
- Estados y fechas de facturación, pago y conciliación

**Filtros:**
- `{{rango_fecha}}`
- `{{equipo_unificado_id}}`
- `{{estado_facturacion}}`
- `{{estado_pago}}`
- `{{estado_conciliacion}}`
- `{{estado_general}}`

**Uso:**
- Tabla de detalle principal
- Drill-down para análisis específicos
- Exportación de datos

---

#### CONSULTA 4: Comparativa Mensual Año Actual vs Anterior
**Propósito:** Tendencias mensuales por equipo unificado comparando años

**Campos principales:**
- `mes`, `nombre_mes`, `equipo_unificado`
- Métricas de año actual y año anterior
- Variaciones absolutas y porcentuales

**Filtros:**
- `{{equipo_unificado_id}}`
- `{{estado_facturacion}}`
- `{{estado_pago}}`
- `{{estado_conciliacion}}`

**Uso:**
- Gráficas de líneas comparativas
- Análisis de crecimiento por equipo
- Identificación de estacionalidad por canal

---

#### CONSULTA ADICIONAL: Lista de Equipos Unificados
**Propósito:** Poblar el dropdown del filtro de equipos unificados

**Campos:**
- `equipo_unificado_id` - ID del equipo
- `equipo_unificado_nombre` - Nombre para mostrar
- `equipos_incluidos` - Lista de equipos individuales
- `cantidad_equipos` - Número de equipos incluidos

**Uso:**
- Configurar el filtro dropdown de equipos unificados
- Documentación de agrupaciones

---

## Configuración Paso a Paso en Metabase

### Paso 1: Crear las Preguntas SQL

1. **Nueva pregunta SQL:**
   - Ir a "New" → "SQL Query"
   - Seleccionar conexión `odoo16c`
   - Copiar y pegar cada consulta del archivo
   - Guardar con nombre descriptivo

2. **Nombres sugeridos:**
   - "Dashboard Ventas - Diario por Equipo"
   - "Dashboard Ventas - KPIs por Año"
   - "Dashboard Ventas - Detalle de Órdenes"
   - "Dashboard Ventas - Comparativa Mensual"
   - "Catálogo - Equipos Unificados"

### Paso 2: Configurar el Filtro de Equipos Unificados

**IMPORTANTE:** Primero crea la "CONSULTA ADICIONAL" para listar equipos unificados.

#### Configuración del filtro {{equipo_unificado_id}}

1. **En la pregunta SQL, Metabase detectará el filtro automáticamente**

2. **Configuración del filtro:**
   - Click en el ícono de configuración del filtro
   - **Filter widget type:** Dropdown list
   - **How should people filter:** Dropdown list
   - **Limit list values:** Yes
   - **Source:** From another model or question
   - **Select question:** "Catálogo - Equipos Unificados"
   - **Column to filter on:** No mapear (usar directamente)
   - **Value column:** `equipo_unificado_id`
   - **Label column:** `equipo_unificado_nombre`
   - **Allow multiple selections:** Yes ✓

3. **Resultado:**
   - Los usuarios verán: "Mercado libre", "Amazon", "Google", etc.
   - Al seleccionar uno, filtrará automáticamente todos los equipos incluidos
   - Pueden seleccionar múltiples equipos unificados

### Paso 3: Configurar Otros Filtros

#### {{rango_fecha}}
- **Type:** Field Filter
- **Widget:** Date Filter
- **Display name:** "Rango de Fecha"
- **Default:** Last 30 days (o el que prefieras)

#### {{estado_facturacion}}
- **Type:** Text
- **Widget:** Dropdown list
- **Display name:** "Estado de Facturación"
- **Source:** Custom list
- **Values:**
  ```
  Facturado
  No Facturado
  ```
- **Allow multiple:** Yes

#### {{estado_pago}}
- **Type:** Text
- **Widget:** Dropdown list
- **Display name:** "Estado de Pago"
- **Values:**
  ```
  Pagado
  No Pagado
  ```
- **Allow multiple:** Yes

#### {{estado_conciliacion}}
- **Type:** Text
- **Widget:** Dropdown list
- **Display name:** "Estado de Conciliación"
- **Values:**
  ```
  Conciliado
  No Conciliado
  ```
- **Allow multiple:** Yes

#### {{estado_general}}
- **Type:** Text
- **Widget:** Dropdown list
- **Display name:** "Estado General"
- **Values:**
  ```
  Orden sin Factura
  Factura sin Pago
  Pago sin Conciliar
  Completo
  ```
- **Allow multiple:** Yes

### Paso 4: Crear el Dashboard

1. **Nuevo Dashboard:**
   - "New" → "Dashboard"
   - Nombre: "Dashboard de Ventas por Equipo Unificado"

2. **Agregar preguntas:**
   - Click en "+ Add a question"
   - Seleccionar cada pregunta creada

### Diseño Recomendado del Dashboard

```
┌─────────────────────────────────────────────────────────────┐
│ FILTROS GLOBALES                                            │
│ [Rango Fecha] [Equipo Unificado] [Estado Fact] [Estado P]  │
└─────────────────────────────────────────────────────────────┘

┌──────────┬──────────┬──────────┬──────────┬──────────────┐
│ Total    │ Total    │ Total    │ Ticket   │ % Facturado  │
│ Órdenes  │ Ventas   │ Facturado│ Promedio │              │
└──────────┴──────────┴──────────┴──────────┴──────────────┘

┌─────────────────────────────┬─────────────────────────────┐
│ Gráfica de Barras:          │ Gráfica de Dona:            │
│ Ventas por Equipo Unificado │ Distribución por Estado     │
│ (Consulta 2)                │ (Consulta 2)                │
└─────────────────────────────┴─────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Gráfica de Líneas: Comparativa Mensual                     │
│ (Consulta 4)                                                │
│ Año Actual vs Año Anterior por Equipo                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Tabla Detallada: Órdenes con Equipo Unificado              │
│ (Consulta 3)                                                │
└─────────────────────────────────────────────────────────────┘
```

### Paso 5: Conectar Filtros al Dashboard

1. **En modo de edición del dashboard:**
   - Click en el ícono de lápiz (Edit)
   - Click en "Add a Filter"

2. **Para cada filtro:**
   - Agregar filtro del tipo correspondiente
   - Conectar a todas las preguntas relevantes
   - Mapear a las variables correctas

3. **Ejemplo - Filtro de Equipo Unificado:**
   - Add Filter → ID
   - Display name: "Equipo Unificado"
   - Configurar como dropdown con valores de "Catálogo - Equipos Unificados"
   - Conectar a todas las preguntas
   - Mapear a `{{equipo_unificado_id}}`

---

## Ejemplo de Uso del Filtro de Equipos Unificados

### Caso: Analizar ventas de Mercado Libre

1. **Seleccionar en el filtro:** "Mercado libre"

2. **Automáticamente filtra:**
   - Órdenes del equipo "Mercado Libre" (team_id 5)
   - Órdenes del equipo "Mercado Libre Full" (team_id 10)
   - Órdenes del equipo "Mercado Libre Agencia" (team_id 11)

3. **Resultados mostrados:**
   - Columna `equipo_unificado` muestra: "Mercado libre"
   - Columna `equipo_venta_nombre` (en detalle) muestra el equipo específico

4. **Múltiples equipos:**
   - Seleccionar "Mercado libre" + "Amazon"
   - Filtra 5 equipos en total (3 de ML + 2 de Amazon)
   - Agrupa resultados por equipo unificado

---

## Resultados de Prueba

### Ventas de "Mercado libre" (2024-2025)

```
 año  | equipo_unificado | total_ordenes | total_ventas  | ticket_promedio
------+------------------+---------------+---------------+-----------------
 2025 | Mercado libre    |         2,936 | $7,202,939.76 |       $2,453.32
 2024 | Mercado libre    |         1,025 | $2,789,828.30 |       $2,721.78
```

**Esto incluye todas las órdenes de:**
- Mercado Libre
- Mercado Libre Full
- Mercado Libre Agencia

---

## Interpretación de Estados

### Estado de Facturación
- **Facturado:** Orden tiene factura en estado 'posted'
- **No Facturado:** Sin factura válida

### Estado de Pago
- **Pagado:** Orden tiene al menos un pago registrado
- **No Pagado:** Sin pagos registrados

### Estado de Conciliación
- **Conciliado:** Pago conciliado con factura (tiene `reconcile_date`)
- **No Conciliado:** Sin conciliación

### Estado General
- **Orden sin Factura:** No facturada
- **Factura sin Pago:** Facturada pero sin pago
- **Pago sin Conciliar:** Facturada y pagada pero sin conciliar
- **Completo:** Facturada, pagada y conciliada

---

## Ventajas de los Equipos Unificados

✅ **Análisis consolidado:** Agrupa múltiples canales relacionados
✅ **Filtrado inteligente:** Un clic filtra varios equipos
✅ **Flexibilidad:** Selecciona uno o varios equipos unificados
✅ **Claridad:** Visualización simplificada en gráficas
✅ **Detalle disponible:** La tabla de detalle muestra el equipo específico

---

## Próximos Pasos

1. ✅ Importar las 5 consultas a Metabase
2. ✅ Configurar el filtro de equipos unificados
3. ✅ Crear el dashboard con las visualizaciones
4. ✅ Configurar filtros globales
5. ✅ Compartir con el equipo

---

## Tips y Mejores Prácticas

### Rendimiento
- Las consultas usan índices existentes en las tablas
- Los filtros opcionales `[[AND ...]]` no afectan si no se usan
- Usar rangos de fecha específicos mejora el rendimiento

### Visualizaciones Recomendadas

**Para Consulta 1:**
- Tabla con agrupación por fecha y equipo
- Gráfica de barras apiladas (eje X: fecha, series: equipos)

**Para Consulta 2:**
- Tarjetas (cards) para KPIs principales
- Gráfica de barras horizontales (equipos vs ventas)
- Gráfica de dona (distribución por equipo)

**Para Consulta 3:**
- Tabla con todas las columnas
- Habilitar búsqueda y ordenamiento
- Export a CSV/Excel

**Para Consulta 4:**
- Gráfica de líneas múltiples
- Serie 1: Ventas año actual
- Serie 2: Ventas año anterior
- Color diferente por equipo unificado

---

## Troubleshooting

### El filtro de equipos no muestra valores
- Verifica que creaste la "CONSULTA ADICIONAL" primero
- Revisa la configuración del dropdown
- Asegúrate de mapear correctamente Value y Label

### No aparecen datos para ciertos equipos
- Verifica que el equipo tenga relación en `commission_team_unified_crm_team_rel`
- Confirma que las órdenes tienen `team_id` asignado
- Revisa que `commission_team_unified.active = true`

### Las ventas no coinciden con otros reportes
- Verifica el filtro de estados (sale/done)
- Confirma el rango de fechas usado
- Revisa la conversión de zona horaria (America/Mexico_City)

---

## Soporte

Para modificaciones o consultas adicionales, considera:
- Agregar más filtros (cliente, categoría de producto)
- Crear drill-throughs entre consultas
- Agregar métricas calculadas (margen, comisión)
- Integrar con otras tablas (productos, clientes)
