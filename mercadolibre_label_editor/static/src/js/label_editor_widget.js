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
            pdfWidth: 0,  // Ancho real del PDF (sin escala)
            pdfHeight: 0, // Alto real del PDF (sin escala)
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

        // Recargar PDF cuando cambie el valor o el record ID
        onWillUpdateProps((nextProps) => {
            const currentResId = this.props.record.resId;
            const nextResId = nextProps.record.resId;
            const currentPdfData = this.props.record.data[this.props.name];
            const nextPdfData = nextProps.record.data[nextProps.name];

            // Detectar cambio de resId (después de guardar un registro nuevo)
            if (currentResId !== nextResId) {
                console.log('LabelEditorWidget - Record ID changed (saved):', currentResId, '->', nextResId);
                setTimeout(() => this.loadPDF(), 100);
            }
            // Detectar cambio en el PDF
            else if (currentPdfData !== nextPdfData) {
                console.log('LabelEditorWidget - PDF data changed, reloading...');
                setTimeout(() => this.loadPDF(), 100);
            }

            // Detectar cambios en los campos para actualizar el overlay en tiempo real
            // Necesitamos comparar a nivel profundo, no solo la referencia
            const currentFieldsData = this._serializeFields(this.props.record.data.field_ids);
            const nextFieldsData = this._serializeFields(nextProps.record.data.field_ids);

            if (currentFieldsData !== nextFieldsData) {
                console.log('LabelEditorWidget - Fields data changed, updating overlay in real-time...');
                // Incrementar key para forzar re-renderizado del overlay
                this.state.fieldsUpdateKey++;
            }
        });
    }

    _serializeFields(fieldIds) {
        /**
         * Serializa los campos a un string para detectar cambios
         * Compara: valor, posición, estilo, activo
         */
        if (!fieldIds || !fieldIds.records) return 'empty';

        return fieldIds.records.map(field => {
            const data = field.data;
            return JSON.stringify({
                id: field.id,
                name: data.name,
                value: data.value,
                x: data.position_x,
                y: data.position_y,
                size: data.font_size,
                color: data.color,
                align: data.align,
                font: data.font_family,
                active: data.active
            });
        }).join('|');
    }

    async loadPDF() {
        console.log('═══════════════════════════════════════════════');
        console.log('LabelEditorWidget - Intentando cargar PDF...');
        console.log('LabelEditorWidget - Record ID:', this.props.record.resId);
        console.log('LabelEditorWidget - Record Model:', this.props.record.resModel);
        console.log('LabelEditorWidget - Field name:', this.props.name);
        console.log('═══════════════════════════════════════════════');

        // En Odoo, los campos Binary necesitan descargarse explícitamente
        // No podemos usar props.record.data directamente para binarios grandes
        const recordId = this.props.record.resId;
        const fieldName = this.props.name;

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

            // Preparar canvas - usar scale 1.5 para mejor calidad visual
            const renderScale = 1.5;
            const viewport = page.getViewport({ scale: renderScale });
            const canvas = this.canvasRef.el;

            if (canvas) {
                canvas.width = viewport.width;
                canvas.height = viewport.height;

                // Guardar el scale y dimensiones reales del PDF para cálculos de coordenadas
                this.state.scale = renderScale;

                // Obtener dimensiones reales del PDF (sin escala)
                const realPdfWidth = viewport.width / renderScale;
                const realPdfHeight = viewport.height / renderScale;

                // Guardar en el state
                this.state.pdfWidth = Math.round(realPdfWidth);
                this.state.pdfHeight = Math.round(realPdfHeight);

                // Guardar en el record si no existen
                if (!this.props.record.data.pdf_width || !this.props.record.data.pdf_height) {
                    this.props.record.update({
                        pdf_width: Math.round(realPdfWidth),
                        pdf_height: Math.round(realPdfHeight)
                    });
                }

                const context = canvas.getContext('2d');
                const renderContext = {
                    canvasContext: context,
                    viewport: viewport
                };

                await page.render(renderContext).promise;
                this.state.pdfLoaded = true;
                this.state.error = null;
                console.log('LabelEditorWidget - PDF renderizado exitosamente con scale:', renderScale);
                console.log('LabelEditorWidget - Canvas dimensions:', canvas.width, 'x', canvas.height);
                console.log('LabelEditorWidget - PDF real dimensions:', realPdfWidth, 'x', realPdfHeight);
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

        // Obtener coordenadas relativas al canvas en su tamaño de renderizado
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        const canvasX = (ev.clientX - rect.left) * scaleX;
        const canvasY = (ev.clientY - rect.top) * scaleY;

        // Convertir a coordenadas del PDF real (dividir por el scale de renderizado)
        const pdfX = Math.round(canvasX / this.state.scale);
        const pdfYCanvas = Math.round(canvasY / this.state.scale);

        // INVERTIR Y: En PyPDF2, Y=0 está abajo, pero en canvas HTML está arriba
        // Necesitamos invertir para que sea compatible con PyPDF2
        const pdfHeight = this.state.pdfHeight || this.props.record.data.pdf_height || 0;
        const pdfY = pdfHeight - pdfYCanvas;

        this.state.mouseX = pdfX;
        this.state.mouseY = pdfY;
        this.state.showCoordinates = true;
    }

    onCanvasMouseLeave() {
        this.state.showCoordinates = false;
    }

    onCanvasClick(ev) {
        const canvas = this.canvasRef.el;
        if (!canvas) return;

        const rect = canvas.getBoundingClientRect();

        // Obtener coordenadas relativas al canvas en su tamaño de renderizado
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        const canvasX = (ev.clientX - rect.left) * scaleX;
        const canvasY = (ev.clientY - rect.top) * scaleY;

        // Convertir a coordenadas del PDF real (sin el scale de renderizado)
        const pdfX = Math.round(canvasX / this.state.scale);
        const pdfYCanvas = Math.round(canvasY / this.state.scale);

        // INVERTIR Y: En PyPDF2, Y=0 está abajo, pero en canvas HTML está arriba
        const pdfHeight = this.state.pdfHeight || this.props.record.data.pdf_height || 0;
        const pdfY = pdfHeight - pdfYCanvas;

        console.log(`Posición clickeada (PDF PyPDF2): X=${pdfX}, Y=${pdfY}`);
        console.log(`Canvas renderizado: ${canvasX}x${canvasY}, Canvas Y: ${pdfYCanvas}, PDF Height: ${pdfHeight}`);

        // Copiar al portapapeles las coordenadas del PDF real (formato PyPDF2)
        const coords = `X: ${pdfX}, Y: ${pdfY}`;
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

        // Obtener altura del PDF (preferir state, luego record)
        const pdfHeight = this.state.pdfHeight || this.props.record.data.pdf_height || 0;

        if (!pdfHeight) {
            console.warn('LabelEditorWidget - PDF height no disponible, no se pueden renderizar campos');
            return [];
        }

        const fields = fieldIds.records
            .filter(field => field.data.active !== false)
            .map((field, index) => {
                // Las coordenadas en la BD están en formato PyPDF2 (Y=0 abajo)
                // Necesitamos invertir Y para el canvas HTML (Y=0 arriba)
                const pdfYPyPDF2 = field.data.position_y || 0;
                const canvasY = pdfHeight - pdfYPyPDF2;

                const fieldData = {
                    id: field.id || index,
                    name: field.data.name || '',
                    value: field.data.value || '',
                    x: field.data.position_x || 0,
                    y: canvasY,  // Y invertida para el canvas
                    fontSize: field.data.font_size || 12,
                    color: field.data.color || '#000000',
                    align: field.data.align || 'left',
                    fontFamily: field.data.font_family || 'Helvetica',
                };
                return fieldData;
            });

        console.log(`LabelEditorWidget - Campos configurados (${fields.length}), PDF Height: ${pdfHeight}:`, fields);
        return fields;
    }
}

LabelEditorWidget.template = "mercadolibre_label_editor.LabelEditorWidget";
LabelEditorWidget.props = {
    ...standardFieldProps,
};

registry.category("fields").add("label_editor", LabelEditorWidget);
