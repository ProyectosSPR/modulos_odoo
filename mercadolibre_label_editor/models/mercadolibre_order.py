# -*- coding: utf-8 -*-

import base64
import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class MercadolibreOrder(models.Model):
    _inherit = 'mercadolibre.order'

    def _download_and_save_shipping_label(self, logistic_config=None):
        """
        Override para aplicar plantilla personalizada automáticamente
        después de descargar la etiqueta de MercadoLibre.
        """
        # Llamar al método original
        result = super()._download_and_save_shipping_label(logistic_config)

        # Si la descarga fue exitosa y hay plantilla configurada, aplicarla
        if result.get('success') and logistic_config and logistic_config.label_template_id:
            attachment = result.get('attachment')

            if attachment and self.sale_order_id:
                try:
                    _logger.info(
                        f'Aplicando plantilla "{logistic_config.label_template_id.name}" '
                        f'a etiqueta de orden {self.ml_order_id}'
                    )

                    # Obtener PDF original
                    pdf_bytes = base64.b64decode(attachment.datas)

                    # Aplicar plantilla usando el procesador
                    processor = self.env['ml.label.processor']
                    modified_pdf = processor.apply_template(
                        pdf_bytes=pdf_bytes,
                        template=logistic_config.label_template_id,
                        context_record=self.sale_order_id
                    )

                    # Actualizar adjunto con PDF modificado
                    new_filename = f'etiqueta_ml_{self.ml_shipment_id}_personalizada.pdf'
                    attachment.write({
                        'datas': base64.b64encode(modified_pdf),
                        'name': new_filename,
                    })

                    result['template_applied'] = True
                    result['template_name'] = logistic_config.label_template_id.name
                    result['filename'] = new_filename

                    _logger.info(
                        f'Plantilla aplicada exitosamente a etiqueta {self.ml_shipment_id}'
                    )

                except Exception as e:
                    _logger.error(
                        f'Error aplicando plantilla a etiqueta {self.ml_shipment_id}: {e}',
                        exc_info=True
                    )
                    result['template_error'] = str(e)
                    result['template_applied'] = False

                    # Notificar al usuario del error pero mantener el PDF original
                    self.message_post(
                        body=f'⚠️ Error aplicando plantilla personalizada: {str(e)}<br/>'
                             f'Se guardó la etiqueta original sin modificaciones.',
                        subject='Error en Plantilla de Etiqueta'
                    )

        return result

    def action_regenerate_label_with_template(self):
        """
        Regenera la etiqueta aplicando la plantilla configurada.
        Útil para re-procesar etiquetas ya descargadas.
        """
        self.ensure_one()

        if not self.ml_shipment_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin Envío',
                    'message': 'Esta orden no tiene un envío de MercadoLibre asociado.',
                    'type': 'warning',
                }
            }

        if not self.sale_order_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin Orden de Venta',
                    'message': 'Esta orden ML no tiene orden de venta asociada.',
                    'type': 'warning',
                }
            }

        # Obtener configuración de tipo logístico
        logistic_config = self.logistic_type_id

        if not logistic_config or not logistic_config.label_template_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin Plantilla',
                    'message': 'No hay plantilla configurada para este tipo logístico.',
                    'type': 'warning',
                }
            }

        # Buscar etiqueta existente
        existing_attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'sale.order'),
            ('res_id', '=', self.sale_order_id.id),
            ('name', 'ilike', f'etiqueta_ml_{self.ml_shipment_id}')
        ], limit=1)

        if not existing_attachment:
            # Si no existe, descargar primero
            return self.action_download_shipping_label()

        try:
            # Aplicar plantilla sobre etiqueta existente
            pdf_bytes = base64.b64decode(existing_attachment.datas)

            processor = self.env['ml.label.processor']
            modified_pdf = processor.apply_template(
                pdf_bytes=pdf_bytes,
                template=logistic_config.label_template_id,
                context_record=self.sale_order_id
            )

            # Actualizar attachment
            existing_attachment.write({
                'datas': base64.b64encode(modified_pdf),
                'name': f'etiqueta_ml_{self.ml_shipment_id}_personalizada.pdf',
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Etiqueta Regenerada',
                    'message': f'Etiqueta procesada con plantilla "{logistic_config.label_template_id.name}"',
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error(f'Error regenerando etiqueta: {e}', exc_info=True)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Error al regenerar etiqueta: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }
