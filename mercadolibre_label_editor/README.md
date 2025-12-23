# MercadoLibre Label Editor

Módulo de Odoo 16 que permite personalizar etiquetas de envío de MercadoLibre agregando información adicional como número de orden, datos del cliente, etc.

## Características

- ✅ **Editor de Plantillas**: Crea plantillas reutilizables para diferentes tipos logísticos
- ✅ **Campos Dinámicos**: Usa variables como `${sale_order.name}` para datos en tiempo real
- ✅ **Configuración Visual**: Posiciona campos con coordenadas X,Y en píxeles
- ✅ **Estilos Personalizados**: Configura fuente, tamaño, color y rotación
- ✅ **Integración Automática**: Se aplica al descargar etiquetas de MercadoLibre
- ✅ **Vista Previa**: Genera PDFs de prueba con datos de ejemplo
- ✅ **Multi-empresa**: Soporte completo para multi-compañía

## Instalación

### Dependencias Python

```bash
pip3 install PyPDF2 reportlab pdf2image
```

**Nota**: `pdf2image` requiere poppler-utils:
```bash
# Ubuntu/Debian
sudo apt-get install poppler-utils

# macOS
brew install poppler
```

### Instalar módulo

1. Copia el módulo a tu carpeta de addons
2. Actualiza la lista de aplicaciones
3. Instala "MercadoLibre Label Editor"

## Uso

### 1. Crear Plantilla

1. Ve a **MercadoLibre > Configuración > Plantillas de Etiqueta**
2. Click en **Crear**
3. Sube un PDF de ejemplo (descarga una etiqueta ML real)
4. Agrega campos en la pestaña **Campos de Texto**:
   - **Nombre**: Descripción del campo
   - **Tipo**: Estático o Dinámico
   - **Valor**: Texto fijo o variable `${...}`
   - **Posición X,Y**: Coordenadas en píxeles
   - **Estilo**: Fuente, tamaño, color, rotación

### 2. Asignar a Tipo Logístico

1. Ve a **MercadoLibre > Configuración > Tipos Logísticos**
2. Edita el tipo logístico (ej: Full ML)
3. En **Automatización > Etiquetas de Envio ML**:
   - Activa **Descargar Etiqueta ML**
   - Selecciona tu **Plantilla Etiqueta**
4. Guarda

### 3. Uso Automático

Cuando llegue una orden ML:
1. El sistema sincroniza la orden
2. Crea la sale.order en Odoo
3. Descarga la etiqueta de MercadoLibre
4. **Aplica automáticamente la plantilla configurada**
5. Guarda el PDF personalizado como adjunto

### 4. Regenerar Manual

Para órdenes ya sincronizadas:
1. Abre la orden de MercadoLibre
2. Click en **Regenerar con Plantilla**

## Variables Disponibles

### Orden de Venta
- `${sale_order.name}` - Número de orden (SO001)
- `${sale_order.partner_id.name}` - Nombre del cliente
- `${sale_order.partner_id.phone}` - Teléfono
- `${sale_order.date_order}` - Fecha de orden
- `${sale_order.amount_total}` - Total
- `${sale_order.warehouse_id.name}` - Almacén

### Orden MercadoLibre
- `${ml_order.ml_order_id}` - ID orden ML
- `${ml_order.ml_pack_id}` - Pack ID
- `${ml_order.ml_shipment_id}` - Shipment ID
- `${ml_order.logistic_type}` - Tipo logístico

### Especiales
- `${today}` - Fecha de hoy (YYYY-MM-DD)
- `${now}` - Fecha y hora actual
- `${company.name}` - Nombre de la compañía

## Ejemplos de Configuración

### Campo: Número de Orden
```
Nombre: Número de Orden
Tipo: Dinámico
Valor: ${sale_order.name}
Posición X: 50
Posición Y: 30
Fuente: Helvetica-Bold
Tamaño: 16
Color: #000000
Rotación: 0
```

### Campo: Cliente con Rotación
```
Nombre: Cliente Diagonal
Tipo: Dinámico
Valor: ${sale_order.partner_id.name}
Posición X: 400
Posición Y: 200
Fuente: Helvetica
Tamaño: 14
Color: #FF0000
Rotación: 45
```

### Campo: Texto Estático
```
Nombre: Sello
Tipo: Estático
Valor: PROCESADO
Posición X: 300
Posición Y: 500
Fuente: Helvetica-Bold
Tamaño: 20
Color: #FF0000
Rotación: -15
```

## Coordenadas

- **Origen**: Esquina superior izquierda (0, 0)
- **Unidad**: Píxeles
- **Eje X**: Aumenta hacia la derecha
- **Eje Y**: Aumenta hacia abajo
- **Rotación**: Grados en sentido antihorario (0-360)

## Troubleshooting

### El PDF no se procesa

**Solución**: Verifica que PyPDF2 y reportlab estén instalados:
```bash
pip3 list | grep -E "PyPDF2|reportlab"
```

### Las coordenadas no coinciden

**Problema**: El PDF de ejemplo tiene diferentes dimensiones.

**Solución**: Las coordenadas se calculan asumiendo 150 DPI. Si la etiqueta real es diferente, ajusta las posiciones manualmente.

### La plantilla no se aplica

**Verificar**:
1. El tipo logístico tiene `download_shipping_label = True`
2. Hay una plantilla asignada en `label_template_id`
3. La plantilla tiene campos activos
4. El PDF de ejemplo está cargado

### Error al generar preview

**Solución**: Instala pdf2image y poppler:
```bash
pip3 install pdf2image
sudo apt-get install poppler-utils  # Linux
```

## Arquitectura Técnica

### Modelos

- **ml.label.template**: Plantilla de etiqueta
- **ml.label.template.field**: Campo de texto en plantilla
- **ml.label.processor**: Motor de procesamiento (AbstractModel)

### Extends

- **mercadolibre.logistic.type**: +3 campos (label_template_id, etc.)
- **mercadolibre.order**: Hook en `_download_and_save_shipping_label()`

### Flujo de Procesamiento

```
1. MercadoLibre Order sincronizada
   ↓
2. _download_and_save_shipping_label()
   ↓
3. Descarga PDF original de ML API
   ↓
4. ¿Hay plantilla configurada?
   ↓ (Sí)
5. ml.label.processor.apply_template()
   ↓
6. PyPDF2 lee PDF original
   ↓
7. ReportLab crea overlay con textos
   ↓
8. Combina PDFs
   ↓
9. Guarda como adjunto en sale.order
```

## Seguridad

- **Usuario de Etiquetas ML**: Solo lectura
- **Administrador de Etiquetas ML**: Crear/editar plantillas
- **Multi-empresa**: Las plantillas respetan company_id

## Soporte

Para reportar bugs o sugerir mejoras, contacta al equipo de desarrollo.

## Licencia

LGPL-3

## Autor

Tu Empresa - 2024
