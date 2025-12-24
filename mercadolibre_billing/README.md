# MercadoLibre Billing - Módulo de Facturación

## Descripción

Módulo Odoo 16 para sincronizar las facturas y comisiones de **MercadoLibre (ML)** y **MercadoPago (MP)** con Odoo, creando automáticamente órdenes de compra y facturas de proveedor.

## Características Principales

### ✅ Sincronización de Facturación
- Descarga facturas y notas de crédito desde ML y MP
- Soporte para ambos grupos (ML/MP) en el mismo módulo
- Sincronización manual y automática vía cron
- Paginación inteligente para grandes volúmenes de datos
- Sistema de logs robusto integrado con mercadolibre.log

### ✅ Gestión de Periodos
- Organización por periodos mensuales (period_key)
- Estados: draft → syncing → synced → processed
- Contadores de facturas y notas de crédito
- Totales automáticos por periodo

### ✅ Creación Automática de POs
- Una Purchase Order por cada detalle (máxima granularidad)
- Soporte para notas de crédito (líneas negativas)
- Configuración flexible: confirmar POs automáticamente o manual
- Relación con periodos de facturación

### ✅ Diferencias ML vs MP

**MercadoLibre (ML)**:
- Endpoint: `.../group/ML/details`
- Campos específicos:
  - `sales_info`: order_id, operation_id
  - `shipping_info`: shipping_id, pack_id, receiver_shipping_cost
  - `items_info[]`: información de productos
  - `discount_info`: descuentos

**MercadoPago (MP)**:
- Endpoint: `.../group/MP/details`
- Campos específicos:
  - `operation_info`: reference_id, store_id, store_name
  - `movement_id`: en lugar de operation_id
  - `perception_info`: taxable_amount, aliquot

## Estructura del Módulo

```
mercadolibre_billing/
├── models/
│   ├── mercadolibre_billing_period.py      # Periodos mensuales
│   ├── mercadolibre_billing_detail.py      # Detalles de facturación (ML y MP)
│   ├── mercadolibre_billing_sync_config.py # Configuración de sincronización
│   ├── purchase_order.py                   # Herencia de purchase.order
│   └── account_move.py                     # Herencia de account.move
├── wizard/
│   └── mercadolibre_billing_sync.py        # Wizard de sincronización manual
├── views/
│   ├── mercadolibre_billing_period_views.xml
│   ├── mercadolibre_billing_detail_views.xml
│   ├── mercadolibre_billing_sync_config_views.xml
│   ├── purchase_order_views.xml
│   ├── account_move_views.xml
│   └── mercadolibre_billing_menus.xml
├── data/
│   ├── product_data.xml                    # Productos de comisión
│   └── mercadolibre_billing_cron.xml       # Cron de sincronización
├── security/
│   ├── ir.model.access.csv
│   └── mercadolibre_billing_rules.xml
└── __manifest__.py
```

## Instalación

1. Copiar el módulo en la carpeta de addons
2. Actualizar lista de módulos en Odoo
3. Instalar el módulo "MercadoLibre Billing"

## Configuración

### 1. Crear Configuración de Sincronización

Ir a: **MercadoLibre > Facturación ML/MP > Configuración**

- Seleccionar cuenta ML/MP
- Elegir grupo: ML, MP o Ambos
- Configurar sincronización automática (opcional)
- Establecer producto de comisiones
- Configurar opciones de POs automáticas

### 2. Sincronización Manual

Ir a: **MercadoLibre > Facturación ML/MP > Sincronizar**

- Seleccionar cuenta
- Definir rango de fechas (desde/hasta)
- Elegir grupo (ML/MP/Ambos)
- Opciones de creación automática de POs

### 3. Sincronización Automática

La sincronización automática se ejecuta cada 6 horas (configurable) y procesa:
- Los últimos N meses configurados (default: 3)
- Solo periodos en estado draft o error
- Crea POs automáticamente si está configurado

## Flujo de Trabajo

1. **Sincronización**: 
   - Se crean periodos (ej: ML - Enero 2025)
   - Se descargan detalles de facturación vía API
   - Estado cambia a 'synced'

2. **Creación de POs**:
   - Desde el periodo: botón "Crear Órdenes de Compra"
   - O automático si está configurado
   - Una PO por cada detalle individual
   - Estado del detalle cambia a 'purchase_created'

3. **Facturación**:
   - Confirmar POs manualmente o automático
   - Crear facturas de proveedor desde POs
   - Estado del detalle cambia a 'invoiced'

## API Endpoints Utilizados

### MercadoLibre
```
GET https://api.mercadolibre.com/billing/integration/periods/key/{period_key}/group/ML/details
```

### MercadoPago
```
GET https://api.mercadolibre.com/billing/integration/periods/key/{period_key}/group/MP/details
```

**Parámetros**:
- `document_type`: BILL (facturas)
- `limit`: Límite por página (default: 50, máx: 1000)
- `offset`: Desplazamiento para paginación (máx: 10000)

## Modelos de Datos

### mercadolibre.billing.period
- `period_key`: Primer día del mes (2025-01-01)
- `billing_group`: ML o MP
- `state`: draft/syncing/synced/processed/error
- `detail_ids`: Relación con detalles
- `total_charges`, `total_credit_notes`, `net_amount`

### mercadolibre.billing.detail
- `ml_detail_id`: ID único del cargo (UNIQUE)
- `billing_group`: ML o MP
- `is_credit_note`: Calculado desde charge_bonified_id
- Campos ML: sales_info, shipping_info, items_info, discount_info
- Campos MP: operation_info, perception_info
- `purchase_order_id`, `invoice_id`: Relaciones

### mercadolibre.billing.sync.config
- `billing_group`: ML, MP o both
- `auto_sync`: Activar cron
- `auto_create_purchase_orders`
- `auto_validate_purchase_orders`
- `commission_product_id`

## Menús

- **Periodos de Facturación**: Ver/gestionar periodos mensuales
- **Detalles de Facturación**: Ver todos los detalles individuales
- **Sincronizar**: Wizard de sincronización manual
- **Configuración**: Configuraciones de sincronización automática

## Dependencias

- `mercadolibre_connector`: Sistema de autenticación y tokens
- `purchase`: Órdenes de compra
- `account`: Facturación
- `mail`: Tracking y notificaciones

## Notas Técnicas

- **Paginación**: Maneja automáticamente la paginación de la API (campo `display`)
- **Reintentos**: Sistema de reintentos en caso de error 401 (token expirado)
- **Logging**: Todas las llamadas API se registran en mercadolibre.log
- **Multi-compañía**: Soporte completo con record rules
- **Constraint**: period_key + account_id + billing_group debe ser único

## Soporte

Para reportar problemas o sugerencias, contactar al equipo de desarrollo.
