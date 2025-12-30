# -*- coding: utf-8 -*-

import base64
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class MercadolibreOrder(models.Model):
    _inherit = 'mercadolibre.order'

    # =========================================================================
    # WEBHOOK - SINCRONIZACIÓN DE ÓRDENES EXISTENTES
    # =========================================================================

    @api.model
    def process_notification(self, account, data):
        """
        Override para agregar sincronización de órdenes de venta existentes
        cuando llega un webhook.
        """
        # Llamar al método original
        result = super().process_notification(account, data)

        # Si fue exitoso y la orden tiene sale_order, sincronizar
        if result.get('status') == 'success' and result.get('order_id'):
            order = self.browse(result['order_id'])
            if order.sale_order_id:
                try:
                    self._sync_to_existing_sale_order(order)
                except Exception as e:
                    _logger.error(f'Error sincronizando a sale.order: {e}')

        return result

    def _sync_to_existing_sale_order(self, order=None):
        """
        Sincroniza los datos actualizados de mercadolibre.order a sale.order existente.
        Se llama cuando llega un webhook para una orden que ya tiene orden de venta.
        Actualiza: estados ML, estado de envío, tags, monto pagado, etc.
        """
        if order is None:
            order = self

        order.ensure_one()

        if not order.sale_order_id:
            return

        sale_order = order.sale_order_id
        _logger.info(f'═══ SYNC WEBHOOK → SALE.ORDER {sale_order.name} ═══')
        _logger.info(f'Orden ML: {order.ml_order_id}')
        _logger.info(f'Estado ML: {order.status}')

        # Actualizar campos en sale.order si cambiaron
        update_vals = {}
        changes = []

        # Sincronizar shipment_id si no estaba
        if order.ml_shipment_id and not sale_order.ml_shipment_id:
            update_vals['ml_shipment_id'] = order.ml_shipment_id
            _logger.info(f'Actualizando shipment_id: {order.ml_shipment_id}')

        # Sincronizar tipo logístico si cambió
        if order.logistic_type and order.logistic_type != sale_order.ml_logistic_type:
            update_vals['ml_logistic_type'] = order.logistic_type
            _logger.info(f'Actualizando tipo logístico: {order.logistic_type}')

        # Sincronizar estado ML (nuevo campo)
        if order.status and order.status != sale_order.ml_status:
            update_vals['ml_status'] = order.status
            changes.append(f'estado: {sale_order.ml_status or "vacío"} → {order.status}')
            _logger.info(f'Actualizando ml_status: {order.status}')

        # Obtener estado de envío usando el método helper
        shipping_status = order._get_shipping_status()

        # Sincronizar estado de envío ML (nuevo campo)
        if shipping_status and shipping_status != sale_order.ml_shipping_status:
            update_vals['ml_shipping_status'] = shipping_status
            changes.append(f'envío: {sale_order.ml_shipping_status or "vacío"} → {shipping_status}')
            _logger.info(f'Actualizando ml_shipping_status: {shipping_status}')

        # Sincronizar tags ML (nuevo campo)
        order_tags = order.ml_tags if hasattr(order, 'ml_tags') and order.ml_tags else ''
        if order_tags and order_tags != (sale_order.ml_tags or ''):
            update_vals['ml_tags'] = order_tags
            changes.append('tags actualizados')
            _logger.info(f'Actualizando ml_tags: {order_tags}')

        # Sincronizar monto pagado (nuevo campo)
        if order.paid_amount and order.paid_amount != sale_order.ml_paid_amount:
            update_vals['ml_paid_amount'] = order.paid_amount
            changes.append(f'pago: {sale_order.ml_paid_amount or 0} → {order.paid_amount}')
            _logger.info(f'Actualizando ml_paid_amount: {order.paid_amount}')

        # Actualizar fecha de sync
        update_vals['ml_sync_date'] = fields.Datetime.now()

        if update_vals:
            sale_order.write(update_vals)
            if changes:
                _logger.info(f'Cambios aplicados: {", ".join(changes)}')

        # =====================================================
        # USAR MÉTODO CENTRALIZADO PARA ACTUALIZAR ESTADOS Y TAGS
        # =====================================================
        # Obtener tags de ML como string
        order_tags = order.ml_tags if hasattr(order, 'ml_tags') and order.ml_tags else ''

        # Usar la variable shipping_status ya calculada arriba
        tag_result = sale_order._update_ml_status_and_tags(
            shipment_status=shipping_status,
            payment_status=order.status,
            ml_tags=order_tags,
            paid_amount=order.paid_amount,
        )

        # Agregar cambios de tags al log
        if tag_result.get('tags_added'):
            changes.append(f'tags +: {", ".join(tag_result["tags_added"])}')
        if tag_result.get('tags_removed'):
            changes.append(f'tags -: {", ".join(tag_result["tags_removed"])}')

        # Verificar si debe cancelar en Odoo cuando ML cancela
        if order.status == 'cancelled' and sale_order.state not in ['cancel', 'done']:
            # Buscar configuración de sync que aplique
            sync_config = self.env['mercadolibre.order.sync.config'].search([
                ('account_id', '=', order.account_id.id),
                ('cancel_on_ml_cancel', '=', True),
                ('state', '=', 'active'),
            ], limit=1)

            if sync_config:
                try:
                    _logger.info(f'Cancelando orden {sale_order.name} por estado ML cancelled')
                    sale_order.with_context(
                        disable_cancel_warning=True
                    )._action_cancel()
                    changes.append('CANCELADA por estado ML')
                    sale_order.message_post(
                        body='⛔ Orden cancelada automáticamente porque '
                             'fue cancelada en MercadoLibre.',
                        subject='Cancelación Automática ML'
                    )
                except Exception as cancel_error:
                    _logger.error(f'Error cancelando orden {sale_order.name}: {cancel_error}')

        # Publicar en chatter si hubo cambios relevantes
        if order.status in ('paid', 'partially_paid') and order.ml_shipment_id:
            # Verificar si necesitamos procesar etiqueta
            logistic_config = order.logistic_type_id
            if logistic_config:
                should_download = logistic_config.download_shipping_label
                should_print = logistic_config.auto_print_label

                # Verificar si ya existe etiqueta
                existing_label = self.env['ir.attachment'].search([
                    ('res_model', '=', 'sale.order'),
                    ('res_id', '=', sale_order.id),
                    ('name', 'ilike', f'etiqueta_ml_{order.ml_shipment_id}')
                ], limit=1)

                if (should_download or should_print) and not existing_label:
                    _logger.info('Procesando etiqueta desde webhook...')
                    self._process_shipping_label(logistic_config, sale_order)
                elif existing_label and should_print:
                    # Ya existe etiqueta, solo imprimir si está configurado
                    _logger.info('Etiqueta existe, verificando si hay que reimprimir...')

        # Notificar en chatter solo si hubo cambios relevantes
        if changes:
            changes_html = '<br/>'.join([f'• {c}' for c in changes])
            sale_order.message_post(
                body=f'🔄 Actualización desde MercadoLibre (Webhook orders_v2):<br/>'
                     f'{changes_html}<br/>'
                     f'• Shipment: {order.ml_shipment_id or "Pendiente"}',
                subject='Actualización ML (Webhook)'
            )
        else:
            # Solo notificar si es primera vez con shipment
            if update_vals.get('ml_shipment_id'):
                sale_order.message_post(
                    body=f'🔄 Actualización desde MercadoLibre:<br/>'
                         f'• Estado: {order.status}<br/>'
                         f'• Monto pagado: ${order.paid_amount}<br/>'
                         f'• Shipment: {order.ml_shipment_id}',
                    subject='Actualización ML (Webhook)'
                )

        _logger.info(f'═══ FIN SYNC WEBHOOK ═══')

    def action_download_shipping_label(self):
        """
        Override para asegurar que siempre se pase la configuración del tipo logístico.
        Esto permite aplicar la plantilla y guardar en picking.
        """
        self.ensure_one()
        if not self.ml_shipment_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin Envío',
                    'message': 'Esta orden no tiene ID de envío de MercadoLibre.',
                    'type': 'warning',
                }
            }

        # Obtener configuración del tipo logístico para aplicar plantilla
        logistic_config = self.logistic_type_id

        result = self._download_and_save_shipping_label(logistic_config)

        if result.get('success'):
            # Construir mensaje con detalles
            msg_parts = [f'Etiqueta guardada: {result.get("filename")}']
            if result.get('template_applied'):
                msg_parts.append(f'Plantilla: {result.get("template_name")}')
            if result.get('picking_attachments'):
                msg_parts.append(f'Pickings: {result.get("picking_attachments")}')

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Etiqueta Descargada',
                    'message': ' | '.join(msg_parts),
                    'type': 'success',
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': result.get('error', 'Error desconocido'),
                    'type': 'danger',
                }
            }

    def _attach_label_to_picking(self, attachment):
        """
        Vincula la etiqueta de envío a los pickings relacionados de la orden de venta.
        Crea una copia del attachment para cada picking de tipo 'outgoing'.

        Args:
            attachment: ir.attachment de la etiqueta

        Returns:
            list de ir.attachment creados para los pickings
        """
        self.ensure_one()
        created_attachments = []

        if not self.sale_order_id or not attachment:
            return created_attachments

        # Buscar pickings de salida (envíos) relacionados con la orden de venta
        pickings = self.sale_order_id.picking_ids.filtered(
            lambda p: p.picking_type_code == 'outgoing' and p.state != 'cancel'
        )

        if not pickings:
            _logger.debug(
                f'No hay pickings de salida para orden {self.sale_order_id.name}'
            )
            return created_attachments

        for picking in pickings:
            # Verificar si ya existe el attachment en este picking
            existing = self.env['ir.attachment'].search([
                ('res_model', '=', 'stock.picking'),
                ('res_id', '=', picking.id),
                ('name', 'ilike', f'etiqueta_ml_{self.ml_shipment_id}')
            ], limit=1)

            if existing:
                # Actualizar el existente con los nuevos datos
                existing.write({
                    'datas': attachment.datas,
                    'name': attachment.name,
                })
                created_attachments.append(existing)
                _logger.info(
                    f'Etiqueta actualizada en picking {picking.name}'
                )
            else:
                # Crear nuevo attachment para el picking
                new_attachment = self.env['ir.attachment'].create({
                    'name': attachment.name,
                    'type': 'binary',
                    'datas': attachment.datas,
                    'res_model': 'stock.picking',
                    'res_id': picking.id,
                    'mimetype': attachment.mimetype or 'application/pdf',
                })
                created_attachments.append(new_attachment)
                _logger.info(
                    f'Etiqueta vinculada a picking {picking.name}'
                )

        return created_attachments

    def _download_and_save_shipping_label(self, logistic_config=None):
        """
        Override para aplicar plantilla personalizada automáticamente
        después de descargar la etiqueta de MercadoLibre.
        """
        # Llamar al método original
        result = super()._download_and_save_shipping_label(logistic_config)

        # Si la descarga fue exitosa, vincular al picking
        if result.get('success'):
            attachment = result.get('attachment')

            # Aplicar plantilla si está configurada
            if logistic_config and logistic_config.label_template_id and attachment and self.sale_order_id:
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

            # Vincular etiqueta a los pickings (con o sin plantilla aplicada)
            if attachment:
                try:
                    picking_attachments = self._attach_label_to_picking(attachment)
                    if picking_attachments:
                        result['picking_attachments'] = len(picking_attachments)
                        _logger.info(
                            f'Etiqueta vinculada a {len(picking_attachments)} picking(s)'
                        )
                except Exception as e:
                    _logger.error(
                        f'Error vinculando etiqueta a pickings: {e}',
                        exc_info=True
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

            # Vincular/actualizar etiqueta en los pickings
            picking_attachments = self._attach_label_to_picking(existing_attachment)
            picking_msg = f' y {len(picking_attachments)} picking(s)' if picking_attachments else ''

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Etiqueta Regenerada',
                    'message': f'Etiqueta procesada con plantilla "{logistic_config.label_template_id.name}"{picking_msg}',
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

    # =========================================================================
    # IMPRESIÓN DE ETIQUETAS
    # =========================================================================

    def action_print_shipping_label(self):
        """
        Override para corregir el bug del método _get_logistic_type_config() que no existe.
        Imprime la etiqueta de envío usando la configuración del tipo logístico.
        """
        self.ensure_one()

        _logger.info(f'═══ INICIO IMPRESIÓN ETIQUETA ═══')
        _logger.info(f'Orden ML: {self.ml_order_id}')
        _logger.info(f'Shipment ID: {self.ml_shipment_id}')

        if not self.ml_shipment_id:
            _logger.warning('Sin shipment_id, no se puede imprimir')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin Envío',
                    'message': 'Esta orden no tiene ID de envío de MercadoLibre.',
                    'type': 'warning',
                }
            }

        # Obtener configuración del tipo logístico (CORREGIDO: era _get_logistic_type_config())
        logistic_config = self.logistic_type_id
        _logger.info(f'Tipo logístico: {logistic_config.name if logistic_config else "NO CONFIGURADO"}')

        if not logistic_config:
            _logger.warning('Sin configuración de tipo logístico')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin Configuración',
                    'message': 'No hay configuración de tipo logístico para esta orden.',
                    'type': 'warning',
                }
            }

        # Log de configuración de impresora
        _logger.info(f'Printer URL: {logistic_config.printer_url}')
        _logger.info(f'Printer Name: {logistic_config.printer_name}')
        _logger.info(f'Printer Copies: {logistic_config.printer_copies}')

        # Descargar etiqueta si no existe (esto también aplica plantilla si está configurada)
        _logger.info('Descargando/obteniendo etiqueta...')
        result = self._download_and_save_shipping_label(logistic_config)

        if not result.get('success'):
            _logger.error(f'Error descargando etiqueta: {result.get("error")}')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error Descarga',
                    'message': result.get('error', 'Error descargando etiqueta'),
                    'type': 'danger',
                }
            }

        attachment = result.get('attachment')
        _logger.info(f'Attachment obtenido: {attachment.name if attachment else "NINGUNO"}')
        _logger.info(f'Attachment size: {len(attachment.datas) if attachment and attachment.datas else 0} bytes (base64)')

        # Enviar a impresora
        _logger.info('Enviando a impresora...')
        print_result = self._send_label_to_printer_with_logs(attachment, logistic_config)

        if print_result.get('success'):
            _logger.info(f'═══ IMPRESIÓN EXITOSA ═══')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Etiqueta Enviada',
                    'message': f'Etiqueta enviada a impresora: {logistic_config.printer_name}',
                    'type': 'success',
                }
            }
        else:
            _logger.error(f'═══ ERROR EN IMPRESIÓN: {print_result.get("error")} ═══')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error Impresión',
                    'message': print_result.get('error', 'Error enviando a impresora'),
                    'type': 'danger',
                }
            }

    def _send_label_to_printer_with_logs(self, attachment, logistic_config):
        """
        Envía la etiqueta a la impresora HTTP con logs detallados para debugging.
        """
        import requests

        _logger.info('─── INICIO _send_label_to_printer_with_logs ───')

        # Validaciones
        if not logistic_config.printer_url:
            _logger.error('printer_url no configurada')
            return {'success': False, 'error': 'URL de impresora no configurada'}

        if not logistic_config.printer_name:
            _logger.error('printer_name no configurado')
            return {'success': False, 'error': 'Nombre de impresora no configurado'}

        if not attachment or not attachment.datas:
            _logger.error('Attachment vacío o sin datos')
            return {'success': False, 'error': 'No hay etiqueta para imprimir'}

        try:
            # Decodificar el archivo
            file_content = base64.b64decode(attachment.datas)
            _logger.info(f'Archivo decodificado: {len(file_content)} bytes')
            _logger.info(f'Nombre archivo: {attachment.name}')
            _logger.info(f'Mimetype: {attachment.mimetype}')

            # Preparar el request
            url = logistic_config.printer_url
            files = {
                'file': (attachment.name, file_content, attachment.mimetype or 'application/pdf')
            }
            data = {
                'printer': logistic_config.printer_name,
                'copies': str(logistic_config.printer_copies or 1),
            }

            _logger.info(f'URL destino: {url}')
            _logger.info(f'Data: {data}')
            _logger.info(f'Enviando request POST...')

            # Hacer el request
            response = requests.post(
                url,
                files=files,
                data=data,
                timeout=30
            )

            _logger.info(f'Response Status Code: {response.status_code}')
            _logger.info(f'Response Headers: {dict(response.headers)}')
            _logger.info(f'Response Body: {response.text[:500] if response.text else "(vacío)"}')

            if response.status_code in (200, 201, 202):
                _logger.info('✓ Impresión exitosa')

                # Registrar en el chatter
                if self.sale_order_id:
                    self.sale_order_id.message_post(
                        body=f'🖨️ Etiqueta enviada a impresora: {logistic_config.printer_name} '
                             f'({logistic_config.printer_copies} copia(s))'
                    )

                return {'success': True, 'response': response.text}
            else:
                error_msg = f'Error HTTP {response.status_code}: {response.text[:200]}'
                _logger.error(f'✗ {error_msg}')
                return {'success': False, 'error': error_msg}

        except requests.Timeout:
            _logger.error('✗ Timeout al conectar con impresora')
            return {'success': False, 'error': 'Timeout al conectar con impresora (30s)'}
        except requests.ConnectionError as e:
            _logger.error(f'✗ Error de conexión: {e}')
            return {'success': False, 'error': f'No se pudo conectar a {logistic_config.printer_url}'}
        except Exception as e:
            _logger.error(f'✗ Error inesperado: {e}', exc_info=True)
            return {'success': False, 'error': str(e)}

    def _process_shipping_label(self, logistic_config, sale_order):
        """
        Override para corregir el bug donde sale_order_id no está asignado aún.
        Asigna temporalmente sale_order_id antes de procesar la etiqueta.
        """
        result = {
            'downloaded': False,
            'printed': False,
            'errors': []
        }

        if not logistic_config:
            return result

        _logger.info(f'═══ PROCESANDO ETIQUETA EN FLUJO DE SYNC ═══')
        _logger.info(f'Orden ML: {self.ml_order_id}')
        _logger.info(f'Sale Order: {sale_order.name if sale_order else "N/A"}')
        _logger.info(f'Shipment ID: {self.ml_shipment_id}')
        _logger.info(f'Plantilla: {logistic_config.label_template_id.name if logistic_config.label_template_id else "NO CONFIGURADA"}')

        # CORRECCIÓN: Asignar sale_order_id ANTES de descargar
        # porque _download_and_save_shipping_label usa self.sale_order_id
        if sale_order and not self.sale_order_id:
            _logger.info(f'Asignando sale_order_id temporalmente: {sale_order.id}')
            self.sale_order_id = sale_order.id

        # Descargar etiqueta si está configurado
        if logistic_config.download_shipping_label and self.ml_shipment_id:
            _logger.info('Descargando etiqueta...')
            download_result = self._download_and_save_shipping_label(logistic_config)

            if download_result.get('success'):
                result['downloaded'] = True
                result['attachment'] = download_result.get('attachment')

                _logger.info(f'✓ Etiqueta descargada: {download_result.get("filename")}')
                if download_result.get('template_applied'):
                    _logger.info(f'✓ Plantilla aplicada: {download_result.get("template_name")}')
                if download_result.get('picking_attachments'):
                    _logger.info(f'✓ Vinculada a {download_result.get("picking_attachments")} picking(s)')

                # Imprimir si está configurado
                if logistic_config.auto_print_label:
                    _logger.info('Enviando a impresora...')
                    print_result = self._send_label_to_printer_with_logs(
                        download_result['attachment'],
                        logistic_config
                    )
                    if print_result.get('success'):
                        result['printed'] = True
                        _logger.info('✓ Etiqueta enviada a impresora')
                    else:
                        error_msg = f"Error impresión: {print_result.get('error')}"
                        result['errors'].append(error_msg)
                        _logger.error(f'✗ {error_msg}')
            else:
                error_msg = f"Error descarga: {download_result.get('error')}"
                result['errors'].append(error_msg)
                _logger.error(f'✗ {error_msg}')

        _logger.info(f'═══ FIN PROCESAMIENTO ETIQUETA ═══')
        return result

    def action_test_printer_connection(self):
        """
        Test completo: Descarga etiqueta → Aplica plantilla → Envía a imprimir.
        Usa el flujo real para probar toda la funcionalidad.
        """
        self.ensure_one()

        _logger.info('═══ TEST COMPLETO: DESCARGAR + PLANTILLA + IMPRIMIR ═══')
        _logger.info(f'Orden ML: {self.ml_order_id}')
        _logger.info(f'Shipment ID: {self.ml_shipment_id}')

        # Validaciones
        if not self.ml_shipment_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin Envío',
                    'message': 'Esta orden no tiene shipment_id para descargar etiqueta.',
                    'type': 'warning',
                }
            }

        logistic_config = self.logistic_type_id
        if not logistic_config:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin Configuración',
                    'message': 'No hay configuración de tipo logístico.',
                    'type': 'warning',
                }
            }

        if not logistic_config.printer_url:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin URL Impresora',
                    'message': 'No hay URL de impresora configurada en el tipo logístico.',
                    'type': 'warning',
                }
            }

        # Log configuración
        _logger.info(f'Tipo logístico: {logistic_config.name}')
        _logger.info(f'Plantilla: {logistic_config.label_template_id.name if logistic_config.label_template_id else "NO CONFIGURADA"}')
        _logger.info(f'Printer URL: {logistic_config.printer_url}')
        _logger.info(f'Printer Name: {logistic_config.printer_name}')

        # PASO 1: Descargar etiqueta (esto también aplica plantilla si está configurada)
        _logger.info('─── PASO 1: Descargando etiqueta de ML ───')
        download_result = self._download_and_save_shipping_label(logistic_config)

        if not download_result.get('success'):
            error_msg = download_result.get('error', 'Error desconocido')
            _logger.error(f'Error en descarga: {error_msg}')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '✗ Error Descarga',
                    'message': error_msg,
                    'type': 'danger',
                    'sticky': True,
                }
            }

        attachment = download_result.get('attachment')
        template_applied = download_result.get('template_applied', False)
        template_name = download_result.get('template_name', '')

        _logger.info(f'✓ Etiqueta descargada: {attachment.name if attachment else "N/A"}')
        _logger.info(f'✓ Plantilla aplicada: {template_applied} ({template_name})')
        _logger.info(f'✓ Pickings vinculados: {download_result.get("picking_attachments", 0)}')

        # PASO 2: Enviar a impresora
        _logger.info('─── PASO 2: Enviando a impresora ───')
        print_result = self._send_label_to_printer_with_logs(attachment, logistic_config)

        if print_result.get('success'):
            # Construir mensaje de éxito
            msg_parts = ['Etiqueta enviada a impresora']
            if template_applied:
                msg_parts.append(f'Plantilla: {template_name}')
            msg_parts.append(f'Impresora: {logistic_config.printer_name}')

            _logger.info('═══ TEST COMPLETO EXITOSO ═══')

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '✓ Test Exitoso',
                    'message': ' | '.join(msg_parts),
                    'type': 'success',
                }
            }
        else:
            error_msg = print_result.get('error', 'Error desconocido')
            _logger.error(f'═══ TEST FALLÓ EN IMPRESIÓN: {error_msg} ═══')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '✗ Error Impresión',
                    'message': f'Etiqueta descargada OK, pero falló impresión: {error_msg}',
                    'type': 'danger',
                    'sticky': True,
                }
            }
