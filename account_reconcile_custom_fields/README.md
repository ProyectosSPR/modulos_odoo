# Account Reconcile Custom Fields

## Descripción

Este módulo extiende la funcionalidad de conciliación de Odoo para permitir empatar facturas con pagos basándose en campos personalizados de órdenes de venta, órdenes de compra o facturas.

## Características

### Modo Manual Interactivo (UI de OCA)

- **Sugerencias automáticas**: Al abrir una línea bancaria para conciliar, el sistema automáticamente busca facturas que coincidan según los mapeos configurados.
- **Búsqueda manual**: Botón "Find Custom Matches" para buscar coincidencias manualmente.
- **Integración completa**: Se integra perfectamente con la interfaz de conciliación de `account_reconcile_oca`.

## Configuración

### 1. Configurar Mapeos de Campos

Ve a **Contabilidad > Configuración > Custom Field Mappings**

Crea un nuevo mapeo:

#### Ejemplo 1: Empatar por referencia bancaria de orden de venta

- **Nombre**: Match Sale Order by Bank Reference
- **Modelo Origen**: Sale Order (sale.order)
- **Campo Origen**: x_bank_reference (campo personalizado)
- **Operador**: Equals (=)
- **Modelo Destino**: Bank Statement Line (account.bank.statement.line)
- **Campo Destino**: payment_ref

#### Ejemplo 2: Empatar por referencia de orden de compra

- **Nombre**: Match Purchase Order by Reference
- **Modelo Origen**: Purchase Order (purchase.order)
- **Campo Origen**: name
- **Operador**: Contains (like)
- **Modelo Destino**: Bank Statement Line (account.bank.statement.line)
- **Campo Destino**: payment_ref

### 2. Usar en Conciliación

#### Automático

1. Ve a **Contabilidad > Extractos Bancarios**
2. Abre una línea bancaria para conciliar
3. El sistema automáticamente buscará y sugerirá facturas que coincidan según los mapeos configurados

#### Manual

1. Abre una línea bancaria para conciliar
2. Haz clic en el botón **"Find Custom Matches"**
3. El sistema buscará todas las facturas que coincidan y las agregará a la conciliación

## Flujo de Trabajo

```
Línea Bancaria (payment_ref = "REF12345")
    ↓
Buscar en Orden de Venta (x_bank_reference = "REF12345")
    ↓
Obtener Facturas de la Orden de Venta
    ↓
Obtener Líneas de Cuentas por Cobrar/Pagar
    ↓
Sugerir para Conciliación
```

## Operadores Disponibles

- **Equals (=)**: Coincidencia exacta
- **Not Equals (!=)**: No igual
- **Contains (like)**: El campo origen contiene el valor del destino
- **Contains (ilike)**: Contiene (insensible a mayúsculas/minúsculas)
- **In**: El valor está en una lista
- **Not In**: El valor no está en una lista

## Filtros Adicionales

Puedes agregar dominios adicionales para filtrar tanto el modelo origen como el destino:

### Ejemplos de Dominios

**Filtrar solo órdenes confirmadas:**
```python
[('state', '=', 'sale')]
```

**Filtrar solo facturas publicadas:**
```python
[('state', '=', 'posted')]
```

**Filtrar por compañía:**
```python
[('company_id', '=', 1)]
```

## Casos de Uso

### Caso 1: E-commerce con referencia de pago

Tu tienda en línea genera órdenes de venta con un campo `x_payment_reference` que envías al cliente. Cuando el cliente paga, el banco incluye esta referencia en el extracto bancario.

**Configuración:**
- Origen: Sale Order → x_payment_reference
- Destino: Bank Statement Line → payment_ref
- Operador: Equals

### Caso 2: Proveedores con número de factura en transferencia

Tus proveedores incluyen su número de factura en el concepto de la transferencia bancaria.

**Configuración:**
- Origen: Invoice (account.move) → name
- Destino: Bank Statement Line → payment_ref
- Operador: Contains

### Caso 3: Órdenes de compra con código interno

Usas un campo personalizado en órdenes de compra para identificar proyectos, y este código aparece en los pagos.

**Configuración:**
- Origen: Purchase Order → x_project_code
- Destino: Payment (account.payment) → ref
- Operador: Contains

## Dependencias

- `account_reconcile_oca`
- `sale`
- `purchase`

## Autor

DML

## Licencia

AGPL-3
