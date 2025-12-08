# Solución: Botón "Buscar Inconsistencias" Siempre Visible

## Problema Original
El botón "Buscar Inconsistencias" no era visible cuando no había registros en la tabla, dejando al usuario sin una manera clara de iniciar una búsqueda.

## Solución Implementada

### Uso de Action Binding

Se utilizó el mecanismo de **action binding** de Odoo para vincular automáticamente la acción del wizard al modelo:

```xml
<record id="action_launch_partner_inconsistency_wizard" model="ir.actions.act_window">
    <field name="name">Buscar Inconsistencias</field>
    <field name="res_model">partner.inconsistency.wizard</field>
    <field name="view_mode">form</field>
    <field name="target">new</field>
    <field name="binding_model_id" ref="model_partner_inconsistency"/>
    <field name="binding_type">action</field>
</record>
```

### ¿Cómo Funciona?

Los campos clave son:
- `binding_model_id`: Vincula la acción al modelo `partner.inconsistency`
- `binding_type`: Define que es una acción (aparece en el menú "Action")

Esto hace que Odoo automáticamente agregue un botón en el menú **"Action"** (⚙️) de la vista, que está **SIEMPRE visible**, incluso sin datos.

## Ubicación del Botón

```
┌─────────────────────────────────────────────────────────────┐
│ Inconsistencias de Proveedores                    [⚙️ Action]│  ← AQUÍ
├─────────────────────────────────────────────────────────────┤
│ [Buscar...] [Cargo] [Abono] [Group By ▼]                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  😊 No se han encontrado inconsistencias.                   │
│                                                              │
│  Para empezar, haz clic en el menú "Action" (⚙️)           │
│  y selecciona "Buscar Inconsistencias"                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘

Al hacer clic en ⚙️ Action:
  ├─ Buscar Inconsistencias  ← ESTE ES EL BOTÓN
  ├─ Export
  └─ ...
```

## Pasos para el Usuario

1. Abrir: **Contabilidad > Acciones de Contabilidad > Inconsistencias de Proveedores**

2. Hacer clic en el icono **⚙️ "Action"** en la esquina superior derecha

3. Seleccionar **"Buscar Inconsistencias"** del menú desplegable

4. Se abre el wizard con los filtros:
   - Cuentas Contables
   - Mapeo a Utilizar
   - Rango de Fechas
   - Incluir Apuntes Conciliados

5. Hacer clic en **"Buscar"**

6. Los resultados aparecen en la tabla con:
   - Referencias comunes
   - Tipos de apuntes (Cargo/Abono)
   - Partners involucrados
   - Montos

## Mejoras Adicionales en la Search View

También se agregaron filtros útiles:

```xml
<filter string="Cargo (Débito)" name="filter_debit" domain="[('tipo_apunte_1', '=', 'debit')]"/>
<filter string="Abono (Crédito)" name="filter_credit" domain="[('tipo_apunte_1', '=', 'credit')]"/>
```

Y agrupaciones:
```xml
<filter string="Referencia" name="group_referencia" context="{'group_by':'referencia_comun'}"/>
<filter string="Mapeo" name="group_mapping" context="{'group_by':'mapping_id'}"/>
<filter string="Tipo Apunte 1" name="group_tipo1" context="{'group_by':'tipo_apunte_1'}"/>
```

## Ventajas de Esta Solución

1. ✅ **Siempre visible**: El menú "Action" está presente incluso sin datos
2. ✅ **Estándar de Odoo**: Usa el patrón nativo de Odoo para acciones
3. ✅ **Sin código JavaScript**: Solución puramente XML
4. ✅ **Fácil de encontrar**: Los usuarios conocen el menú "Action"
5. ✅ **Consistente**: Se comporta como otras acciones de Odoo

## Comparación con Otras Soluciones

### ❌ Botón en Tree View
- Solo visible cuando hay datos
- No funciona en vista vacía

### ❌ Botón en Search View
- Sintaxis compleja
- Problemas con referencias externas
- No soportado nativamente

### ✅ Action Binding (Solución Actual)
- Siempre visible
- Sintaxis simple
- Patrón nativo de Odoo
- Fácil de mantener

## Archivos Modificados

- `views/partner_inconsistency_views.xml`
  - Agregado `binding_model_id` y `binding_type` a la acción del wizard
  - Mejorada la search view con filtros útiles
  - Actualizados mensajes de ayuda

## Verificación

Para verificar que funciona:

1. Actualizar el módulo:
```bash
odoo-bin -u account_reconcile_custom_fields -d odoo16c
```

2. Navegar a la vista de inconsistencias

3. Verificar que el menú "Action" (⚙️) muestra "Buscar Inconsistencias"

4. Hacer clic y confirmar que abre el wizard

## Resultado Final

El usuario ahora tiene una manera clara y visible de iniciar la búsqueda de inconsistencias, siguiendo los patrones estándar de Odoo y proporcionando una experiencia de usuario consistente.
