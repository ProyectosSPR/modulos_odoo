/** @odoo-module **/

import { Component, useRef, onMounted, onWillUpdateProps, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Widget básico para editor de etiquetas ML
 * Versión simplificada que muestra el PDF y permite editar campos en formulario
 */
export class LabelEditorWidget extends Component {
    setup() {
        this.state = useState({
            pdfLoaded: false,
            error: null,
            scale: 1.0,
            mouseX: 0,
            mouseY: 0,
            showCoordinates: false,
            fieldsUpdateKey: 0, // Key para forzar actualización del overlay
        });

        this.canvasRef = useRef("pdfCanvas");
        this.overlayRef = useRef("fieldOverlay");

        onMounted(() => {
            this.loadPDF();
        });

        // Recargar PDF cuando cambie el valor
        onWillUpdateProps((nextProps) => {
            const currentPdfData = this.props.record.data[this.props.name];
            const nextPdfData = nextProps.record.data[nextProps.name];

            if (currentPdfData !== nextPdfData) {
                console.log('LabelEditorWidget - PDF data changed, reloading...');
                // Usar setTimeout para asegurar que el DOM esté actualizado
                setTimeout(() => this.loadPDF(), 100);
            }

            // Detectar cambios en los campos para actualizar el overlay en tiempo real
            const currentFields = this.props.record.data.field_ids;
            const nextFields = nextProps.record.data.field_ids;

            if (currentFields !== nextFields) {
                console.log('LabelEditorWidget - Fields changed, updating overlay in real-time...');
                // Incrementar key para forzar re-renderizado del overlay
                this.state.fieldsUpdateKey++;
            }
        });
    }

    async loadPDF() {
        console.log('LabelEditorWidget - Intentando cargar PDF...');
        console.log('LabelEditorWidget - Props completos:', this.props);
        console.log('LabelEditorWidget - Record data:', this.props.record.data);
        console.log('LabelEditorWidget - Field name:', this.props.name);

        // En Odoo, los campos Binary necesitan descargarse explícitamente
        // No podemos usar props.record.data directamente para binarios grandes
        const recordId = this.props.record.resId;
        const fieldName = this.props.name;

        console.log('LabelEditorWidget - Record ID:', recordId);
        console.log('LabelEditorWidget - Field name:', fieldName);

        if (!recordId) {
            console.warn('LabelEditorWidget - No hay record ID (registro nuevo sin guardar)');
            this.state.error = null;
            this.state.pdfLoaded = false;
            return;
        }

        // Construir URL para descargar el PDF
        const pdfUrl = `/web/content?model=${this.props.record.resModel}&id=${recordId}&field=${fieldName}&download=false`;
        console.log('LabelEditorWidget - URL del PDF:', pdfUrl);

        try {
            // Verificar si PDF.js está disponible
            if (typeof pdfjsLib === 'undefined') {
                console.warn('LabelEditorWidget - PDF.js no está disponible, cargándolo...');
                await this.loadPDFJS();
                if (typeof pdfjsLib === 'undefined') {
                    this.state.error = 'PDF.js no está disponible';
                    return;
                }
            }

            // Configurar worker de PDF.js
            pdfjsLib.GlobalWorkerOptions.workerSrc =
                'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

            console.log('LabelEditorWidget - Descargando PDF desde URL...');

            // Descargar el PDF directamente desde la URL
            const response = await fetch(pdfUrl);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            // Obtener el PDF como ArrayBuffer
            const pdfArrayBuffer = await response.arrayBuffer();
            console.log('LabelEditorWidget - PDF descargado, tamaño:', pdfArrayBuffer.byteLength, 'bytes');

            // Verificar que sea un PDF válido
            const pdfBytes = new Uint8Array(pdfArrayBuffer);
            const header = String.fromCharCode(...pdfBytes.slice(0, 5));
            console.log('LabelEditorWidget - Header del archivo:', header);

            if (!header.startsWith('%PDF')) {
                throw new Error('El archivo no es un PDF válido');
            }

            // Cargar PDF con PDF.js usando el ArrayBuffer
            const loadingTask = pdfjsLib.getDocument({
                data: pdfArrayBuffer,
                verbosity: 0
            });

            const pdf = await loadingTask.promise;
            console.log('LabelEditorWidget - PDF cargado, páginas:', pdf.numPages);

            const page = await pdf.getPage(1);

            // Preparar canvas
            const viewport = page.getViewport({ scale: 1.5 });
            const canvas = this.canvasRef.el;

            if (canvas) {
                canvas.width = viewport.width;
                canvas.height = viewport.height;

                const context = canvas.getContext('2d');
                const renderContext = {
                    canvasContext: context,
                    viewport: viewport
                };

                await page.render(renderContext).promise;
                this.state.pdfLoaded = true;
                this.state.error = null;
                console.log('LabelEditorWidget - PDF renderizado exitosamente');
            } else {
                console.error('LabelEditorWidget - Canvas no disponible');
                this.state.error = 'Canvas no disponible';
            }

        } catch (error) {
            console.error('LabelEditorWidget - Error cargando PDF:', error);
            this.state.error = error.message || 'Error desconocido al cargar PDF';
            this.state.pdfLoaded = false;
        }
    }

    async loadPDFJS() {
        // Cargar PDF.js si no está disponible
        if (typeof pdfjsLib !== 'undefined') {
            return;
        }

        try {
            const script = document.createElement('script');
            script.src = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js';

            await new Promise((resolve, reject) => {
                script.onload = resolve;
                script.onerror = reject;
                document.head.appendChild(script);
            });

            console.log('PDF.js cargado dinámicamente');
        } catch (error) {
            console.error('Error cargando PDF.js:', error);
        }
    }

    get displayInfo() {
        const data = this.props.record.data;

        // Contar campos activos en tiempo real
        const activeFieldsCount = this.configuredFields.length;

        return {
            width: data.pdf_width || 'N/A',
            height: data.pdf_height || 'N/A',
            fieldCount: activeFieldsCount,
        };
    }

    onCanvasMouseMove(ev) {
        const canvas = this.canvasRef.el;
        if (!canvas) return;

        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;

        // Coordenadas relativas al canvas en píxeles reales
        const x = Math.round((ev.clientX - rect.left) * scaleX);
        const y = Math.round((ev.clientY - rect.top) * scaleY);

        this.state.mouseX = x;
        this.state.mouseY = y;
        this.state.showCoordinates = true;
    }

    onCanvasMouseLeave() {
        this.state.showCoordinates = false;
    }

    onCanvasClick(ev) {
        const canvas = this.canvasRef.el;
        if (!canvas) return;

        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;

        const x = Math.round((ev.clientX - rect.left) * scaleX);
        const y = Math.round((ev.clientY - rect.top) * scaleY);

        console.log(`Posición clickeada: X=${x}, Y=${y}`);

        // Copiar al portapapeles
        const coords = `X: ${x}, Y: ${y}`;
        navigator.clipboard.writeText(coords).then(() => {
            console.log('Coordenadas copiadas al portapapeles:', coords);
            // Mostrar notificación
            this.env.services.notification.add(
                `Coordenadas copiadas: ${coords}`,
                { type: 'success' }
            );
        });
    }

    get configuredFields() {
        // El fieldsUpdateKey se usa para forzar re-cálculo cuando cambian los campos
        const _updateKey = this.state.fieldsUpdateKey;

        // Obtener los campos configurados desde el record
        const fieldIds = this.props.record.data.field_ids;
        if (!fieldIds || !fieldIds.records) {
            console.log('LabelEditorWidget - No hay campos configurados');
            return [];
        }

        const fields = fieldIds.records
            .filter(field => field.data.active !== false)
            .map((field, index) => {
                const fieldData = {
                    id: field.id || index,
                    name: field.data.name || '',
                    value: field.data.value || '',
                    x: field.data.position_x || 0,
                    y: field.data.position_y || 0,
                    fontSize: field.data.font_size || 12,
                    color: field.data.color || '#000000',
                    align: field.data.align || 'left',
                    fontFamily: field.data.font_family || 'Helvetica',
                };
                return fieldData;
            });

        console.log(`LabelEditorWidget - Campos configurados (${fields.length}):`, fields);
        return fields;
    }
}

LabelEditorWidget.template = "mercadolibre_label_editor.LabelEditorWidget";
LabelEditorWidget.props = {
    ...standardFieldProps,
};

registry.category("fields").add("label_editor", LabelEditorWidget);
