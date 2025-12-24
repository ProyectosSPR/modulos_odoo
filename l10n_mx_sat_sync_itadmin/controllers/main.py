# -*- coding: utf-8 -*-

from odoo.addons.web.controllers.action import Action
from odoo.http import request, route

from odoo.addons.web.controllers.action import Action
# Set company_id variable, so it is accessible in Action domain

class ActionSatSync(Action):
    _description = 'ActionSatSync'

    @route('/web/action/load', type='json', auth="user")
    def load(self, action_id, additional_context=None):
        value = super(ActionSatSync, self).load(action_id, additional_context)
        if value and value.get('xml_id', '') == 'l10n_mx_sat_sync_itadmin.action_attachment_cfdi_supplier_invoices':
            try:
                ctx = value.get('context', '{}')
                ctx = eval(ctx)
                if 'company_id' not in ctx:
                    cids = request.httprequest.cookies.get('cids', str(request.env.company.id))
                    company_ids = [int(cid) for cid in cids.split(',')]
                    company_id = company_ids and company_ids[0] or request.env.company.id
                    ctx.update({'company_id': company_id})  # request.env.company.id
                    value['context'] = str(ctx)
            except Exception:
                pass
        return value
