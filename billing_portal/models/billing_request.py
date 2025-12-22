# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)


class BillingRequest(models.Model):
    _name = 'billing.request'
    _description = 'Solicitud de Facturación'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Referencia',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('Nuevo')
    )

    # Datos del solicitante
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

        # Buscar cliente existente por RFC
        partner = self.env['res.partner'].search([
            ('vat', '=', self.rfc)
        ], limit=1)

        if not partner:
            # Buscar por email
            partner = self.env['res.partner'].search([
                ('email', '=', self.email)
            ], limit=1)

        csf_data = json.loads(self.csf_data or '{}')

        if partner:
            # Actualizar datos fiscales
            partner.write(self._prepare_partner_vals(csf_data))
            self.partner_created = False
        else:
            # Crear nuevo cliente
            vals = self._prepare_partner_vals(csf_data)
            vals['customer_rank'] = 1
            partner = self.env['res.partner'].create(vals)
            self.partner_created = True

        self.write({
            'partner_id': partner.id,
            'progress': 50,
            'status_message': _('Cliente %s') % (_('creado') if self.partner_created else _('actualizado'))
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
                if self.uso_cfdi_id:
                    invoice.write({'uso_cfdi_id': self.uso_cfdi_id.id})
                if self.forma_pago_id:
                    invoice.write({'forma_pago_id': self.forma_pago_id.id})

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
            'message': self.status_message or self.error_message,
            'invoice_name': self.invoice_name,
            'is_error': self.state == 'error',
            'is_done': self.state == 'done',
        }
