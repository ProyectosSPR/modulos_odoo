#!/bin/bash

echo "========================================="
echo "  Verificación: MercadoLibre Label Editor"
echo "========================================="
echo ""

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_passed=0
check_failed=0

# Función de verificación
check() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $1"
        ((check_passed++))
    else
        echo -e "${RED}✗${NC} $1"
        ((check_failed++))
    fi
}

# 1. Verificar estructura de archivos
echo "1. Estructura de archivos"
echo "-------------------------"

test -f "__manifest__.py"
check "__manifest__.py existe"

test -f "__init__.py"
check "__init__.py existe"

test -f "README.md"
check "README.md existe"

test -d "models"
check "Directorio models/ existe"

test -d "views"
check "Directorio views/ existe"

test -d "security"
check "Directorio security/ existe"

echo ""

# 2. Verificar modelos Python
echo "2. Modelos Python"
echo "-----------------"

test -f "models/ml_label_template.py"
check "ml_label_template.py existe"

test -f "models/ml_label_processor.py"
check "ml_label_processor.py existe"

python3 -m py_compile models/*.py 2>/dev/null
check "Modelos compilan sin errores"

echo ""

# 3. Verificar vistas XML
echo "3. Vistas XML"
echo "-------------"

for xml_file in views/*.xml; do
    python3 -c "import xml.etree.ElementTree as ET; ET.parse('$xml_file')" 2>/dev/null
    check "$(basename $xml_file) es válido"
done

echo ""

# 4. Verificar dependencias Python
echo "4. Dependencias Python"
echo "----------------------"

python3 -c "import PyPDF2" 2>/dev/null
check "PyPDF2 instalado"

python3 -c "import reportlab" 2>/dev/null
check "reportlab instalado"

python3 -c "from pdf2image import convert_from_bytes" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} pdf2image instalado (opcional)"
    ((check_passed++))
else
    echo -e "${YELLOW}⚠${NC} pdf2image no instalado (opcional, para preview)"
fi

echo ""

# 5. Verificar seguridad
echo "5. Archivos de seguridad"
echo "------------------------"

test -f "security/ir.model.access.csv"
check "ir.model.access.csv existe"

test -f "security/ml_label_security.xml"
check "ml_label_security.xml existe"

echo ""

# 6. Resumen
echo "========================================="
echo "  RESUMEN"
echo "========================================="
echo -e "${GREEN}Pasados:${NC} $check_passed"
echo -e "${RED}Fallidos:${NC} $check_failed"
echo ""

if [ $check_failed -eq 0 ]; then
    echo -e "${GREEN}¡Módulo listo para instalar!${NC}"
    exit 0
else
    echo -e "${RED}Hay errores que corregir${NC}"
    exit 1
fi
