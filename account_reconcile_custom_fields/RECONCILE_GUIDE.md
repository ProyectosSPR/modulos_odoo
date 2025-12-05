# Guía de Conciliación con Filtros Personalizados

## Descripción

Este módulo agrega una nueva forma de conciliar cuentas usando filtros personalizados basados en campos de órdenes de venta, órdenes de compra o facturas.

## Ubicación en el Menú

**Contabilidad > Acciones de Contabilidad > Reconcile with Custom Fields**

## ¿Cómo Funciona?

### 1. Vista Kanban

Cuando abres el menú, verás una vista kanban con todas las combinaciones de:
- **Cuenta** (cuentas por cobrar/pagar)
- **Partner** (cliente/proveedor)

Que tienen movimientos pendientes de conciliar.

### 2. Seleccionar una Tarjeta

Haz clic en cualquier tarjeta para abrir la vista de conciliación para esa cuenta y partner.

### 3. Aplicar Filtros Personalizados

En la vista de formulario verás una sección **"Custom Field Filters"** con dos campos:

#### A. Seleccionar Mapeo de Campos
Elige un mapeo de campos personalizado de la lista desplegable. Por ejemplo:
- "Match Sale Order by Bank Reference"
- "Match Purchase Order by Reference"
- "Match Invoice by Payment Reference"

#### B. Ingresar Valor de Búsqueda
Escribe el valor que quieres buscar. Ejemplos:
- `SO001` - Para buscar orden de venta SO001
- `REF-12345` - Para buscar por referencia bancaria
- `PO00123` - Para buscar orden de compra

### 4. Aplicar el Filtro

Haz clic en el botón **"Apply Custom Filter"**

El sistema:
1. Busca en el modelo origen (Sale Order, Purchase Order, etc.) el valor que ingresaste
2. Obtiene las facturas relacionadas con esos registros
3. Extrae las líneas de cuenta por cobrar/pagar
4. Filtra por la cuenta y partner actuales
5. Agrega automáticamente esas líneas al área de conciliación

### 5. Revisar y Conciliar

Una vez que se agregaron las líneas:
- Revisa que sean las correctas
- Puedes agregar o quitar líneas manualmente si es necesario
- Haz clic en **"Reconcile"** cuando todo esté listo

### 6. Limpiar Filtro

Si quieres empezar de nuevo:
- Haz clic en **"Clear Filter"** para limpiar el filtro personalizado
- O haz clic en **"Clean"** para limpiar toda la conciliación

## Ejemplo Completo: E-commerce

### Escenario
Tu tienda online genera órdenes de venta con un campo `x_bank_reference` que el cliente debe incluir en su pago.

### Pasos

1. **Crear el Mapeo** (solo una vez)
   - Ve a Contabilidad > Configuración > Custom Field Mappings
   - Crea un mapeo:
     - Nombre: "Match by Bank Reference"
     - Source Model: Sale Order
     - Source Field: x_bank_reference
     - Operator: Equals
     - Target Model: Journal Item (account.move.line)
     - Target Field: name o ref

2. **Recibiste un Pago**
   - El cliente pagó e incluyó "REF-12345" en la transferencia
   - Importaste el extracto bancario
   - Ahora necesitas conciliar

3. **Conciliar**
   - Ve a Contabilidad > Reconcile with Custom Fields
   - Busca la tarjeta con:
     - Cuenta: Cuentas por Cobrar (101.01.001)
     - Partner: Cliente XYZ
   - Haz clic en la tarjeta
   - En "Custom Field Filters":
     - Mapeo: "Match by Bank Reference"
     - Valor: `REF-12345`
   - Clic en "Apply Custom Filter"
   - El sistema encuentra la orden SO001 con x_bank_reference = "REF-12345"
   - Obtiene la factura INV/2024/00123 de esa orden
   - Agrega automáticamente la línea de cuenta por cobrar
   - Revisa y clic en "Reconcile"

## Ventajas de Este Método

### ✓ Búsqueda Flexible
Puedes buscar por cualquier campo de órdenes o facturas, no solo los campos estándar.

### ✓ Múltiples Mapeos
Puedes tener varios mapeos configurados y elegir cuál usar en cada caso.

### ✓ Filtrado Inteligente
El sistema automáticamente filtra por la cuenta y partner correctos.

### ✓ Control Manual
Después de aplicar el filtro, puedes revisar y ajustar manualmente antes de conciliar.

### ✓ Mismo Contexto
Trabajas en el mismo contexto de cuenta + partner, manteniendo el foco.

## Diferencias con Otros Métodos

### vs. Conciliación Normal (Contabilidad > Reconcile)
- **Normal**: Buscas manualmente las líneas para conciliar
- **Con Filtros**: El sistema busca por ti usando tus criterios personalizados

### vs. Conciliación por Línea Bancaria
- **Línea Bancaria**: Concilias pago por pago en el extracto
- **Con Filtros**: Concilias por cuenta/partner, ideal para limpiar cuentas por cobrar/pagar

### vs. Conciliación Masiva (account_mass_reconcile)
- **Masiva**: Ejecuta reglas automáticamente en lote
- **Con Filtros**: Búsqueda manual con sugerencias inteligentes

## Consejos y Trucos

### Buscar Parcial
Si no sabes el valor exacto, usa operador "like":
- Valor: `SO` → Encuentra SO001, SO002, etc.
- Valor: `2024` → Encuentra cualquier orden con 2024

### Múltiples Intentos
Puedes aplicar diferentes filtros hasta encontrar lo que buscas:
1. Primer intento: Buscar por orden de venta
2. Si no encuentra: Buscar por número de factura
3. Si no encuentra: Buscar por referencia

### Combinar con Búsqueda Manual
Después de aplicar el filtro, puedes agregar más líneas manualmente usando el campo de búsqueda en la pestaña "Reconcile".

## Solución de Problemas

### No aparecen resultados
**Verificar**:
1. El mapeo está activo
2. El valor que buscas existe en el modelo origen
3. Las órdenes/facturas tienen facturas generadas
4. Las facturas están en estado "Posted"
5. Las líneas no están ya conciliadas

### Aparecen líneas incorrectas
**Revisar**:
1. El operador del mapeo (= vs like)
2. El dominio de filtros adicionales
3. Que el partner y cuenta sean correctos

### El botón no hace nada
**Asegurar**:
1. Seleccionaste un mapeo
2. Ingresaste un valor de búsqueda
3. No estás en modo "reconciled"

## Flujo Completo

```
1. Contabilidad > Reconcile with Custom Fields
   ↓
2. Click en tarjeta (Cuenta + Partner)
   ↓
3. Seleccionar mapeo: "Match by Bank Reference"
   ↓
4. Ingresar valor: "REF-12345"
   ↓
5. Click "Apply Custom Filter"
   ↓
6. Sistema busca: Sale Order donde x_bank_reference = "REF-12345"
   ↓
7. Obtiene facturas de esas órdenes
   ↓
8. Filtra líneas de cuenta por cobrar/pagar
   ↓
9. Agrega líneas al área de conciliación
   ↓
10. Revisar líneas
   ↓
11. Click "Reconcile"
   ↓
12. ¡Conciliado!
```

## Casos de Uso

### Caso 1: Limpieza de Cuentas por Cobrar
**Situación**: Tienes muchos clientes con pagos pendientes de conciliar.

**Solución**:
1. Ve a Reconcile with Custom Fields
2. Para cada cliente, aplica filtros por número de orden
3. Concilia rápidamente todas sus facturas

### Caso 2: Proveedores con Referencia Específica
**Situación**: Los proveedores incluyen su número de factura en los pagos.

**Solución**:
1. Crea mapeo: Invoice → payment_reference
2. Para cada proveedor, busca por su número de factura
3. Concilia automáticamente

### Caso 3: Proyectos con Código Único
**Situación**: Usas códigos de proyecto en órdenes y pagos.

**Solución**:
1. Crea mapeo: Sale Order → x_project_code
2. Busca por código de proyecto
3. Concilia todas las facturas del proyecto

## Preguntas Frecuentes

**P: ¿Puedo usar esto con extractos bancarios?**
R: Sí, pero ese flujo se maneja mejor desde la vista de extractos bancarios donde ya tienes integración automática.

**P: ¿Cuándo usar este método vs. extractos bancarios?**
R: Usa este método cuando quieras limpiar cuentas por cuenta y partner, no pago por pago.

**P: ¿Puedo conciliar parcialmente?**
R: Sí, puedes agregar/quitar líneas manualmente antes de conciliar.

**P: ¿Qué pasa si no tengo mapeos configurados?**
R: Debes configurar al menos un mapeo primero en Configuración > Custom Field Mappings.
