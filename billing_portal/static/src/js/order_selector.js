/** @odoo-module **/

/**
 * Order Selector Component
 *
 * Handles order search, selection, and multi-order invoicing
 * for the billing portal.
 */

const OrderSelector = {
    // Configuration
    config: {
        searchInputSelector: '#order-search-input',
        searchButtonSelector: '#btn-search-orders',
        orderListSelector: '#order-list',
        selectedOrdersSelector: '#selected-orders',
        totalAmountSelector: '#total-amount',
        orderCountSelector: '#order-count',
        minSearchLength: 3,
        searchDebounceMs: 500,
    },

    // State
    state: {
        orders: [],
        selectedOrders: new Map(),
        searchTerm: '',
        isLoading: false,
    },

    /**
     * Initialize the component
     * @param {object} options - Custom options
     */
    init(options = {}) {
        this.config = { ...this.config, ...options };

        this.searchInput = document.querySelector(this.config.searchInputSelector);
        this.searchButton = document.querySelector(this.config.searchButtonSelector);
        this.orderList = document.querySelector(this.config.orderListSelector);
        this.selectedOrdersEl = document.querySelector(this.config.selectedOrdersSelector);
        this.totalAmountEl = document.querySelector(this.config.totalAmountSelector);
        this.orderCountEl = document.querySelector(this.config.orderCountSelector);

        if (!this.searchInput || !this.orderList) {
            console.warn('Order Selector: Required elements not found');
            return;
        }

        this.bindEvents();
    },

    /**
     * Bind event listeners
     */
    bindEvents() {
        // Search on input (debounced)
        const debouncedSearch = BillingPortal.debounce(() => this.performSearch(), this.config.searchDebounceMs);
        this.searchInput.addEventListener('input', debouncedSearch);

        // Search on Enter
        this.searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.performSearch();
            }
        });

        // Search button click
        if (this.searchButton) {
            this.searchButton.addEventListener('click', () => this.performSearch());
        }

        // Delegate click events for order checkboxes
        this.orderList.addEventListener('change', (e) => {
            if (e.target.matches('.order-checkbox')) {
                this.handleOrderToggle(e.target);
            }
        });

        // Select all checkbox
        const selectAllCheckbox = document.getElementById('select-all-orders');
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', (e) => this.toggleSelectAll(e.target.checked));
        }
    },

    /**
     * Perform order search
     */
    async performSearch() {
        const searchTerm = this.searchInput.value.trim();

        if (searchTerm.length < this.config.minSearchLength) {
            BillingPortal.showToast(`Ingrese al menos ${this.config.minSearchLength} caracteres`, 'warning');
            return;
        }

        this.state.searchTerm = searchTerm;
        this.state.isLoading = true;
        this.showLoadingState();

        try {
            const result = await BillingPortal.rpc('search-orders', {
                search: searchTerm,
            });

            this.state.isLoading = false;

            if (result.success) {
                this.state.orders = result.orders;
                this.renderOrders(result.orders);

                if (result.orders.length === 0) {
                    BillingPortal.showToast('No se encontraron órdenes', 'info');
                }
            } else {
                this.renderError(result.errors);
            }
        } catch (error) {
            this.state.isLoading = false;
            console.error('Search error:', error);
            this.renderError([error.message]);
        }
    },

    /**
     * Show loading state
     */
    showLoadingState() {
        this.orderList.innerHTML = `
            <div class="text-center py-5">
                <div class="spinner-border text-primary mb-3"></div>
                <p class="text-muted">Buscando órdenes...</p>
            </div>
        `;
    },

    /**
     * Render orders list
     * @param {Array} orders - Orders to render
     */
    renderOrders(orders) {
        if (orders.length === 0) {
            this.orderList.innerHTML = `
                <div class="text-center py-5">
                    <i class="fa fa-search fa-3x text-muted mb-3"></i>
                    <p class="text-muted">No se encontraron órdenes con "${this.state.searchTerm}"</p>
                </div>
            `;
            return;
        }

        let html = `
            <div class="table-responsive">
                <table class="table table-hover">
                    <thead>
                        <tr>
                            <th width="40">
                                <input type="checkbox" class="form-check-input" id="select-all-orders">
                            </th>
                            <th>Referencia</th>
                            <th>Orden</th>
                            <th>Fecha</th>
                            <th>Estado</th>
                            <th class="text-end">Total</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        orders.forEach(order => {
            const isSelected = this.state.selectedOrders.has(order.id);
            const statusBadge = this.getStatusBadge(order);

            html += `
                <tr class="${isSelected ? 'table-primary' : ''}" data-order-id="${order.id}">
                    <td>
                        <input type="checkbox"
                               class="form-check-input order-checkbox"
                               data-order-id="${order.id}"
                               ${isSelected ? 'checked' : ''}
                               ${!order.is_billable ? 'disabled' : ''}>
                    </td>
                    <td>
                        <strong>${order.client_order_ref || '-'}</strong>
                        ${order.ml_order_id ? `<br><small class="text-muted">ML: ${order.ml_order_id}</small>` : ''}
                    </td>
                    <td>
                        <code>${order.name}</code>
                    </td>
                    <td>
                        ${BillingPortal.formatDate(order.date_order)}
                    </td>
                    <td>
                        ${statusBadge}
                    </td>
                    <td class="text-end">
                        <strong>${BillingPortal.formatCurrency(order.amount_total)}</strong>
                    </td>
                </tr>
            `;
        });

        html += `
                    </tbody>
                </table>
            </div>
        `;

        this.orderList.innerHTML = html;

        // Re-bind select all checkbox
        const selectAllCheckbox = document.getElementById('select-all-orders');
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', (e) => this.toggleSelectAll(e.target.checked));
        }
    },

    /**
     * Get status badge HTML for order
     * @param {object} order - Order data
     * @returns {string} HTML string
     */
    getStatusBadge(order) {
        if (!order.is_billable) {
            return '<span class="badge bg-secondary">No facturable</span>';
        }

        const shipmentStatus = {
            'pending': '<span class="badge bg-warning">Pendiente envío</span>',
            'shipped': '<span class="badge bg-info">En tránsito</span>',
            'delivered': '<span class="badge bg-success">Entregado</span>',
            'cancelled': '<span class="badge bg-danger">Cancelado</span>',
        };

        if (order.ml_shipment_status) {
            return shipmentStatus[order.ml_shipment_status] || '';
        }

        const invoiceStatus = {
            'no': '<span class="badge bg-warning">Sin facturar</span>',
            'to invoice': '<span class="badge bg-info">Por facturar</span>',
            'invoiced': '<span class="badge bg-success">Facturado</span>',
        };

        return invoiceStatus[order.invoice_status] || '';
    },

    /**
     * Handle order checkbox toggle
     * @param {HTMLInputElement} checkbox - Checkbox element
     */
    handleOrderToggle(checkbox) {
        const orderId = parseInt(checkbox.dataset.orderId);
        const order = this.state.orders.find(o => o.id === orderId);

        if (!order) return;

        if (checkbox.checked) {
            this.state.selectedOrders.set(orderId, order);
        } else {
            this.state.selectedOrders.delete(orderId);
        }

        this.updateSelectedDisplay();
        this.dispatchEvent('order:selection-changed', { selectedOrders: this.getSelectedOrders() });
    },

    /**
     * Toggle select all orders
     * @param {boolean} selectAll - Whether to select all
     */
    toggleSelectAll(selectAll) {
        const checkboxes = this.orderList.querySelectorAll('.order-checkbox:not(:disabled)');

        checkboxes.forEach(checkbox => {
            const orderId = parseInt(checkbox.dataset.orderId);
            const order = this.state.orders.find(o => o.id === orderId);

            if (selectAll && order) {
                checkbox.checked = true;
                this.state.selectedOrders.set(orderId, order);
            } else {
                checkbox.checked = false;
                this.state.selectedOrders.delete(orderId);
            }
        });

        this.updateSelectedDisplay();
        this.dispatchEvent('order:selection-changed', { selectedOrders: this.getSelectedOrders() });
    },

    /**
     * Update selected orders display
     */
    updateSelectedDisplay() {
        const count = this.state.selectedOrders.size;
        let total = 0;

        this.state.selectedOrders.forEach(order => {
            total += order.amount_total;
        });

        // Update count
        if (this.orderCountEl) {
            this.orderCountEl.textContent = count;
        }

        // Update total
        if (this.totalAmountEl) {
            this.totalAmountEl.textContent = BillingPortal.formatCurrency(total);
        }

        // Update selected orders list
        if (this.selectedOrdersEl) {
            if (count === 0) {
                this.selectedOrdersEl.innerHTML = `
                    <div class="text-muted text-center py-3">
                        <i class="fa fa-info-circle me-2"></i>
                        Seleccione órdenes para facturar
                    </div>
                `;
            } else {
                let html = '<ul class="list-group list-group-flush">';
                this.state.selectedOrders.forEach(order => {
                    html += `
                        <li class="list-group-item d-flex justify-content-between align-items-center py-2">
                            <span>
                                <strong>${order.client_order_ref || order.name}</strong>
                            </span>
                            <span class="text-muted">
                                ${BillingPortal.formatCurrency(order.amount_total)}
                            </span>
                        </li>
                    `;
                });
                html += '</ul>';
                this.selectedOrdersEl.innerHTML = html;
            }
        }

        // Enable/disable continue button
        const continueBtn = document.getElementById('btn-continue-billing');
        if (continueBtn) {
            continueBtn.disabled = count === 0;
        }
    },

    /**
     * Render error state
     * @param {Array} errors - Error messages
     */
    renderError(errors) {
        this.orderList.innerHTML = `
            <div class="alert alert-danger">
                <i class="fa fa-exclamation-circle me-2"></i>
                ${errors.join('<br>')}
            </div>
        `;
    },

    /**
     * Get selected orders
     * @returns {Array} Array of selected orders
     */
    getSelectedOrders() {
        return Array.from(this.state.selectedOrders.values());
    },

    /**
     * Get selected order IDs
     * @returns {Array<number>} Array of order IDs
     */
    getSelectedOrderIds() {
        return Array.from(this.state.selectedOrders.keys());
    },

    /**
     * Clear selection
     */
    clearSelection() {
        this.state.selectedOrders.clear();
        this.updateSelectedDisplay();

        // Uncheck all checkboxes
        const checkboxes = this.orderList.querySelectorAll('.order-checkbox');
        checkboxes.forEach(cb => cb.checked = false);

        const selectAllCheckbox = document.getElementById('select-all-orders');
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = false;
        }
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
    if (document.querySelector('#order-search-input')) {
        OrderSelector.init();
    }
});

// Export
window.OrderSelector = OrderSelector;
