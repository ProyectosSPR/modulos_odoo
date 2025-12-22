# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging
import base64

_logger = logging.getLogger(__name__)


class BillingRequest(models.Model):
    _name = 'billing.request'
    _description = 'Solicitud de Facturación'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _mail_post_access = 'read'  # Permitir publicar mensajes con acceso de lectura

    name = fields.Char(
        string='Referencia',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('Nuevo')
    )

    # Datos del solicitante
    user_id = fields.Many2one(
        'res.users',
        string='Usuario Solicitante',
        default=lambda self: self.env.user,
        tracking=True
    )

    receiver_id = fields.Char(
        string='Receiver ID (ML)',
        index=True,
        tracking=True
    )

    email = fields.Char(
        string='Email',
        required=True,
        tracking=True
    )

    phone = fields.Char(
        string='Teléfono'
    )

    # Órdenes relacionadas
    order_ids = fields.Many2many(
        'sale.order',
        'billing_request_sale_order_rel',
        'request_id',
        'order_id',
        string='Órdenes de Venta'
    )

    order_references = fields.Text(
        string='Referencias de Órdenes',
        help='Referencias de órdenes de ML (order_id, pack_id)'
    )

    # Datos del CSF
    csf_attachment_id = fields.Many2one(
        'ir.attachment',
        string='Constancia CSF'
    )

    csf_data = fields.Text(
        string='Datos Extraídos CSF',
        help='JSON con los datos extraídos de la constancia'
    )

    csf_extraction_method = fields.Selection([
        ('local', 'Extracción Local (OCR)'),
        ('ai', 'Extracción con IA'),
        ('manual', 'Captura Manual'),
    ], string='Método de Extracción')

    # Datos fiscales extraídos
    rfc = fields.Char(string='RFC', tracking=True)
    razon_social = fields.Char(string='Razón Social')
    codigo_postal = fields.Char(string='Código Postal')

    regimen_fiscal_id = fields.Many2one(
        'catalogo.regimen.fiscal',
        string='Régimen Fiscal'
    )

    uso_cfdi_id = fields.Many2one(
        'catalogo.uso.cfdi',
        string='Uso CFDI'
    )

    forma_pago_id = fields.Many2one(
        'catalogo.forma.pago',
        string='Forma de Pago'
    )

    # Cliente Odoo
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente Odoo',
        tracking=True
    )

    partner_created = fields.Boolean(
        string='Cliente Creado',
        default=False
    )

    # Factura generada
    invoice_id = fields.Many2one(
        'account.move',
        string='Factura Generada',
        tracking=True
    )

    invoice_name = fields.Char(
        related='invoice_id.name',
        string='Número de Factura'
    )

    # Campos CFDI de la factura (del módulo cdfi_invoice)
    # Usamos campos computados en lugar de related para evitar errores si cdfi_invoice no está instalado
    folio_fiscal = fields.Char(
        string='Folio Fiscal (UUID)',
        compute='_compute_cfdi_info',
        readonly=True
    )

    cfdi_state = fields.Char(
        string='Estado CFDI',
        compute='_compute_cfdi_info',
        readonly=True
    )

    @api.depends('invoice_id')
    def _compute_cfdi_info(self):
        """Obtiene información CFDI de la factura si el módulo cdfi_invoice está instalado"""
        for record in self:
            record.folio_fiscal = False
            record.cfdi_state = False

            if not record.invoice_id:
                continue

            invoice = record.invoice_id
            # Intentar obtener folio_fiscal si el campo existe
            if hasattr(invoice, 'folio_fiscal') and invoice.folio_fiscal:
                record.folio_fiscal = invoice.folio_fiscal

            # Intentar obtener estado_factura si el campo existe
            if hasattr(invoice, 'estado_factura') and invoice.estado_factura:
                record.cfdi_state = invoice.estado_factura

    # Archivos CFDI para descarga
    cfdi_xml_file = fields.Binary(
        string='XML CFDI',
        compute='_compute_cfdi_files',
        help='Archivo XML del CFDI timbrado'
    )

    cfdi_xml_filename = fields.Char(
        compute='_compute_cfdi_files'
    )

    cfdi_pdf_file = fields.Binary(
        string='PDF CFDI',
        compute='_compute_cfdi_files',
        help='Representación impresa del CFDI'
    )

    cfdi_pdf_filename = fields.Char(
        compute='_compute_cfdi_files'
    )

    has_cfdi_files = fields.Boolean(
        compute='_compute_cfdi_files',
        string='Tiene archivos CFDI'
    )

    # Mensajería cliente-contador
    message_from_client = fields.Text(
        string='Mensaje del Cliente',
        tracking=True,
        help='Mensaje o comentarios del cliente para el contador'
    )

    message_to_client = fields.Text(
        string='Respuesta al Cliente',
        tracking=True,
        help='Respuesta del contador hacia el cliente'
    )

    last_message_date = fields.Datetime(
        string='Última Comunicación',
        tracking=True
    )

    unread_messages = fields.Boolean(
        string='Mensajes sin leer',
        default=False
    )

    # Estado y progreso
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('validating', 'Validando CSF'),
        ('csf_validated', 'CSF Validado'),
        ('creating_partner', 'Creando Cliente'),
        ('creating_invoice', 'Creando Factura'),
        ('pending_stamp', 'Pendiente Timbrado'),
        ('done', 'Completado'),
        ('error', 'Error'),
        ('cancelled', 'Cancelado'),
    ], string='Estado', default='draft', tracking=True)

    progress = fields.Integer(
        string='Progreso',
        default=0
    )

    status_message = fields.Char(
        string='Mensaje de Estado'
    )

    error_message = fields.Text(
        string='Mensaje de Error'
    )

    # Campos de auditoría
    ip_address = fields.Char(string='Dirección IP')
    user_agent = fields.Char(string='User Agent')

    # Configuración
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'billing.request'
                ) or _('Nuevo')
        return super().create(vals_list)

    def action_validate_csf(self):
        """Valida el CSF adjunto"""
        self.ensure_one()
        if not self.csf_attachment_id:
            raise UserError(_('Debe adjuntar la Constancia de Situación Fiscal'))

        self.write({
            'state': 'validating',
            'progress': 10,
            'status_message': _('Validando constancia...')
        })

        # Llamar al servicio de validación
        validator = self.env['billing.csf.validator']
        pdf_content = self.csf_attachment_id.datas

        import base64
        pdf_bytes = base64.b64decode(pdf_content)

        result = validator.validate_csf(pdf_bytes)

        if result.get('success'):
            data = result.get('data', {})
            self.write({
                'state': 'csf_validated',
                'progress': 30,
                'status_message': _('CSF validado correctamente'),
                'csf_data': json.dumps(data, ensure_ascii=False),
                'csf_extraction_method': result.get('method'),
                'rfc': data.get('rfc'),
                'razon_social': data.get('razon_social'),
                'codigo_postal': data.get('codigo_postal'),
            })

            # Buscar régimen fiscal si está en los datos
            if data.get('regimen_fiscal_id'):
                self.regimen_fiscal_id = data.get('regimen_fiscal_id')
        else:
            errors = result.get('errors', [])
            self.write({
                'state': 'error',
                'progress': 0,
                'error_message': '\n'.join(errors)
            })

    def action_create_partner(self):
        """Crea o actualiza el cliente en Odoo"""
        self.ensure_one()

        if not self.rfc:
            raise UserError(_('No hay RFC para crear el cliente'))

        self.write({
            'state': 'creating_partner',
            'progress': 40,
            'status_message': _('Buscando/creando cliente...')
        })

        partner = self._find_or_create_billing_partner()

        self.write({
            'partner_id': partner.id,
            'progress': 50,
            'status_message': _('Cliente %s') % (_('creado') if self.partner_created else _('actualizado'))
        })

        # Actualizar billing_partner_id en las órdenes
        if self.order_ids:
            self.order_ids.write({'billing_partner_id': partner.id})
            _logger.info("Actualizado billing_partner_id=%d en órdenes: %s",
                        partner.id, self.order_ids.mapped('name'))

    def _find_or_create_billing_partner(self):
        """
        Busca o crea el cliente de facturación basándose en el RFC del CSF.

        Orden de búsqueda:
        1. Por RFC (vat)
        2. Por email
        3. Crear nuevo

        También vincula el partner con el usuario de Odoo si existe.

        Returns:
            res.partner: El partner encontrado o creado
        """
        self.ensure_one()

        # 1. Buscar cliente existente por RFC
        partner = self.env['res.partner'].search([
            ('vat', '=', self.rfc),
            ('parent_id', '=', False),  # Solo partners principales
        ], limit=1)

        if partner:
            _logger.info("Partner encontrado por RFC %s: %s (ID: %d)",
                        self.rfc, partner.name, partner.id)

        # 2. Si no se encuentra por RFC, buscar por email
        if not partner and self.email:
            partner = self.env['res.partner'].search([
                ('email', '=', self.email),
                ('parent_id', '=', False),
            ], limit=1)

            if partner:
                _logger.info("Partner encontrado por email %s: %s (ID: %d)",
                            self.email, partner.name, partner.id)

        csf_data = json.loads(self.csf_data or '{}')

        if partner:
            # Actualizar datos fiscales del partner existente
            partner.write(self._prepare_partner_vals(csf_data))
            self.partner_created = False
            _logger.info("Partner actualizado con datos del CSF")
        else:
            # Crear nuevo cliente
            vals = self._prepare_partner_vals(csf_data)
            vals['customer_rank'] = 1
            partner = self.env['res.partner'].create(vals)
            self.partner_created = True
            _logger.info("Nuevo partner creado: %s (ID: %d)", partner.name, partner.id)

        # Vincular partner con usuario de Odoo si el usuario tiene partner diferente
        self._link_partner_to_user(partner)

        return partner

    def _link_partner_to_user(self, partner):
        """
        Vincula el partner de facturación con el usuario de Odoo.
        Si el usuario ya tiene un partner, este nuevo partner se convierte en
        un contacto de facturación vinculado.
        """
        if not self.user_id:
            return

        user_partner = self.user_id.partner_id

        # Si el usuario no tiene partner o su partner es el public_user, asignar directamente
        if not user_partner or user_partner.id == self.env.ref('base.public_partner', raise_if_not_found=False).id:
            return

        # Si el partner del usuario es diferente al partner de facturación
        if user_partner.id != partner.id:
            # Marcar en el partner que está vinculado a este usuario para facturación
            if not partner.user_ids:
                # El partner no tiene usuarios, lo vinculamos como contacto de facturación
                _logger.info("Partner %s vinculado como contacto de facturación del usuario %s",
                            partner.name, self.user_id.login)

            # Marcar que el CSF fue validado
            partner.write({
                'csf_validated': True,
                'csf_validation_date': fields.Datetime.now(),
            })

    def _prepare_partner_vals(self, csf_data):
        """Prepara los valores para crear/actualizar el cliente"""
        vals = {
            'name': self.razon_social or csf_data.get('razon_social'),
            'vat': self.rfc,
            'email': self.email,
            'phone': self.phone,
            'zip': self.codigo_postal or csf_data.get('codigo_postal'),
            'street': csf_data.get('nombre_vialidad', ''),
            'street2': csf_data.get('colonia', ''),
            'city': csf_data.get('municipio', ''),
            'country_id': self.env.ref('base.mx').id,
        }

        # Estado
        if csf_data.get('entidad_federativa'):
            state = self.env['res.country.state'].search([
                ('country_id', '=', self.env.ref('base.mx').id),
                ('name', 'ilike', csf_data.get('entidad_federativa'))
            ], limit=1)
            if state:
                vals['state_id'] = state.id

        # Régimen fiscal
        if self.regimen_fiscal_id:
            vals['regimen_fiscal_id'] = self.regimen_fiscal_id.id

        # Uso CFDI
        if self.uso_cfdi_id:
            vals['uso_cfdi_id'] = self.uso_cfdi_id.id

        return vals

    def action_create_invoice(self):
        """Crea la factura a partir de las órdenes seleccionadas"""
        self.ensure_one()

        if not self.order_ids:
            raise UserError(_('No hay órdenes seleccionadas para facturar'))

        if not self.partner_id:
            raise UserError(_('Debe crear el cliente primero'))

        self.write({
            'state': 'creating_invoice',
            'progress': 60,
            'status_message': _('Creando factura...')
        })

        try:
            # Crear wizard de facturación
            wizard = self.env['sale.advance.payment.inv'].create({
                'advance_payment_method': 'delivered',
                'sale_order_ids': [(6, 0, self.order_ids.ids)],
            })

            # Ejecutar facturación
            wizard.with_context(
                active_model='sale.order',
                active_ids=self.order_ids.ids,
                active_id=self.order_ids[0].id
            ).create_invoices()

            # Obtener la factura creada
            invoices = self.order_ids.mapped('invoice_ids').filtered(
                lambda i: i.state == 'draft'
            )

            if invoices:
                invoice = invoices[0]

                # Cambiar cliente si es diferente
                if invoice.partner_id != self.partner_id:
                    invoice.write({
                        'partner_id': self.partner_id.id,
                    })

                # Agregar datos fiscales
                invoice_vals = {}
                if self.uso_cfdi_id:
                    invoice_vals['uso_cfdi_id'] = self.uso_cfdi_id.id
                if self.forma_pago_id:
                    invoice_vals['forma_pago_id'] = self.forma_pago_id.id

                # Agregar notas de MercadoLibre con referencias de las órdenes
                ml_notes = self._build_ml_invoice_notes()
                if ml_notes:
                    invoice_vals['narration'] = ml_notes

                if invoice_vals:
                    invoice.write(invoice_vals)

                # Publicar factura
                invoice.action_post()

                self.write({
                    'invoice_id': invoice.id,
                    'state': 'pending_stamp',
                    'progress': 80,
                    'status_message': _('Factura %s creada, pendiente de timbrado') % invoice.name
                })

                # Crear actividad para contabilidad
                self._create_stamp_activity(invoice)

        except Exception as e:
            _logger.exception("Error creando factura")
            self.write({
                'state': 'error',
                'error_message': str(e)
            })

    def _build_ml_invoice_notes(self):
        """
        Construye las notas de la factura con referencias de MercadoLibre.

        Incluye:
        - Referencias de órdenes de venta (client_order_ref)
        - IDs de órdenes de MercadoLibre (ml_order_id)
        - IDs de paquetes (ml_pack_id)
        """
        notes = []

        for order in self.order_ids:
            order_notes = []

            # Referencia de la orden
            if order.client_order_ref:
                order_notes.append(f"Ref: {order.client_order_ref}")
            else:
                order_notes.append(f"Orden: {order.name}")

            # ID de orden ML
            if order.ml_order_id:
                order_notes.append(f"ML Order: {order.ml_order_id}")

            # ID de pack ML
            if order.ml_pack_id:
                order_notes.append(f"ML Pack: {order.ml_pack_id}")

            if order_notes:
                notes.append(" | ".join(order_notes))

        if notes:
            header = _("Referencias MercadoLibre:")
            return f"{header}\n" + "\n".join(notes)

        return ""

    def _create_stamp_activity(self, invoice):
        """Crea actividades para seguimiento de timbrado"""
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            return

        # Obtener usuarios de contabilidad
        users = self.env['res.users'].search([
            ('groups_id', 'in', self.env.ref('account.group_account_manager').id)
        ], limit=2)

        for user in users:
            self.env['mail.activity'].create({
                'res_model_id': self.env['ir.model']._get('account.move').id,
                'res_id': invoice.id,
                'activity_type_id': activity_type.id,
                'summary': _('Validar timbrado de factura'),
                'note': _('Factura generada desde portal de facturación. Solicitud: %s') % self.name,
                'date_deadline': fields.Date.today(),
                'user_id': user.id,
            })

    def action_mark_done(self):
        """Marca la solicitud como completada"""
        self.ensure_one()
        self.write({
            'state': 'done',
            'progress': 100,
            'status_message': _('Proceso completado')
        })

    def action_cancel(self):
        """Cancela la solicitud"""
        self.ensure_one()
        self.write({
            'state': 'cancelled',
            'status_message': _('Solicitud cancelada')
        })

    def action_reset_draft(self):
        """Regresa la solicitud a borrador"""
        self.ensure_one()
        self.write({
            'state': 'draft',
            'progress': 0,
            'status_message': '',
            'error_message': ''
        })

    def get_status_for_portal(self):
        """Retorna el estado formateado para el portal"""
        self.ensure_one()
        return {
            'state': self.state,
            'progress': self.progress,
            'status_message': self.status_message,
            'error_message': self.error_message,
            'invoice_name': self.invoice_name,
            'folio_fiscal': self.folio_fiscal,
            'cfdi_state': self.cfdi_state,
            'has_cfdi_files': self.has_cfdi_files,
            'message_to_client': self.message_to_client,
            'last_message_date': self.last_message_date.isoformat() if self.last_message_date else None,
            'is_error': self.state == 'error',
            'is_done': self.state == 'done',
        }

    @api.depends('invoice_id')
    def _compute_cfdi_files(self):
        """Obtiene los archivos XML y PDF del CFDI desde la factura"""
        for record in self:
            record.cfdi_xml_file = False
            record.cfdi_xml_filename = False
            record.cfdi_pdf_file = False
            record.cfdi_pdf_filename = False
            record.has_cfdi_files = False

            if not record.invoice_id:
                continue

            invoice = record.invoice_id

            # Buscar XML adjunto
            xml_attachment = self.env['ir.attachment'].sudo().search([
                ('res_model', '=', 'account.move'),
                ('res_id', '=', invoice.id),
                ('name', 'like', '.xml'),
                ('name', 'not like', 'CANCEL_%'),
            ], limit=1, order='create_date desc')

            if xml_attachment:
                record.cfdi_xml_file = xml_attachment.datas
                record.cfdi_xml_filename = xml_attachment.name
                record.has_cfdi_files = True

            # Para el PDF, intentar obtenerlo del campo de la factura o generarlo
            if hasattr(invoice, 'pdf_cdfi_invoice') and invoice.pdf_cdfi_invoice:
                record.cfdi_pdf_file = invoice.pdf_cdfi_invoice
                record.cfdi_pdf_filename = f'{invoice.name.replace("/", "_")}.pdf'
                record.has_cfdi_files = True
            else:
                # Buscar PDF adjunto
                pdf_attachment = self.env['ir.attachment'].sudo().search([
                    ('res_model', '=', 'account.move'),
                    ('res_id', '=', invoice.id),
                    ('mimetype', '=', 'application/pdf'),
                ], limit=1, order='create_date desc')

                if pdf_attachment:
                    record.cfdi_pdf_file = pdf_attachment.datas
                    record.cfdi_pdf_filename = pdf_attachment.name
                    record.has_cfdi_files = True

    def action_send_client_message(self, message):
        """Envía un mensaje del cliente al contador"""
        self.ensure_one()
        self.write({
            'message_from_client': message,
            'last_message_date': fields.Datetime.now(),
            'unread_messages': True,
        })

        # Registrar en el chatter
        self.message_post(
            body=_('<strong>Mensaje del cliente:</strong><br/>%s') % message,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )

        # Notificar a contabilidad
        self._notify_accounting_team(_('Nuevo mensaje del cliente en solicitud %s') % self.name)

        return True

    def action_send_accountant_message(self, message):
        """Envía un mensaje del contador al cliente"""
        self.ensure_one()
        self.write({
            'message_to_client': message,
            'last_message_date': fields.Datetime.now(),
        })

        # Registrar en el chatter
        self.message_post(
            body=_('<strong>Respuesta al cliente:</strong><br/>%s') % message,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )

        return True

    def action_mark_messages_read(self):
        """Marca los mensajes como leídos"""
        self.write({'unread_messages': False})

    def _notify_accounting_team(self, subject):
        """Notifica al equipo de contabilidad"""
        # Verificar si las notificaciones están habilitadas
        notify_enabled = self.env['ir.config_parameter'].sudo().get_param(
            'billing_portal.notify_on_request', 'True'
        )
        if notify_enabled != 'True':
            return

        # Buscar usuarios del grupo de contabilidad
        users = self.env['res.users'].search([
            ('groups_id', 'in', self.env.ref('account.group_account_manager').id)
        ], limit=3)

        for user in users:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=subject,
                user_id=user.id,
            )

    def action_view_invoice(self):
        """Abre la factura relacionada"""
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_('No hay factura generada'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Factura'),
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
        }

    def action_view_partner(self):
        """Abre el cliente relacionado"""
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_('No hay cliente relacionado'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Cliente'),
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
        }

    def action_reset_to_draft(self):
        """Regresa a borrador desde error o cancelado"""
        self.ensure_one()
        if self.state not in ('error', 'cancelled'):
            raise UserError(_('Solo se puede reiniciar desde estado de error o cancelado'))

        self.write({
            'state': 'draft',
            'progress': 0,
            'status_message': '',
            'error_message': '',
        })
