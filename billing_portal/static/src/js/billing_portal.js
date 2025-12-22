/**
 * Billing Portal - Main JavaScript Module
 *
 * Provides core functionality for the billing portal including:
 * - RPC communication with Odoo backend
 * - Common utilities and helpers
 * - Event management
 *
 * This is a vanilla JS component, not an Odoo module.
 */

const BillingPortal = {
    // API base URL
    apiBase: '/portal/billing/api',

    // Cache for catalogs
    _catalogs: null,

    /**
     * Make a JSON RPC call to the backend
     * @param {string} endpoint - API endpoint
     * @param {object} params - Request parameters
     * @returns {Promise<object>} Response data
     */
    async rpc(endpoint, params = {}) {
        const url = endpoint.startsWith('/') ? endpoint : `${this.apiBase}/${endpoint}`;

        console.log('🔌 RPC CALL INICIADA');
        console.log('  📍 URL:', url);
        console.log('  📦 Params:', params);

        try {
            const requestBody = {
                jsonrpc: '2.0',
                method: 'call',
                params: params,
                id: Math.floor(Math.random() * 1000000000),
            };

            console.log('  📤 Request body:', requestBody);

            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody),
            });

            console.log('  📥 Response status:', response.status);

            if (!response.ok) {
                console.error('  ❌ HTTP error:', response.status);
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log('  📥 Response data:', data);

            if (data.error) {
                console.error('  ❌ RPC error:', data.error);
                throw new Error(data.error.data?.message || data.error.message || 'Error desconocido');
            }

            console.log('  ✅ RPC exitoso, resultado:', data.result);
            return data.result;
        } catch (error) {
            console.error('❌ RPC Error:', error);
            console.error('  Stack:', error.stack);
            throw error;
        }
    },

    /**
     * Load catalogs from backend (cached)
     * @returns {Promise<object>} Catalog data
     */
    async loadCatalogs() {
        if (this._catalogs) {
            return this._catalogs;
        }

        const result = await this.rpc('catalogs');
        if (result.success) {
            this._catalogs = result;
        }
        return result;
    },

    /**
     * Format currency amount
     * @param {number} amount - Amount to format
     * @param {string} currency - Currency code (default: MXN)
     * @returns {string} Formatted amount
     */
    formatCurrency(amount, currency = 'MXN') {
        return new Intl.NumberFormat('es-MX', {
            style: 'currency',
            currency: currency,
        }).format(amount);
    },

    /**
     * Format date
     * @param {string} dateStr - Date string
     * @param {object} options - Intl.DateTimeFormat options
     * @returns {string} Formatted date
     */
    formatDate(dateStr, options = {}) {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        return new Intl.DateTimeFormat('es-MX', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            ...options,
        }).format(date);
    },

    /**
     * Show a toast notification
     * @param {string} message - Message to display
     * @param {string} type - Type: 'success', 'error', 'warning', 'info'
     * @param {number} duration - Duration in ms (default: 5000)
     */
    showToast(message, type = 'info', duration = 5000) {
        // Create toast container if not exists
        let container = document.getElementById('billing-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'billing-toast-container';
            container.className = 'position-fixed top-0 end-0 p-3';
            container.style.zIndex = '9999';
            document.body.appendChild(container);
        }

        // Create toast element
        const toastId = `toast-${Date.now()}`;
        const iconMap = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle',
        };
        const bgMap = {
            success: 'bg-success',
            error: 'bg-danger',
            warning: 'bg-warning',
            info: 'bg-info',
        };

        const toast = document.createElement('div');
        toast.id = toastId;
        toast.className = `toast show ${bgMap[type]} text-white`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="toast-body d-flex align-items-center">
                <i class="fa ${iconMap[type]} me-2"></i>
                <span>${message}</span>
                <button type="button" class="btn-close btn-close-white ms-auto" data-bs-dismiss="toast"></button>
            </div>
        `;

        container.appendChild(toast);

        // Auto-hide
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, duration);

        // Close button handler
        toast.querySelector('.btn-close').addEventListener('click', () => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        });
    },

    /**
     * Show loading overlay
     * @param {string} message - Loading message
     */
    showLoading(message = 'Cargando...') {
        let overlay = document.getElementById('billing-loading-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'billing-loading-overlay';
            overlay.className = 'position-fixed top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center';
            overlay.style.cssText = 'background: rgba(0,0,0,0.5); z-index: 9998;';
            overlay.innerHTML = `
                <div class="bg-white rounded p-4 text-center">
                    <div class="spinner-border text-primary mb-3" role="status"></div>
                    <p class="mb-0" id="loading-message">${message}</p>
                </div>
            `;
            document.body.appendChild(overlay);
        } else {
            document.getElementById('loading-message').textContent = message;
            overlay.style.display = 'flex';
        }
    },

    /**
     * Hide loading overlay
     */
    hideLoading() {
        const overlay = document.getElementById('billing-loading-overlay');
        if (overlay) {
            overlay.style.display = 'none';
        }
    },

    /**
     * Validate RFC format
     * @param {string} rfc - RFC to validate
     * @returns {boolean} True if valid
     */
    validateRFC(rfc) {
        if (!rfc) return false;
        // RFC format: 3-4 letters + 6 digits + 3 alphanumeric
        const rfcRegex = /^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$/i;
        return rfcRegex.test(rfc.trim());
    },

    /**
     * Validate email format
     * @param {string} email - Email to validate
     * @returns {boolean} True if valid
     */
    validateEmail(email) {
        if (!email) return false;
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email.trim());
    },

    /**
     * Validate Mexican postal code
     * @param {string} cp - Postal code to validate
     * @returns {boolean} True if valid
     */
    validatePostalCode(cp) {
        if (!cp) return false;
        return /^\d{5}$/.test(cp.trim());
    },

    /**
     * Debounce function calls
     * @param {Function} func - Function to debounce
     * @param {number} wait - Wait time in ms
     * @returns {Function} Debounced function
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    /**
     * Initialize module on DOM ready
     */
    init() {
        console.log('🚀 BillingPortal.init() ejecutado');
        console.log('📍 URL actual:', window.location.href);
        console.log('📦 BillingPortal object:', this);

        // Add global event listeners
        document.addEventListener('DOMContentLoaded', () => {
            console.log('✅ DOM cargado completamente');
            console.log('📄 Document ready event fired');
            // Initialize any global components
            this.initTooltips();
        });
    },

    /**
     * Initialize Bootstrap tooltips
     */
    initTooltips() {
        const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
        tooltips.forEach(el => {
            if (typeof bootstrap !== 'undefined') {
                new bootstrap.Tooltip(el);
            }
        });
    },
};

// Initialize on load
BillingPortal.init();

// Export for use in other modules
window.BillingPortal = BillingPortal;
