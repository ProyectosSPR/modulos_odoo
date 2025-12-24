# RESUMEN DE CAMBIOS - Módulo MercadoLibre Billing

## Fecha: 2024-12-24
## Versión: 16.0.2.0.0

---

## OBJETIVO

Mejorar el módulo de facturación de MercadoLibre/MercadoPago implementando la lógica del flujo n8n que:
1. Agrupa detalles por documento legal
2. Crea múltiples POs (una por detalle)
3. Genera UNA factura de proveedor agrupando todas las POs del mismo documento legal
4. Descarga y adjunta el PDF de la factura desde MercadoLibre
5. Aplica IVA correctamente
6. Valida duplicados antes de crear facturas

---

## CAMBIOS IMPLEMENTADOS

### 1. **Nuevos Campos en `mercadolibre.billing.sync.config`**

#### Campos de Facturación:
- `auto_post_invoices`: Publicar facturas automáticamente
- `group_invoices_by_legal_document`: Agrupar facturas por documento legal (default: True)
- `skip_if_invoice_exists`: Omitir si ya existe factura con el mismo número legal
- `attach_ml_pdf`: Descargar y adjuntar PDF de MercadoLibre

#### Campos Contables:
- `purchase_tax_id`: Impuesto de compra a aplicar (ej: IVA 16%)

**Ubicación:** [mercadolibre_billing_sync_config.py:82-124](mercadolibre_billing/models/mercadolibre_billing_sync_config.py)

---

### 2. **Actualización de `mercadolibre.billing.detail`**

#### Cambios en `action_create_purchase_order()`:

**A. Partner Ref con Trazabilidad:**
```python
# Incluye: Factura + (Ref MP o Orden ML)
partner_ref = "Fact: A001-123 | Ref: 123456789"
```

**B. Aplicación de Impuestos:**
```python
if config.purchase_tax_id:
    po_line_vals['taxes_id'] = [(6, 0, [config.purchase_tax_id.id])]
```

**Ubicación:** [mercadolibre_billing_detail.py:527-622](mercadolibre_billing/models/mercadolibre_billing_detail.py)

---

### 3. **Nuevos Campos en `mercadolibre.billing.invoice`**

#### Campos para PDF:
- `ml_pdf_file_id`: ID del archivo PDF en MercadoLibre
- `ml_pdf_attachment_id`: Adjunto del PDF descargado

**Ubicación:** [mercadolibre_billing_invoice.py:106-115](mercadolibre_billing/models/mercadolibre_billing_invoice.py)

---

### 4. **Método Principal: `action_create_grouped_invoice()`**

**Ubicación:** `mercadolibre.billing.invoice`

#### Flujo:
```
1. Validar que todos los detalles tengan PO creada
2. Validar que todas las POs estén confirmadas
3. Verificar si ya existe factura con el mismo ref (si skip_if_invoice_exists=True)
4. Crear factura de proveedor agrupando todas las POs
5. Agregar líneas desde cada PO
6. Aplicar impuestos desde las líneas de PO
7. Agregar línea de nota con información del documento legal
8. Recalcular impuestos
9. Publicar automáticamente (si auto_post_invoices=True)
10. Descargar y adjuntar PDF (si attach_ml_pdf=True)
```

**Ubicación:** [mercadolibre_billing_invoice.py:154-244](mercadolibre_billing/models/mercadolibre_billing_invoice.py)

---

### 5. **Descarga de PDFs desde MercadoLibre**

#### Método: `_download_and_attach_pdf()`

**Endpoint:**
```
GET https://api.mercadolibre.com/billing/integration/legal_document/{file_id}
```

**Proceso:**
1. Obtener token OAuth válido
2. Descargar PDF desde API de ML
3. Convertir a base64
4. Crear adjunto en `ir.attachment`
5. Vincular con factura de proveedor

**Ubicación:** [mercadolibre_billing_invoice.py:310-359](mercadolibre_billing/models/mercadolibre_billing_invoice.py)

---

### 6. **Captura de `file_id` del PDF**

Actualizado el método `_get_or_create_invoice_group()` para extraer el `file_id` del PDF desde:
```json
{
  "document_info": {
    "legal_document_files": [
      {
        "file_id": "abc123xyz"
      }
    ]
  }
}
```

**Ubicación:** [mercadolibre_billing_detail.py:386-428](mercadolibre_billing/models/mercadolibre_billing_detail.py)

---

### 7. **Método en Periodo: `action_create_grouped_invoices()`**

**Ubicación:** `mercadolibre.billing.period`

#### Funcionalidad:
- Procesa TODOS los `invoice_groups` del periodo
- Valida que cada grupo tenga:
  - Todas las POs creadas
  - Todas las POs confirmadas
- Crea factura agrupada para cada documento legal
- Omite duplicados si ya existe factura
- Reporta errores sin detener el proceso

**Ubicación:** [mercadolibre_billing_period.py:445-564](mercadolibre_billing/models/mercadolibre_billing_period.py)

---

### 8. **Integración con Sincronización Automática**

Actualizado `_execute_sync()` en config para ejecutar creación de facturas:

```python
if self.auto_create_invoices:
    period.action_create_grouped_invoices()
```

**Ubicación:** [mercadolibre_billing_sync_config.py:227-238](mercadolibre_billing/models/mercadolibre_billing_sync_config.py)

---

### 9. **Vistas Actualizadas**

#### A. Vista de Configuración
- Nuevos grupos: "Configuración de Facturación"
- Campos agregados: `auto_post_invoices`, `skip_if_invoice_exists`, `attach_ml_pdf`, `purchase_tax_id`

**Ubicación:** [mercadolibre_billing_sync_config_views.xml:51-78](mercadolibre_billing/views/mercadolibre_billing_sync_config_views.xml)

#### B. Vista de Periodo
- Nuevo botón: "Crear Facturas Agrupadas"

**Ubicación:** [mercadolibre_billing_period_views.xml:36-38](mercadolibre_billing/views/mercadolibre_billing_period_views.xml)

#### C. Nueva Vista de Invoice
- Vista tree/form completa para `mercadolibre.billing.invoice`
- Botón: "Crear Factura de Proveedor"
- Campos para PDF adjunto

**Ubicación:** [mercadolibre_billing_invoice_views.xml](mercadolibre_billing/views/mercadolibre_billing_invoice_views.xml)

#### D. Nuevo Menú
- "Facturas ML/MP" (sequence: 15)

**Ubicación:** [mercadolibre_billing_menus.xml:16-21](mercadolibre_billing/views/mercadolibre_billing_menus.xml)

---

## FLUJO COMPLETO IMPLEMENTADO

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. SINCRONIZACIÓN                                               │
│    - Descarga detalles desde API ML/MP                          │
│    - Agrupa por documento legal (mercadolibre.billing.invoice)  │
│    - Extrae file_id del PDF                                     │
└────────────────────────┬────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. CREACIÓN DE ÓRDENES DE COMPRA                                │
│    Por cada detalle:                                            │
│    - Crea 1 PO individual                                       │
│    - Partner Ref: "Fact: XXX | Ref/Orden: YYY"                  │
│    - Aplica impuesto configurado (purchase_tax_id)              │
│    - Confirma automáticamente (si auto_validate=True)           │
└────────────────────────┬────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. VALIDACIÓN DE DUPLICADOS (opcional)                          │
│    - Busca factura existente con mismo ref                     │
│    - Si existe y skip_if_invoice_exists=True → Omite           │
└────────────────────────┬────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. CREACIÓN DE FACTURA AGRUPADA                                 │
│    - Agrupa todas las POs del mismo documento legal            │
│    - Crea account.move con:                                     │
│      • ref = legal_document_number                             │
│      • Líneas desde todas las POs                              │
│      • Impuestos aplicados desde PO lines                      │
│      • Línea de nota con origen                                │
│    - Recalcula impuestos                                        │
│    - Publica (si auto_post_invoices=True)                      │
└────────────────────────┬────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. DESCARGA DE PDF (opcional)                                   │
│    - GET /billing/integration/legal_document/{file_id}         │
│    - Convierte a base64                                         │
│    - Adjunta a la factura                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## DIFERENCIAS CON FLUJO N8N

| Aspecto | Flujo n8n | Módulo Odoo Mejorado |
|---------|-----------|----------------------|
| **Base de datos externa** | PostgreSQL (mp_billing_details) | Odoo nativo (mercadolibre.billing.detail) |
| **Validación duplicados** | Tabla ordenes_compra_ml | Campo ref en account.move |
| **Mapeo productos** | Tabla meli_transaction_mapping | Configuración global (commission_product_id) |
| **Agrupación** | SQL + Loop manual | Modelo mercadolibre.billing.invoice |
| **IVA** | Hardcoded 16% | Configurable (purchase_tax_id) |
| **PDF** | Consulta tabla externa | Almacenado en invoice_group |
| **Automatización** | Cron n8n | Cron Odoo + wizard manual |

---

## CONFIGURACIÓN RECOMENDADA

### Paso 1: Configurar Impuesto
1. Ir a: Contabilidad > Configuración > Impuestos
2. Buscar: IVA 16% Compras
3. Copiar ID del impuesto

### Paso 2: Configurar Sincronización
1. Ir a: MercadoLibre > Facturación ML/MP > Configuración
2. Crear/editar configuración:
   - **Cuenta ML/MP:** Seleccionar
   - **Grupo:** ML/MP/Ambos
   - **Auto sincronizar:** ✓
   - **Auto crear POs:** ✓
   - **Auto confirmar POs:** ✓
   - **Auto crear facturas:** ✓
   - **Publicar automáticamente:** ⚠️ (validar primero)
   - **Omitir duplicados:** ✓
   - **Adjuntar PDF:** ✓
   - **Producto comisión:** Seleccionar
   - **Impuesto compra:** IVA 16%
   - **Cuenta gastos:** Seleccionar
   - **Diario:** Compras

### Paso 3: Ejecutar Sincronización
1. Ir a: MercadoLibre > Facturación ML/MP > Sincronizar
2. Seleccionar fechas y ejecutar
3. Monitorear en: Periodos de Facturación

---

## VENTAJAS DE LA IMPLEMENTACIÓN

✅ **Trazabilidad completa:** partner_ref incluye toda la info
✅ **Sin tablas externas:** Todo en Odoo nativo
✅ **Flexible:** Configuración por cliente
✅ **Robusto:** Validaciones y manejo de errores
✅ **Auditable:** Logs y chatter en todos los modelos
✅ **Escalable:** Procesa lotes grandes sin fallar
✅ **PDF automático:** Descarga directa desde ML

---

## PRÓXIMOS PASOS (OPCIONALES)

1. **Mapeo de productos:** Tabla para mapear transaction_detail → product_id
2. **Reportes:** Dashboard de comisiones ML/MP
3. **Notificaciones:** Alertas por email cuando hay facturas pendientes
4. **Reconciliación:** Auto-reconciliar con pagos de ML/MP

---

## ARCHIVOS MODIFICADOS

```
mercadolibre_billing/
├── models/
│   ├── mercadolibre_billing_sync_config.py     [MODIFICADO]
│   ├── mercadolibre_billing_detail.py          [MODIFICADO]
│   ├── mercadolibre_billing_invoice.py         [MODIFICADO]
│   └── mercadolibre_billing_period.py          [MODIFICADO]
├── views/
│   ├── mercadolibre_billing_sync_config_views.xml  [MODIFICADO]
│   ├── mercadolibre_billing_period_views.xml       [MODIFICADO]
│   ├── mercadolibre_billing_invoice_views.xml      [NUEVO]
│   └── mercadolibre_billing_menus.xml              [MODIFICADO]
├── __manifest__.py                              [MODIFICADO]
└── RESUMEN_CAMBIOS.md                          [NUEVO]
```

---

## NOTAS TÉCNICAS

### Manejo de Transacciones
- Cada detalle se procesa en un `savepoint()`
- Errores individuales no detienen el proceso completo
- Logs detallados en `mercadolibre.log`

### Seguridad
- Record rules por compañía
- Permisos heredados de `mercadolibre_connector`
- Tokens OAuth manejados con `sudo()`

### Performance
- Paginación de 50 registros en API
- Procesamiento por lotes
- Commits periódicos en sync

---

## CONTACTO

Para soporte o preguntas sobre esta implementación, contactar al equipo de desarrollo.
