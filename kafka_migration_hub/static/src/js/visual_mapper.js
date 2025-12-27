/**
 * Visual Mapper - Designer tipo Canva para mapeo de tablas/campos
 * Permite arrastrar y conectar campos de origen a destino visualmente
 */
odoo.define('kafka_migration_hub.VisualMapper', function (require) {
    'use strict';

    var publicWidget = require('web.public.widget');
    var ajax = require('web.ajax');
    var core = require('web.core');
    var _t = core._t;

    /**
     * Clase principal del Visual Mapper
     */
    var VisualMapper = publicWidget.Widget.extend({
        selector: '.visual-mapper-container',
        events: {
            'click .add-source-table': '_onAddSourceTable',
            'click .add-target-model': '_onAddTargetModel',
            'click .auto-map-btn': '_onAutoMap',
            'click .clear-mappings-btn': '_onClearMappings',
            'click .save-mappings-btn': '_onSaveMappings',
            'click .zoom-in': '_onZoomIn',
            'click .zoom-out': '_onZoomOut',
            'click .fit-screen': '_onFitScreen',
            'mousedown .table-node': '_onNodeMouseDown',
            'mousedown .field-item': '_onFieldMouseDown',
        },

        /**
         * @override
         */
        start: function () {
            var self = this;
            this.projectId = this.$el.data('project-id');
            this.mappings = [];
            this.nodes = [];
            this.connections = [];
            this.zoom = 1;
            this.pan = { x: 0, y: 0 };
            this.selectedField = null;
            this.draggedNode = null;

            // Canvas para dibujar conexiones
            this.canvas = this.$('.connections-canvas')[0];
            this.ctx = this.canvas ? this.canvas.getContext('2d') : null;

            // Cargar datos iniciales
            this._loadProjectData();

            // Event listeners globales
            $(document).on('mousemove.visualMapper', this._onMouseMove.bind(this));
            $(document).on('mouseup.visualMapper', this._onMouseUp.bind(this));
            $(window).on('resize.visualMapper', this._onResize.bind(this));

            return this._super.apply(this, arguments);
        },

        /**
         * @override
         */
        destroy: function () {
            $(document).off('.visualMapper');
            $(window).off('.visualMapper');
            this._super.apply(this, arguments);
        },

        /**
         * Cargar datos del proyecto
         */
        _loadProjectData: function () {
            var self = this;

            ajax.jsonRpc('/migration/api/project/' + this.projectId + '/schema', 'call', {})
                .then(function (result) {
                    if (result.success) {
                        self._renderSourceTables(result.source_tables);
                        self._renderTargetModels(result.target_models);
                        self._loadExistingMappings(result.mappings);
                    }
                });
        },

        /**
         * Renderizar tablas de origen
         */
        _renderSourceTables: function (tables) {
            var self = this;
            var $container = this.$('.source-panel .tables-container');
            $container.empty();

            tables.forEach(function (table, index) {
                var $node = self._createTableNode(table, 'source', index);
                $container.append($node);
                self.nodes.push({
                    id: 'source_' + table.name,
                    element: $node,
                    type: 'source',
                    data: table,
                    x: 50,
                    y: 50 + (index * 220)
                });
            });

            this._updateCanvas();
        },

        /**
         * Renderizar modelos de destino (Odoo)
         */
        _renderTargetModels: function (models) {
            var self = this;
            var $container = this.$('.target-panel .tables-container');
            $container.empty();

            models.forEach(function (model, index) {
                var $node = self._createModelNode(model, 'target', index);
                $container.append($node);
                self.nodes.push({
                    id: 'target_' + model.model,
                    element: $node,
                    type: 'target',
                    data: model,
                    x: 500,
                    y: 50 + (index * 220)
                });
            });

            this._updateCanvas();
        },

        /**
         * Crear nodo de tabla (origen)
         */
        _createTableNode: function (table, type, index) {
            var self = this;
            var $node = $('<div>', {
                class: 'table-node ' + type + '-node',
                'data-table': table.name,
                'data-type': type,
                css: {
                    top: (50 + index * 220) + 'px',
                    left: type === 'source' ? '50px' : '500px'
                }
            });

            // Header
            var $header = $('<div>', { class: 'node-header' })
                .append($('<span>', { class: 'node-icon' }).html('&#128451;'))
                .append($('<span>', { class: 'node-title' }).text(table.name))
                .append($('<span>', { class: 'node-count badge' }).text(table.columns.length));

            // Fields
            var $fields = $('<div>', { class: 'node-fields' });
            table.columns.forEach(function (col) {
                var $field = $('<div>', {
                    class: 'field-item',
                    'data-field': col.name,
                    'data-table': table.name,
                    'data-type': type
                });

                var typeIcon = self._getTypeIcon(col.type);
                $field.append($('<span>', { class: 'field-type-icon' }).html(typeIcon));
                $field.append($('<span>', { class: 'field-name' }).text(col.name));
                $field.append($('<span>', { class: 'field-type text-muted' }).text(col.type));

                // Indicador de clave
                if (col.is_pk) {
                    $field.append($('<span>', { class: 'field-key badge badge-warning' }).text('PK'));
                }
                if (col.is_fk) {
                    $field.append($('<span>', { class: 'field-key badge badge-info' }).text('FK'));
                }

                // Handle para conexion
                $field.append($('<div>', { class: 'field-handle ' + type + '-handle' }));

                $fields.append($field);
            });

            $node.append($header).append($fields);
            return $node;
        },

        /**
         * Crear nodo de modelo Odoo (destino)
         */
        _createModelNode: function (model, type, index) {
            var self = this;
            var $node = $('<div>', {
                class: 'table-node ' + type + '-node',
                'data-model': model.model,
                'data-type': type,
                css: {
                    top: (50 + index * 220) + 'px',
                    left: '500px'
                }
            });

            // Header
            var $header = $('<div>', { class: 'node-header target-header' })
                .append($('<span>', { class: 'node-icon' }).html('&#127968;'))
                .append($('<span>', { class: 'node-title' }).text(model.name || model.model))
                .append($('<span>', { class: 'node-subtitle text-muted' }).text(model.model));

            // Fields
            var $fields = $('<div>', { class: 'node-fields' });
            model.fields.forEach(function (field) {
                var $field = $('<div>', {
                    class: 'field-item',
                    'data-field': field.name,
                    'data-model': model.model,
                    'data-type': type
                });

                var typeIcon = self._getTypeIcon(field.type);
                $field.append($('<span>', { class: 'field-type-icon' }).html(typeIcon));
                $field.append($('<span>', { class: 'field-name' }).text(field.name));
                $field.append($('<span>', { class: 'field-type text-muted' }).text(field.type));

                // Indicador required
                if (field.required) {
                    $field.append($('<span>', { class: 'field-required badge badge-danger' }).text('*'));
                }

                // Handle para conexion
                $field.append($('<div>', { class: 'field-handle ' + type + '-handle' }));

                $fields.append($field);
            });

            $node.append($header).append($fields);
            return $node;
        },

        /**
         * Obtener icono segun tipo de campo
         */
        _getTypeIcon: function (type) {
            var icons = {
                'char': '&#128172;',     // Texto
                'varchar': '&#128172;',
                'text': '&#128196;',
                'integer': '&#128290;',   // Numero
                'int': '&#128290;',
                'bigint': '&#128290;',
                'float': '&#128178;',
                'decimal': '&#128178;',
                'numeric': '&#128178;',
                'boolean': '&#9989;',     // Check
                'bool': '&#9989;',
                'date': '&#128197;',      // Calendario
                'datetime': '&#128337;',  // Reloj
                'timestamp': '&#128337;',
                'many2one': '&#128279;',  // Link
                'one2many': '&#128281;',
                'many2many': '&#128256;',
                'binary': '&#128190;',    // Archivo
                'selection': '&#128203;', // Lista
            };
            return icons[type.toLowerCase()] || '&#128300;';
        },

        /**
         * Cargar mapeos existentes
         */
        _loadExistingMappings: function (mappings) {
            var self = this;
            this.mappings = mappings || [];

            this.mappings.forEach(function (mapping) {
                self._createConnection(mapping);
            });

            this._drawConnections();
        },

        /**
         * Evento: Mouse down en campo (inicio de conexion)
         */
        _onFieldMouseDown: function (ev) {
            var $field = $(ev.currentTarget);
            var type = $field.data('type');

            // Solo permite arrastrar desde origen
            if (type !== 'source') return;

            ev.preventDefault();
            ev.stopPropagation();

            this.selectedField = {
                element: $field,
                table: $field.data('table'),
                field: $field.data('field'),
                type: type
            };

            $field.addClass('dragging');
            this.$('.target-node .field-item').addClass('drop-target');

            // Crear linea temporal
            this.tempLine = {
                startX: ev.pageX,
                startY: ev.pageY
            };
        },

        /**
         * Evento: Mouse move
         */
        _onMouseMove: function (ev) {
            // Arrastrar nodo
            if (this.draggedNode) {
                var $node = this.draggedNode.element;
                $node.css({
                    left: (ev.pageX - this.draggedNode.offsetX) + 'px',
                    top: (ev.pageY - this.draggedNode.offsetY) + 'px'
                });
                this._drawConnections();
                return;
            }

            // Dibujar linea temporal de conexion
            if (this.selectedField && this.tempLine) {
                this._drawTempLine(ev.pageX, ev.pageY);
            }
        },

        /**
         * Evento: Mouse up
         */
        _onMouseUp: function (ev) {
            // Soltar nodo
            if (this.draggedNode) {
                this.draggedNode = null;
                return;
            }

            // Finalizar conexion de campo
            if (this.selectedField) {
                var $target = $(ev.target).closest('.field-item');

                if ($target.length && $target.data('type') === 'target') {
                    // Crear conexion
                    var mapping = {
                        source_table: this.selectedField.table,
                        source_field: this.selectedField.field,
                        target_model: $target.data('model'),
                        target_field: $target.data('field'),
                    };
                    this._addMapping(mapping);
                }

                // Limpiar
                this.selectedField.element.removeClass('dragging');
                this.$('.field-item').removeClass('drop-target');
                this.selectedField = null;
                this.tempLine = null;
                this._drawConnections();
            }
        },

        /**
         * Evento: Mouse down en nodo (arrastrar nodo)
         */
        _onNodeMouseDown: function (ev) {
            if ($(ev.target).hasClass('field-item')) return;

            var $node = $(ev.currentTarget);
            this.draggedNode = {
                element: $node,
                offsetX: ev.pageX - $node.offset().left,
                offsetY: ev.pageY - $node.offset().top
            };
        },

        /**
         * Agregar mapeo
         */
        _addMapping: function (mapping) {
            // Verificar si ya existe
            var exists = this.mappings.some(function (m) {
                return m.source_table === mapping.source_table &&
                       m.source_field === mapping.source_field &&
                       m.target_model === mapping.target_model &&
                       m.target_field === mapping.target_field;
            });

            if (!exists) {
                this.mappings.push(mapping);
                this._createConnection(mapping);
                this._drawConnections();
                this._showNotification(_t('Mapeo creado'), 'success');
            }
        },

        /**
         * Crear conexion visual
         */
        _createConnection: function (mapping) {
            this.connections.push({
                mapping: mapping,
                sourceId: mapping.source_table + '_' + mapping.source_field,
                targetId: mapping.target_model + '_' + mapping.target_field
            });
        },

        /**
         * Dibujar todas las conexiones
         */
        _drawConnections: function () {
            if (!this.ctx) return;

            var self = this;
            var canvas = this.canvas;
            var container = this.$('.canvas-container')[0];

            // Ajustar tamano del canvas
            canvas.width = container.offsetWidth;
            canvas.height = container.offsetHeight;

            // Limpiar
            this.ctx.clearRect(0, 0, canvas.width, canvas.height);

            // Dibujar cada conexion
            this.connections.forEach(function (conn) {
                self._drawConnection(conn);
            });
        },

        /**
         * Dibujar una conexion
         */
        _drawConnection: function (conn) {
            var $source = this.$('.source-node [data-table="' + conn.mapping.source_table + '"][data-field="' + conn.mapping.source_field + '"]');
            var $target = this.$('.target-node [data-model="' + conn.mapping.target_model + '"][data-field="' + conn.mapping.target_field + '"]');

            if (!$source.length || !$target.length) return;

            var containerOffset = this.$('.canvas-container').offset();
            var sourcePos = $source.offset();
            var targetPos = $target.offset();

            var startX = sourcePos.left + $source.outerWidth() - containerOffset.left;
            var startY = sourcePos.top + ($source.outerHeight() / 2) - containerOffset.top;
            var endX = targetPos.left - containerOffset.left;
            var endY = targetPos.top + ($target.outerHeight() / 2) - containerOffset.top;

            // Dibujar curva bezier
            this.ctx.beginPath();
            this.ctx.strokeStyle = '#7c3aed';
            this.ctx.lineWidth = 2;

            var cp1x = startX + (endX - startX) / 2;
            var cp1y = startY;
            var cp2x = startX + (endX - startX) / 2;
            var cp2y = endY;

            this.ctx.moveTo(startX, startY);
            this.ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, endX, endY);
            this.ctx.stroke();

            // Dibujar flecha
            this._drawArrow(endX, endY, cp2x, cp2y);
        },

        /**
         * Dibujar flecha al final de la linea
         */
        _drawArrow: function (x, y, fromX, fromY) {
            var angle = Math.atan2(y - fromY, x - fromX);
            var arrowLength = 10;

            this.ctx.beginPath();
            this.ctx.fillStyle = '#7c3aed';
            this.ctx.moveTo(x, y);
            this.ctx.lineTo(
                x - arrowLength * Math.cos(angle - Math.PI / 6),
                y - arrowLength * Math.sin(angle - Math.PI / 6)
            );
            this.ctx.lineTo(
                x - arrowLength * Math.cos(angle + Math.PI / 6),
                y - arrowLength * Math.sin(angle + Math.PI / 6)
            );
            this.ctx.closePath();
            this.ctx.fill();
        },

        /**
         * Dibujar linea temporal durante arrastre
         */
        _drawTempLine: function (mouseX, mouseY) {
            if (!this.ctx || !this.tempLine) return;

            this._drawConnections();

            var containerOffset = this.$('.canvas-container').offset();
            var $source = this.selectedField.element;
            var sourcePos = $source.offset();

            var startX = sourcePos.left + $source.outerWidth() - containerOffset.left;
            var startY = sourcePos.top + ($source.outerHeight() / 2) - containerOffset.top;
            var endX = mouseX - containerOffset.left;
            var endY = mouseY - containerOffset.top;

            this.ctx.beginPath();
            this.ctx.strokeStyle = '#94a3b8';
            this.ctx.lineWidth = 2;
            this.ctx.setLineDash([5, 5]);

            var cp1x = startX + (endX - startX) / 2;
            var cp1y = startY;
            var cp2x = startX + (endX - startX) / 2;
            var cp2y = endY;

            this.ctx.moveTo(startX, startY);
            this.ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, endX, endY);
            this.ctx.stroke();
            this.ctx.setLineDash([]);
        },

        /**
         * Auto-mapear campos por nombre similar
         */
        _onAutoMap: function () {
            var self = this;

            ajax.jsonRpc('/migration/api/project/' + this.projectId + '/auto-map', 'call', {})
                .then(function (result) {
                    if (result.success) {
                        result.suggested_mappings.forEach(function (mapping) {
                            self._addMapping(mapping);
                        });
                        self._showNotification(
                            _t('%s mapeos sugeridos', result.suggested_mappings.length),
                            'success'
                        );
                    }
                });
        },

        /**
         * Limpiar todos los mapeos
         */
        _onClearMappings: function () {
            this.mappings = [];
            this.connections = [];
            this._drawConnections();
            this._showNotification(_t('Mapeos limpiados'), 'info');
        },

        /**
         * Guardar mapeos
         */
        _onSaveMappings: function () {
            var self = this;

            ajax.jsonRpc('/migration/api/project/' + this.projectId + '/mappings/save', 'call', {
                mappings: this.mappings
            }).then(function (result) {
                if (result.success) {
                    self._showNotification(_t('Mapeos guardados exitosamente'), 'success');
                } else {
                    self._showNotification(result.error || _t('Error guardando'), 'danger');
                }
            });
        },

        /**
         * Zoom in
         */
        _onZoomIn: function () {
            this.zoom = Math.min(this.zoom + 0.1, 2);
            this._applyZoom();
        },

        /**
         * Zoom out
         */
        _onZoomOut: function () {
            this.zoom = Math.max(this.zoom - 0.1, 0.5);
            this._applyZoom();
        },

        /**
         * Ajustar a pantalla
         */
        _onFitScreen: function () {
            this.zoom = 1;
            this.pan = { x: 0, y: 0 };
            this._applyZoom();
        },

        /**
         * Aplicar zoom
         */
        _applyZoom: function () {
            this.$('.canvas-container').css({
                transform: 'scale(' + this.zoom + ') translate(' + this.pan.x + 'px, ' + this.pan.y + 'px)'
            });
            this._drawConnections();
        },

        /**
         * Evento: Resize
         */
        _onResize: function () {
            this._drawConnections();
        },

        /**
         * Mostrar notificacion
         */
        _showNotification: function (message, type) {
            var $notif = $('<div>', {
                class: 'mapper-notification alert alert-' + type,
                text: message
            });
            this.$('.notifications-area').append($notif);
            setTimeout(function () {
                $notif.fadeOut(function () { $(this).remove(); });
            }, 3000);
        }
    });

    publicWidget.registry.VisualMapper = VisualMapper;
    return VisualMapper;
});
