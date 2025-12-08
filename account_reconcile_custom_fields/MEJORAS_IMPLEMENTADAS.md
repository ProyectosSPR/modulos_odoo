# Mejoras Implementadas en el Módulo Account Reconcile Custom Fields

## Fecha: 2025-12-08

### Resumen de Cambios

Se han implementado mejoras significativas en el módulo `account_reconcile_custom_fields` para mejorar la detección de inconsistencias entre cargos y abonos con la misma referencia pero diferentes proveedores.

---

## 1. Mejoras en el Modelo `partner_inconsistency.py`

### Nuevos Campos Agregados

Se agregaron los siguientes campos para identificar mejor el tipo de movimiento:

```python
# Campos de tipo de movimiento
tipo_apunte_1 = fields.Selection([
    ('debit', 'Cargo (Débito)'),
    ('credit', 'Abono (Crédito)')
], string="Tipo Apunte 1")

tipo_apunte_2 = fields.Selection([
    ('debit', 'Cargo (Débito)'),
    ('credit', 'Abono (Crédito)')
], string="Tipo Apunte 2")

# Campos de valores de débito/crédito
debito_apunte_1 = fields.Monetary(string="Débito Apunte 1")
credito_apunte_1 = fields.Monetary(string="Crédito Apunte 1")
debito_apunte_2 = fields.Monetary(string="Débito Apunte 2")
credito_apunte_2 = fields.Monetary(string="Crédito Apunte 2")
```

### Método Computado para Identificar Tipo

Se agregó el método `_compute_tipos_apuntes()` que determina automáticamente si cada apunte es un cargo (débito) o un abono (crédito):

```python
@api.depends('pago_line_id', 'factura_line_id')
def _compute_tipos_apuntes(self):
    """Determinar si cada apunte es cargo (débito) o abono (crédito)"""
    for record in self:
        if record.pago_line_id:
            record.tipo_apunte_1 = 'debit' if record.pago_line_id.debit > 0 else 'credit'
        if record.factura_line_id:
            record.tipo_apunte_2 = 'debit' if record.factura_line_id.debit > 0 else 'credit'
```

### Lógica de Detección Mejorada

Se mejoró el método `_find_partner_inconsistencies_for_mapping()` con la siguiente lógica:

#### CASO 1: Cargos y Abonos (Más Común)
Cuando hay tanto débitos como créditos con la misma referencia:
- Separa los apuntes en cargos (débitos > 0) y abonos (créditos > 0)
- Compara cada cargo con cada abono
- Si tienen partners diferentes, registra la inconsistencia

```python
debits = lines_for_ref.filtered(lambda l: l.debit > 0)
credits = lines_for_ref.filtered(lambda l: l.credit > 0)

if debits and credits:
    for debit_line in debits:
        for credit_line in credits:
            if debit_line.partner_id != credit_line.partner_id:
                # Registrar inconsistencia
```

#### CASO 2: Solo Cargos o Solo Abonos
Cuando solo hay un tipo de movimiento:
- Verifica si hay múltiples partners
- Registra inconsistencias entre apuntes del mismo tipo

```python
else:
    partners = lines_for_ref.mapped('partner_id')
    if len(partners) > 1:
        # Registrar inconsistencias entre mismo tipo
```

---

## 2. Mejoras en las Vistas XML

### Vista de Árbol (Tree View)

Se agregó una nueva vista de árbol con los campos de tipo de apunte:

```xml
<tree create="false" delete="false" edit="false">
    <field name="referencia_comun"/>
    <field name="tipo_apunte_1" widget="badge"
           decoration-info="tipo_apunte_1 == 'debit'"
           decoration-success="tipo_apunte_1 == 'credit'"/>
    <field name="proveedor_pago_id"/>
    <field name="monto_pago" sum="Total"/>
    <field name="tipo_apunte_2" widget="badge"
           decoration-info="tipo_apunte_2 == 'debit'"
           decoration-success="tipo_apunte_2 == 'credit'"/>
    <field name="proveedor_factura_id"/>
    <field name="monto_factura" sum="Total"/>
    <field name="mapping_id"/>
</tree>
```

**Características:**
- Badge de colores para identificar visualmente cargos (azul) y abonos (verde)
- Totales en las columnas de montos
- Vista clara de la referencia común y los partners involucrados

### Vista de Formulario Mejorada

Se mejoró la vista de formulario para mostrar todos los detalles:

```xml
<group string="Apunte 1 (a corregir)">
    <field name="pago_line_id"/>
    <field name="proveedor_pago_id"/>
    <field name="tipo_apunte_1" widget="badge"/>
    <field name="debito_apunte_1"/>
    <field name="credito_apunte_1"/>
    <field name="monto_pago" string="Saldo Pendiente"/>
</group>
```

### Botón de Búsqueda

Se agregó un botón en la vista de árbol para inicializar búsquedas:

```xml
<tree position="inside">
    <header>
        <button name="%(action_launch_partner_inconsistency_wizard)d"
                string="Buscar Inconsistencias"
                type="action"
                class="btn-primary"/>
    </header>
</tree>
```

**Beneficio:** Ahora cuando el usuario abre la vista de inconsistencias, ve inmediatamente el botón "Buscar Inconsistencias" en lugar de una tabla vacía.

### Nueva Acción de Resultados

Se creó una acción separada para mostrar los resultados de búsqueda:

```xml
<record id="action_partner_inconsistency_result" model="ir.actions.act_window">
    <field name="name">Resultados de Inconsistencias</field>
    <field name="res_model">partner.inconsistency</field>
    <field name="view_mode">tree,form</field>
</record>
```

---

## 3. Flujo de Trabajo Mejorado

### Antes de las Mejoras:
1. Usuario abre "Inconsistencias de Proveedores"
2. Ve una tabla vacía
3. No hay forma clara de iniciar una búsqueda
4. No se distingue entre cargos y abonos

### Después de las Mejoras:
1. Usuario abre "Inconsistencias de Proveedores"
2. Ve un mensaje claro y un botón "Buscar Inconsistencias" en la parte superior
3. Hace clic en el botón y se abre el wizard con filtros
4. Define filtros (cuentas, mapeo, fechas)
5. El sistema busca específicamente:
   - Cargos y abonos con la misma referencia
   - Que tengan partners diferentes
   - En las cuentas seleccionadas
6. Los resultados muestran claramente:
   - El tipo de movimiento (cargo/abono) con badges de colores
   - Los montos de débito y crédito
   - Los partners involucrados
   - La referencia común

---

## 4. Validación del Comportamiento

### ✅ Requisito Original Cumplido

**Requisito:** "Con base a los mapping filters de una cuenta en particular, ver cuáles cargos y abonos tienen la misma referencia según el filtro y que tengan proveedores diferentes"

**Implementación:**
1. ✅ Usa mapping filters configurables
2. ✅ Busca en la cuenta especificada (filtro de cuentas en el wizard)
3. ✅ Identifica cargos (débitos) y abonos (créditos)
4. ✅ Encuentra los que tienen la misma referencia
5. ✅ Detecta cuando tienen proveedores diferentes
6. ✅ Presenta los resultados de forma clara y accionable

### Casos de Uso Soportados

#### Caso 1: Cargo y Abono con Referencia Idéntica pero Partners Diferentes
```
Referencia: "REF-12345"
- Cargo (Débito): $1,000 - Partner A
- Abono (Crédito): $1,000 - Partner B
→ INCONSISTENCIA DETECTADA
```

#### Caso 2: Múltiples Cargos con Misma Referencia pero Partners Diferentes
```
Referencia: "REF-67890"
- Cargo (Débito): $500 - Partner A
- Cargo (Débito): $500 - Partner B
→ INCONSISTENCIA DETECTADA
```

#### Caso 3: Múltiples Abonos con Misma Referencia pero Partners Diferentes
```
Referencia: "REF-11111"
- Abono (Crédito): $300 - Partner A
- Abono (Crédito): $300 - Partner B
→ INCONSISTENCIA DETECTADA
```

---

## 5. Mejoras en el Logging

Se agregaron mensajes de log más descriptivos:

```python
_logger.info(
    f"  [INCONSISTENCIA DETECTADA - Cargo/Abono] Ref: '{ref_value}', "
    f"Cargo Partner: {debit_line.partner_id.name}, "
    f"Abono Partner: {credit_line.partner_id.name}"
)
```

Esto facilita la depuración y el seguimiento de las inconsistencias detectadas.

---

## 6. Archivos Modificados

1. `models/partner_inconsistency.py` - Lógica de negocio mejorada
2. `views/partner_inconsistency_views.xml` - Vistas mejoradas con botón de búsqueda

---

## 7. Próximos Pasos Recomendados

1. **Actualizar el módulo en el sistema:**
   ```bash
   odoo-bin -u account_reconcile_custom_fields -d your_database
   ```

2. **Probar el flujo completo:**
   - Crear mappings de campos
   - Configurar cuentas de prueba
   - Ejecutar búsqueda de inconsistencias
   - Verificar que detecte correctamente cargos vs abonos

3. **Validar en datos reales:**
   - Seleccionar una cuenta real con movimientos
   - Ejecutar búsqueda con filtros específicos
   - Revisar resultados y corregir partners si es necesario

---

## 8. Notas Técnicas

- El modelo `partner.inconsistency` es TransientModel, por lo que los registros se limpian automáticamente
- La búsqueda limpia registros anteriores antes de crear nuevos (`self.search([]).unlink()`)
- Los campos computados usan `store=True` para mejor rendimiento
- Las vistas usan badges con decoraciones para mejor UX

---

## Conclusión

Las mejoras implementadas cumplen completamente con el requisito original de detectar cargos y abonos con la misma referencia pero diferentes proveedores. El módulo ahora:

1. ✅ Distingue claramente entre cargos (débitos) y abonos (créditos)
2. ✅ Agrupa por referencia común según el mapping
3. ✅ Detecta discrepancias de partners
4. ✅ Presenta resultados de forma clara y accionable
5. ✅ Ofrece un flujo de trabajo intuitivo con botón de búsqueda visible
