# Guía Rápida de Uso - Account Reconcile Custom Fields

## Instalación

1. Copia el módulo a tu carpeta de addons de Odoo
2. Actualiza la lista de aplicaciones
3. Instala el módulo **Account Reconcile Custom Fields**

## Configuración Inicial

### Paso 1: Crear un Mapeo de Campos

1. Ve a **Contabilidad > Configuración > Custom Field Mappings**
2. Haz clic en **Crear**
3. Completa los campos:

#### Ejemplo Práctico: E-commerce

**Escenario**: Tienes una tienda online que genera órdenes de venta. En cada orden guardas un campo `x_bank_reference` (por ejemplo: "PAY-123456") que le envías al cliente para que lo incluya en la transferencia bancaria.

**Configuración del Mapeo:**

- **Nombre**: "Match by Bank Reference"
- **Secuencia**: 10
- **Activo**: ✓

**Pestaña "Source Configuration":**
- **Source Model**: Sale Order (sale.order)
- **Source Field**: x_bank_reference (debes crear este campo primero)
- **Source Domain Filter**: `[('state', '=', 'sale')]` (solo órdenes confirmadas)

**Pestaña "Target Configuration":**
- **Target Model**: Bank Statement Line (account.bank.statement.line)
- **Target Field**: payment_ref
- **Target Domain Filter**: `[]` (todas las líneas)

**Pestaña "Matching Rules":**
- **Operator**: Equals (=)
- **Match Type**: Exact Match

4. Guarda el mapeo

### Paso 2: Crear Campos Personalizados (si no existen)

Si necesitas crear campos personalizados:

1. Ve a **Configuración > Técnico > Estructura de Base de Datos > Modelos**
2. Busca el modelo (ej: "Sale Order")
3. Haz clic en **Campos**
4. Crea un nuevo campo:
   - **Nombre del campo**: x_bank_reference
   - **Etiqueta de campo**: Bank Reference
   - **Tipo de campo**: Char

## Uso en Conciliación

### Modo Automático (Recomendado)

1. Ve a **Contabilidad > Extractos Bancarios**
2. Abre un extracto bancario
3. Haz clic en cualquier línea para conciliar
4. **El sistema automáticamente** buscará y agregará las facturas que coincidan según tus mapeos
5. Verás un banner informativo: "X custom field mapping(s) available for this line"
6. Revisa las sugerencias y haz clic en **Validate** si todo está correcto

### Modo Manual

1. Abre una línea bancaria para conciliar
2. Haz clic en el botón **"Find Custom Matches"**
3. El sistema buscará todas las coincidencias y las agregará
4. Verás una notificación: "Found X matching line(s)"
5. Revisa y valida la conciliación

## Ejemplos de Configuración

### Ejemplo 1: Match por nombre de orden de venta

```
Nombre: Match Sale Order by Name
Source: Sale Order → name
Operator: like
Target: Bank Statement Line → payment_ref
```

**Caso de uso**: El cliente incluye el número de orden (SO001) en el concepto del pago

### Ejemplo 2: Match por referencia de factura

```
Nombre: Match Invoice by Payment Reference
Source: Invoice (account.move) → payment_reference
Operator: =
Target: Bank Statement Line → payment_ref
```

**Caso de uso**: Las facturas tienen un campo payment_reference que coincide exactamente con lo que viene en el extracto

### Ejemplo 3: Match por orden de compra

```
Nombre: Match Purchase Order
Source: Purchase Order → name
Operator: like
Target: Bank Statement Line → narration
```

**Caso de uso**: Cuando pagas a proveedores, incluyes el número de orden de compra en el concepto

## Flujo de Trabajo Completo

### Escenario: Tienda Online

1. **Cliente hace una orden**
   - Se crea orden de venta SO001
   - Campo x_bank_reference = "REF-12345"
   - Se envía factura al cliente con instrucciones: "Include REF-12345 in your payment"

2. **Cliente paga**
   - Transferencia bancaria con concepto: "Payment REF-12345"

3. **Importas extracto bancario**
   - Línea con payment_ref = "Payment REF-12345"

4. **Conciliación**
   - Abres la línea para conciliar
   - El sistema busca en Sale Orders donde x_bank_reference contenga "REF-12345"
   - Encuentra SO001
   - Obtiene las facturas de SO001
   - Sugiere automáticamente las líneas por cobrar de esas facturas
   - Solo tienes que hacer clic en Validate

## Solución de Problemas

### No aparecen sugerencias

**Verificar:**
1. El mapeo está activo (campo "Active" = ✓)
2. Los campos existen en ambos modelos
3. El valor del campo destino no está vacío
4. El dominio de filtros es correcto
5. Existen facturas sin conciliar que coincidan

### Error de tipos incompatibles

**Solución:**
- Asegúrate de que los tipos de campos sean compatibles
- Char ↔ Char ✓
- Char ↔ Text ✓
- Integer ↔ Float ✓
- Many2one ↔ Integer ✓

### Las facturas no aparecen

**Verificar:**
1. Las órdenes de venta/compra tienen facturas generadas
2. Las facturas están en estado "Posted"
3. Las facturas tienen líneas sin conciliar
4. El filtro de dominio no está excluyendo las facturas

## Ventajas

✓ **Automático**: No necesitas buscar manualmente las facturas
✓ **Flexible**: Configura múltiples mapeos para diferentes casos
✓ **Integrado**: Funciona con la interfaz de conciliación de OCA
✓ **Personalizable**: Usa tus propios campos personalizados
✓ **Eficiente**: Reduce el tiempo de conciliación significativamente

## Preguntas Frecuentes

**P: ¿Puedo tener múltiples mapeos activos?**
R: Sí, el sistema buscará coincidencias usando todos los mapeos activos

**P: ¿Funciona con campos personalizados?**
R: Sí, puedes usar cualquier campo del modelo, incluyendo campos personalizados (x_)

**P: ¿Puedo usarlo para pagos además de extractos bancarios?**
R: Sí, selecciona "Payment" como Target Model

**P: ¿Qué pasa si encuentra múltiples facturas?**
R: El sistema agregará todas las facturas que coincidan, hasta completar el monto de la línea bancaria

**P: ¿Puedo desactivar temporalmente un mapeo?**
R: Sí, desmarca el campo "Active" en el mapeo
