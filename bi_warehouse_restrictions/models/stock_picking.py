# -*- coding: utf-8 -*-
# Part of Browseinfo. See LICENSE file for full copyright and licensing details.


from odoo import api, fields, models


class InheritStockPicking(models.Model):
    _inherit ="stock.picking"


    def search(self, args, **kwargs):
        allowed_access = self.env.user.has_group('bi_warehouse_restrictions.group_restrict_operations')
        current_uid = self._context.get('uid')
        user = self.env['res.users'].browse(current_uid)

        if user.restrict_operation and user.restrict_location and user.restrict_warehouse_list and allowed_access:
            args += ['|','|',
            ('picking_type_id','in',self.env.user.operation_ids.ids),
            ('location_id','in',self.env.user.location_ids.ids),
            ('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids),]

        elif  user.restrict_operation and user.restrict_location and allowed_access :
            args += ['|',('picking_type_id','in',self.env.user.operation_ids.ids),('location_id','in',self.env.user.location_ids.ids)]
        elif  user.restrict_operation and user.restrict_warehouse_list and allowed_access :
            args += ['|',('picking_type_id','in',self.env.user.operation_ids.ids),('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)]

        elif  user.restrict_location and user.restrict_warehouse_list and allowed_access :
            args += ['|',('location_id','in',self.env.user.location_ids.ids),('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)]

        elif user.restrict_operation and allowed_access:
           args += [('picking_type_id','in',self.env.user.operation_ids.ids)]
        elif user.restrict_location and allowed_access:
            args += [('location_id','in',self.env.user.location_ids.ids)]
        elif user.restrict_warehouse_list and allowed_access:
            args += [('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)]

        return super(InheritStockPicking, self).search(args, **kwargs)


    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        context = dict(self.env.context)
        allowed_access = self.env.user.has_group('bi_warehouse_restrictions.group_restrict_operations')
        current_uid = self._context.get('uid')
        user = self.env['res.users'].browse(current_uid)

        if user.restrict_operation and user.restrict_location and user.restrict_warehouse_list and allowed_access:
            args += ['|','|',
            ('picking_type_id','in',self.env.user.operation_ids.ids),
            ('location_id','in',self.env.user.location_ids.ids),
            ('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids),]

        elif  user.restrict_operation and user.restrict_location and allowed_access :
            args += ['|',('picking_type_id','in',self.env.user.operation_ids.ids),('location_id','in',self.env.user.location_ids.ids)]
        elif  user.restrict_operation and user.restrict_warehouse_list and allowed_access :
            args += ['|',('picking_type_id','in',self.env.user.operation_ids.ids),('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)]

        elif  user.restrict_location and user.restrict_warehouse_list and allowed_access :
            args += ['|',('location_id','in',self.env.user.location_ids.ids),('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)]

        elif user.restrict_operation and allowed_access:
           args += [('picking_type_id','in',self.env.user.operation_ids.ids)]
        elif user.restrict_location and allowed_access:
            args += [('location_id','in',self.env.user.location_ids.ids)]
        elif user.restrict_warehouse_list and allowed_access:
            args += [('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)]

        return super(InheritStockPicking, self.sudo().with_context(context))._name_search(name=name, args=args, operator=operator, limit=limit, name_get_uid=name_get_uid)



class InheritStockLocation(models.Model):
    _inherit="stock.location"

    def search(self, args, **kwargs):
        allowed_access = self.env.user.has_group('bi_warehouse_restrictions.group_restrict_operations')
        current_uid = self._context.get('uid')
        user = self.env['res.users'].browse(current_uid)

        final_location_ids = user.location_ids
        if user.restrict_location and allowed_access:
            args = [('id','in',final_location_ids.ids)]

        return super(InheritStockLocation, self).search(args, **kwargs)


    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        allowed_access = self.env.user.has_group('bi_warehouse_restrictions.group_restrict_operations')
        current_uid = self._context.get('uid')
        user = self.env['res.users'].browse(current_uid)
        final_location_ids = user.location_ids

        if user.restrict_location and allowed_access:
            args = [('id','in',final_location_ids.ids)]

        return super(InheritStockLocation, self)._name_search(name=name, args=args, operator=operator, limit=limit, name_get_uid=name_get_uid)

class InheritStockWarehouse(models.Model):
    _inherit="stock.warehouse"

    def search(self, args, **kwargs):
        allowed_access = self.env.user.has_group('bi_warehouse_restrictions.group_restrict_operations')
        current_uid = self._context.get('uid')
        user = self.env['res.users'].browse(current_uid)
        final_warehouse_ids = user.warehouse_ids

        if user.restrict_warehouse_list and allowed_access:
            args = [('id','in',final_warehouse_ids.ids)]

        return super(InheritStockWarehouse, self).search(args, **kwargs)

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        allowed_access = self.env.user.has_group('bi_warehouse_restrictions.group_restrict_operations')
        current_uid = self._context.get('uid')
        user = self.env['res.users'].browse(current_uid)
        final_warehouse_ids = user.warehouse_ids

        if user.restrict_warehouse_list and allowed_access:
            args = [('id','in',final_warehouse_ids.ids)]

        return super(InheritStockWarehouse, self)._name_search(name=name, args=args, operator=operator, limit=limit, name_get_uid=name_get_uid)

