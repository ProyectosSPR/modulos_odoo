# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2021-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################

from . import controllers
from . import wizard
from . import report
from . import models
from odoo import api, SUPERUSER_ID


def _load_account_details_post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for record in env['account.financial.report'].search([('type', '=', 'account_type')]):
        if record.get_metadata()[0].get('xmlid') == 'base_accounting_kit.account_financial_report_other_income0':
            for rec in env['account.account'].search([('account_type', '=', 'income_other')]):
                record.write({"account_ids": [(4, rec.id)]})

        elif record.get_metadata()[0].get('xmlid') == 'base_accounting_kit.financial_report_cost_of_revenue':
            for rec in env['account.account'].search([('account_type', '=', 'expense_direct_cost')]):
                record.write({"account_ids": [(4, rec.id)]})

        elif record.get_metadata()[0].get('xmlid') == 'base_accounting_kit.account_financial_report_operating_income0':
            for rec in env['account.account'].search([('account_type', '=', 'income')]):
                record.write({"account_ids": [(4, rec.id)]})

        elif record.get_metadata()[0].get('xmlid') == 'base_accounting_kit.account_financial_report_equiti3':
            for rec in env['account.account'].search([('account_type', '=', 'equity_unaffected')]):
                record.write({"account_ids": [(4, rec.id)]})

        elif record.get_metadata()[0].get('xmlid') == 'base_accounting_kit.account_financial_report_extra01':
            for rec in env['account.account'].search([('account_type', '=', 'expense')]):
                if rec.code != '899.01.99':
                   record.write({"account_ids": [(4, rec.id)]})

        elif record.get_metadata()[0].get('xmlid') == 'base_accounting_kit.account_financial_report_extra02':
            for rec in env['account.account'].search([('account_type', '=', 'expense_depreciation')]):
                record.write({"account_ids": [(4, rec.id)]})

        elif record.get_metadata()[0].get('xmlid') == 'base_accounting_kit.account_financial_report_extra07':
            for rec in env['account.account'].search([('account_type', '=', 'asset_receivable')]):
                record.write({"account_ids": [(4, rec.id)]})

        elif record.get_metadata()[0].get('xmlid') == 'base_accounting_kit.account_financial_report_extra05':
            for rec in env['account.account'].search([('account_type', '=', 'asset_non_current')]):
                record.write({"account_ids": [(4, rec.id)]})

        elif record.get_metadata()[0].get('xmlid') == 'base_accounting_kit.account_financial_report_extra08':
            for rec in env['account.account'].search([('account_type', '=', 'asset_current')]):
                record.write({"account_ids": [(4, rec.id)]})

#        elif record.get_metadata()[0].get('xmlid') == 'base_accounting_kit.account_financial_report_extra07':
#            for rec in env['account.account'].search([('account_type', '=', 'asset_prepayments')]):
#                record.write({"account_ids": [(4, rec.id)]})

        elif record.get_metadata()[0].get('xmlid') == 'base_accounting_kit.account_financial_report_extra04':
            for rec in env['account.account'].search([('account_type', '=', 'asset_fixed')]):
                record.write({"account_ids": [(4, rec.id)]})

        elif record.get_metadata()[0].get('xmlid') == 'base_accounting_kit.account_financial_report_extra06':
            for rec in env['account.account'].search([('account_type', '=', 'asset_cash')]):
                record.write({"account_ids": [(4, rec.id)]})

        elif record.get_metadata()[0].get('xmlid') == 'base_accounting_kit.account_financial_report_extra10':
            for rec in env['account.account'].search([('account_type', '=', 'liability_payable')]):
                record.write({"account_ids": [(4, rec.id)]})

        elif record.get_metadata()[0].get('xmlid') == 'base_accounting_kit.account_financial_report_earnings0':
            for rec in env['account.account'].search([('account_type', '=', 'equity')]):
                record.write({"account_ids": [(4, rec.id)]})

        elif record.get_metadata()[0].get('xmlid') == 'base_accounting_kit.account_financial_report_extra09':
            for rec in env['account.account'].search([('account_type', '=', 'liability_current')]):
                record.write({"account_ids": [(4, rec.id)]})

        elif record.get_metadata()[0].get('xmlid') == 'base_accounting_kit.account_financial_report_extra11':
            for rec in env['account.account'].search([('account_type', '=', 'liability_non_current')]):
                record.write({"account_ids": [(4, rec.id)]})

#        elif record.get_metadata()[0].get('xmlid') == 'base_accounting_kit.account_financial_report_extra06':
#            for rec in env['account.account'].search([('account_type', '=', 'liability_credit_card')]):
#                record.write({"account_ids": [(4, rec.id)]})


def unlink_records_financial_report(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for record in env['account.financial.report'].search(
            [('type', '=', 'account_type')]):
        record.write({"account_ids": [(5, 0, 0)]})
