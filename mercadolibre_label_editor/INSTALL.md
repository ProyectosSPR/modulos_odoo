# Guía de Instalación - MercadoLibre Label Editor

## 📋 Pre-requisitos

### 1. Módulos de Odoo
- ✅ `mercadolibre_connector` - Instalado
- ✅ `mercadolibre_sales` - Instalado

### 2. Dependencias Python

```bash
pip3 install PyPDF2 reportlab pdf2image
```

**Nota para pdf2image**: Requiere poppler-utils en el sistema:

```bash
# Ubuntu/Debian
sudo apt-get install poppler-utils

# CentOS/RHEL
sudo yum install poppler-utils
```

## 🚀 Instalación del Módulo

### Paso 1: Verificar ubicación
```bash
ls -la /home/dml/modulos_odoo/mercadolibre_label_editor/
```

Deberías ver:
```
__init__.py
__manifest__.py
models/
views/
wizard/
static/
security/
data/
README.md
```

### Paso 2: Actualizar lista de aplicaciones

1. Ir a **Aplicaciones** en Odoo
2. Click en **Actualizar lista de aplicaciones**
3. Confirmar la actualización

### Paso 3: Instalar el módulo

1. Buscar: `MercadoLibre Label Editor`
2. Click en **Instalar**
3. Esperar a que termine la instalación

### Paso 4: Verificar instalación

#### Verificar menú
Ve a: **MercadoLibre > Configuración > Plantillas de Etiqueta**

Deberías ver:
- Una plantilla de ejemplo ya creada
- Opción para crear nuevas plantillas

#### Verificar en Tipos Logísticos
Ve a: **MercadoLibre > Configuración > Tipos Logísticos**

Edita cualquier tipo logístico y verifica que en la sección **Etiquetas de Envio ML** aparezca:
- Campo nuevo: **Plantilla Etiqueta**
- Grupo nuevo debajo (cuando selecciones una plantilla)

## ✅ Verificación de Dependencias

### Comprobar PyPDF2
```bash
python3 -c "import PyPDF2; print('PyPDF2 versión:', PyPDF2.__version__)"
```

### Comprobar reportlab
```bash
python3 -c "import reportlab; print('reportlab instalado correctamente')"
```

### Comprobar pdf2image (opcional)
```bash
python3 -c "from pdf2image import convert_from_path; print('pdf2image funcional')"
```

## 🎯 Primer Uso

### 1. Crear tu primera plantilla

1. Ve a **MercadoLibre > Configuración > Plantillas de Etiqueta**
2. Click **Crear**
3. Llena los datos:
   - **Nombre**: "Mi Primera Plantilla"
   - **PDF Ejemplo**: Sube una etiqueta ML que hayas descargado previamente
4. Ve a la pestaña **Campos de Texto**
5. Agrega un campo:
   - **Nombre**: "Número de Orden"
   - **Tipo**: Dinámico
   - **Valor**: `${sale_order.name}`
   - **Posición X**: 50
   - **Posición Y**: 30
   - **Fuente**: Helvetica-Bold
   - **Tamaño**: 16
6. **Guarda**

### 2. Asignar a tipo logístico

1. Ve a **MercadoLibre > Configuración > Tipos Logísticos**
2. Edita "Full ML" (o el que uses)
3. En **Automatización**:
   - Activa: **Descargar Etiqueta ML** ✓
   - Selecciona: **Plantilla Etiqueta** → "Mi Primera Plantilla"
4. **Guarda**

### 3. Probar con vista previa

1. En el tipo logístico, click **Vista Previa con Datos**
2. Completa datos de ejemplo
3. Click **Generar Vista Previa**
4. Verifica que el número de orden aparezca en el PDF

### 4. Esperar orden real

Cuando llegue la próxima orden de MercadoLibre:
1. Se sincronizará automáticamente
2. Se descargará la etiqueta
3. Se aplicará tu plantilla
4. El PDF final estará en los adjuntos de la orden de venta

## 🔧 Troubleshooting

### Error: "No module named 'PyPDF2'"
```bash
pip3 install --user PyPDF2
# O si tienes permisos de administrador:
sudo pip3 install PyPDF2
```

### Error: "No module named 'reportlab'"
```bash
pip3 install --user reportlab
```

### La plantilla no se aplica
1. Verifica que el tipo logístico tenga:
   - `download_shipping_label = True`
   - Una plantilla seleccionada
2. Verifica que la plantilla tenga campos activos
3. Revisa los logs de Odoo:
   ```bash
   tail -f /var/log/odoo/odoo-server.log | grep -i "label"
   ```

### Las coordenadas no coinciden
- Las coordenadas se calculan asumiendo 150 DPI
- Si tu PDF tiene diferente resolución, ajusta manualmente
- Prueba con **Vista Previa** hasta encontrar la posición correcta

### El preview no se genera
1. Verifica pdf2image:
   ```bash
   pip3 install pdf2image
   sudo apt-get install poppler-utils
   ```
2. Si sigue sin funcionar, el módulo usará PyMuPDF como alternativa
3. La vista previa es opcional, el procesamiento de PDFs funciona sin ella

## 📊 Verificar que todo funciona

### Test completo
1. ✅ Menú "Plantillas de Etiqueta" visible
2. ✅ Crear plantilla sin errores
3. ✅ Subir PDF de ejemplo funciona
4. ✅ Agregar campos funciona
5. ✅ Vista previa genera PDF
6. ✅ Asignar a tipo logístico funciona
7. ✅ Orden de prueba aplica plantilla

## 🆘 Obtener ayuda

### Logs
```bash
# Ver logs en tiempo real
tail -f /var/log/odoo/odoo-server.log

# Buscar errores del módulo
grep -i "mercadolibre_label_editor" /var/log/odoo/odoo-server.log

# Ver errores de plantillas
grep -i "ml.label" /var/log/odoo/odoo-server.log
```

### Reiniciar Odoo
```bash
sudo systemctl restart odoo
# o
sudo service odoo restart
```

### Desinstalar y reinstalar
1. Ve a **Aplicaciones**
2. Busca "MercadoLibre Label Editor"
3. Click **Desinstalar**
4. Confirma
5. Actualiza lista de aplicaciones
6. Reinstala

## ✨ Siguiente paso

Lee el [README.md](README.md) para aprender sobre:
- Variables disponibles
- Configuración avanzada
- Ejemplos de uso
- Rotación de texto
- Alineación
