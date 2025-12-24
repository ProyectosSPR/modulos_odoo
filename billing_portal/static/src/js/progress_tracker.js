/**
 * Progress Tracker Component
 *
 * Handles real-time progress tracking for billing requests,
 * including auto-refresh and status updates.
 *
 * This is a vanilla JS component, not an Odoo module.
 */

const ProgressTracker = {
    // Configuration
    config: {
        requestId: null,
        progressBarSelector: '#progressBar',
        progressPercentSelector: '#progressPercent',
        statusMessageSelector: '#statusMessage',
        statusTitleSelector: '#statusTitle',
        statusDetailSelector: '#statusDetail',
        refreshInterval: 3000,
        maxRefreshAttempts: 100,
    },

    // State
    state: {
        isTracking: false,
        refreshTimer: null,
        refreshAttempts: 0,
        lastStatus: null,
    },

    // Status configurations
    statusConfig: {
        draft: {
            class: 'alert-info',
            icon: 'fa-hourglass-start',
            title: 'Iniciando...',
        },
        validating: {
            class: 'alert-info',
            icon: 'fa-spinner fa-spin',
            title: 'Validando CSF...',
        },
        csf_validated: {
            class: 'alert-info',
            icon: 'fa-check',
            title: 'CSF Validado',
        },
        creating_partner: {
            class: 'alert-info',
            icon: 'fa-spinner fa-spin',
            title: 'Creando Cliente...',
        },
        creating_invoice: {
            class: 'alert-info',
            icon: 'fa-spinner fa-spin',
            title: 'Creando Factura...',
        },
        pending_stamp: {
            class: 'alert-warning',
            icon: 'fa-clock-o',
            title: 'Pendiente de Timbrado',
        },
        done: {
            class: 'alert-success',
            icon: 'fa-check-circle',
            title: 'Completado',
        },
        error: {
            class: 'alert-danger',
            icon: 'fa-exclamation-circle',
            title: 'Error',
        },
        cancelled: {
            class: 'alert-secondary',
            icon: 'fa-ban',
            title: 'Cancelado',
        },
    },

    /**
     * Initialize the tracker
     * @param {object} options - Configuration options
     */
    init(options = {}) {
        this.config = { ...this.config, ...options };

        // Get request ID from data attribute or options
        const container = document.querySelector('[data-request-id]');
        if (container) {
            this.config.requestId = parseInt(container.dataset.requestId);
        }

        this.progressBar = document.querySelector(this.config.progressBarSelector);
        this.progressPercent = document.querySelector(this.config.progressPercentSelector);
        this.statusMessage = document.querySelector(this.config.statusMessageSelector);
        this.statusTitle = document.querySelector(this.config.statusTitleSelector);
        this.statusDetail = document.querySelector(this.config.statusDetailSelector);

        if (this.config.requestId) {
            this.startTracking();
        }
    },

    /**
     * Start tracking progress
     */
    startTracking() {
        if (this.state.isTracking) return;

        this.state.isTracking = true;
        this.state.refreshAttempts = 0;

        // Initial fetch
        this.fetchStatus();

        // Set up interval for auto-refresh
        this.scheduleNextRefresh();
    },

    /**
     * Stop tracking progress
     */
    stopTracking() {
        this.state.isTracking = false;
        if (this.state.refreshTimer) {
            clearTimeout(this.state.refreshTimer);
            this.state.refreshTimer = null;
        }
    },

    /**
     * Schedule next status refresh
     */
    scheduleNextRefresh() {
        if (!this.state.isTracking) return;

        // Check if we've reached max attempts
        if (this.state.refreshAttempts >= this.config.maxRefreshAttempts) {
            console.log('Max refresh attempts reached');
            this.stopTracking();
            return;
        }

        // Check if status is final
        const finalStates = ['done', 'error', 'cancelled'];
        if (this.state.lastStatus && finalStates.includes(this.state.lastStatus.state)) {
            console.log('Final state reached, stopping refresh');
            this.stopTracking();
            return;
        }

        this.state.refreshTimer = setTimeout(() => {
            this.fetchStatus();
            this.scheduleNextRefresh();
        }, this.config.refreshInterval);
    },

    /**
     * Fetch current status from backend
     */
    async fetchStatus() {
        if (!this.config.requestId) return;

        this.state.refreshAttempts++;

        try {
            const result = await BillingPortal.rpc(`request-status/${this.config.requestId}`, {});

            if (result.success) {
                this.updateDisplay(result.status);
                this.state.lastStatus = result.status;
                this.dispatchEvent('progress:updated', { status: result.status });
            }
        } catch (error) {
            console.error('Error fetching status:', error);
        }
    },

    /**
     * Update display with new status
     * @param {object} status - Status data
     */
    updateDisplay(status) {
        // Update progress bar
        if (this.progressBar) {
            this.progressBar.style.width = `${status.progress}%`;
            this.progressBar.setAttribute('aria-valuenow', status.progress);

            // Update color based on state
            this.progressBar.classList.remove('bg-danger', 'bg-warning', 'bg-success', 'bg-info');
            if (status.state === 'error') {
                this.progressBar.classList.add('bg-danger');
            } else if (status.state === 'pending_stamp') {
                this.progressBar.classList.add('bg-warning');
            } else if (status.state === 'done') {
                this.progressBar.classList.add('bg-success');
            }
        }

        // Update progress percentage
        if (this.progressPercent) {
            this.progressPercent.textContent = status.progress;
        }

        // Update status message container
        if (this.statusMessage) {
            const config = this.statusConfig[status.state] || this.statusConfig.draft;

            // Update classes
            this.statusMessage.className = `status-message mb-4 p-3 rounded alert ${config.class}`;
        }

        // Update status title
        if (this.statusTitle) {
            const config = this.statusConfig[status.state] || this.statusConfig.draft;
            this.statusTitle.textContent = config.title;
        }

        // Update status detail
        if (this.statusDetail) {
            this.statusDetail.textContent = status.status_message || status.error_message || '';
        }

        // Update step indicators
        this.updateStepIndicators(status);

        // Update invoice info if available
        if (status.invoice_name) {
            this.showInvoiceInfo(status);
        }

        // Show error details if in error state
        if (status.state === 'error' && status.error_message) {
            this.showErrorDetails(status.error_message);
        }
    },

    /**
     * Update step indicators
     * @param {object} status - Status data
     */
    updateStepIndicators(status) {
        const steps = [
            { element: '.step-csf', progress: 10, activeState: 'validating' },
            { element: '.step-partner', progress: 40, activeState: 'creating_partner' },
            { element: '.step-invoice', progress: 60, activeState: 'creating_invoice' },
            { element: '.step-stamp', progress: 80, activeState: 'pending_stamp' },
            { element: '.step-done', progress: 100, activeState: 'done' },
        ];

        steps.forEach(step => {
            const el = document.querySelector(step.element);
            if (!el) return;

            const icon = el.querySelector('i, .spinner-border');
            const isCompleted = status.progress >= step.progress;
            const isActive = status.state === step.activeState;

            // Update classes
            el.classList.remove('list-group-item-success', 'list-group-item-warning');
            if (isCompleted) {
                el.classList.add('list-group-item-success');
            } else if (isActive) {
                el.classList.add('list-group-item-warning');
            }

            // Update icon
            if (icon) {
                if (isCompleted) {
                    icon.className = 'fa fa-check-circle text-success me-3';
                } else if (isActive) {
                    icon.className = 'spinner-border spinner-border-sm text-primary me-3';
                } else {
                    icon.className = 'fa fa-circle text-muted me-3';
                }
            }
        });
    },

    /**
     * Show invoice information
     * @param {object} status - Status with invoice info
     */
    showInvoiceInfo(status) {
        let invoiceInfo = document.getElementById('invoice-info');
        if (!invoiceInfo) {
            invoiceInfo = document.createElement('div');
            invoiceInfo.id = 'invoice-info';
            invoiceInfo.className = 'alert alert-success mt-4';

            const container = document.querySelector('.process-steps');
            if (container) {
                container.after(invoiceInfo);
            }
        }

        invoiceInfo.innerHTML = `
            <h6 class="alert-heading">
                <i class="fa fa-file-invoice me-2"></i>
                Factura Generada
            </h6>
            <p class="mb-0">
                Número de factura: <strong>${status.invoice_name}</strong>
            </p>
            ${status.state === 'pending_stamp' ? `
                <hr>
                <p class="mb-0 small">
                    La factura será enviada al email registrado una vez que sea timbrada por el área de contabilidad.
                </p>
            ` : ''}
        `;
    },

    /**
     * Show error details
     * @param {string} errorMessage - Error message
     */
    showErrorDetails(errorMessage) {
        let errorBox = document.getElementById('error-details');
        if (!errorBox) {
            errorBox = document.createElement('div');
            errorBox.id = 'error-details';
            errorBox.className = 'alert alert-danger mt-4';

            const container = document.querySelector('.process-steps');
            if (container) {
                container.after(errorBox);
            }
        }

        errorBox.innerHTML = `
            <h6 class="alert-heading">
                <i class="fa fa-exclamation-triangle me-2"></i>
                Detalle del Error
            </h6>
            <p class="mb-0">${errorMessage}</p>
            <hr>
            <div class="d-flex gap-2">
                <button type="button" class="btn btn-outline-danger btn-sm" onclick="location.reload()">
                    <i class="fa fa-refresh me-1"></i> Reintentar
                </button>
                <a href="/portal/billing/orders" class="btn btn-outline-secondary btn-sm">
                    <i class="fa fa-arrow-left me-1"></i> Volver
                </a>
            </div>
        `;
    },

    /**
     * Manually refresh status
     */
    refresh() {
        this.fetchStatus();
    },

    /**
     * Get current status
     * @returns {object|null} Current status
     */
    getStatus() {
        return this.state.lastStatus;
    },

    /**
     * Dispatch custom event
     * @param {string} eventName - Event name
     * @param {object} detail - Event detail
     */
    dispatchEvent(eventName, detail = {}) {
        const event = new CustomEvent(eventName, {
            detail: detail,
            bubbles: true,
        });
        document.dispatchEvent(event);
    },
};

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Check if we're on a progress page
    const progressContainer = document.querySelector('[data-request-id]');
    if (progressContainer) {
        ProgressTracker.init();
    }
});

// Export
window.ProgressTracker = ProgressTracker;
