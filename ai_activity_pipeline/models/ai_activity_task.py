# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import json
import logging

_logger = logging.getLogger(__name__)


class AIActivityTask(models.Model):
    _name = 'ai.activity.task'
    _description = 'AI Generated Activity Task'
    _order = 'priority desc, create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Task Name', required=True, tracking=True)

    # Source
    conversation_id = fields.Many2one(
        'ai.conversation',
        string='Source Conversation',
        ondelete='set null'
    )
    agent_id = fields.Many2one(
        'ai.agent',
        string='Agent',
        ondelete='set null'
    )

    # Task type
    task_type = fields.Selection([
        ('create_invoice', 'Create Invoice'),
        ('create_lead', 'Create CRM Lead'),
        ('create_ticket', 'Create Support Ticket'),
        ('send_quote', 'Send Quotation'),
        ('create_task', 'Create Task'),
        ('schedule_call', 'Schedule Call'),
        ('send_email', 'Send Email'),
        ('update_record', 'Update Record'),
        ('custom', 'Custom Action'),
    ], string='Task Type', required=True, tracking=True)

    # State
    state = fields.Selection([
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('processing', 'Processing'),
        ('done', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='pending', tracking=True)

    # Priority
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Urgent'),
    ], string='Priority', default='1')

    # Extracted data from AI
    extracted_data = fields.Text(
        string='Extracted Data',
        help='JSON with data extracted from conversation'
    )

    # Human-readable summary
    summary = fields.Text(
        string='Summary',
        help='Human-readable description of what this task will do'
    )

    # Validation
    requires_approval = fields.Boolean(
        string='Requires Approval',
        default=True
    )
    auto_execute = fields.Boolean(
        string='Auto Execute',
        default=False,
        help='Execute automatically when approved'
    )

    # Approval tracking
    approved_by = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True
    )
    approved_date = fields.Datetime(
        string='Approved Date',
        readonly=True
    )

    # Execution tracking
    executed_by = fields.Many2one(
        'res.users',
        string='Executed By',
        readonly=True
    )
    executed_date = fields.Datetime(
        string='Executed Date',
        readonly=True
    )

    # Result
    res_model = fields.Char(string='Result Model')
    res_id = fields.Integer(string='Result ID')
    result_message = fields.Text(string='Result Message')
    error_message = fields.Text(string='Error Message')

    # Customer reference
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        help='Customer related to this task'
    )

    # Scheduling
    scheduled_date = fields.Datetime(
        string='Scheduled Date',
        help='When to execute this task'
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Generate summary if not provided
            if not vals.get('summary') and vals.get('extracted_data'):
                vals['summary'] = self._generate_summary(
                    vals.get('task_type'),
                    vals.get('extracted_data')
                )
        return super().create(vals_list)

    def _generate_summary(self, task_type, extracted_data):
        """Generate human-readable summary from extracted data"""
        try:
            data = json.loads(extracted_data) if isinstance(extracted_data, str) else extracted_data
        except json.JSONDecodeError:
            return "Task data available"

        summaries = {
            'create_invoice': lambda d: f"Create invoice for {d.get('partner_name', 'customer')} - Amount: {d.get('amount', 'N/A')}",
            'create_lead': lambda d: f"Create lead: {d.get('name', 'New opportunity')} - Expected: {d.get('expected_revenue', 'N/A')}",
            'create_ticket': lambda d: f"Create ticket: {d.get('subject', 'Support request')}",
            'send_quote': lambda d: f"Send quote to {d.get('partner_name', 'customer')}",
            'schedule_call': lambda d: f"Schedule call with {d.get('partner_name', 'customer')} on {d.get('date', 'TBD')}",
            'send_email': lambda d: f"Send email to {d.get('to', 'recipient')}: {d.get('subject', 'No subject')}",
        }

        generator = summaries.get(task_type)
        if generator:
            return generator(data)
        return f"Execute {task_type} task"

    def get_extracted_data(self):
        """Get extracted data as dictionary"""
        self.ensure_one()
        if not self.extracted_data:
            return {}
        try:
            return json.loads(self.extracted_data)
        except json.JSONDecodeError:
            return {}

    def set_extracted_data(self, data):
        """Set extracted data from dictionary"""
        self.ensure_one()
        self.extracted_data = json.dumps(data, indent=2, default=str)

    def action_approve(self):
        """Approve task for execution"""
        self.ensure_one()
        if self.state != 'pending':
            raise UserError("Only pending tasks can be approved.")

        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approved_date': fields.Datetime.now(),
        })

        if self.auto_execute:
            self.action_execute()

        return True

    def action_reject(self):
        """Reject/cancel task"""
        self.ensure_one()
        if self.state in ['done', 'processing']:
            raise UserError("Cannot reject completed or processing tasks.")

        self.write({'state': 'cancelled'})
        return True

    def action_execute(self):
        """Execute the task"""
        self.ensure_one()
        if self.state not in ['approved', 'pending']:
            raise UserError("Only approved tasks can be executed.")

        if self.state == 'pending' and self.requires_approval:
            raise UserError("This task requires approval before execution.")

        self.write({'state': 'processing'})

        try:
            data = self.get_extracted_data()

            # Execute based on task type
            method_name = f'_execute_{self.task_type}'
            if hasattr(self, method_name):
                result = getattr(self, method_name)(data)
            else:
                result = self._execute_custom(data)

            self.write({
                'state': 'done',
                'res_model': result.get('model'),
                'res_id': result.get('id'),
                'result_message': result.get('message'),
                'executed_by': self.env.user.id,
                'executed_date': fields.Datetime.now(),
            })

            return True

        except Exception as e:
            _logger.exception(f"Error executing task {self.id}")
            self.write({
                'state': 'failed',
                'error_message': str(e),
            })
            return False

    def action_retry(self):
        """Retry failed task"""
        self.ensure_one()
        if self.state != 'failed':
            raise UserError("Only failed tasks can be retried.")

        self.write({
            'state': 'approved',
            'error_message': False,
        })
        return self.action_execute()

    def action_view_result(self):
        """View the created record"""
        self.ensure_one()
        if not self.res_model or not self.res_id:
            raise UserError("No result record available.")

        return {
            'type': 'ir.actions.act_window',
            'res_model': self.res_model,
            'res_id': self.res_id,
            'view_mode': 'form',
            'target': 'current',
        }

    # Task execution methods
    def _execute_create_invoice(self, data):
        """Create customer invoice"""
        partner_id = data.get('partner_id') or self.partner_id.id
        if not partner_id:
            raise ValidationError("Customer is required to create invoice")

        lines = data.get('lines', [])
        if not lines:
            # Create default line
            lines = [{
                'name': data.get('description', 'Service from AI conversation'),
                'quantity': data.get('quantity', 1),
                'price_unit': data.get('amount', 0),
            }]

        invoice_lines = []
        for line in lines:
            invoice_lines.append((0, 0, {
                'name': line.get('name', 'Product/Service'),
                'quantity': line.get('quantity', 1),
                'price_unit': line.get('price_unit', 0),
                'product_id': line.get('product_id'),
            }))

        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner_id,
            'invoice_line_ids': invoice_lines,
            'narration': f"Created from AI conversation {self.conversation_id.name if self.conversation_id else ''}",
        })

        return {
            'model': 'account.move',
            'id': invoice.id,
            'message': f"Invoice {invoice.name} created successfully"
        }

    def _execute_create_lead(self, data):
        """Create CRM lead/opportunity"""
        partner_id = data.get('partner_id') or self.partner_id.id

        lead = self.env['crm.lead'].create({
            'name': data.get('name', f'Lead from AI - {self.name}'),
            'partner_id': partner_id,
            'contact_name': data.get('contact_name'),
            'email_from': data.get('email'),
            'phone': data.get('phone'),
            'description': data.get('description', ''),
            'expected_revenue': data.get('expected_revenue', 0),
            'type': 'opportunity' if data.get('is_opportunity') else 'lead',
        })

        return {
            'model': 'crm.lead',
            'id': lead.id,
            'message': f"Lead '{lead.name}' created successfully"
        }

    def _execute_create_ticket(self, data):
        """Create helpdesk ticket (if module installed)"""
        # Check if helpdesk module is installed
        if 'helpdesk.ticket' in self.env:
            ticket = self.env['helpdesk.ticket'].create({
                'name': data.get('subject', self.name),
                'description': data.get('description', ''),
                'partner_id': data.get('partner_id') or self.partner_id.id,
            })
            return {
                'model': 'helpdesk.ticket',
                'id': ticket.id,
                'message': f"Ticket '{ticket.name}' created"
            }
        else:
            # Fallback to mail.activity or simple note
            return self._execute_create_task(data)

    def _execute_send_quote(self, data):
        """Create and optionally send quotation"""
        partner_id = data.get('partner_id') or self.partner_id.id
        if not partner_id:
            raise ValidationError("Customer is required to create quotation")

        lines = data.get('lines', [])
        order_lines = []
        for line in lines:
            product_id = line.get('product_id')
            if product_id:
                product = self.env['product.product'].browse(product_id)
                order_lines.append((0, 0, {
                    'product_id': product_id,
                    'name': product.name,
                    'product_uom_qty': line.get('quantity', 1),
                    'price_unit': line.get('price_unit', product.list_price),
                }))

        if not order_lines:
            # Create with generic line
            order_lines.append((0, 0, {
                'name': data.get('description', 'Quotation item'),
                'product_uom_qty': data.get('quantity', 1),
                'price_unit': data.get('amount', 0),
            }))

        order = self.env['sale.order'].create({
            'partner_id': partner_id,
            'order_line': order_lines,
        })

        return {
            'model': 'sale.order',
            'id': order.id,
            'message': f"Quotation {order.name} created"
        }

    def _execute_create_task(self, data):
        """Create a task/activity"""
        partner_id = data.get('partner_id') or self.partner_id.id

        # Create as mail.activity on partner
        if partner_id:
            partner = self.env['res.partner'].browse(partner_id)
            activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)

            activity = self.env['mail.activity'].create({
                'res_model_id': self.env['ir.model']._get('res.partner').id,
                'res_id': partner_id,
                'activity_type_id': activity_type.id if activity_type else False,
                'summary': data.get('summary', self.name),
                'note': data.get('description', ''),
                'date_deadline': data.get('deadline', fields.Date.today()),
                'user_id': self.env.user.id,
            })

            return {
                'model': 'mail.activity',
                'id': activity.id,
                'message': f"Task created for {partner.name}"
            }

        return {
            'model': False,
            'id': False,
            'message': "Task registered (no specific record created)"
        }

    def _execute_schedule_call(self, data):
        """Schedule a call activity"""
        partner_id = data.get('partner_id') or self.partner_id.id
        if not partner_id:
            raise ValidationError("Customer is required to schedule call")

        activity_type = self.env.ref('mail.mail_activity_data_call', raise_if_not_found=False)

        activity = self.env['mail.activity'].create({
            'res_model_id': self.env['ir.model']._get('res.partner').id,
            'res_id': partner_id,
            'activity_type_id': activity_type.id if activity_type else False,
            'summary': data.get('summary', f'Call - {self.name}'),
            'note': data.get('notes', ''),
            'date_deadline': data.get('date', fields.Date.today()),
            'user_id': data.get('user_id', self.env.user.id),
        })

        return {
            'model': 'mail.activity',
            'id': activity.id,
            'message': f"Call scheduled for {activity.date_deadline}"
        }

    def _execute_send_email(self, data):
        """Send email"""
        email_to = data.get('to')
        if not email_to and self.partner_id:
            email_to = self.partner_id.email

        if not email_to:
            raise ValidationError("Email recipient is required")

        mail = self.env['mail.mail'].create({
            'subject': data.get('subject', 'Message from AI Assistant'),
            'body_html': data.get('body', data.get('message', '')),
            'email_to': email_to,
            'email_from': data.get('from', self.env.company.email),
        })
        mail.send()

        return {
            'model': 'mail.mail',
            'id': mail.id,
            'message': f"Email sent to {email_to}"
        }

    def _execute_update_record(self, data):
        """Update existing record"""
        model = data.get('model')
        record_id = data.get('record_id')
        values = data.get('values', {})

        if not model or not record_id:
            raise ValidationError("Model and record ID are required")

        record = self.env[model].browse(record_id)
        if not record.exists():
            raise ValidationError(f"Record {model}:{record_id} not found")

        record.write(values)

        return {
            'model': model,
            'id': record_id,
            'message': f"Record {model}:{record_id} updated"
        }

    def _execute_custom(self, data):
        """Execute custom action"""
        # Custom actions should be implemented by extending modules
        return {
            'model': False,
            'id': False,
            'message': f"Custom task '{self.name}' completed"
        }

    @api.model
    def _cron_process_approved_tasks(self):
        """Cron job to process approved tasks"""
        tasks = self.search([
            ('state', '=', 'approved'),
            ('auto_execute', '=', True),
            '|',
            ('scheduled_date', '=', False),
            ('scheduled_date', '<=', fields.Datetime.now()),
        ], limit=50)

        for task in tasks:
            try:
                task.action_execute()
            except Exception as e:
                _logger.error(f"Cron: Failed to execute task {task.id}: {e}")

        return True

    @api.model
    def _cron_cleanup_old_tasks(self):
        """Cleanup old completed/cancelled tasks"""
        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(days=90)

        old_tasks = self.search([
            ('state', 'in', ['done', 'cancelled']),
            ('executed_date', '<', cutoff),
        ])

        old_tasks.unlink()
        return True
