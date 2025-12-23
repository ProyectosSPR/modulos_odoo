# 📖 Guía de Uso - MercadoLibre Label Editor

## 🎯 ¿Qué hace este módulo?

Permite **personalizar las etiquetas de envío de MercadoLibre** agregando información adicional como:
- Número de orden de venta
- Nombre del cliente
- Teléfono
- Fecha
- Cualquier otro dato de la orden

## 🚀 Cómo Usar (Paso a Paso)

### Paso 1: Crear una Plantilla

1. Ve a: **MercadoLibre → Configuración → Plantillas de Etiqueta**
2. Click en **"Crear"**
3. Escribe un nombre descriptivo (Ej: "Plantilla Estándar RML")

### Paso 2: Cargar PDF de Ejemplo

1. En la pestaña **"📄 PDF Ejemplo"**:
   - Descarga una etiqueta real desde MercadoLibre
   - Click en **"Seleccionar archivo"**
   - Sube el PDF de la etiqueta ML

2. El sistema detectará automáticamente:
   - ✅ Dimensiones del PDF
   - ✅ Genera una vista previa

3. Verás un mensaje verde: **"¡PDF cargado correctamente!"**

### Paso 3: Agregar Campos Personalizados

1. Ve a la pestaña **"✏️ Campos de Texto"**
2. Click en **"Agregar una línea"**
3. Configura el campo:

#### Ejemplo 1: Número de Orden
```
Descripción: Número de Orden
Tipo: Variable Dinámica
Valor: ${sale_order.name}
Posición X: 50
Posición Y: 100
Tamaño Fuente: 14
Color: #000000
```

#### Ejemplo 2: Cliente
```
Descripción: Cliente
Tipo: Variable Dinámica
Valor: Cliente: ${sale_order.partner_id.name}
Posición X: 50
Posición Y: 120
Tamaño Fuente: 12
Color: #000000
```

#### Ejemplo 3: Texto Fijo
```
Descripción: Mensaje
Tipo: Texto Estático
Valor: ¡FRÁGIL - MANEJAR CON CUIDADO!
Posición X: 50
Posición Y: 200
Tamaño Fuente: 16
Color: #FF0000
```

### Paso 4: Ajustar Posiciones

1. Guarda la plantilla
2. Click en **"Vista Previa"** en el botón superior
3. Verifica que los campos estén bien posicionados
4. Si necesitas ajustar:
   - Edita el campo
   - Cambia las coordenadas X,Y
   - Guarda y vuelve a previsualizar

### Paso 5: Asignar a Tipo Logístico

1. Ve a: **MercadoLibre → Configuración → Tipos Logísticos**
2. Abre el tipo logístico que usas (Ej: "cross_docking")
3. En el campo **"Plantilla de Etiqueta"**:
   - Selecciona tu plantilla creada
4. Guarda

### Paso 6: ¡Listo! Ahora es Automático

Cuando descargues etiquetas ML:
1. El sistema aplicará automáticamente tu plantilla
2. Generará el PDF personalizado
3. Lo guardará como adjunto en la orden ML

---

## 📋 Variables Disponibles

Copia y pega estas variables en tus campos dinámicos:

### Orden de Venta
- `${sale_order.name}` - Número de orden (SO001)
- `${sale_order.partner_id.name}` - Nombre del cliente
- `${sale_order.partner_id.phone}` - Teléfono del cliente
- `${sale_order.partner_id.email}` - Email del cliente
- `${sale_order.date_order}` - Fecha de la orden
- `${sale_order.warehouse_id.name}` - Almacén

### Orden MercadoLibre
- `${ml_order.ml_order_id}` - ID de orden ML
- `${ml_order.ml_pack_id}` - Pack ID
- `${ml_order.ml_shipment_id}` - Shipment ID
- `${ml_order.logistic_type}` - Tipo logístico

### Variables Especiales
- `${today}` - Fecha de hoy (23/12/2025)
- `${now}` - Fecha y hora actual
- `${company.name}` - Nombre de tu empresa

---

## 🎨 Consejos de Diseño

### Posicionamiento
- **X = 0, Y = 0** es la esquina superior izquierda
- Valores típicos para etiquetas 10x10cm (595x595px):
  - Margen izquierdo: X = 50
  - Espaciado vertical: Y += 20 entre líneas

### Tamaños de Fuente
- **8-10pt**: Textos pequeños (notas, códigos)
- **12-14pt**: Textos normales (datos principales)
- **16-20pt**: Títulos y advertencias

### Colores
- **Negro (#000000)**: Textos normales
- **Rojo (#FF0000)**: Advertencias, urgente
- **Azul (#0000FF)**: Links, información secundaria
- **Gris (#666666)**: Texto secundario

### Alineación
- **Izquierda**: Para la mayoría de textos
- **Centro**: Para títulos
- **Derecha**: Para números, códigos

---

## 🔧 Resolución de Problemas

### ❌ No veo la vista previa del PDF
**Solución:** Instala las dependencias:
```bash
pip3 install pdf2image PyMuPDF
```

### ❌ Los campos no aparecen en la etiqueta
**Verificar:**
1. ¿El campo está activo? (toggle verde)
2. ¿La posición X,Y está dentro del PDF?
3. ¿El tamaño de fuente no es muy grande?
4. ¿El color no es blanco sobre blanco?

### ❌ Las variables muestran "${...}" literal
**Causa:** La plantilla no está asignada al tipo logístico
**Solución:** Ve a Tipos Logísticos y asigna tu plantilla

### ❌ Error al descargar etiqueta
**Verificar:**
1. ¿Las dependencias están instaladas? (PyPDF2, reportlab)
2. ¿El PDF de ejemplo es válido?
3. ¿Los campos tienen posiciones válidas?

---

## 📊 Ejemplos de Uso Común

### Ejemplo 1: Etiqueta Simple
```
Campo 1:
  Nombre: Orden
  Tipo: Dinámico
  Valor: Orden: ${sale_order.name}
  X: 50, Y: 50, Tamaño: 14pt

Campo 2:
  Nombre: Cliente
  Tipo: Dinámico
  Valor: ${sale_order.partner_id.name}
  X: 50, Y: 70, Tamaño: 12pt
```

### Ejemplo 2: Etiqueta Completa
```
Campo 1: Orden ML
  ${ml_order.ml_order_id}
  X: 50, Y: 50

Campo 2: Orden Interna
  Orden: ${sale_order.name}
  X: 50, Y: 70

Campo 3: Cliente
  ${sale_order.partner_id.name}
  X: 50, Y: 90

Campo 4: Teléfono
  Tel: ${sale_order.partner_id.phone}
  X: 50, Y: 110

Campo 5: Fecha
  ${today}
  X: 50, Y: 130

Campo 6: Advertencia
  ¡FRÁGIL!
  X: 50, Y: 200, Color: Rojo, Tamaño: 18pt
```

### Ejemplo 3: Código QR + Texto
```
Campo 1: Código para QR
  Tipo: Dinámico
  Valor: ML${ml_order.ml_order_id}-${sale_order.name}
  X: 400, Y: 50, Tamaño: 10pt

Campo 2: Instrucciones
  Tipo: Estático
  Valor: Escanear código arriba
  X: 400, Y: 70, Tamaño: 8pt
```

---

## 🎓 Tips Pro

1. **Duplica plantillas**: Usa el botón "Duplicar" para crear variantes
2. **Usa secuencias**: El orden de procesamiento importa si hay campos superpuestos
3. **Prueba con datos reales**: Usa el botón "Vista Previa" con una orden real
4. **Mantén simple**: Menos campos = más legible
5. **Usa contraste**: Texto oscuro sobre etiqueta clara
6. **Evita bordes**: Deja 20-30px de margen en los bordes del PDF

---

## 📞 Soporte

Si tienes problemas:
1. Revisa esta guía primero
2. Verifica los logs de Odoo
3. Prueba con una plantilla simple primero
4. Reporta el error con capturas de pantalla

---

**Versión:** 1.0.1
**Última actualización:** 2025-12-23
**Estado:** ✅ Producción
