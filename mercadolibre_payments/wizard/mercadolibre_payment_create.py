# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MercadolibrePaymentCreateWizard(models.TransientModel):
    _name = 'mercadolibre.payment.create.wizard'
    _description = 'Wizard para Crear Pagos Odoo desde MercadoPago'

    ml_payment_id = fields.Many2one(
        'mercadolibre.payment',
        string='Pago MercadoPago',
        readonly=True
    )
    ml_payment_ids = fields.Many2many(
        'mercadolibre.payment',
        string='Pagos MercadoPago',
        help='Pagos seleccionados para crear pagos en Odoo'
    )

    mode = fields.Selection([
        ('single', 'Pago Individual'),
        ('batch', 'Pagos Multiples'),
    ], string='Modo', default='single', required=True)

    # Informacion del pago (solo lectura)
    payment_direction = fields.Selection([
        ('incoming', 'Recibido'),
        ('outgoing', 'Realizado'),
    ], string='Direccion', readonly=True)

    amount = fields.Float(
        string='Monto',
        readonly=True,
        digits=(16, 2)
    )
    description = fields.Text(
        string='Descripcion',
        readonly=True
    )
    total_charges = fields.Float(
        string='Comisiones',
        compute='_compute_total_charges',
        readonly=True
    )
    has_commissions = fields.Boolean(
        string='Tiene Comisiones',
        compute='_compute_total_charges',
    )

    # Configuracion del pago Odoo
    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
        required=True,
        domain="[('type', 'in', ['bank', 'cash']), ('company_id', '=', company_id)]"
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        required=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compania',
        default=lambda self: self.env.company
    )

    # Comisiones
    create_commission = fields.Boolean(
        string='Crear Pago de Comision',
        default=True
    )
    commission_journal_id = fields.Many2one(
        'account.journal',
        string='Diario Comision',
        domain="[('type', 'in', ['bank', 'cash']), ('company_id', '=', company_id)]"
    )
    commission_partner_id = fields.Many2one(
        'res.partner',
        string='Partner Comision',
        help='Proveedor para la comision (ej: MercadoPago)'
    )

    # Deteccion de proveedor
    detected_vendor_id = fields.Many2one(
        'mercadolibre.known.vendor',
        string='Proveedor Detectado',
        readonly=True
    )
    use_detected_vendor = fields.Boolean(
        string='Usar Proveedor Detectado',
        default=True
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        ml_payment = False

        # Si viene de accion individual (formulario)
        if self.env.context.get('default_ml_payment_id'):
            ml_payment_id = self.env.context.get('default_ml_payment_id')
            ml_payment = self.env['mercadolibre.payment'].browse(ml_payment_id)
            res['ml_payment_id'] = ml_payment_id
            res['mode'] = 'single'

        # Si viene de accion desde lista (active_ids)
        elif self.env.context.get('active_ids') and self.env.context.get('active_model') == 'mercadolibre.payment':
            active_ids = self.env.context.get('active_ids', [])
            if len(active_ids) == 1:
                # Un solo pago seleccionado - modo single
                ml_payment = self.env['mercadolibre.payment'].browse(active_ids[0])
                res['ml_payment_id'] = active_ids[0]
                res['mode'] = 'single'
            elif len(active_ids) > 1:
                # Multiples pagos seleccionados - modo batch
                res['mode'] = 'batch'
                res['ml_payment_ids'] = [(6, 0, active_ids)]
                # Obtener company del primer pago
                first_payment = self.env['mercadolibre.payment'].browse(active_ids[0])
                res['company_id'] = first_payment.company_id.id

        # Configurar campos para modo single
        if ml_payment and res.get('mode') == 'single':
            res['payment_direction'] = ml_payment.payment_direction
            res['amount'] = ml_payment.transaction_amount
            res['description'] = ml_payment.description
            res['company_id'] = ml_payment.company_id.id

            # Detectar proveedor para egresos
            if ml_payment.payment_direction == 'outgoing' and ml_payment.description:
                KnownVendor = self.env['mercadolibre.known.vendor']
                vendor = KnownVendor.find_vendor_by_description(ml_payment.description)
                if vendor:
                    res['detected_vendor_id'] = vendor.id
                    res['partner_id'] = vendor.partner_id.id
                    res['use_detected_vendor'] = True

        return res

    @api.onchange('use_detected_vendor', 'detected_vendor_id')
    def _onchange_detected_vendor(self):
        if self.use_detected_vendor and self.detected_vendor_id:
            self.partner_id = self.detected_vendor_id.partner_id

    @api.onchange('payment_direction')
    def _onchange_payment_direction(self):
        """Sugiere journals segun la direccion del pago"""
        if not self.journal_id:
            domain = [
                ('type', 'in', ['bank', 'cash']),
                ('company_id', '=', self.company_id.id)
            ]
            journals = self.env['account.journal'].search(domain, limit=1)
            if journals:
                self.journal_id = journals[0]

    @api.depends('ml_payment_id', 'ml_payment_ids', 'mode')
    def _compute_total_charges(self):
        """Calcula comisiones para modo single y batch"""
        for wizard in self:
            if wizard.mode == 'single' and wizard.ml_payment_id:
                wizard.total_charges = wizard.ml_payment_id.total_charges or 0.0
                wizard.has_commissions = wizard.total_charges > 0
            elif wizard.mode == 'batch' and wizard.ml_payment_ids:
                # Sumar todas las comisiones de los pagos seleccionados
                wizard.total_charges = sum(p.total_charges or 0.0 for p in wizard.ml_payment_ids)
                wizard.has_commissions = wizard.total_charges > 0
            else:
                wizard.total_charges = 0.0
                wizard.has_commissions = False

    def action_create_payment(self):
        """Crea el pago en Odoo"""
        self.ensure_one()

        if self.mode == 'single':
            return self._create_single_payment()
        else:
            return self._create_batch_payments()

    def _create_single_payment(self):
        """Crea un solo pago"""
        self.ensure_one()

        ml_payment = self.ml_payment_id

        if not ml_payment:
            raise ValidationError(_('No se selecciono un pago de MercadoPago'))

        if ml_payment.odoo_payment_id:
            raise ValidationError(_('Este pago ya tiene un pago Odoo asociado: %s') % ml_payment.odoo_payment_id.name)

        # Determinar tipo de pago
        if self.payment_direction == 'incoming':
            payment_type = 'inbound'
            partner_type = 'customer'
        else:
            payment_type = 'outbound'
            partner_type = 'supplier'

        # Fecha del pago
        payment_date = ml_payment.date_approved or ml_payment.date_created or fields.Datetime.now()
        if hasattr(payment_date, 'date'):
            payment_date = payment_date.date()

        # Crear pago principal usando metodo extendido
        payment_vals = {
            'payment_type': payment_type,
            'partner_type': partner_type,
            'partner_id': self.partner_id.id,
            'amount': abs(self.amount),
            'currency_id': ml_payment.currency_id.id or self.company_id.currency_id.id,
            'journal_id': self.journal_id.id,
            'date': payment_date,
            'ml_responsible_user_id': self.env.user.id,
        }

        # Usar metodo extendido que construye el ref con formato correcto
        # [Orden Venta] - [pack_id o order_id] - [payment_id]
        payment = self.env['account.payment'].create_from_ml_payment(ml_payment, payment_vals)

        # Actualizar ML payment
        update_vals = {
            'odoo_payment_id': payment.id,
            'odoo_payment_state': 'created',
            'odoo_payment_error': False,
            'partner_id': self.partner_id.id,
        }

        # Actualizar proveedor detectado si aplica
        if self.use_detected_vendor and self.detected_vendor_id:
            update_vals['matched_vendor_id'] = self.detected_vendor_id.id

        # Crear pago de comision si corresponde
        commission_payment = False
        if self.create_commission and ml_payment.total_charges > 0:
            if not self.commission_journal_id:
                raise ValidationError(_('Seleccione un diario para las comisiones'))
            if not self.commission_partner_id:
                raise ValidationError(_('Seleccione un partner para las comisiones'))

            commission_vals = {
                'payment_type': 'outbound',
                'partner_type': 'supplier',
                'partner_id': self.commission_partner_id.id,
                'amount': abs(ml_payment.total_charges),
                'currency_id': ml_payment.currency_id.id or self.company_id.currency_id.id,
                'journal_id': self.commission_journal_id.id,
                'date': payment_date,
                'ref': f'ML-COM-{ml_payment.mp_payment_id}',
                # Campos ML para trazabilidad
                'ml_payment_id': ml_payment.id,
                'ml_payment_mp_id': ml_payment.mp_payment_id,
                'ml_status': ml_payment.status,
                'ml_responsible_user_id': self.env.user.id,
            }
            commission_payment = self.env['account.payment'].create(commission_vals)
            update_vals['commission_payment_id'] = commission_payment.id

        ml_payment.write(update_vals)

        # Mostrar resultado
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pago Creado'),
            'res_model': 'account.payment',
            'res_id': payment.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _create_batch_payments(self):
        """Crea pagos en lote"""
        self.ensure_one()

        if not self.ml_payment_ids:
            raise ValidationError(_('No hay pagos seleccionados'))

        created_count = 0
        error_count = 0
        errors = []

        for ml_payment in self.ml_payment_ids:
            if ml_payment.odoo_payment_id:
                continue  # Ya tiene pago

            if ml_payment.status != 'approved':
                continue  # No aprobado

            try:
                # Determinar partner
                partner = self.partner_id
                if ml_payment.payment_direction == 'outgoing':
                    # Intentar detectar proveedor
                    KnownVendor = self.env['mercadolibre.known.vendor']
                    vendor = KnownVendor.find_vendor_by_description(ml_payment.description)
                    if vendor:
                        partner = vendor.partner_id
                        ml_payment.matched_vendor_id = vendor.id

                # Determinar tipo de pago
                if ml_payment.payment_direction == 'incoming':
                    payment_type = 'inbound'
                    partner_type = 'customer'
                else:
                    payment_type = 'outbound'
                    partner_type = 'supplier'

                # Fecha
                payment_date = ml_payment.date_approved or ml_payment.date_created or fields.Datetime.now()
                if hasattr(payment_date, 'date'):
                    payment_date = payment_date.date()

                # Crear pago usando metodo extendido
                payment_vals = {
                    'payment_type': payment_type,
                    'partner_type': partner_type,
                    'partner_id': partner.id,
                    'amount': abs(ml_payment.transaction_amount),
                    'currency_id': ml_payment.currency_id.id or self.company_id.currency_id.id,
                    'journal_id': self.journal_id.id,
                    'date': payment_date,
                    'ml_responsible_user_id': self.env.user.id,
                }

                # Usar metodo extendido que construye el ref con formato correcto
                payment = self.env['account.payment'].create_from_ml_payment(ml_payment, payment_vals)

                update_vals = {
                    'odoo_payment_id': payment.id,
                    'odoo_payment_state': 'created',
                    'partner_id': partner.id,
                }

                # Comision
                if self.create_commission and ml_payment.total_charges > 0 and self.commission_journal_id and self.commission_partner_id:
                    commission_vals = {
                        'payment_type': 'outbound',
                        'partner_type': 'supplier',
                        'partner_id': self.commission_partner_id.id,
                        'amount': abs(ml_payment.total_charges),
                        'currency_id': ml_payment.currency_id.id or self.company_id.currency_id.id,
                        'journal_id': self.commission_journal_id.id,
                        'date': payment_date,
                        'ref': f'ML-COM-{ml_payment.mp_payment_id}',
                        # Campos ML para trazabilidad
                        'ml_payment_id': ml_payment.id,
                        'ml_payment_mp_id': ml_payment.mp_payment_id,
                        'ml_status': ml_payment.status,
                        'ml_responsible_user_id': self.env.user.id,
                    }
                    commission_payment = self.env['account.payment'].create(commission_vals)
                    update_vals['commission_payment_id'] = commission_payment.id

                ml_payment.write(update_vals)
                created_count += 1

            except Exception as e:
                error_count += 1
                errors.append(f'{ml_payment.mp_payment_id}: {str(e)}')
                ml_payment.write({
                    'odoo_payment_state': 'error',
                    'odoo_payment_error': str(e),
                })

        # Mostrar resumen
        message = _('Pagos creados: %d\nErrores: %d') % (created_count, error_count)
        if errors:
            message += '\n\n' + '\n'.join(errors[:10])  # Max 10 errores

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Creacion de Pagos Completada'),
                'message': message,
                'type': 'success' if error_count == 0 else 'warning',
                'sticky': True,
            }
        }
