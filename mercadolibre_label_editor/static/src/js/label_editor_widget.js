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
        });

        this.canvasRef = useRef("pdfCanvas");

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
        });
    }

    async loadPDF() {
        // Obtener el valor del PDF desde props
        const pdfData = this.props.record.data[this.props.name];

        console.log('LabelEditorWidget - Intentando cargar PDF...');
        console.log('LabelEditorWidget - Props completos:', this.props);
        console.log('LabelEditorWidget - Record data:', this.props.record.data);
        console.log('LabelEditorWidget - Field name:', this.props.name);
        console.log('PDF Data:', pdfData ? `${pdfData.substring(0, 50)}...` : 'null');

        if (!pdfData) {
            console.warn('LabelEditorWidget - No hay PDF cargado');
            this.state.error = null; // No mostrar error si simplemente no hay PDF
            this.state.pdfLoaded = false;
            return;
        }

        try {
            // Verificar si PDF.js está disponible
            if (typeof pdfjsLib === 'undefined') {
                console.warn('LabelEditorWidget - PDF.js no está disponible, cargándolo...');
                // Intentar cargar PDF.js dinámicamente
                await this.loadPDFJS();
                if (typeof pdfjsLib === 'undefined') {
                    this.state.error = 'PDF.js no está disponible';
                    return;
                }
            }

            // Configurar worker de PDF.js
            pdfjsLib.GlobalWorkerOptions.workerSrc =
                'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

            console.log('LabelEditorWidget - Cargando PDF con PDF.js...');

            // Depuración: mostrar tipo y muestra del PDF data
            console.log('LabelEditorWidget - Tipo de pdfData:', typeof pdfData);
            console.log('LabelEditorWidget - Muestra de datos (primeros 100 chars):', pdfData.substring(0, 100));
            console.log('LabelEditorWidget - Últimos 50 chars:', pdfData.substring(pdfData.length - 50));

            // Limpiar y validar base64
            let cleanedPdfData = pdfData;

            // Si tiene prefijo data:application/pdf;base64, quitarlo
            if (pdfData.includes('base64,')) {
                console.log('LabelEditorWidget - Detectado prefijo data URI, removiendo...');
                cleanedPdfData = pdfData.split('base64,')[1];
            }

            // Limpiar espacios en blanco, saltos de línea y caracteres no válidos
            cleanedPdfData = cleanedPdfData.replace(/[\s\n\r]/g, '');

            // Validar que solo contenga caracteres base64 válidos
            const base64Regex = /^[A-Za-z0-9+/]*={0,2}$/;
            if (!base64Regex.test(cleanedPdfData)) {
                console.error('LabelEditorWidget - Base64 contiene caracteres inválidos');
                console.log('LabelEditorWidget - Muestra del base64 limpiado:', cleanedPdfData.substring(0, 100));

                // Intentar limpiar caracteres no base64
                cleanedPdfData = cleanedPdfData.replace(/[^A-Za-z0-9+/=]/g, '');
                console.log('LabelEditorWidget - Base64 después de limpieza adicional:', cleanedPdfData.substring(0, 100));
            }

            console.log('LabelEditorWidget - Base64 limpiado, longitud:', cleanedPdfData.length);

            // Convertir base64 a Uint8Array de manera segura
            let pdfBytes;
            try {
                const binaryString = atob(cleanedPdfData);
                const len = binaryString.length;
                pdfBytes = new Uint8Array(len);
                for (let i = 0; i < len; i++) {
                    pdfBytes[i] = binaryString.charCodeAt(i);
                }
                console.log('LabelEditorWidget - PDF convertido a bytes, tamaño:', pdfBytes.length);

                // Verificar que sea un PDF válido (debe empezar con %PDF)
                const header = String.fromCharCode(...pdfBytes.slice(0, 5));
                console.log('LabelEditorWidget - Header del archivo:', header);
                if (!header.startsWith('%PDF')) {
                    console.warn('LabelEditorWidget - ADVERTENCIA: El archivo no parece ser un PDF válido');
                }
            } catch (decodeError) {
                console.error('LabelEditorWidget - Error decodificando base64:', decodeError);
                console.error('LabelEditorWidget - Longitud del base64:', cleanedPdfData.length);
                console.error('LabelEditorWidget - Primeros 200 caracteres:', cleanedPdfData.substring(0, 200));
                this.state.error = 'Error decodificando PDF: ' + decodeError.message;
                return;
            }

            // Cargar PDF con los bytes
            const loadingTask = pdfjsLib.getDocument({
                data: pdfBytes,
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
