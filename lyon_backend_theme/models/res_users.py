# -*- coding: utf-8 -*-
from odoo import fields, models,api

class ResUsers(models.Model):
    _inherit = "res.users"

    chatter_position = fields.Selection(
        [("normal", "Normal"), ("sided", "Sided")],
        default="sided",
    )
    
    
    lyon_backend_theme_has_dark_mode = fields.Boolean(string="Has Dark Mode",copy=False)
    
    
    
    """Override to add access rights.
    Access rights are disabled by default, but allowed on some specific
    fields defined in self.SELF_{READ/WRITE}ABLE_FIELDS.
    """

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ["chatter_position","lyon_backend_theme_has_dark_mode"]

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ["chatter_position","lyon_backend_theme_has_dark_mode"]


    @api.model
    def get_or_set_lyon_backend_theme_has_dark_mode(self, toggle_dark_mode=False):
        has_dark_mode = False  
        query = """SELECT lyon_backend_theme_has_dark_mode 
                    FROM res_users
                    WHERE id = %(user_id)s;
                    """
        self.env.cr.execute(query, {
            'user_id': self.env.uid,
        })
        res = self.env.cr.fetchone()
        if res:
            has_dark_mode = res[0]                
        if toggle_dark_mode:
            has_dark_mode = not has_dark_mode
            query = """update res_users set lyon_backend_theme_has_dark_mode=%(dark_mode_flag)s 
                        WHERE id = %(user_id)s;
                        """
            self.env.cr.execute(query, {
                'dark_mode_flag': has_dark_mode,
                'user_id': self.env.uid,
            })
        return has_dark_mode

    