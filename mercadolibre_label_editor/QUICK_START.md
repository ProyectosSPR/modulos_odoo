# 🚀 Inicio Rápido - MercadoLibre Label Editor

## ✅ Estado de Instalación

**Módulo creado exitosamente** ✓

Ubicación: `/home/dml/modulos_odoo/mercadolibre_label_editor/`

## 📦 Instalación en 3 Pasos

### 1️⃣ Actualizar lista de aplicaciones

En Odoo:
1. Ve a **Aplicaciones**
2. Click en **⋮ (menú)** → **Actualizar lista de aplicaciones**
3. Click **Actualizar**

### 2️⃣ Buscar e instalar

1. En el buscador escribe: `label editor`
2. Aparecerá: **MercadoLibre Label Editor**
3. Click **Instalar**
4. Espera a que termine (30-60 segundos)

### 3️⃣ Verificar instalación

Ve a: **MercadoLibre > Configuración > Plantillas de Etiqueta**

Si ves el menú y una plantilla de ejemplo → **¡Instalación exitosa!** 🎉

---

## 🎯 Uso en 5 Minutos

### Paso 1: Preparar una etiqueta de ejemplo

1. Descarga una etiqueta ML real desde una orden existente
2. Guárdala como `etiqueta_ejemplo.pdf`

### Paso 2: Crear tu plantilla

1. Ve a **MercadoLibre > Configuración > Plantillas de Etiqueta**
2. Click **Crear**
3. Completa:
   - **Nombre**: "Etiqueta Full con Orden"
   - **PDF Ejemplo**: Sube `etiqueta_ejemplo.pdf`
4. Ve a pestaña **Campos de Texto**
5. Click **Agregar una línea**
6. Configura:
   ```
   Nombre:      Número de Orden
   Tipo:        Dinámico
   Valor:       ${sale_order.name}
   Posición X:  50
   Posición Y:  30
   Fuente:      Helvetica-Bold
   Tamaño:      16
   Color:       #000000
   Rotación:    0
   Alineación:  Izquierda
   Activo:      ✓
   ```
7. Click **Guardar**

### Paso 3: Probar la plantilla

1. En la plantilla, click **Vista Previa**
2. Completa datos de ejemplo:
   - Número de Orden: `SO0123`
   - Cliente: `Juan Pérez`
3. Click **Generar Vista Previa**
4. Verifica que `SO0123` aparezca en el PDF

Si la posición no es correcta:
- Edita el campo
- Ajusta X e Y
- Vuelve a generar vista previa

### Paso 4: Asignar a tipo logístico

1. Ve a **MercadoLibre > Configuración > Tipos Logísticos**
2. Edita **Full ML** (o el que uses)
3. En la pestaña **Automatización**:
   - ✓ Activa: **Descargar Etiqueta ML**
   - Selecciona: **Plantilla Etiqueta** → "Etiqueta Full con Orden"
4. Click **Guardar**

### Paso 5: ¡Listo! Espera una orden

Cuando llegue la próxima orden de MercadoLibre:
1. Se sincroniza automáticamente ✓
2. Se crea la orden de venta ✓
3. Se descarga la etiqueta ML ✓
4. **Se aplica tu plantilla** ✓
5. El PDF personalizado está en adjuntos ✓

---

## 💡 Tips Rápidos

### Encontrar coordenadas correctas
1. Abre el PDF de ejemplo en un visor
2. Usa la herramienta de medida (si la hay)
3. O usa prueba y error con **Vista Previa**
4. Esquina superior izquierda es (0, 0)
5. X aumenta hacia la derecha
6. Y aumenta hacia abajo

### Agregar más campos

Ejemplos útiles:

**Cliente:**
```
Valor: ${sale_order.partner_id.name}
X: 50, Y: 60
Fuente: Helvetica
Tamaño: 12
```

**Fecha:**
```
Valor: ${today}
X: 400, Y: 30
Fuente: Courier
Tamaño: 10
```

**ID ML:**
```
Valor: ML: ${ml_order.ml_order_id}
X: 50, Y: 90
Fuente: Courier
Tamaño: 8
```

**Texto diagonal:**
```
Valor: PROCESADO
X: 300, Y: 400
Fuente: Helvetica-Bold
Tamaño: 20
Color: #FF0000
Rotación: 45
```

### Variables más usadas

| Variable | Resultado |
|----------|-----------|
| `${sale_order.name}` | SO0001 |
| `${sale_order.partner_id.name}` | Juan Pérez |
| `${sale_order.partner_id.phone}` | +52 55 1234 5678 |
| `${ml_order.ml_order_id}` | 1234567890 |
| `${ml_order.ml_pack_id}` | PACK-001 |
| `${today}` | 2024-01-15 |
| `${company.name}` | Mi Empresa |

---

## 🔧 Si algo no funciona

### La plantilla no se aplica

**Verificar:**
1. Tipo logístico tiene **Descargar Etiqueta ML** activado ✓
2. Hay una plantilla seleccionada ✓
3. La plantilla tiene campos **Activos** ✓

### Las coordenadas están mal

**Solución:**
1. Usa **Vista Previa** para ajustar
2. Incrementa/decrementa X,Y de 10 en 10
3. Cuando esté cerca, ajusta de 1 en 1

### El texto no se ve

**Verificar:**
1. Color no es blanco (#FFFFFF) sobre fondo blanco
2. Tamaño de fuente no es muy pequeño (<6)
3. Posición está dentro del PDF (X < ancho, Y < alto)

### Regenerar etiqueta existente

Si ya descargaste una etiqueta antes de configurar la plantilla:

1. Abre la orden ML
2. Click **Regenerar con Plantilla**
3. Se aplicará la plantilla al PDF existente

---

## 📚 Documentación Completa

Para más información consulta:
- [README.md](README.md) - Documentación completa
- [INSTALL.md](INSTALL.md) - Guía de instalación detallada

---

## ✨ Características Avanzadas

### Múltiples plantillas
Crea diferentes plantillas para diferentes tipos logísticos:
- Plantilla Full ML
- Plantilla Envío Propio
- Plantilla Agencia

### Plantilla con rotación
Para etiquetas en formato apaisado, rota el texto:
```
Rotación: 90  (vertical)
Rotación: 45  (diagonal)
Rotación: -15 (ligeramente inclinado)
```

### Combinar texto estático y dinámico
```
Valor: Orden: ${sale_order.name} - Cliente: ${sale_order.partner_id.name}
```

### Desactivar campos temporalmente
En lugar de borrar, marca como **Inactivo** ✗

---

## 🎓 Ejemplo Completo

**Objetivo:** Agregar orden, cliente y fecha a etiqueta Full ML

**Campos a crear:**

1. **Orden (arriba izquierda)**
   - Valor: `${sale_order.name}`
   - X: 50, Y: 30, Tamaño: 16, Bold

2. **Cliente (debajo de orden)**
   - Valor: `${sale_order.partner_id.name}`
   - X: 50, Y: 55, Tamaño: 12, Regular

3. **Fecha (arriba derecha)**
   - Valor: `${today}`
   - X: 450, Y: 30, Tamaño: 10, Courier

4. **Sello diagonal (centro)**
   - Valor: `VERIFICADO`
   - X: 250, Y: 350, Tamaño: 24, Bold, Rojo, Rotación: 45°

**Resultado:** PDF con toda la info personalizada ✨

---

## ⚡ Atajos

- **Duplicar plantilla**: Botón "Duplicar" en la plantilla
- **Vista previa rápida**: Desde tipo logístico → "Vista Previa con Datos"
- **Editar campos masivo**: Exporta a CSV → Edita → Importa

---

¡Listo para personalizar tus etiquetas! 🎉
