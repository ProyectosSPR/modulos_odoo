########################################################################
#                                                                      #
#     ------------------------ODOO WAVES----------------------         #
#     --------------odoowaves.solution@gmail.com--------------         #
#                                                                      #
########################################################################
{
    "name": "Odoo Python Pip Installer",
    "summary": "Install Python libraries directly from Odoo interface",
    "category": "Extra Tools",
    "version": "16.0.1.0.0",
    "sequence": 2,
    "author": "Odoo Waves",
    "license": "LGPL-3",
    "website": "",
    "description": "Python Library Installer - Allows installing pip packages from Odoo",
    "depends": ["base"],
    "data": [
        'security/ir.model.access.csv',
        'wizard/pip_command_view.xml',
        'wizard/message_wizard_view.xml',
        'views/menus.xml',
    ],
    "images": ['static/description/banner.gif'],
    "application": True,
    "installable": True,
    "auto_install": False,
    "pre_init_hook": "pre_init_check",
}
