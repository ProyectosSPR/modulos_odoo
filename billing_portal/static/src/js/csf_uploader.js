/** @odoo-module **/

/**
 * CSF Uploader Component
 *
 * Handles PDF upload, validation, and data extraction
 * for Constancia de Situación Fiscal (CSF) documents.
 */

const CSFUploader = {
    // Configuration
    config: {
        maxFileSize: 10 * 1024 * 1024, // 10MB
        allowedTypes: ['application/pdf'],
        dropzoneSelector: '#csf-dropzone',
        fileInputSelector: '#csf-file-input',
        previewSelector: '#csf-preview',
        dataContainerSelector: '#csf-data-container',
    },

    // Current state
    state: {
        file: null,
        fileBase64: null,
        extractedData: null,
        isValidating: false,
        validationMethod: null,
    },

    /**
     * Initialize the uploader
     * @param {object} options - Custom options to override defaults
     */
    init(options = {}) {
        this.config = { ...this.config, ...options };

        this.dropzone = document.querySelector(this.config.dropzoneSelector);
        this.fileInput = document.querySelector(this.config.fileInputSelector);
        this.preview = document.querySelector(this.config.previewSelector);
        this.dataContainer = document.querySelector(this.config.dataContainerSelector);

        if (!this.dropzone || !this.fileInput) {
            console.warn('CSF Uploader: Required elements not found');
            return;
        }

        this.bindEvents();
    },

    /**
     * Bind event listeners
     */
    bindEvents() {
        // Click to upload
        this.dropzone.addEventListener('click', () => this.fileInput.click());

        // File input change
        this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));

        // Drag and drop events
        this.dropzone.addEventListener('dragover', (e) => this.handleDragOver(e));
        this.dropzone.addEventListener('dragleave', (e) => this.handleDragLeave(e));
        this.dropzone.addEventListener('drop', (e) => this.handleDrop(e));

        // Prevent default drag behaviors on document
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            document.body.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            });
        });
    },

    /**
     * Handle drag over event
     */
    handleDragOver(e) {
        e.preventDefault();
        e.stopPropagation();
        this.dropzone.classList.add('dragover');
    },

    /**
     * Handle drag leave event
     */
    handleDragLeave(e) {
        e.preventDefault();
        e.stopPropagation();
        this.dropzone.classList.remove('dragover');
    },

    /**
     * Handle drop event
     */
    handleDrop(e) {
        e.preventDefault();
        e.stopPropagation();
        this.dropzone.classList.remove('dragover');

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            this.processFile(files[0]);
        }
    },

    /**
     * Handle file selection from input
     */
    handleFileSelect(e) {
        const files = e.target.files;
        if (files.length > 0) {
            this.processFile(files[0]);
        }
    },

    /**
     * Process selected file
     * @param {File} file - Selected file
     */
    async processFile(file) {
        // Validate file type
        if (!this.config.allowedTypes.includes(file.type)) {
            BillingPortal.showToast('Solo se permiten archivos PDF', 'error');
            return;
        }

        // Validate file size
        if (file.size > this.config.maxFileSize) {
            BillingPortal.showToast('El archivo excede el tamaño máximo de 10MB', 'error');
            return;
        }

        this.state.file = file;

        // Show preview
        this.showFilePreview(file);

        // Convert to base64 and validate
        try {
            this.state.fileBase64 = await this.fileToBase64(file);
            await this.validateCSF();
        } catch (error) {
            console.error('Error processing file:', error);
            BillingPortal.showToast('Error al procesar el archivo', 'error');
        }
    },

    /**
     * Convert file to base64
     * @param {File} file - File to convert
     * @returns {Promise<string>} Base64 string
     */
    fileToBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = (error) => reject(error);
            reader.readAsDataURL(file);
        });
    },

    /**
     * Show file preview
     * @param {File} file - File to preview
     */
    showFilePreview(file) {
        if (!this.preview) return;

        this.dropzone.style.display = 'none';
        this.preview.style.display = 'block';
        this.preview.innerHTML = `
            <div class="card">
                <div class="card-body">
                    <div class="d-flex align-items-center">
                        <i class="fa fa-file-pdf-o fa-3x text-danger me-3"></i>
                        <div class="flex-grow-1">
                            <h6 class="mb-1">${file.name}</h6>
                            <small class="text-muted">${this.formatFileSize(file.size)}</small>
                        </div>
                        <button type="button" class="btn btn-outline-secondary btn-sm" id="btn-remove-csf">
                            <i class="fa fa-times"></i>
                        </button>
                    </div>
                    <div class="mt-3" id="csf-validation-status">
                        <div class="d-flex align-items-center">
                            <div class="spinner-border spinner-border-sm text-primary me-2"></div>
                            <span>Validando CSF...</span>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Bind remove button
        document.getElementById('btn-remove-csf').addEventListener('click', () => this.removeFile());
    },

    /**
     * Remove current file
     */
    removeFile() {
        this.state.file = null;
        this.state.fileBase64 = null;
        this.state.extractedData = null;

        this.fileInput.value = '';

        if (this.preview) {
            this.preview.style.display = 'none';
        }

        if (this.dropzone) {
            this.dropzone.style.display = 'block';
        }

        if (this.dataContainer) {
            this.dataContainer.style.display = 'none';
            this.dataContainer.innerHTML = '';
        }

        // Trigger event
        this.dispatchEvent('csf:removed');
    },

    /**
     * Validate CSF with backend
     */
    async validateCSF() {
        if (!this.state.fileBase64) {
            BillingPortal.showToast('No hay archivo para validar', 'error');
            return;
        }

        this.state.isValidating = true;

        try {
            const result = await BillingPortal.rpc('validate-csf', {
                csf_pdf: this.state.fileBase64,
            });

            this.state.isValidating = false;

            if (result.success) {
                this.state.extractedData = result.data;
                this.state.validationMethod = result.method;
                this.showExtractedData(result.data, result.method);
                this.updateValidationStatus(true, result.method);
                this.dispatchEvent('csf:validated', { data: result.data, method: result.method });
            } else {
                this.updateValidationStatus(false, null, result.errors);
                this.dispatchEvent('csf:error', { errors: result.errors });
            }
        } catch (error) {
            this.state.isValidating = false;
            console.error('Validation error:', error);
            this.updateValidationStatus(false, null, [error.message]);
            this.dispatchEvent('csf:error', { errors: [error.message] });
        }
    },

    /**
     * Update validation status display
     * @param {boolean} success - Whether validation succeeded
     * @param {string} method - Validation method used
     * @param {Array} errors - Error messages if failed
     */
    updateValidationStatus(success, method, errors = []) {
        const statusEl = document.getElementById('csf-validation-status');
        if (!statusEl) return;

        if (success) {
            const methodLabel = method === 'ai' ? 'IA' : 'Local';
            statusEl.innerHTML = `
                <div class="alert alert-success mb-0 py-2">
                    <i class="fa fa-check-circle me-2"></i>
                    CSF validado correctamente
                    <span class="badge bg-secondary ms-2">${methodLabel}</span>
                </div>
            `;
        } else {
            statusEl.innerHTML = `
                <div class="alert alert-danger mb-0 py-2">
                    <i class="fa fa-exclamation-circle me-2"></i>
                    Error en validación
                    ${errors.length > 0 ? `<small class="d-block mt-1">${errors.join(', ')}</small>` : ''}
                </div>
            `;
        }
    },

    /**
     * Show extracted data from CSF
     * @param {object} data - Extracted data
     * @param {string} method - Extraction method
     */
    showExtractedData(data, method) {
        if (!this.dataContainer) return;

        this.dataContainer.style.display = 'block';

        // Build data display
        const fields = [
            { key: 'rfc', label: 'RFC', icon: 'fa-id-card' },
            { key: 'razon_social', label: 'Razón Social', icon: 'fa-building' },
            { key: 'nombre', label: 'Nombre', icon: 'fa-user' },
            { key: 'codigo_postal', label: 'Código Postal', icon: 'fa-map-marker' },
            { key: 'regimen_fiscal', label: 'Régimen Fiscal', icon: 'fa-balance-scale' },
            { key: 'entidad_federativa', label: 'Estado', icon: 'fa-globe' },
            { key: 'municipio', label: 'Municipio', icon: 'fa-map' },
            { key: 'colonia', label: 'Colonia', icon: 'fa-home' },
            { key: 'calle', label: 'Calle', icon: 'fa-road' },
            { key: 'numero_exterior', label: 'No. Exterior', icon: 'fa-hashtag' },
        ];

        let html = `
            <div class="card mt-3">
                <div class="card-header bg-success text-white">
                    <i class="fa fa-check-circle me-2"></i>
                    Datos Extraídos del CSF
                </div>
                <div class="card-body">
                    <div class="row">
        `;

        fields.forEach(field => {
            let value = data[field.key];

            // Handle special cases
            if (field.key === 'regimen_fiscal' && Array.isArray(value)) {
                value = value.map(r => `${r.codigo} - ${r.descripcion}`).join('<br>');
            } else if (typeof value === 'object' && value !== null) {
                value = JSON.stringify(value);
            }

            if (value) {
                html += `
                    <div class="col-md-6 mb-2">
                        <div class="d-flex align-items-start">
                            <i class="fa ${field.icon} text-muted me-2 mt-1"></i>
                            <div>
                                <small class="text-muted d-block">${field.label}</small>
                                <strong>${value}</strong>
                            </div>
                        </div>
                    </div>
                `;
            }
        });

        html += `
                    </div>
                </div>
            </div>
        `;

        this.dataContainer.innerHTML = html;

        // Populate hidden form fields if they exist
        this.populateFormFields(data);
    },

    /**
     * Populate form fields with extracted data
     * @param {object} data - Extracted data
     */
    populateFormFields(data) {
        // RFC
        const rfcInput = document.getElementById('input-rfc');
        if (rfcInput && data.rfc) {
            rfcInput.value = data.rfc;
        }

        // Razón Social
        const razonInput = document.getElementById('input-razon-social');
        if (razonInput && data.razon_social) {
            razonInput.value = data.razon_social;
        }

        // Código Postal
        const cpInput = document.getElementById('input-codigo-postal');
        if (cpInput && data.codigo_postal) {
            cpInput.value = data.codigo_postal;
        }

        // Régimen Fiscal (select)
        const regimenSelect = document.getElementById('select-regimen-fiscal');
        if (regimenSelect && data.regimen_fiscal_id) {
            regimenSelect.value = data.regimen_fiscal_id;
        }

        // Store full data in hidden field
        const dataInput = document.getElementById('input-csf-data');
        if (dataInput) {
            dataInput.value = JSON.stringify(data);
        }
    },

    /**
     * Get current state
     * @returns {object} Current state
     */
    getState() {
        return { ...this.state };
    },

    /**
     * Get extracted data
     * @returns {object|null} Extracted data
     */
    getData() {
        return this.state.extractedData;
    },

    /**
     * Get file as base64
     * @returns {string|null} Base64 string
     */
    getFileBase64() {
        return this.state.fileBase64;
    },

    /**
     * Format file size
     * @param {number} bytes - Size in bytes
     * @returns {string} Formatted size
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
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
    // Only initialize if dropzone exists
    if (document.querySelector('#csf-dropzone')) {
        CSFUploader.init();
    }
});

// Export for use in other modules
window.CSFUploader = CSFUploader;
