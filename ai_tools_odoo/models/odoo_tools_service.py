# -*- coding: utf-8 -*-
from odoo import models, api
import json
import logging

_logger = logging.getLogger(__name__)


class OdooToolsService(models.AbstractModel):
    _name = 'ai.odoo.tools.service'
    _description = 'Odoo Tools Service for AI Agents'

    # ==========================================
    # PRODUCT TOOLS
    # ==========================================

    @api.model
    def tool_search_products(self, query, category=None, limit=5):
        """
        Search products by name, reference, or barcode.

        Args:
            query: Search term
            category: Optional category name to filter
            limit: Maximum results (default 5)

        Returns:
            Formatted string with product information
        """
        domain = [
            '|', '|',
            ('name', 'ilike', query),
            ('default_code', 'ilike', query),
            ('barcode', 'ilike', query),
            ('sale_ok', '=', True),
        ]

        if category:
            cat = self.env['product.category'].search([('name', 'ilike', category)], limit=1)
            if cat:
                domain.append(('categ_id', 'child_of', cat.id))

        products = self.env['product.product'].search(domain, limit=int(limit))

        if not products:
            return f"No encontré productos con '{query}'."

        result = [f"Encontré {len(products)} producto(s):"]
        for p in products:
            stock_info = ""
            if p.type == 'product':
                qty = p.qty_available
                stock_info = f" | Stock: {qty:.0f} unidades"

            result.append(
                f"• {p.name} (Ref: {p.default_code or 'N/A'}) - "
                f"${p.list_price:,.2f}{stock_info}"
            )

        return "\n".join(result)

    @api.model
    def tool_get_product_details(self, product_ref):
        """
        Get detailed information about a specific product.

        Args:
            product_ref: Product reference code or name

        Returns:
            Detailed product information
        """
        product = self.env['product.product'].search([
            '|',
            ('default_code', '=', product_ref),
            ('name', 'ilike', product_ref),
        ], limit=1)

        if not product:
            return f"No encontré el producto '{product_ref}'."

        info = [
            f"Producto: {product.name}",
            f"Referencia: {product.default_code or 'N/A'}",
            f"Precio: ${product.list_price:,.2f}",
            f"Categoría: {product.categ_id.name}",
        ]

        if product.type == 'product':
            info.append(f"Stock disponible: {product.qty_available:.0f} unidades")
            info.append(f"Stock reservado: {product.outgoing_qty:.0f} unidades")

        if product.description_sale:
            info.append(f"Descripción: {product.description_sale[:200]}")

        return "\n".join(info)

    @api.model
    def tool_check_stock(self, product_ref, warehouse=None):
        """
        Check stock availability for a product.

        Args:
            product_ref: Product reference or name
            warehouse: Optional warehouse name

        Returns:
            Stock information
        """
        product = self.env['product.product'].search([
            '|',
            ('default_code', '=', product_ref),
            ('name', 'ilike', product_ref),
        ], limit=1)

        if not product:
            return f"No encontré el producto '{product_ref}'."

        if product.type != 'product':
            return f"{product.name} es un servicio/consumible sin control de stock."

        if warehouse:
            wh = self.env['stock.warehouse'].search([('name', 'ilike', warehouse)], limit=1)
            if wh:
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', product.id),
                    ('location_id', 'child_of', wh.lot_stock_id.id),
                ])
                qty = sum(quants.mapped('quantity'))
                return f"{product.name}: {qty:.0f} unidades disponibles en {wh.name}"

        return f"{product.name}: {product.qty_available:.0f} unidades disponibles en total"

    # ==========================================
    # ORDER TOOLS
    # ==========================================

    @api.model
    def tool_get_order_status(self, order_ref):
        """
        Get the status of a sales order.

        Args:
            order_ref: Order reference (SO number or client reference)

        Returns:
            Order status and details
        """
        order = self.env['sale.order'].search([
            '|',
            ('name', 'ilike', order_ref),
            ('client_order_ref', 'ilike', order_ref),
        ], limit=1)

        if not order:
            return f"No encontré el pedido '{order_ref}'."

        state_names = {
            'draft': 'Borrador',
            'sent': 'Presupuesto Enviado',
            'sale': 'Pedido Confirmado',
            'done': 'Bloqueado',
            'cancel': 'Cancelado',
        }

        info = [
            f"Pedido: {order.name}",
            f"Cliente: {order.partner_id.name}",
            f"Estado: {state_names.get(order.state, order.state)}",
            f"Fecha: {order.date_order.strftime('%d/%m/%Y')}",
            f"Total: ${order.amount_total:,.2f}",
        ]

        # Check deliveries
        if order.picking_ids:
            delivered = order.picking_ids.filtered(lambda p: p.state == 'done')
            pending = order.picking_ids.filtered(lambda p: p.state not in ['done', 'cancel'])
            if delivered:
                info.append(f"Entregas completadas: {len(delivered)}")
            if pending:
                info.append(f"Entregas pendientes: {len(pending)}")

        # Check invoices
        if order.invoice_ids:
            invoiced = order.invoice_ids.filtered(lambda i: i.state == 'posted')
            if invoiced:
                paid = invoiced.filtered(lambda i: i.payment_state == 'paid')
                info.append(f"Facturado: ${sum(invoiced.mapped('amount_total')):,.2f}")
                if paid:
                    info.append(f"Pagado: ${sum(paid.mapped('amount_total')):,.2f}")

        return "\n".join(info)

    @api.model
    def tool_get_customer_orders(self, customer_ref, limit=5):
        """
        Get recent orders for a customer.

        Args:
            customer_ref: Customer name, email, or phone
            limit: Maximum orders to return

        Returns:
            List of recent orders
        """
        partner = self._find_partner(customer_ref)
        if not partner:
            return f"No encontré al cliente '{customer_ref}'."

        orders = self.env['sale.order'].search([
            ('partner_id', '=', partner.id),
            ('state', '!=', 'cancel'),
        ], order='date_order desc', limit=int(limit))

        if not orders:
            return f"No hay pedidos registrados para {partner.name}."

        result = [f"Últimos pedidos de {partner.name}:"]
        for order in orders:
            result.append(
                f"• {order.name} | {order.date_order.strftime('%d/%m/%Y')} | "
                f"${order.amount_total:,.2f} | {order.state}"
            )

        return "\n".join(result)

    # ==========================================
    # INVOICE TOOLS
    # ==========================================

    @api.model
    def tool_get_invoice_status(self, invoice_ref):
        """
        Get invoice status and payment information.

        Args:
            invoice_ref: Invoice number or reference

        Returns:
            Invoice details and payment status
        """
        invoice = self.env['account.move'].search([
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            '|',
            ('name', 'ilike', invoice_ref),
            ('ref', 'ilike', invoice_ref),
        ], limit=1)

        if not invoice:
            return f"No encontré la factura '{invoice_ref}'."

        payment_states = {
            'not_paid': 'No Pagada',
            'in_payment': 'En Proceso',
            'paid': 'Pagada',
            'partial': 'Pago Parcial',
            'reversed': 'Reversada',
        }

        info = [
            f"Factura: {invoice.name}",
            f"Cliente: {invoice.partner_id.name}",
            f"Fecha: {invoice.invoice_date.strftime('%d/%m/%Y') if invoice.invoice_date else 'N/A'}",
            f"Total: ${invoice.amount_total:,.2f}",
            f"Estado de pago: {payment_states.get(invoice.payment_state, invoice.payment_state)}",
        ]

        if invoice.amount_residual > 0:
            info.append(f"Saldo pendiente: ${invoice.amount_residual:,.2f}")
            if invoice.invoice_date_due:
                info.append(f"Fecha de vencimiento: {invoice.invoice_date_due.strftime('%d/%m/%Y')}")

        return "\n".join(info)

    @api.model
    def tool_get_customer_balance(self, customer_ref):
        """
        Get customer account balance.

        Args:
            customer_ref: Customer name, email, or reference

        Returns:
            Account balance information
        """
        partner = self._find_partner(customer_ref)
        if not partner:
            return f"No encontré al cliente '{customer_ref}'."

        # Get receivable balance
        receivable = partner.credit

        # Get pending invoices
        pending_invoices = self.env['account.move'].search([
            ('partner_id', '=', partner.id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'not in', ['paid', 'reversed']),
        ])

        info = [
            f"Balance de {partner.name}:",
            f"Saldo por cobrar: ${receivable:,.2f}",
            f"Facturas pendientes: {len(pending_invoices)}",
        ]

        if pending_invoices:
            oldest = pending_invoices.sorted('invoice_date')[0]
            info.append(f"Factura más antigua: {oldest.name} del {oldest.invoice_date.strftime('%d/%m/%Y')}")

        return "\n".join(info)

    # ==========================================
    # CUSTOMER TOOLS
    # ==========================================

    @api.model
    def tool_get_customer_info(self, customer_ref):
        """
        Get customer information.

        Args:
            customer_ref: Customer name, email, phone, or VAT

        Returns:
            Customer details
        """
        partner = self._find_partner(customer_ref)
        if not partner:
            return f"No encontré al cliente '{customer_ref}'."

        info = [
            f"Cliente: {partner.name}",
        ]

        if partner.vat:
            info.append(f"NIF/CUIT: {partner.vat}")
        if partner.email:
            info.append(f"Email: {partner.email}")
        if partner.phone:
            info.append(f"Teléfono: {partner.phone}")
        if partner.mobile:
            info.append(f"Móvil: {partner.mobile}")
        if partner.street:
            address = partner.street
            if partner.city:
                address += f", {partner.city}"
            if partner.state_id:
                address += f", {partner.state_id.name}"
            info.append(f"Dirección: {address}")

        return "\n".join(info)

    def _find_partner(self, ref):
        """Find partner by various criteria"""
        return self.env['res.partner'].search([
            '|', '|', '|', '|',
            ('name', 'ilike', ref),
            ('email', 'ilike', ref),
            ('phone', 'ilike', ref),
            ('mobile', 'ilike', ref),
            ('vat', 'ilike', ref),
        ], limit=1)

    # ==========================================
    # CRM TOOLS
    # ==========================================

    @api.model
    def tool_get_lead_info(self, lead_ref):
        """
        Get CRM lead/opportunity information.

        Args:
            lead_ref: Lead name or reference

        Returns:
            Lead details
        """
        lead = self.env['crm.lead'].search([
            ('name', 'ilike', lead_ref),
        ], limit=1)

        if not lead:
            return f"No encontré la oportunidad '{lead_ref}'."

        info = [
            f"{'Oportunidad' if lead.type == 'opportunity' else 'Lead'}: {lead.name}",
            f"Cliente: {lead.partner_id.name if lead.partner_id else lead.contact_name or 'N/A'}",
            f"Etapa: {lead.stage_id.name}",
        ]

        if lead.expected_revenue:
            info.append(f"Ingreso esperado: ${lead.expected_revenue:,.2f}")
        if lead.probability:
            info.append(f"Probabilidad: {lead.probability}%")
        if lead.user_id:
            info.append(f"Comercial: {lead.user_id.name}")

        return "\n".join(info)

    # ==========================================
    # ACTIVITY TASK TOOL
    # ==========================================

    @api.model
    def tool_create_activity_task(self, task_type, description, extracted_data=None, priority='1'):
        """
        Create a pending task for human review.

        Args:
            task_type: Type of task (create_invoice, create_lead, etc.)
            description: What needs to be done
            extracted_data: Relevant data from conversation
            priority: 0=low, 1=normal, 2=high, 3=urgent

        Returns:
            Confirmation message
        """
        valid_types = [
            'create_invoice', 'create_lead', 'create_ticket',
            'send_quote', 'create_task', 'schedule_call',
            'send_email', 'custom'
        ]

        if task_type not in valid_types:
            task_type = 'custom'

        data = extracted_data or {}
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                data = {'raw': data}

        # Find partner if reference provided
        partner_id = None
        if data.get('customer_ref'):
            partner = self._find_partner(data['customer_ref'])
            if partner:
                partner_id = partner.id
                data['partner_name'] = partner.name

        task = self.env['ai.activity.task'].create({
            'name': description,
            'task_type': task_type,
            'extracted_data': json.dumps(data, indent=2, default=str),
            'priority': str(priority),
            'partner_id': partner_id,
            'conversation_id': self.env.context.get('conversation_id'),
            'agent_id': self.env.context.get('agent_id'),
        })

        return f"He registrado tu solicitud (Tarea #{task.id}): {description}. Un agente lo revisará pronto."


# Extend AIAgentTool to include builtin Odoo tools
class AIAgentToolOdoo(models.Model):
    _inherit = 'ai.agent.tool'

    @api.model
    def _get_builtin_tool_methods(self):
        """Get mapping of builtin tool names to methods"""
        service = self.env['ai.odoo.tools.service']
        return {
            'search_products': service.tool_search_products,
            'get_product_details': service.tool_get_product_details,
            'check_stock': service.tool_check_stock,
            'get_order_status': service.tool_get_order_status,
            'get_customer_orders': service.tool_get_customer_orders,
            'get_invoice_status': service.tool_get_invoice_status,
            'get_customer_balance': service.tool_get_customer_balance,
            'get_customer_info': service.tool_get_customer_info,
            'get_lead_info': service.tool_get_lead_info,
            'create_activity_task': service.tool_create_activity_task,
        }

    def _execute_builtin(self, env, params):
        """Execute builtin Odoo tool"""
        methods = self._get_builtin_tool_methods()

        if self.technical_name in methods:
            method = methods[self.technical_name]
            return method(**params)

        # Fallback to original behavior
        return super()._execute_builtin(env, params)
