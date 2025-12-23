/** @odoo-module **/

import { Component, useRef, onMounted, useState } from "@odoo/owl";
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
        });

        this.canvasRef = useRef("pdfCanvas");

        onMounted(() => {
            this.loadPDF();
        });
    }

    async loadPDF() {
        const pdfData = this.props.value;

        if (!pdfData) {
            this.state.error = "No hay PDF cargado";
            return;
        }

        try {
            // Verificar si PDF.js está disponible
            if (typeof pdfjsLib === 'undefined') {
                console.warn('PDF.js no está cargado, mostrando vista simplificada');
                this.state.pdfLoaded = false;
                return;
            }

            // Configurar worker de PDF.js
            pdfjsLib.GlobalWorkerOptions.workerSrc =
                'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

            // Cargar PDF
            const loadingTask = pdfjsLib.getDocument({ data: atob(pdfData) });
            const pdf = await loadingTask.promise;
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
            }

        } catch (error) {
            console.error('Error cargando PDF:', error);
            this.state.error = error.message;
        }
    }

    get displayInfo() {
        const record = this.props.record;
        const data = record.data;

        return {
            width: data.pdf_width || 'N/A',
            height: data.pdf_height || 'N/A',
            fieldCount: data.field_count || 0,
        };
    }
}

LabelEditorWidget.template = "mercadolibre_label_editor.LabelEditorWidget";
LabelEditorWidget.props = {
    ...standardFieldProps,
};

registry.category("fields").add("label_editor", LabelEditorWidget);
