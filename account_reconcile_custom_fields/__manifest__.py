# Copyright 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Account Reconcile Custom Fields",
    "version": "16.0.1.0.0",
    "category": "Accounting",
    "license": "AGPL-3",
    "summary": "Reconcile invoices and payments by matching custom fields from orders",
    "author": "DML",
    "website": "",
    "depends": [
        "account_reconcile_oca",
        "sale",
        "purchase",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/reconcile_field_mapping_views.xml",
        "views/account_bank_statement_line_views.xml",
        "views/account_account_reconcile_views.xml",
        "views/partner_inconsistency_wizard_views.xml",
        "views/partner_inconsistency_views.xml",
    ],
    "demo": [
        "demo/demo_data.xml",
    ],
    "installable": True,
    "application": False,
}
