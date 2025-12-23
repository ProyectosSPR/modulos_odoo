-- Script SQL para limpiar instalación fallida de mercadolibre_label_editor
-- USAR SOLO SI LA INSTALACIÓN FALLÓ Y NECESITAS REINSTALAR

-- IMPORTANTE: Reemplaza 'tu_base_de_datos' con el nombre real de tu base de datos
-- Ejecutar como usuario postgres:
-- psql -U odoo tu_base_de_datos < fix_installation.sql

-- 1. Eliminar el módulo de la tabla ir_module_module
DELETE FROM ir_module_module WHERE name = 'mercadolibre_label_editor';

-- 2. Eliminar vistas creadas (si existen)
DELETE FROM ir_ui_view WHERE model IN ('ml.label.template', 'ml.label.template.field', 'ml.label.preview.wizard');

-- 3. Eliminar modelos de la tabla ir_model
DELETE FROM ir_model WHERE model IN ('ml.label.template', 'ml.label.template.field', 'ml.label.processor', 'ml.label.preview.wizard');

-- 4. Eliminar campos de la tabla ir_model_fields
DELETE FROM ir_model_fields WHERE model IN ('ml.label.template', 'ml.label.template.field', 'ml.label.processor', 'ml.label.preview.wizard');

-- 5. Eliminar permisos de acceso
DELETE FROM ir_model_access WHERE model_id IN (
    SELECT id FROM ir_model WHERE model IN ('ml.label.template', 'ml.label.template.field', 'ml.label.processor', 'ml.label.preview.wizard')
);

-- 6. Eliminar menús
DELETE FROM ir_ui_menu WHERE name = 'Plantillas de Etiqueta';

-- 7. Eliminar acciones
DELETE FROM ir_act_window WHERE res_model IN ('ml.label.template', 'ml.label.template.field', 'ml.label.preview.wizard');

-- 8. Limpiar grupos de seguridad
DELETE FROM res_groups WHERE name IN ('Usuario de Etiquetas ML', 'Administrador de Etiquetas ML');

-- Listo! Ahora puedes intentar instalar el módulo nuevamente desde la interfaz de Odoo
