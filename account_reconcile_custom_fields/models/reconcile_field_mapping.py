# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ReconcileFieldMapping(models.Model):
    _name = "reconcile.field.mapping"
    _description = "Reconciliation Field Mapping Configuration"
    _order = "sequence, id"

    name = fields.Char(string="Name", required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )

    # Configuración de modelo origen (órdenes/facturas)
    source_model_id = fields.Many2one(
        "ir.model",
        string="Source Model",
        required=True,
        ondelete='cascade',
        domain=[
            "|", "|",
            ("model", "=", "sale.order"),
            ("model", "=", "purchase.order"),
            ("model", "=", "account.move"),
        ],
        help="Model to search in (Sale Order, Purchase Order, or Invoice)",
    )
    source_model = fields.Char(
        string="Source Model Technical Name",
        related="source_model_id.model",
        store=True,
    )
    source_field_id = fields.Many2one(
        "ir.model.fields",
        string="Source Field",
        required=True,
        ondelete='cascade',
        domain="[('model_id', '=', source_model_id)]",
        help="Field in the source model to match",
    )
    source_field_name = fields.Char(
        string="Source Field Name",
        related="source_field_id.name",
        store=True,
    )

    # Operador de comparación
    operator = fields.Selection(
        selection=[
            ("=", "Equals (=)"),
            ("!=", "Not Equals (!=)"),
            ("like", "Contains (like)"),
            ("ilike", "Contains (case insensitive)"),
            ("in", "In"),
            ("not in", "Not In"),
        ],
        string="Operator",
        required=True,
        default="=",
        help="Comparison operator for matching",
    )

    # Configuración de modelo destino (pagos/líneas bancarias)
    target_model_id = fields.Many2one(
        "ir.model",
        string="Target Model",
        required=True,
        ondelete='cascade',
        domain=[
            "|", "|",
            ("model", "=", "account.payment"),
            ("model", "=", "account.bank.statement.line"),
            ("model", "=", "account.move.line"),
        ],
        help="Model to match against (Payment, Bank Statement Line, or Journal Item)",
    )
    target_model = fields.Char(
        string="Target Model Technical Name",
        related="target_model_id.model",
        store=True,
    )
    target_field_id = fields.Many2one(
        "ir.model.fields",
        string="Target Field",
        required=True,
        ondelete='cascade',
        domain="[('model_id', '=', target_model_id)]",
        help="Field in the target model to match against",
    )
    target_field_name = fields.Char(
        string="Target Field Name",
        related="target_field_id.name",
        store=True,
    )

    # Filtros adicionales
    source_domain = fields.Char(
        string="Source Domain Filter",
        default="[]",
        help="Additional domain filter for source model (e.g., [('state', '=', 'sale')])",
    )
    target_domain = fields.Char(
        string="Target Domain Filter",
        default="[]",
        help="Additional domain filter for target model (e.g., [('state', '=', 'posted')])",
    )

    # Configuración de matching
    match_type = fields.Selection(
        selection=[
            ("exact", "Exact Match"),
            ("partial", "Partial Match"),
        ],
        string="Match Type",
        default="exact",
        required=True,
    )

    @api.constrains("source_field_id", "target_field_id")
    def _check_field_types(self):
        """Validar que los tipos de campos sean compatibles"""
        for record in self:
            if record.source_field_id and record.target_field_id:
                source_type = record.source_field_id.ttype
                target_type = record.target_field_id.ttype

                # Tipos compatibles para comparación
                compatible_types = {
                    "char": ["char", "text", "html"],
                    "text": ["char", "text", "html"],
                    "integer": ["integer", "float"],
                    "float": ["integer", "float"],
                    "many2one": ["many2one", "integer"],
                }

                if source_type in compatible_types:
                    if target_type not in compatible_types.get(source_type, []):
                        raise ValidationError(
                            _(
                                "Field types are not compatible: %s (%s) vs %s (%s)"
                            )
                            % (
                                record.source_field_id.name,
                                source_type,
                                record.target_field_id.name,
                                target_type,
                            )
                        )

    def _get_source_records(self, target_value):
        """
        Buscar registros en el modelo origen que coincidan con el valor del destino

        :param target_value: valor del campo destino a buscar
        :return: recordset del modelo origen
        """
        self.ensure_one()

        if not target_value:
            return self.env[self.source_model].browse()

        # Construir dominio de búsqueda
        domain = []

        # Agregar filtro del campo
        domain.append((self.source_field_name, self.operator, target_value))

        # Agregar dominio adicional si existe
        if self.source_domain and self.source_domain != "[]":
            try:
                additional_domain = eval(self.source_domain)
                domain.extend(additional_domain)
            except Exception:
                pass

        # Buscar en el modelo origen
        return self.env[self.source_model].search(domain)

    def _get_invoices_from_source(self, source_records):
        """
        Obtener facturas relacionadas con los registros origen

        :param source_records: registros del modelo origen (órdenes)
        :return: recordset de facturas (account.move)
        """
        self.ensure_one()

        invoices = self.env["account.move"].browse()

        if self.source_model == "sale.order":
            for order in source_records:
                invoices |= order.invoice_ids.filtered(
                    lambda inv: inv.move_type in ["out_invoice", "out_refund"]
                    and inv.state == "posted"
                )
        elif self.source_model == "purchase.order":
            for order in source_records:
                invoices |= order.invoice_ids.filtered(
                    lambda inv: inv.move_type in ["in_invoice", "in_refund"]
                    and inv.state == "posted"
                )
        elif self.source_model == "account.move":
            invoices = source_records.filtered(
                lambda inv: inv.move_type in [
                    "out_invoice",
                    "out_refund",
                    "in_invoice",
                    "in_refund",
                ]
                and inv.state == "posted"
            )

        return invoices

    def _get_receivable_payable_lines(self, invoices):
        """
        Obtener líneas de cuentas por cobrar/pagar de las facturas

        :param invoices: recordset de facturas
        :return: recordset de account.move.line
        """
        lines = self.env["account.move.line"].browse()

        for invoice in invoices:
            lines |= invoice.line_ids.filtered(
                lambda line: line.account_id.account_type in [
                    "asset_receivable",
                    "liability_payable",
                ]
                and not line.reconciled
            )

        return lines

    def find_matching_lines(self, target_record):
        """
        Encontrar líneas de factura que coincidan con el registro destino

        :param target_record: registro del modelo destino (pago/línea bancaria)
        :return: recordset de account.move.line para conciliar
        """
        self.ensure_one()

        # Obtener valor del campo destino
        target_value = target_record[self.target_field_name]

        if not target_value:
            return self.env["account.move.line"].browse()

        # Buscar en el modelo origen
        source_records = self._get_source_records(target_value)

        if not source_records:
            return self.env["account.move.line"].browse()

        # Obtener facturas relacionadas
        invoices = self._get_invoices_from_source(source_records)

        if not invoices:
            return self.env["account.move.line"].browse()

        # Obtener líneas por cobrar/pagar
        matching_lines = self._get_receivable_payable_lines(invoices)

        return matching_lines
