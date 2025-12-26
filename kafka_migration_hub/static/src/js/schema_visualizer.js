/** @odoo-module **/

/**
 * Migration Hub Schema Visualizer
 * Displays source schema grouped by AI-suggested topics
 */

document.addEventListener('DOMContentLoaded', function() {
    const SchemaVisualizer = {
        projectId: null,
        schema: null,
        topics: [],
        mappings: {},

        init: function(projectId) {
            this.projectId = projectId;
            this.bindEvents();
            this.loadSchema();
        },

        bindEvents: function() {
            // Topic header toggle
            document.addEventListener('click', (e) => {
                if (e.target.closest('.mh-topic-header')) {
                    this.toggleTopic(e.target.closest('.mh-topic-header'));
                }
            });

            // Table selection
            document.addEventListener('click', (e) => {
                if (e.target.closest('.mh-table-item')) {
                    this.selectTable(e.target.closest('.mh-table-item'));
                }
            });

            // Search input
            const searchInput = document.querySelector('.mh-schema-search');
            if (searchInput) {
                searchInput.addEventListener('input', this.handleSearch.bind(this));
            }

            // Refresh button
            const refreshBtn = document.querySelector('.mh-schema-refresh');
            if (refreshBtn) {
                refreshBtn.addEventListener('click', this.loadSchema.bind(this));
            }
        },

        loadSchema: function() {
            const container = document.querySelector('.mh-schema-container');
            if (!container || !this.projectId) return;

            // Show loading
            container.innerHTML = `
                <div class="mh-loading text-center p-5">
                    <i class="fa fa-spinner fa-spin fa-3x"></i>
                    <p class="mt-3">Cargando esquema...</p>
                </div>
            `;

            fetch(`/my/migration/api/project/${this.projectId}/schema`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.schema = data.schema;
                    this.topics = data.topics || [];
                    this.mappings = data.mappings || {};
                    this.renderSchema();
                } else {
                    this.showError(data.error || 'Error cargando esquema');
                }
            })
            .catch(error => {
                console.error('Error loading schema:', error);
                this.showError('Error de conexión');
            });
        },

        renderSchema: function() {
            const container = document.querySelector('.mh-schema-container');
            if (!container) return;

            let html = `
                <div class="mh-schema-panel mh-source-panel">
                    <div class="mh-panel-header">
                        <i class="fa fa-database"></i> Esquema Origen
                        <span class="badge bg-secondary ms-2">${this.schema.tables?.length || 0} tablas</span>
                    </div>
                    <div class="mh-panel-body">
                        <div class="mh-schema-search-wrapper mb-3">
                            <input type="text" class="form-control mh-schema-search"
                                   placeholder="Buscar tablas...">
                        </div>
                        <div class="mh-topics-list">
            `;

            // Group tables by suggested topic
            const groupedTables = this.groupTablesByTopic();

            // Render each topic group
            for (const [topicId, group] of Object.entries(groupedTables)) {
                const topic = this.topics.find(t => t.id == topicId) || {
                    name: 'Sin Clasificar',
                    icon: '📋'
                };

                html += `
                    <div class="mh-topic-group" data-topic-id="${topicId}">
                        <div class="mh-topic-header">
                            <span class="topic-icon">${topic.icon || '📋'}</span>
                            <span class="topic-name">${topic.name}</span>
                            <span class="topic-count">${group.tables.length}</span>
                            <i class="fa fa-chevron-down ms-auto"></i>
                        </div>
                        <div class="mh-topic-tables">
                            ${this.renderTables(group.tables)}
                        </div>
                    </div>
                `;
            }

            html += `
                        </div>
                    </div>
                </div>
                <div class="mh-schema-panel mh-target-panel">
                    <div class="mh-panel-header">
                        <i class="fa fa-cubes"></i> Modelos Odoo Destino
                    </div>
                    <div class="mh-panel-body">
                        <div class="mh-table-details" id="tableDetails">
                            <div class="mh-empty-state">
                                <i class="fa fa-hand-pointer-o empty-icon"></i>
                                <h4>Seleccione una tabla</h4>
                                <p>Haga clic en una tabla del esquema origen para ver sus detalles y configurar el mapeo.</p>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            container.innerHTML = html;
        },

        groupTablesByTopic: function() {
            const groups = {};

            // Initialize with "unclassified" group
            groups['0'] = { tables: [] };

            // Initialize topic groups
            this.topics.forEach(topic => {
                groups[topic.id] = { tables: [] };
            });

            // Group tables
            if (this.schema.tables) {
                this.schema.tables.forEach(table => {
                    const mapping = this.mappings[table.name];
                    const topicId = mapping?.suggested_topic_id || '0';

                    if (!groups[topicId]) {
                        groups[topicId] = { tables: [] };
                    }

                    groups[topicId].tables.push({
                        ...table,
                        mapping: mapping
                    });
                });
            }

            // Remove empty groups
            for (const [key, value] of Object.entries(groups)) {
                if (value.tables.length === 0) {
                    delete groups[key];
                }
            }

            return groups;
        },

        renderTables: function(tables) {
            if (!tables || tables.length === 0) {
                return '<p class="text-muted">No hay tablas en este grupo</p>';
            }

            return tables.map(table => {
                const confidence = table.mapping?.ai_confidence || 0;
                const confidenceClass = confidence >= 0.8 ? 'high' : (confidence >= 0.6 ? 'medium' : 'low');
                const confidenceText = Math.round(confidence * 100) + '%';

                return `
                    <div class="mh-table-item" data-table="${table.name}">
                        <i class="fa fa-table table-icon"></i>
                        <span class="table-name">${table.name}</span>
                        <span class="table-rows">${this.formatNumber(table.row_count || 0)} filas</span>
                        ${confidence > 0 ? `<span class="mh-confidence ${confidenceClass}">${confidenceText}</span>` : ''}
                    </div>
                `;
            }).join('');
        },

        toggleTopic: function(header) {
            const group = header.closest('.mh-topic-group');
            const tables = group.querySelector('.mh-topic-tables');
            const icon = header.querySelector('.fa-chevron-down, .fa-chevron-up');

            if (tables.style.display === 'none') {
                tables.style.display = 'block';
                icon.classList.replace('fa-chevron-up', 'fa-chevron-down');
            } else {
                tables.style.display = 'none';
                icon.classList.replace('fa-chevron-down', 'fa-chevron-up');
            }
        },

        selectTable: function(tableItem) {
            // Remove previous selection
            document.querySelectorAll('.mh-table-item.selected').forEach(item => {
                item.classList.remove('selected');
            });

            // Add selection to current
            tableItem.classList.add('selected');

            const tableName = tableItem.dataset.table;
            this.loadTableDetails(tableName);
        },

        loadTableDetails: function(tableName) {
            const detailsContainer = document.getElementById('tableDetails');
            if (!detailsContainer) return;

            // Show loading
            detailsContainer.innerHTML = `
                <div class="text-center p-4">
                    <i class="fa fa-spinner fa-spin"></i> Cargando detalles...
                </div>
            `;

            fetch(`/my/migration/api/project/${this.projectId}/table/${tableName}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.renderTableDetails(data);
                } else {
                    detailsContainer.innerHTML = `
                        <div class="alert alert-danger">${data.error || 'Error cargando detalles'}</div>
                    `;
                }
            })
            .catch(error => {
                console.error('Error loading table details:', error);
                detailsContainer.innerHTML = `
                    <div class="alert alert-danger">Error de conexión</div>
                `;
            });
        },

        renderTableDetails: function(data) {
            const detailsContainer = document.getElementById('tableDetails');
            if (!detailsContainer) return;

            const table = data.table;
            const columns = data.columns || [];
            const mapping = data.mapping || {};
            const suggestions = data.suggestions || [];

            let html = `
                <div class="mh-table-details-content">
                    <h5><i class="fa fa-table"></i> ${table.name}</h5>
                    <div class="mh-table-info mb-3">
                        <span class="badge bg-secondary">${this.formatNumber(table.row_count || 0)} filas</span>
                        <span class="badge bg-info">${columns.length} columnas</span>
                    </div>
            `;

            // AI Suggestion
            if (mapping.suggested_topic_id) {
                const topic = this.topics.find(t => t.id == mapping.suggested_topic_id);
                html += `
                    <div class="mh-ai-suggestion mb-3">
                        <div class="alert alert-info">
                            <i class="fa fa-magic"></i>
                            <strong>Sugerencia IA:</strong> ${topic?.name || 'Desconocido'}
                            <span class="mh-confidence ${mapping.ai_confidence >= 0.8 ? 'high' : 'medium'}">
                                ${Math.round((mapping.ai_confidence || 0) * 100)}%
                            </span>
                            ${mapping.ai_reason ? `<br><small>${mapping.ai_reason}</small>` : ''}
                        </div>
                    </div>
                `;
            }

            // Topic Selection
            html += `
                <div class="mb-3">
                    <label class="form-label"><strong>Tópico Destino:</strong></label>
                    <select class="form-select" id="topicSelect" data-table="${table.name}">
                        <option value="">-- Seleccionar --</option>
                        ${this.topics.map(t => `
                            <option value="${t.id}" ${mapping.topic_id == t.id ? 'selected' : ''}>
                                ${t.icon || ''} ${t.name}
                            </option>
                        `).join('')}
                    </select>
                </div>
            `;

            // Columns list
            html += `
                <div class="mh-columns-section">
                    <h6><i class="fa fa-columns"></i> Columnas</h6>
                    <div class="mh-field-list">
                        ${columns.map(col => this.renderColumn(col, suggestions)).join('')}
                    </div>
                </div>
            `;

            // Actions
            html += `
                <div class="mh-table-actions mt-3">
                    <button class="btn btn-primary mh-btn-save-mapping" data-table="${table.name}">
                        <i class="fa fa-save"></i> Guardar Mapeo
                    </button>
                    <button class="btn btn-outline-secondary mh-btn-ai-suggest" data-table="${table.name}">
                        <i class="fa fa-magic"></i> Sugerencias IA
                    </button>
                </div>
            `;

            html += '</div>';
            detailsContainer.innerHTML = html;

            // Bind events for new elements
            this.bindTableDetailEvents();
        },

        renderColumn: function(column, suggestions) {
            const suggestion = suggestions.find(s => s.source_column === column.name);

            return `
                <div class="mh-field-item">
                    <div class="field-info">
                        <span class="field-name">${column.name}</span>
                        <span class="field-type">${column.type}</span>
                        ${column.is_pk ? '<span class="badge bg-warning">PK</span>' : ''}
                        ${column.is_fk ? '<span class="badge bg-info">FK</span>' : ''}
                    </div>
                    ${suggestion ? `
                        <div class="field-suggestion">
                            <i class="fa fa-arrow-right"></i>
                            <span>${suggestion.target_field}</span>
                            <span class="mh-confidence ${suggestion.confidence >= 0.8 ? 'high' : 'medium'}">
                                ${Math.round(suggestion.confidence * 100)}%
                            </span>
                        </div>
                    ` : ''}
                </div>
            `;
        },

        bindTableDetailEvents: function() {
            // Topic select change
            const topicSelect = document.getElementById('topicSelect');
            if (topicSelect) {
                topicSelect.addEventListener('change', (e) => {
                    this.updateTableTopic(e.target.dataset.table, e.target.value);
                });
            }

            // Save mapping button
            const saveBtn = document.querySelector('.mh-btn-save-mapping');
            if (saveBtn) {
                saveBtn.addEventListener('click', (e) => {
                    this.saveMapping(e.target.dataset.table);
                });
            }

            // AI suggest button
            const aiBtn = document.querySelector('.mh-btn-ai-suggest');
            if (aiBtn) {
                aiBtn.addEventListener('click', (e) => {
                    this.requestAISuggestions(e.target.dataset.table);
                });
            }
        },

        updateTableTopic: function(tableName, topicId) {
            fetch(`/my/migration/api/project/${this.projectId}/mapping/update`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    table_name: tableName,
                    topic_id: topicId
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.showNotification('Tópico actualizado', 'success');
                    // Update local mapping
                    if (this.mappings[tableName]) {
                        this.mappings[tableName].topic_id = topicId;
                    }
                } else {
                    this.showNotification(data.error || 'Error actualizando', 'error');
                }
            })
            .catch(error => {
                console.error('Error updating topic:', error);
                this.showNotification('Error de conexión', 'error');
            });
        },

        saveMapping: function(tableName) {
            // Collect all field mappings
            const fieldMappings = [];
            document.querySelectorAll('.mh-field-item').forEach(item => {
                const fieldName = item.querySelector('.field-name').textContent;
                const targetField = item.querySelector('.field-target-select')?.value;
                if (targetField) {
                    fieldMappings.push({
                        source_column: fieldName,
                        target_field: targetField
                    });
                }
            });

            fetch(`/my/migration/api/project/${this.projectId}/mapping/save`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    table_name: tableName,
                    field_mappings: fieldMappings
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.showNotification('Mapeo guardado correctamente', 'success');
                } else {
                    this.showNotification(data.error || 'Error guardando mapeo', 'error');
                }
            })
            .catch(error => {
                console.error('Error saving mapping:', error);
                this.showNotification('Error de conexión', 'error');
            });
        },

        requestAISuggestions: function(tableName) {
            const btn = document.querySelector('.mh-btn-ai-suggest');
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Analizando...';
            }

            fetch(`/my/migration/api/project/${this.projectId}/ai/suggest`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    table_name: tableName
                })
            })
            .then(response => response.json())
            .then(data => {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fa fa-magic"></i> Sugerencias IA';
                }

                if (data.success) {
                    this.showNotification('Sugerencias generadas', 'success');
                    this.loadTableDetails(tableName); // Reload to show suggestions
                } else {
                    this.showNotification(data.error || 'Error generando sugerencias', 'error');
                }
            })
            .catch(error => {
                console.error('Error requesting AI suggestions:', error);
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fa fa-magic"></i> Sugerencias IA';
                }
                this.showNotification('Error de conexión', 'error');
            });
        },

        handleSearch: function(e) {
            const searchTerm = e.target.value.toLowerCase();

            document.querySelectorAll('.mh-table-item').forEach(item => {
                const tableName = item.dataset.table.toLowerCase();
                if (tableName.includes(searchTerm)) {
                    item.style.display = 'flex';
                } else {
                    item.style.display = 'none';
                }
            });

            // Show/hide topic groups based on visible tables
            document.querySelectorAll('.mh-topic-group').forEach(group => {
                const visibleTables = group.querySelectorAll('.mh-table-item[style="display: flex"], .mh-table-item:not([style])');
                if (visibleTables.length > 0 || searchTerm === '') {
                    group.style.display = 'block';
                } else {
                    group.style.display = 'none';
                }
            });
        },

        showError: function(message) {
            const container = document.querySelector('.mh-schema-container');
            if (container) {
                container.innerHTML = `
                    <div class="mh-error-state text-center p-5">
                        <i class="fa fa-exclamation-triangle fa-3x text-danger"></i>
                        <h4 class="mt-3">Error</h4>
                        <p>${message}</p>
                        <button class="btn btn-primary mh-schema-refresh">
                            <i class="fa fa-refresh"></i> Reintentar
                        </button>
                    </div>
                `;
            }
        },

        showNotification: function(message, type) {
            // Create notification element
            const notification = document.createElement('div');
            notification.className = `mh-notification ${type}`;
            notification.innerHTML = `
                <i class="fa fa-${type === 'success' ? 'check' : 'times'}-circle"></i>
                ${message}
            `;

            document.body.appendChild(notification);

            // Animate in
            setTimeout(() => notification.classList.add('show'), 10);

            // Remove after 3 seconds
            setTimeout(() => {
                notification.classList.remove('show');
                setTimeout(() => notification.remove(), 300);
            }, 3000);
        },

        formatNumber: function(num) {
            if (num >= 1000000) {
                return (num / 1000000).toFixed(1) + 'M';
            } else if (num >= 1000) {
                return (num / 1000).toFixed(1) + 'K';
            }
            return num.toString();
        }
    };

    // Initialize if on schema page
    const schemaContainer = document.querySelector('.mh-schema-container');
    if (schemaContainer) {
        const projectId = schemaContainer.dataset.projectId;
        if (projectId) {
            SchemaVisualizer.init(projectId);
        }
    }

    // Export
    window.SchemaVisualizer = SchemaVisualizer;
});
