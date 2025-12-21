/** @odoo-module **/

/**
 * MercadoLibre Chat - Auto-scroll y mejoras de UX
 */

// Función para hacer scroll al último mensaje
function scrollToBottom(container, smooth = true) {
    if (container) {
        if (smooth) {
            container.scrollTo({
                top: container.scrollHeight,
                behavior: 'smooth'
            });
        } else {
            container.scrollTop = container.scrollHeight;
        }
    }
}

// Agregar botón de scroll to bottom
function addScrollButton(container) {
    const wrapper = container.closest('.ml-chat-wrapper');
    if (!wrapper) return;

    // Verificar si ya existe el botón
    if (wrapper.querySelector('.ml-chat-scroll-btn')) return;

    const btn = document.createElement('button');
    btn.className = 'ml-chat-scroll-btn';
    btn.innerHTML = '<i class="fa fa-chevron-down"></i>';
    btn.title = 'Ir al final';
    btn.onclick = () => scrollToBottom(container);

    wrapper.style.position = 'relative';
    wrapper.appendChild(btn);

    // Mostrar/ocultar botón según scroll position
    container.addEventListener('scroll', () => {
        const isAtBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
        btn.classList.toggle('visible', !isAtBottom);
    });

    // Verificar estado inicial
    const isAtBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
    btn.classList.toggle('visible', !isAtBottom);
}

// Inicializar chat container
function initChatContainer(container) {
    if (!container || container.dataset.mlChatInit) return;
    container.dataset.mlChatInit = 'true';

    // Scroll al final inmediatamente
    scrollToBottom(container, false);

    // Agregar botón de scroll
    addScrollButton(container);

    // Segundo intento con delay (por si el contenido tarda en cargar)
    setTimeout(() => scrollToBottom(container, false), 200);
    setTimeout(() => scrollToBottom(container, false), 500);
}

// Observador para detectar cuando se renderiza el chat
function initChatObserver() {
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.addedNodes.length) {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === 1) {
                        // Buscar contenedor de chat
                        const chatContainers = node.querySelectorAll?.('.ml-chat-container') || [];
                        chatContainers.forEach(initChatContainer);

                        if (node.classList?.contains('ml-chat-container')) {
                            initChatContainer(node);
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

    // Inicializar contenedores existentes
    document.querySelectorAll('.ml-chat-container').forEach(initChatContainer);
});

// También inicializar en load (para asegurar)
window.addEventListener('load', () => {
    document.querySelectorAll('.ml-chat-container').forEach(initChatContainer);
});

// Función global para refresh del chat
window.mlChatRefresh = function() {
    document.querySelectorAll('.ml-chat-container').forEach(container => {
        container.dataset.mlChatInit = '';
        initChatContainer(container);
    });
};

// Función global para scroll to bottom
window.mlChatScrollToBottom = function() {
    document.querySelectorAll('.ml-chat-container').forEach(container => {
        scrollToBottom(container);
    });
};

// Contador de caracteres en tiempo real
document.addEventListener('input', (e) => {
    if (e.target.matches('.ml-message-body, [name="body"], textarea[name="body"], .ml-chat-input, [name="quick_message"]')) {
        const textarea = e.target;
        const maxChars = 350;
        const currentChars = (textarea.value || textarea.textContent || '').length;

        // Buscar o crear contador
        let counter = textarea.parentElement.querySelector('.ml-chat-char-count');
        if (!counter) {
            counter = document.createElement('div');
            counter.className = 'ml-chat-char-count';
            counter.style.cssText = 'position: absolute; right: 70px; bottom: 18px; font-size: 11px;';
            const composeBar = textarea.closest('.ml-chat-compose-bar');
            if (composeBar) {
                composeBar.style.position = 'relative';
                composeBar.appendChild(counter);
            } else {
                textarea.parentElement.appendChild(counter);
            }
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

// ============================================
// Funcionalidad de Expandir Chat
// ============================================

function toggleChatExpand(wrapper) {
    if (!wrapper) return;

    const isExpanded = wrapper.classList.contains('expanded');

    if (isExpanded) {
        // Contraer
        wrapper.classList.remove('expanded');
        document.body.style.overflow = '';

        // Remover overlay
        const overlay = document.querySelector('.ml-chat-overlay');
        if (overlay) overlay.remove();

        // Cambiar icono
        const btn = wrapper.querySelector('.ml-chat-expand-btn i');
        if (btn) {
            btn.classList.remove('fa-compress');
            btn.classList.add('fa-expand');
        }
    } else {
        // Expandir
        wrapper.classList.add('expanded');
        document.body.style.overflow = 'hidden';

        // Crear overlay
        const overlay = document.createElement('div');
        overlay.className = 'ml-chat-overlay visible';
        overlay.onclick = () => toggleChatExpand(wrapper);
        document.body.appendChild(overlay);

        // Mover wrapper fuera del form si es necesario
        document.body.appendChild(wrapper);

        // Cambiar icono
        const btn = wrapper.querySelector('.ml-chat-expand-btn i');
        if (btn) {
            btn.classList.remove('fa-expand');
            btn.classList.add('fa-compress');
        }

        // Scroll al final
        const container = wrapper.querySelector('.ml-chat-container');
        if (container) {
            setTimeout(() => scrollToBottom(container, false), 100);
        }
    }
}

// Event listener para botón de expandir
document.addEventListener('click', (e) => {
    const expandBtn = e.target.closest('.ml-chat-expand-btn');
    if (expandBtn) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        const wrapper = expandBtn.closest('.ml-chat-main-wrapper');
        if (wrapper) {
            toggleChatExpand(wrapper);
        }
        return false;
    }
});

// Cerrar con tecla Escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const expandedWrapper = document.querySelector('.ml-chat-main-wrapper.expanded');
        if (expandedWrapper) {
            toggleChatExpand(expandedWrapper);
        }
    }
});

// Enviar mensaje con Enter (Shift+Enter para nueva línea)
document.addEventListener('keydown', (e) => {
    if (e.target.matches('.ml-chat-input, [name="quick_message"]')) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            // Buscar y hacer click en el botón de enviar
            const composeBar = e.target.closest('.ml-chat-compose-bar');
            if (composeBar) {
                const sendBtn = composeBar.querySelector('.ml-chat-send-btn');
                if (sendBtn) {
                    sendBtn.click();
                }
            }
        }
    }
});

// Detectar cambios de pestaña en el notebook de Odoo
document.addEventListener('click', (e) => {
    if (e.target.matches('.nav-link, .o_notebook_headers a, [data-bs-toggle="tab"]')) {
        // Pequeño delay para que se renderice el contenido
        setTimeout(() => {
            document.querySelectorAll('.ml-chat-container').forEach(container => {
                if (container.offsetParent !== null) { // Solo si es visible
                    initChatContainer(container);
                }
            });
        }, 100);
    }
});

// ============================================
// Lightbox para Imágenes
// ============================================

function openLightbox(imgSrc) {
    // Crear lightbox
    const lightbox = document.createElement('div');
    lightbox.className = 'ml-chat-lightbox';
    lightbox.innerHTML = `
        <span class="ml-chat-lightbox-close">&times;</span>
        <img src="${imgSrc}" alt="Imagen ampliada"/>
    `;

    // Cerrar al hacer click
    lightbox.onclick = () => lightbox.remove();

    document.body.appendChild(lightbox);
}

// Event listener para imágenes del chat
document.addEventListener('click', (e) => {
    const attachment = e.target.closest('.ml-chat-attachment');
    if (attachment) {
        e.preventDefault();
        const img = attachment.querySelector('img');
        if (img) {
            openLightbox(img.src);
        }
    }
});

// Exportar para uso en módulos OWL
export const mlChatUtils = {
    scrollToBottom,
    initChatContainer,
    initChatObserver,
    openLightbox,
};
