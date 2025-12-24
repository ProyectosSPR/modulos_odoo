# Sale Order Invoice Payment Info & Commission System

## Descripción

Este módulo extiende la funcionalidad de Órdenes de Venta en Odoo 16 para proporcionar información detallada sobre las facturas relacionadas, los pagos aplicados a dichas facturas, y un completo sistema de cálculo de comisiones para vendedores.

## Características

### Información de Facturas
- Número de factura
- Fecha de factura
- Cliente facturado
- Importe total de la factura
- Importe pendiente
- Estado de la factura
- Estado de pago
- Líneas de producto de cada factura

### Información de Pagos
- Nombre del pago
- Referencia del pago
- Fecha del pago
- Monto del pago
- Fecha de creación del pago
- Fecha de conciliación

### Sistema de Comisiones

#### 1. Equipos Unificados
- Agrupación de múltiples equipos de ventas bajo un mismo nombre
- Ejemplo: "Mercado Libre" puede incluir "ML Full", "ML Agencia", etc.
- Asignación de porcentaje de comisión por equipo unificado
- Gestión flexible de equipos

#### 2. Reglas de Alcance vs Recompensa
- Configuración dinámica de reglas
- Ejemplos:
  - 100% de alcance de meta → 100% de recompensa
  - 90% de alcance de meta → 70% de recompensa
  - 80% de alcance de meta → 50% de recompensa
- Totalmente personalizable según necesidades del negocio

#### 3. Metas de Ventas
- Configuración de metas mensuales por vendedor
- Opción de meta general (sin vendedor específico)
- Gestión por periodo (mes/año)
- Montos en la moneda de la compañía

#### 4. Cálculo de Comisiones
- Cálculo automático basado en ventas marcadas como pagadas
- Selección de base de cálculo: Subtotal o Total (con/sin impuestos)
- Fórmula: `Comisión = Total Vendido × (% Comisión / 100) × (% Recompensa / 100)`
- Flujo de estados: Borrador → Confirmado → Pagado
- Visualización de órdenes de venta relacionadas
- Reportes analíticos (pivot, gráficos)

#### 5. Histórico de Comisiones
- Vista de comisiones pagadas por mes
- Filtros por vendedor, periodo, equipo
- Análisis de tendencias
- Reportes agrupados

## Instalación

1. Copiar el módulo en la carpeta de addons de Odoo
2. Actualizar la lista de aplicaciones
3. Buscar "Sale Order Invoice Payment Info"
4. Instalar el módulo

## Uso

### Información de Facturas y Pagos

1. Ir a Ventas > Órdenes > Órdenes de venta
2. Abrir cualquier orden de venta que tenga facturas asociadas
3. Navegar a la pestaña "Facturas y Pagos"
4. Visualizar toda la información de facturas y pagos en una tabla organizada

### Sistema de Comisiones

#### Configuración Inicial

1. **Configurar Equipos Unificados:**
   - Ir a: Comisiones de Vendedores > Configuración > Equipos Unificados
   - Crear un nuevo equipo unificado (ej: "Mercado Libre")
   - Seleccionar los equipos de ventas que pertenecen a este grupo
   - Establecer el porcentaje de comisión (ej: 0.5%)

2. **Configurar Reglas de Alcance:**
   - Ir a: Comisiones de Vendedores > Configuración > Reglas de Alcance
   - Crear las reglas necesarias:
     - 100% alcance → 100% recompensa
     - 90% alcance → 70% recompensa
     - 80% alcance → 50% recompensa
     - etc.

3. **Configurar Metas:**
   - Ir a: Comisiones de Vendedores > Configuración > Metas de Ventas
   - Crear metas mensuales:
     - Seleccionar mes y año
     - Seleccionar vendedor (opcional, dejar vacío para meta general)
     - Establecer el monto de la meta en pesos

#### Proceso de Comisiones

1. **Marcar Ventas como Pagadas:**
   - Ir a la orden de venta
   - Hacer clic en "Marcar Comisión Pagada"
   - Se registrará la fecha de comisión pagada

2. **Calcular Comisiones:**
   - Ir a: Comisiones de Vendedores > Cálculo de Comisiones
   - Crear nuevo registro
   - Seleccionar periodo (mes/año) y vendedor
   - Elegir base de cálculo (Subtotal o Total)
   - El sistema calculará automáticamente:
     - Total vendido (de órdenes marcadas como pagadas)
     - % de alcance de meta
     - % de recompensa (según reglas)
     - % de comisión del equipo
     - Monto final de comisión

3. **Confirmar y Pagar:**
   - Revisar el cálculo
   - Hacer clic en "Confirmar"
   - Cuando se pague, hacer clic en "Marcar como Pagado"

4. **Ver Histórico:**
   - Ir a: Comisiones de Vendedores > Comisiones Pagadas
   - Ver todas las comisiones pagadas agrupadas por vendedor, mes, etc.

## Estructura del Módulo

```
sale_order_invoice_payment_info/
├── __init__.py
├── __manifest__.py
├── README.md
├── models/
│   ├── __init__.py
│   ├── sale_order.py
│   └── commission.py
├── views/
│   ├── sale_order_views.xml
│   ├── commission_views.xml
│   └── commission_menus.xml
└── security/
    └── ir.model.access.csv
```

## Modelos

### sale.order (heredado)
- `invoice_payment_info_ids`: One2many hacia la información de facturas y pagos
- `invoice_payment_count`: Contador de registros
- `commission_paid`: Boolean para marcar si la comisión fue pagada
- `commission_paid_date`: Fecha de pago de comisión
- `action_mark_commission_paid()`: Marca la comisión como pagada
- `action_unmark_commission_paid()`: Desmarca la comisión

### sale.order.invoice.payment.info (nuevo)
Modelo transitorio que almacena temporalmente la información combinada de facturas y pagos.

### commission.team.unified (nuevo)
Equipos de ventas unificados con porcentaje de comisión asignado.

### commission.goal.rule (nuevo)
Reglas configurables de alcance de meta vs porcentaje de recompensa.

### commission.goal (nuevo)
Metas de ventas por vendedor y periodo.

### commission.calculation (nuevo)
Cálculo de comisiones con toda la lógica de negocio y flujo de estados.

## Dependencias

- sale
- account
- sales_team

## Compatibilidad

- Odoo 16.0

## Autor

Tu Empresa

## Sistema de Proyecciones y Reportes

### Descripción

El sistema de proyecciones permite planificar las ventas esperadas por equipo de ventas y mes, creando múltiples versiones editables que el director de finanzas puede modificar constantemente. Además, proporciona reportes por cuatrimestre que comparan los objetivos, estimados y ventas reales.

### Características Principales

1. **Proyecciones de Ventas**
   - Crear múltiples versiones de proyecciones por año
   - Proyecciones mensuales por equipo de ventas unificado
   - Cálculo automático de temporalidad (comparación con proyección anterior)
   - Estados: Borrador, Activa, Cerrada

2. **Reportes por Cuatrimestre**
   - Vista por cuatrimestre (Q1: Ene-Abr, Q2: May-Ago, Q3: Sep-Dic)
   - Desglose mensual dentro de cada cuatrimestre
   - Comparación de:
     - **Objetivo Cuatrimestre**: Suma de metas mensuales configuradas
     - **Estimado**: Monto proyectado en la proyección activa
     - **Venta**: Ventas reales del periodo (órdenes pagadas)
     - **Diferencia**: Venta - Estimado
     - **% Objetivo**: Venta / Objetivo Cuatrimestre × 100
     - **% Estimado**: Venta / Estimado × 100

3. **Análisis y Reportes**
   - Vistas pivot para análisis multidimensional
   - Gráficas de tendencias y comparativas
   - Filtros por año, cuatrimestre, mes y equipo
   - Exportación a Excel/PDF

### Uso del Sistema de Proyecciones

#### Crear una Proyección

1. **Ir a: Comisiones > Proyecciones y Reportes > Proyecciones de Ventas**
2. Hacer clic en "Crear"
3. Llenar los datos:
   - **Nombre**: Ej: "Proyección 2025 v1"
   - **Año**: Año de la proyección
   - **Proyección Anterior**: (Opcional) Seleccionar una proyección anterior para calcular temporalidad
4. En la pestaña "Proyecciones Mensuales":
   - Agregar líneas para cada mes y equipo
   - Seleccionar el **Mes**
   - Seleccionar el **Equipo Unificado** (Mercado Libre, Amazon, Meta, etc.)
   - Ingresar el **Monto Proyectado**
   - El sistema calcula automáticamente el **Cuatrimestre**
5. Hacer clic en "Activar" para que la proyección esté disponible en los reportes

**Nota**: Solo puede haber una proyección activa por año a la vez.

#### Ver Análisis de Proyecciones

1. **Ir a: Comisiones > Proyecciones y Reportes > Análisis de Proyecciones**
2. Usar la vista pivot para analizar:
   - Proyecciones por equipo y mes
   - Totales por cuatrimestre
   - Comparaciones entre equipos

#### Ver Reporte por Cuatrimestre

1. **Ir a: Comisiones > Proyecciones y Reportes > Reporte por Cuatrimestre**
2. El sistema muestra automáticamente:
   - Datos de la proyección activa
   - Ventas reales calculadas del periodo
   - Métricas de diferencia y porcentajes
3. Usar filtros para:
   - Filtrar por cuatrimestre (Q1, Q2, Q3)
   - Ver solo el año actual
   - Agrupar por equipo, mes o cuatrimestre
4. Cambiar entre vistas:
   - **Tree**: Vista de tabla con todas las métricas
   - **Pivot**: Análisis multidimensional
   - **Graph**: Visualización gráfica de tendencias

### Flujo de Trabajo Completo

1. **Configuración Inicial**:
   - Configurar equipos unificados (si no existen)
   - Configurar metas mensuales por equipo

2. **Crear Proyección**:
   - El director de finanzas crea una nueva proyección
   - Llena los montos proyectados para cada mes y equipo
   - Activa la proyección

3. **Monitorear Avance**:
   - A medida que se registran ventas y se marcan como pagadas
   - El reporte por cuatrimestre se actualiza automáticamente
   - Comparar ventas reales vs proyecciones vs objetivos

4. **Ajustar Proyecciones**:
   - Crear una nueva versión de la proyección
   - Modificar los montos proyectados
   - Activar la nueva versión
   - El sistema calcula automáticamente la temporalidad (% de cambio)

### Campos Calculados Automáticamente

- **Total Proyectado**: Suma de todas las proyecciones mensuales
- **Temporalidad**: Porcentaje del total proyectado respecto a la proyección anterior
- **Cuatrimestre**: Se calcula automáticamente según el mes (1-4=Q1, 5-8=Q2, 9-12=Q3)
- **Ventas Reales**: Se calculan desde las órdenes de venta con `payment_valid_date` en el periodo
- **Diferencia**: Venta Real - Monto Proyectado
- **% Objetivo**: (Venta Real / Objetivo Cuatrimestre) × 100
- **% Estimado**: (Venta Real / Monto Proyectado) × 100

### Notas Importantes

- Solo puede haber una proyección **activa** por año
- Las proyecciones en estado "Cerrada" quedan como histórico
- Las ventas reales se calculan basándose en la fecha de pago real de las facturas (`payment_valid_date`)
- El objetivo del cuatrimestre se calcula sumando las metas mensuales configuradas para ese periodo
- La temporalidad permite ver qué tan ambiciosa es una proyección comparada con la anterior

### Ejemplo de Uso

**Escenario**: Director de finanzas quiere proyectar ventas para 2025

1. Crea "Proyección 2025 v1"
2. Agrega líneas para cada equipo y mes:
   - Mercado Libre - Enero: $330,000
   - Mercado Libre - Febrero: $400,000
   - Amazon - Mayo: $2,000
   - Meta - Enero: $120,000
   - etc.
3. Activa la proyección
4. Cada mes, revisa el "Reporte por Cuatrimestre" para ver:
   - ¿Vamos cumpliendo con el objetivo?
   - ¿Las ventas reales coinciden con lo proyectado?
   - ¿Necesitamos ajustar las proyecciones?
5. Si necesita ajustar, crea "Proyección 2025 v2" con los nuevos valores

## Licencia

LGPL-3
