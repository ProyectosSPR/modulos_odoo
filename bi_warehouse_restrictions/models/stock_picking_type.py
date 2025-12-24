# -*- coding: utf-8 -*-
# Part of Browseinfo. See LICENSE file for full copyright and licensing details.


from odoo import api, fields, models
import time
from datetime import date
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, format_datetime


class InheritStockPickingType(models.Model):
    _inherit="stock.picking.type"

    def search(self, args, **kwargs):
        allowed_access = self.env.user.has_group('bi_warehouse_restrictions.group_restrict_operations')
        current_uid = self._context.get('uid')
        user = self.env['res.users'].browse(current_uid)
        final_opertaion_ids = user.operation_ids
        final_warehouse_ids = user.warehouse_ids

        if user.restrict_operation and user.restrict_warehouse_list and allowed_access:
            args = ['|', ('id', 'in', final_opertaion_ids.ids), ('warehouse_id', 'in', final_warehouse_ids.ids)]
        elif user.restrict_operation and allowed_access:
            args = [('id', 'in', final_opertaion_ids.ids), ]
        elif user.restrict_warehouse_list and allowed_access:
            args = [('warehouse_id', 'in', final_warehouse_ids.ids)]
        return super(InheritStockPickingType, self).search(args, **kwargs)

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        allowed_access = self.env.user.has_group('bi_warehouse_restrictions.group_restrict_operations')
        current_uid = self._context.get('uid')
        user = self.env['res.users'].browse(current_uid)
        final_opertaion_ids = user.operation_ids
        final_warehouse_ids = user.warehouse_ids

        if user.restrict_operation and user.restrict_warehouse_list and allowed_access :
            args = ['|',('id','in',final_opertaion_ids.ids),('warehouse_id','in',final_warehouse_ids.ids)]
        elif user.restrict_operation and allowed_access:
            args = [('id','in',final_opertaion_ids.ids),]
        elif user.restrict_warehouse_list and allowed_access:
           args = [('warehouse_id','in',final_warehouse_ids.ids)]

        return super(InheritStockPickingType, self)._name_search(name=name, args=args, operator=operator, limit=limit, name_get_uid=name_get_uid)


    def _compute_picking_count(self):
        allowed_access = self.env.user.has_group('bi_warehouse_restrictions.group_restrict_operations')
        current_uid = self._context.get('uid')
        user = self.env['res.users'].browse(current_uid)
        if user.restrict_operation and user.restrict_location and user.restrict_warehouse_list and allowed_access:
            domains = {
                'count_picking_draft': [('state', '=', 'draft'),'|','|',
                    ('picking_type_id','in',self.env.user.operation_ids.ids),
                    ('location_id','in',self.env.user.location_ids.ids),
                    ('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)],
                'count_picking_waiting': [('state', 'in', ('confirmed', 'waiting')),'|','|',
                    ('picking_type_id','in',self.env.user.operation_ids.ids),
                    ('location_id','in',self.env.user.location_ids.ids),
                    ('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)],
                'count_picking_ready': [('state', '=', 'assigned'),'|','|',
                    ('picking_type_id','in',self.env.user.operation_ids.ids),
                    ('location_id','in',self.env.user.location_ids.ids),
                    ('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)],
                'count_picking': [('state', 'in', ('assigned', 'waiting', 'confirmed')),'|','|',
                    ('picking_type_id','in',self.env.user.operation_ids.ids),
                    ('location_id','in',self.env.user.location_ids.ids),
                    ('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)],
                'count_picking_late': [('scheduled_date', '<', time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)), ('state', 'in', ('assigned', 'waiting', 'confirmed')),'|','|',
                    ('picking_type_id','in',self.env.user.operation_ids.ids),
                    ('location_id','in',self.env.user.location_ids.ids),
                    ('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)],
                'count_picking_backorders': [('backorder_id', '!=', False), ('state', 'in', ('confirmed', 'assigned', 'waiting')),'|','|',
                    ('picking_type_id','in',self.env.user.operation_ids.ids),
                    ('location_id','in',self.env.user.location_ids.ids),
                    ('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)],
            }


        elif  user.restrict_operation and user.restrict_location and allowed_access :
            domains = {
                'count_picking_draft': [('state', '=', 'draft'),'|',('picking_type_id','in',self.env.user.operation_ids.ids),('location_id','in',self.env.user.location_ids.ids)],
                'count_picking_waiting': [('state', 'in', ('confirmed', 'waiting')),'|',('picking_type_id','in',self.env.user.operation_ids.ids),('location_id','in',self.env.user.location_ids.ids)],
                'count_picking_ready': [('state', '=', 'assigned'),'|',('picking_type_id','in',self.env.user.operation_ids.ids),('location_id','in',self.env.user.location_ids.ids)],
                'count_picking': [('state', 'in', ('assigned', 'waiting', 'confirmed')),'|',('picking_type_id','in',self.env.user.operation_ids.ids),('location_id','in',self.env.user.location_ids.ids)],
                'count_picking_late': [('scheduled_date', '<', time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)), ('state', 'in', ('assigned', 'waiting', 'confirmed')),'|',('picking_type_id','in',self.env.user.operation_ids.ids),('location_id','in',self.env.user.location_ids.ids)],
                'count_picking_backorders': [('backorder_id', '!=', False), ('state', 'in', ('confirmed', 'assigned', 'waiting')),'|',('picking_type_id','in',self.env.user.operation_ids.ids),('location_id','in',self.env.user.location_ids.ids)],
            }
        elif  user.restrict_operation and user.restrict_warehouse_list and allowed_access :
            domains = {
                'count_picking_draft': [('state', '=', 'draft'),'|',('picking_type_id','in',self.env.user.operation_ids.ids),('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)],
                'count_picking_waiting': [('state', 'in', ('confirmed', 'waiting')),'|',('picking_type_id','in',self.env.user.operation_ids.ids),('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)],
                'count_picking_ready': [('state', '=', 'assigned'),'|',('picking_type_id','in',self.env.user.operation_ids.ids),('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)],
                'count_picking': [('state', 'in', ('assigned', 'waiting', 'confirmed')),'|',('picking_type_id','in',self.env.user.operation_ids.ids),('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)],
                'count_picking_late': [('scheduled_date', '<', time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)), ('state', 'in', ('assigned', 'waiting', 'confirmed')),'|',('picking_type_id','in',self.env.user.operation_ids.ids),('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)],
                'count_picking_backorders': [('backorder_id', '!=', False), ('state', 'in', ('confirmed', 'assigned', 'waiting')),'|',('picking_type_id','in',self.env.user.operation_ids.ids),('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)],
            }
        elif  user.restrict_location and user.restrict_warehouse_list and allowed_access :
            domains = {
                'count_picking_draft': [('state', '=', 'draft'),'|',('location_id','in',self.env.user.location_ids.ids),('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)],
                'count_picking_waiting': [('state', 'in', ('confirmed', 'waiting')),'|',('location_id','in',self.env.user.location_ids.ids),('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)],
                'count_picking_ready': [('state', '=', 'assigned'),'|',('location_id','in',self.env.user.location_ids.ids),('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)],
                'count_picking': [('state', 'in', ('assigned', 'waiting', 'confirmed')),'|',('location_id','in',self.env.user.location_ids.ids),('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)],
                'count_picking_late': [('scheduled_date', '<', time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)), ('state', 'in', ('assigned', 'waiting', 'confirmed')),'|',('location_id','in',self.env.user.location_ids.ids),('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)],
                'count_picking_backorders': [('backorder_id', '!=', False), ('state', 'in', ('confirmed', 'assigned', 'waiting')),'|',('location_id','in',self.env.user.location_ids.ids),('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)],
            }


        elif user.restrict_location and allowed_access:
            domains = {
                'count_picking_draft': [('state', '=', 'draft'),('location_id','in',self.env.user.location_ids.ids)],
                'count_picking_waiting': [('state', 'in', ('confirmed', 'waiting')),('location_id','in',self.env.user.location_ids.ids)],
                'count_picking_ready': [('state', '=', 'assigned'),('location_id','in',self.env.user.location_ids.ids)],
                'count_picking': [('state', 'in', ('assigned', 'waiting', 'confirmed')),('location_id','in',self.env.user.location_ids.ids)],
                'count_picking_late': [('scheduled_date', '<', time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)), ('state', 'in', ('assigned', 'waiting', 'confirmed')),('location_id','in',self.env.user.location_ids.ids)],
                'count_picking_backorders': [('backorder_id', '!=', False), ('state', 'in', ('confirmed', 'assigned', 'waiting')),('location_id','in',self.env.user.location_ids.ids)],
            }
        elif user.restrict_operation and allowed_access:
            domains = {
                'count_picking_draft': [('state', '=', 'draft'),('picking_type_id','in',self.env.user.operation_ids.ids)],
                'count_picking_waiting': [('state', 'in', ('confirmed', 'waiting')),('picking_type_id','in',self.env.user.operation_ids.ids)],
                'count_picking_ready': [('state', '=', 'assigned'),('picking_type_id','in',self.env.user.operation_ids.ids)],
                'count_picking': [('state', 'in', ('assigned', 'waiting', 'confirmed')),('picking_type_id','in',self.env.user.operation_ids.ids)],
                'count_picking_late': [('scheduled_date', '<', time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)), ('state', 'in', ('assigned', 'waiting', 'confirmed')),('picking_type_id','in',self.env.user.operation_ids.ids)],
                'count_picking_backorders': [('backorder_id', '!=', False), ('state', 'in', ('confirmed', 'assigned', 'waiting')),('picking_type_id','in',self.env.user.operation_ids.ids)],
            }
        elif user.restrict_warehouse_list and allowed_access:
            domains = {
                'count_picking_draft': [('state', '=', 'draft'),('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)],
                'count_picking_waiting': [('state', 'in', ('confirmed', 'waiting')),('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)],
                'count_picking_ready': [('state', '=', 'assigned'),('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)],
                'count_picking': [('state', 'in', ('assigned', 'waiting', 'confirmed')),('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)],
                'count_picking_late': [('scheduled_date', '<', time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)), ('state', 'in', ('assigned', 'waiting', 'confirmed')),('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)],
                'count_picking_backorders': [('backorder_id', '!=', False), ('state', 'in', ('confirmed', 'assigned', 'waiting')),('picking_type_id.warehouse_id','in',self.env.user.warehouse_ids.ids)],
            }
        
        else:
            domains = {
                'count_picking_draft': [('state', '=', 'draft')],
                'count_picking_waiting': [('state', 'in', ('confirmed', 'waiting'))],
                'count_picking_ready': [('state', '=', 'assigned')],
                'count_picking': [('state', 'in', ('assigned', 'waiting', 'confirmed'))],
                'count_picking_late': [('scheduled_date', '<', time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)), ('state', 'in', ('assigned', 'waiting', 'confirmed'))],
                'count_picking_backorders': [('backorder_id', '!=', False), ('state', 'in', ('confirmed', 'assigned', 'waiting'))],
            }
        for field in domains:
            data = self.env['stock.picking'].read_group(domains[field] +
                [('state', 'not in', ('done', 'cancel')), ('picking_type_id', 'in', self.ids)],
                ['picking_type_id'], ['picking_type_id'])
            count = {
                x['picking_type_id'][0]: x['picking_type_id_count']
                for x in data if x['picking_type_id']
            }
            for record in self:
                record[field] = count.get(record.id, 0)
