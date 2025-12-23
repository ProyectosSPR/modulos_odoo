# Correcciones Aplicadas

## Error Corregido: Campo 'sequence' faltante

**Error original:**
```
El campo "sequence" no existe en el modelo "ml.label.template"
```

**Solución aplicada:**
Agregado campo `sequence` al modelo `ml.label.template`:

```python
sequence = fields.Integer(
    string='Secuencia',
    default=10,
    help='Orden de visualización'
)
```

También actualizado el `_order` del modelo:
```python
_order = 'sequence, name'
```

## Instrucciones para Actualizar

Si ya intentaste instalar el módulo y falló:

### Opción 1: Reinstalar desde cero
1. Ve a **Aplicaciones**
2. Busca "MercadoLibre Label Editor"
3. Si aparece como "Instalado" o "Por instalar":
   - Activa modo desarrollador: Ajustes > Activar modo desarrollador
   - Ve a Aplicaciones > Filtros > Instaladas
   - Busca el módulo
   - Click en **Desinstalar**
4. Actualiza lista de aplicaciones
5. Busca e **Instala** nuevamente

### Opción 2: Actualizar el módulo
Si el módulo quedó parcialmente instalado:

```bash
# Reiniciar Odoo con actualización del módulo
sudo systemctl restart odoo
# o desde línea de comandos de Odoo:
odoo-bin -u mercadolibre_label_editor -d TU_BASE_DE_DATOS
```

### Opción 3: Desde interfaz web (modo desarrollador)
1. Activa modo desarrollador
2. Ve a **Ajustes > Técnico > Base de datos > Actualizar lista de módulos**
3. Busca "MercadoLibre Label Editor"
4. Click **Actualizar**

## Verificación Post-Instalación

Después de instalar/actualizar correctamente:

1. Ve a **MercadoLibre > Configuración > Plantillas de Etiqueta**
2. Verifica que puedes:
   - ✓ Ver la lista (tree view)
   - ✓ Crear nueva plantilla
   - ✓ Arrastrar para reordenar (campo sequence funcional)

## Estado Actual

✅ Campo `sequence` agregado correctamente
✅ Código compilado sin errores
✅ Vistas XML validadas
✅ Módulo listo para instalación

---

**Fecha de corrección:** 2024-12-23
**Archivos modificados:** `models/ml_label_template.py`
