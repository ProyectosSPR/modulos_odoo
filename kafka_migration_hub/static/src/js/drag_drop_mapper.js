/** @odoo-module **/

/**
 * Migration Hub Drag & Drop Field Mapper
 * Enables intuitive field mapping through drag and drop
 */

document.addEventListener('DOMContentLoaded', function() {
    const DragDropMapper = {
        projectId: null,
        currentTable: null,
        sourceFields: [],
        targetFields: [],
        mappings: [],
        draggedItem: null,

        init: function(projectId, tableName) {
            this.projectId = projectId;
            this.currentTable = tableName;
            this.loadFieldData();
            this.bindEvents();
        },

        loadFieldData: function() {
            if (!this.projectId || !this.currentTable) return;

            fetch(`/my/migration/api/project/${this.projectId}/table/${this.currentTable}/fields`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.sourceFields = data.source_fields || [];
                    this.targetFields = data.target_fields || [];
                    this.mappings = data.mappings || [];
                    this.render();
                }
            })
            .catch(error => {
                console.error('Error loading field data:', error);
            });
        },

        bindEvents: function() {
            // Global drag events
            document.addEventListener('dragend', () => {
                this.draggedItem = null;
                document.querySelectorAll('.mh-drag-over').forEach(el => {
                    el.classList.remove('mh-drag-over');
                });
            });

            // Clear mapping button
            document.addEventListener('click', (e) => {
                if (e.target.closest('.mh-clear-mapping')) {
                    const mappingId = e.target.closest('.mh-mapping-line').dataset.mappingId;
                    this.clearMapping(mappingId);
                }
            });

            // Auto-map button
            const autoMapBtn = document.querySelector('.mh-btn-auto-map');
            if (autoMapBtn) {
                autoMapBtn.addEventListener('click', () => this.autoMap());
            }

            // Clear all button
            const clearAllBtn = document.querySelector('.mh-btn-clear-all');
            if (clearAllBtn) {
                clearAllBtn.addEventListener('click', () => this.clearAllMappings());
            }

            // Save button
            const saveBtn = document.querySelector('.mh-btn-save-fields');
            if (saveBtn) {
                saveBtn.addEventListener('click', () => this.saveMappings());
            }
        },

        render: function() {
            const container = document.querySelector('.mh-field-mapper');
            if (!container) return;

            let html = `
                <div class="mh-mapper-header">
                    <h5>Mapeo de Campos: ${this.currentTable}</h5>
                    <div class="mh-mapper-actions">
                        <button class="btn btn-sm btn-outline-primary mh-btn-auto-map">
                            <i class="fa fa-magic"></i> Auto-mapear
                        </button>
                        <button class="btn btn-sm btn-outline-secondary mh-btn-clear-all">
                            <i class="fa fa-eraser"></i> Limpiar Todo
                        </button>
                    </div>
                </div>
                <div class="mh-mapper-body">
                    <div class="mh-field-column mh-source-column">
                        <div class="mh-column-header">
                            <i class="fa fa-database"></i> Campos Origen
                        </div>
                        <div class="mh-field-list mh-source-list">
                            ${this.renderSourceFields()}
                        </div>
                    </div>
                    <div class="mh-mapping-area">
                        <div class="mh-mapping-lines">
                            ${this.renderMappingLines()}
                        </div>
                    </div>
                    <div class="mh-field-column mh-target-column">
                        <div class="mh-column-header">
                            <i class="fa fa-cubes"></i> Campos Destino (Odoo)
                        </div>
                        <div class="mh-field-list mh-target-list">
                            ${this.renderTargetFields()}
                        </div>
                    </div>
                </div>
                <div class="mh-mapper-footer">
                    <button class="btn btn-success mh-btn-save-fields">
                        <i class="fa fa-save"></i> Guardar Mapeos
                    </button>
                </div>
            `;

            container.innerHTML = html;

            // Initialize drag and drop after render
            this.initDragDrop();
            this.drawConnectionLines();
        },

        renderSourceFields: function() {
            return this.sourceFields.map(field => {
                const isMapped = this.mappings.some(m => m.source_column === field.name);
                const mapping = this.mappings.find(m => m.source_column === field.name);

                return `
                    <div class="mh-field-item mh-draggable ${isMapped ? 'mapped' : ''}"
                         draggable="true"
                         data-field="${field.name}"
                         data-type="source"
                         id="source-${field.name}">
                        <div class="field-drag-handle">
                            <i class="fa fa-grip-vertical"></i>
                        </div>
                        <div class="field-info">
                            <span class="field-name">${field.name}</span>
                            <span class="field-type">${field.type}</span>
                        </div>
                        <div class="field-badges">
                            ${field.is_pk ? '<span class="badge bg-warning" title="Primary Key">PK</span>' : ''}
                            ${field.is_fk ? '<span class="badge bg-info" title="Foreign Key">FK</span>' : ''}
                            ${field.nullable === false ? '<span class="badge bg-danger" title="Not Null">!</span>' : ''}
                        </div>
                        ${mapping && mapping.ai_confidence ? `
                            <div class="field-ai-indicator" title="Sugerencia IA: ${Math.round(mapping.ai_confidence * 100)}%">
                                <i class="fa fa-magic"></i>
                            </div>
                        ` : ''}
                    </div>
                `;
            }).join('');
        },

        renderTargetFields: function() {
            return this.targetFields.map(field => {
                const isMapped = this.mappings.some(m => m.target_field === field.name);

                return `
                    <div class="mh-field-item mh-drop-target ${isMapped ? 'mapped' : ''}"
                         data-field="${field.name}"
                         data-type="target"
                         id="target-${field.name}">
                        <div class="field-info">
                            <span class="field-name">${field.name}</span>
                            <span class="field-type">${field.ttype}</span>
                        </div>
                        <div class="field-badges">
                            ${field.required ? '<span class="badge bg-danger" title="Requerido">*</span>' : ''}
                            ${field.relation ? `<span class="badge bg-info" title="Relación: ${field.relation}">M2O</span>` : ''}
                        </div>
                    </div>
                `;
            }).join('');
        },

        renderMappingLines: function() {
            return this.mappings.map((mapping, index) => {
                const confidence = mapping.ai_confidence || 0;
                const confidenceClass = confidence >= 0.8 ? 'high' : (confidence >= 0.6 ? 'medium' : 'low');

                return `
                    <div class="mh-mapping-line" data-mapping-id="${index}"
                         data-source="${mapping.source_column}"
                         data-target="${mapping.target_field}">
                        <span class="mapping-source">${mapping.source_column}</span>
                        <span class="mapping-arrow">
                            ${mapping.transform_function ?
                                `<i class="fa fa-cog" title="Transformación: ${mapping.transform_function}"></i>` :
                                '<i class="fa fa-arrow-right"></i>'}
                        </span>
                        <span class="mapping-target">${mapping.target_field}</span>
                        ${confidence > 0 ? `
                            <span class="mh-confidence ${confidenceClass}">${Math.round(confidence * 100)}%</span>
                        ` : ''}
                        <button class="btn btn-sm btn-link mh-clear-mapping" title="Eliminar mapeo">
                            <i class="fa fa-times text-danger"></i>
                        </button>
                    </div>
                `;
            }).join('');
        },

        initDragDrop: function() {
            // Source fields - draggable
            document.querySelectorAll('.mh-draggable').forEach(el => {
                el.addEventListener('dragstart', (e) => this.handleDragStart(e));
                el.addEventListener('dragend', (e) => this.handleDragEnd(e));
            });

            // Target fields - drop zones
            document.querySelectorAll('.mh-drop-target').forEach(el => {
                el.addEventListener('dragover', (e) => this.handleDragOver(e));
                el.addEventListener('dragleave', (e) => this.handleDragLeave(e));
                el.addEventListener('drop', (e) => this.handleDrop(e));
            });
        },

        handleDragStart: function(e) {
            this.draggedItem = e.target.closest('.mh-draggable');
            e.dataTransfer.effectAllowed = 'link';
            e.dataTransfer.setData('text/plain', this.draggedItem.dataset.field);

            // Add dragging class
            setTimeout(() => {
                this.draggedItem.classList.add('dragging');
            }, 0);
        },

        handleDragEnd: function(e) {
            if (this.draggedItem) {
                this.draggedItem.classList.remove('dragging');
            }
            this.draggedItem = null;

            // Remove all drag-over states
            document.querySelectorAll('.mh-drag-over').forEach(el => {
                el.classList.remove('mh-drag-over');
            });
        },

        handleDragOver: function(e) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'link';

            const target = e.target.closest('.mh-drop-target');
            if (target && !target.classList.contains('mapped')) {
                target.classList.add('mh-drag-over');
            }
        },

        handleDragLeave: function(e) {
            const target = e.target.closest('.mh-drop-target');
            if (target) {
                target.classList.remove('mh-drag-over');
            }
        },

        handleDrop: function(e) {
            e.preventDefault();

            const target = e.target.closest('.mh-drop-target');
            if (!target || !this.draggedItem) return;

            target.classList.remove('mh-drag-over');

            const sourceField = this.draggedItem.dataset.field;
            const targetField = target.dataset.field;

            // Check if already mapped
            if (target.classList.contains('mapped')) {
                this.showNotification('Este campo ya está mapeado', 'warning');
                return;
            }

            // Create mapping
            this.createMapping(sourceField, targetField);
        },

        createMapping: function(sourceField, targetField) {
            // Check if source is already mapped
            const existingIndex = this.mappings.findIndex(m => m.source_column === sourceField);
            if (existingIndex >= 0) {
                this.mappings.splice(existingIndex, 1);
            }

            // Add new mapping
            this.mappings.push({
                source_column: sourceField,
                target_field: targetField,
                mapping_type: 'direct'
            });

            // Re-render
            this.render();
            this.showNotification('Mapeo creado', 'success');
        },

        clearMapping: function(mappingId) {
            if (mappingId !== undefined) {
                this.mappings.splice(parseInt(mappingId), 1);
                this.render();
                this.showNotification('Mapeo eliminado', 'info');
            }
        },

        clearAllMappings: function() {
            if (confirm('¿Está seguro de eliminar todos los mapeos?')) {
                this.mappings = [];
                this.render();
                this.showNotification('Todos los mapeos eliminados', 'info');
            }
        },

        autoMap: function() {
            const btn = document.querySelector('.mh-btn-auto-map');
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Analizando...';
            }

            fetch(`/my/migration/api/project/${this.projectId}/table/${this.currentTable}/auto-map`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fa fa-magic"></i> Auto-mapear';
                }

                if (data.success) {
                    this.mappings = data.mappings || [];
                    this.render();
                    this.showNotification(`${data.mappings.length} campos mapeados automáticamente`, 'success');
                } else {
                    this.showNotification(data.error || 'Error en auto-mapeo', 'error');
                }
            })
            .catch(error => {
                console.error('Error in auto-map:', error);
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fa fa-magic"></i> Auto-mapear';
                }
                this.showNotification('Error de conexión', 'error');
            });
        },

        saveMappings: function() {
            const btn = document.querySelector('.mh-btn-save-fields');
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Guardando...';
            }

            fetch(`/my/migration/api/project/${this.projectId}/table/${this.currentTable}/mappings`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    mappings: this.mappings
                })
            })
            .then(response => response.json())
            .then(data => {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fa fa-save"></i> Guardar Mapeos';
                }

                if (data.success) {
                    this.showNotification('Mapeos guardados correctamente', 'success');
                } else {
                    this.showNotification(data.error || 'Error guardando', 'error');
                }
            })
            .catch(error => {
                console.error('Error saving mappings:', error);
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fa fa-save"></i> Guardar Mapeos';
                }
                this.showNotification('Error de conexión', 'error');
            });
        },

        drawConnectionLines: function() {
            // This could be enhanced with SVG lines connecting mapped fields
            // For now, we use the mapping lines list
        },

        showNotification: function(message, type) {
            const notification = document.createElement('div');
            notification.className = `mh-notification ${type}`;

            const icon = type === 'success' ? 'check' : (type === 'error' ? 'times' : 'info');
            notification.innerHTML = `
                <i class="fa fa-${icon}-circle"></i>
                ${message}
            `;

            document.body.appendChild(notification);

            setTimeout(() => notification.classList.add('show'), 10);

            setTimeout(() => {
                notification.classList.remove('show');
                setTimeout(() => notification.remove(), 300);
            }, 3000);
        }
    };

    // Initialize if on field mapping page
    const mapperContainer = document.querySelector('.mh-field-mapper');
    if (mapperContainer) {
        const projectId = mapperContainer.dataset.projectId;
        const tableName = mapperContainer.dataset.table;
        if (projectId && tableName) {
            DragDropMapper.init(projectId, tableName);
        }
    }

    // Export
    window.DragDropMapper = DragDropMapper;
});

// Additional styles for drag and drop
const dragDropStyles = document.createElement('style');
dragDropStyles.textContent = `
    .mh-draggable {
        cursor: grab;
        transition: all 0.2s;
    }

    .mh-draggable:active {
        cursor: grabbing;
    }

    .mh-draggable.dragging {
        opacity: 0.5;
        transform: scale(1.02);
    }

    .mh-drop-target {
        transition: all 0.2s;
    }

    .mh-drop-target.mh-drag-over {
        background: rgba(113, 75, 103, 0.1);
        border: 2px dashed #714B67;
    }

    .mh-field-item.mapped {
        background: rgba(40, 167, 69, 0.1);
        border-left: 3px solid #28a745;
    }

    .field-drag-handle {
        cursor: grab;
        color: #999;
        margin-right: 8px;
    }

    .field-ai-indicator {
        color: #714B67;
        margin-left: auto;
    }

    .mh-mapping-line {
        display: flex;
        align-items: center;
        padding: 8px 12px;
        background: #f8f9fa;
        border-radius: 4px;
        margin-bottom: 8px;
        gap: 10px;
    }

    .mh-mapping-line .mapping-source,
    .mh-mapping-line .mapping-target {
        font-weight: 500;
    }

    .mh-mapping-line .mapping-arrow {
        color: #714B67;
    }

    .mh-notification {
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        border-radius: 8px;
        background: white;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 9999;
        transform: translateX(120%);
        transition: transform 0.3s ease;
    }

    .mh-notification.show {
        transform: translateX(0);
    }

    .mh-notification.success {
        border-left: 4px solid #28a745;
    }

    .mh-notification.error {
        border-left: 4px solid #dc3545;
    }

    .mh-notification.warning {
        border-left: 4px solid #ffc107;
    }

    .mh-notification.info {
        border-left: 4px solid #17a2b8;
    }

    .mh-notification i {
        margin-right: 8px;
    }

    .mh-notification.success i { color: #28a745; }
    .mh-notification.error i { color: #dc3545; }
    .mh-notification.warning i { color: #ffc107; }
    .mh-notification.info i { color: #17a2b8; }
`;
document.head.appendChild(dragDropStyles);
