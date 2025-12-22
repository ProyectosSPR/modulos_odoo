/** @odoo-module **/

/**
 * Validación del formulario de búsqueda de invitados
 */

console.log('🎬 guest_form.js cargado');

// Ejecutar cuando el DOM esté listo
(function() {
    'use strict';

    function initGuestForm() {
        console.log('🔧 initGuestForm() ejecutado');
        console.log('  🕐 Timestamp:', new Date().toISOString());

        const form = document.getElementById('guestSearchForm');
        const input = document.getElementById('order_ref');
        const btn = document.getElementById('btnSearchGuest');

        console.log('🔍 Buscando elementos del formulario...');
        console.log('  - Formulario:', !!form, form);
        console.log('  - Input:', !!input, input);
        console.log('  - Input.value:', input ? input.value : 'NULL');
        console.log('  - Input.name:', input ? input.name : 'NULL');
        console.log('  - Botón:', !!btn, btn);

        if (!form) {
            console.warn('⚠️ Formulario #guestSearchForm NO encontrado');
            return;
        }

        if (!input) {
            console.warn('⚠️ Input #order_ref NO encontrado');
            return;
        }

        console.log('✅ Elementos encontrados, agregando event listeners...');

        // Log cuando se escribe en el input
        input.addEventListener('input', function(e) {
            console.log('⌨️ INPUT EVENT - Valor:', e.target.value);
        });

        // Log cuando el input gana el foco
        input.addEventListener('focus', function(e) {
            console.log('🎯 FOCUS EVENT - Valor:', e.target.value);
        });

        // Log cuando el input pierde el foco
        input.addEventListener('blur', function(e) {
            console.log('👁️ BLUR EVENT - Valor:', e.target.value);
        });

        // Log cuando cambia el valor
        input.addEventListener('change', function(e) {
            console.log('🔄 CHANGE EVENT - Valor:', e.target.value);
        });

        // Validación en submit (ESTE NO SE ESTÁ EJECUTANDO)
        form.addEventListener('submit', function(e) {
            console.log('📝 addEventListener SUBMIT EVENT DETECTADO!');
            console.log('  🕐 Timestamp:', new Date().toISOString());

            const value = input.value.trim();
            console.log('  📦 Valor del input:', value);
            console.log('  📏 Longitud:', value.length);
            console.log('  🔢 Tipo:', typeof value);

            if (!value || value.length < 3) {
                console.error('  ❌ VALIDACIÓN FALLIDA - Valor inválido');
                console.error('  🚫 Previniendo submit del formulario');

                e.preventDefault();
                e.stopPropagation();

                alert('addEventListener: Por favor ingrese al menos 3 caracteres para buscar');
                return false;
            }

            console.log('  ✅ Validación OK, permitiendo submit');
            console.log('  🚀 Formulario se enviará al servidor');
        }, true); // Use capture phase

        // NUEVO: Agregar listener al botón también
        if (btn) {
            btn.addEventListener('click', function(e) {
                console.log('🖱️ BUTTON CLICK EVENT DETECTADO!');
                console.log('  📦 Valor del input en este momento:', input.value);
                console.log('  📏 Longitud:', input.value.length);

                // Validar aquí también
                const value = input.value.trim();
                if (!value || value.length < 3) {
                    console.error('  ❌ CLICK VALIDATION FAILED');
                    e.preventDefault();
                    e.stopPropagation();
                    alert('Click handler: Por favor ingrese al menos 3 caracteres');
                    return false;
                }
                console.log('  ✅ Click validation OK');
            });
        }

        console.log('✅ Event listeners agregados correctamente');

        // Log form attributes
        console.log('📋 Atributos del formulario:');
        console.log('  - action:', form.action);
        console.log('  - method:', form.method);
        console.log('  - onsubmit:', form.onsubmit);

        // Test: intentar enfocar el input
        setTimeout(function() {
            console.log('🎯 Auto-focus en el input...');
            input.focus();
        }, 100);
    }

    // Intentar inicializar inmediatamente
    if (document.readyState === 'loading') {
        console.log('⏳ DOM aún cargando, esperando DOMContentLoaded...');
        document.addEventListener('DOMContentLoaded', initGuestForm);
    } else {
        console.log('✅ DOM ya cargado, inicializando inmediatamente...');
        initGuestForm();
    }

    // Backup: intentar después de un timeout
    setTimeout(function() {
        console.log('🔄 Timeout de seguridad - re-intentando inicialización...');
        initGuestForm();
    }, 1000);

})();
