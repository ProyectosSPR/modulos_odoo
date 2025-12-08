# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PartnerCorrectionWizard(models.TransientModel):
    _name = "partner.correction.wizard"
    _description = "Partner Correction Wizard"

    inconsistency_id = fields.Many2one(
        "partner.inconsistency",
        string="Inconsistencia",
        required=True,
        ondelete="cascade"
    )

    payment_line_id = fields.Many2one(
        "account.move.line",
        string="Línea de Pago (a corregir)",
        required=True,
        readonly=True
    )

    invoice_line_id = fields.Many2one(
        "account.move.line",
        string="Línea de Factura (referencia)",
        required=True,
        readonly=True
    )

    current_partner_id = fields.Many2one(
        "res.partner",
        string="Partner Actual del Pago",
        readonly=True
    )

    suggested_partner_id = fields.Many2one(
        "res.partner",
        string="Partner de la Factura",
        readonly=True
    )

    correction_option = fields.Selection([
        ('use_invoice', 'Usar Partner de la Factura'),
        ('use_current', 'Mantener Partner del Pago (No corregir)'),
        ('use_manual', 'Seleccionar Partner Manualmente'),
    ], string="Opción de Corrección", default='use_invoice', required=True)

    manual_partner_id = fields.Many2one(
        "res.partner",
        string="Seleccionar Partner"
    )

    # Campos informativos
    payment_move_name = fields.Char(
        string="Pago",
        related="payment_line_id.move_id.name",
        readonly=True
    )

    invoice_move_name = fields.Char(
        string="Factura",
        related="invoice_line_id.move_id.name",
        readonly=True
    )

    payment_amount = fields.Monetary(
        string="Monto del Pago",
        related="payment_line_id.credit",
        readonly=True,
        currency_field="currency_id"
    )

    invoice_amount = fields.Monetary(
        string="Monto de la Factura",
        related="invoice_line_id.debit",
        readonly=True,
        currency_field="currency_id"
    )

    currency_id = fields.Many2one(
        related="payment_line_id.currency_id",
        readonly=True
    )

    referencia_comun = fields.Char(
        related="inconsistency_id.referencia_comun",
        readonly=True
    )

    @api.onchange('correction_option')
    def _onchange_correction_option(self):
        """Limpiar manual_partner_id si no se usa la opción manual"""
        if self.correction_option != 'use_manual':
            self.manual_partner_id = False

    def action_apply_correction(self):
        """Aplicar la corrección al pago"""
        self.ensure_one()

        # Determinar qué partner usar
        new_partner_id = False
        if self.correction_option == 'use_invoice':
            new_partner_id = self.suggested_partner_id.id
        elif self.correction_option == 'use_manual':
            if not self.manual_partner_id:
                raise UserError(_("Debe seleccionar un partner manualmente."))
            new_partner_id = self.manual_partner_id.id
        elif self.correction_option == 'use_current':
            # No hacer nada, solo cerrar el wizard
            self.inconsistency_id.unlink()
            return {'type': 'ir.actions.act_window_close'}

        if not new_partner_id:
            raise UserError(_("No se pudo determinar el partner a usar."))

        # Corregir el PAGO (move del payment)
        payment_move = self.payment_line_id.move_id

        _logger.info(
            f"Corrigiendo pago {payment_move.name}: "
            f"Partner {self.current_partner_id.name} → {self.env['res.partner'].browse(new_partner_id).name}"
        )

        # Cambiar a borrador si está publicado
        was_posted = payment_move.state == 'posted'
        if was_posted:
            payment_move.button_draft()

        # Actualizar partner en TODAS las líneas del move
        payment_move.line_ids.with_context(check_move_validity=False).write({
            'partner_id': new_partner_id
        })

        # Re-publicar si estaba publicado
        if was_posted:
            payment_move.action_post()

        # Eliminar la inconsistencia de la lista
        self.inconsistency_id.unlink()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Corrección Exitosa'),
                'message': _(
                    f'El pago {payment_move.name} ha sido actualizado. '
                    f'Nuevo partner: {self.env["res.partner"].browse(new_partner_id).name}'
                ),
                'type': 'success',
                'sticky': False,
            },
        }
