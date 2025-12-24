from odoo import api, models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'
    
    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        if self.env.user == self.env.ref('base.user_root'):
            return super(IrUiMenu, self).search(args, offset=0, limit=None, order=order, count=False)
        else:
            menus = super(IrUiMenu, self).search(args, offset=0, limit=None, order=order, count=False)
            if menus:
                general_ledger_menu_id = self.env.ref('account_financial_report.menu_general_ledger_wizard').id or False
                journal_ledger_menu_id = self.env.ref('account_financial_report.menu_journal_ledger_wizard').id or False
                open_items_menu_id = self.env.ref('account_financial_report.menu_open_items_wizard').id or False
                aged_partner_balance_menu_id = self.env.ref('account_financial_report.menu_aged_partner_balance_wizard').id or False
                
                #dynamic Account reports menu
                daybook_menu_id = self.env.ref('dynamic_accounts_report.menu_report_daybook').id or False
                bankbook_menu_id = self.env.ref('dynamic_accounts_report.menu_bank_book').id or False
                cashbook_menu_id = self.env.ref('dynamic_accounts_report.menu_cash_book').id or False
                trial_balance_menu_id = self.env.ref('dynamic_accounts_report.menu_trial_balance').id or False
                cash_flow_menu_id = self.env.ref('dynamic_accounts_report.menu_cash_flow').id or False

                tax_report_menu_id = self.env.ref('base_accounting_kit.menu_tax_report').id or False

                if general_ledger_menu_id in menus.ids:
                    menus -= self.env['ir.ui.menu'].browse(general_ledger_menu_id)
                if journal_ledger_menu_id in menus.ids:
                    menus -= self.env['ir.ui.menu'].browse(journal_ledger_menu_id)
                if open_items_menu_id in menus.ids:
                    menus -= self.env['ir.ui.menu'].browse(open_items_menu_id)
                if aged_partner_balance_menu_id in menus.ids:
                    menus -= self.env['ir.ui.menu'].browse(aged_partner_balance_menu_id)
                #dynamic Account reports menu
                if daybook_menu_id in menus.ids:
                    menus -= self.env['ir.ui.menu'].browse(daybook_menu_id)
                if bankbook_menu_id in menus.ids:
                    menus -= self.env['ir.ui.menu'].browse(bankbook_menu_id)
                if cashbook_menu_id in menus.ids:
                    menus -= self.env['ir.ui.menu'].browse(cashbook_menu_id)
                if trial_balance_menu_id in menus.ids:
                    menus -= self.env['ir.ui.menu'].browse(trial_balance_menu_id)
                if cash_flow_menu_id in menus.ids:
                    menus -= self.env['ir.ui.menu'].browse(cash_flow_menu_id)
                if tax_report_menu_id in menus.ids:
                    menus -= self.env['ir.ui.menu'].browse(tax_report_menu_id)
                if offset:
                    menus = menus[offset:]
                if limit:
                    menus = menus[:limit]
            return len(menus) if count else menus