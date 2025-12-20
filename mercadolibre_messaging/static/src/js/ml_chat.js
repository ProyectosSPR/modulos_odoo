/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useEffect, useRef } from "@odoo/owl";

/**
 * MercadoLibre Chat - Auto-scroll y mejoras de UX
 */

// Función para hacer scroll al último mensaje
function scrollToBottom(container) {
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

// Observador para detectar cuando se renderiza el chat
function initChatObserver() {
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.addedNodes.length) {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === 1) {
                        // Buscar contenedor de chat
                        const chatContainer = node.querySelector?.('.ml-chat-container') ||
                                            (node.classList?.contains('ml-chat-container') ? node : null);
                        if (chatContainer) {
                            // Pequeño delay para asegurar que el contenido está renderizado
                            setTimeout(() => scrollToBottom(chatContainer), 100);
                        }
                    }
                });
            }
        });
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true
    });

    return observer;
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    initChatObserver();

    // También intentar scroll en contenedores existentes
    document.querySelectorAll('.ml-chat-container').forEach(scrollToBottom);
});

// Re-inicializar cuando Odoo navega entre vistas
if (window.odoo && window.odoo.define) {
    window.odoo.define('mercadolibre_messaging.chat_scroll', function (require) {
        'use strict';

        const publicWidget = require('web.public.widget');
        const core = require('web.core');

        // Widget para auto-scroll del chat
        publicWidget.registry.MLChatScroll = publicWidget.Widget.extend({
            selector: '.ml-chat-container',

            start: function () {
                this._super.apply(this, arguments);
                this._scrollToBottom();
                return Promise.resolve();
            },

            _scrollToBottom: function () {
                this.$el.scrollTop(this.$el[0].scrollHeight);
            },
        });

        return publicWidget.registry.MLChatScroll;
    });
}

// Función global para refresh del chat (útil para llamar desde otros scripts)
window.mlChatRefresh = function() {
    document.querySelectorAll('.ml-chat-container').forEach(scrollToBottom);
};

// Contador de caracteres en tiempo real
document.addEventListener('input', (e) => {
    if (e.target.matches('.ml-message-body, [name="body"]')) {
        const textarea = e.target;
        const maxChars = 350;
        const currentChars = textarea.value.length;

        // Buscar o crear contador
        let counter = textarea.parentElement.querySelector('.ml-chat-char-count');
        if (!counter) {
            counter = document.createElement('div');
            counter.className = 'ml-chat-char-count';
            textarea.parentElement.appendChild(counter);
        }

        counter.textContent = `${currentChars}/${maxChars}`;

        // Cambiar color según caracteres
        counter.classList.remove('warning', 'danger');
        if (currentChars > maxChars) {
            counter.classList.add('danger');
        } else if (currentChars > maxChars * 0.9) {
            counter.classList.add('warning');
        }
    }
});

// Exportar para uso en módulos OWL
export const mlChatUtils = {
    scrollToBottom,
    initChatObserver,
};
