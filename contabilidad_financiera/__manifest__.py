{
    "name": "Contabilidad Financiera",
    "version": "16.03",
    "summary": "Reportes financieros para México",
    "author": 'IT Admin',
    "website": 'https://www.itadmin.com.mx',
    "depends": ["account", "account_financial_report", "cdfi_invoice","dynamic_accounts_report","base_accounting_kit"],
    "data": [
        'security/ir.model.access.csv',
        'views/account_payment.xml',
        'views/account_config.xml',
        'wizard/isr_provisional_wizard_view.xml',
        'wizard/isr_causado_wizard_view.xml',
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
    "license": "AGPL-3",
}
