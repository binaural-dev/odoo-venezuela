# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
import logging
from odoo import models, fields

_logger = logging.getLogger("Shopify Order")


class StockMove(models.Model):
    """Inherit model to set the instance and is shopify delivery order flag"""
    _inherit = "stock.move"

    shopify_fulfillment_order_id = fields.Char("Fulfillment Order ID")
    shopify_fulfillment_line_id = fields.Char("Fulfillment Line ID")
    shopify_fulfillment_order_status = fields.Char("Fulfillment Order Status")

    def _get_new_picking_values(self):
        """We need this method to set Shopify Instance in Stock Picking"""
        res = super(StockMove, self)._get_new_picking_values()
        order_id = self.sale_line_id.order_id
        if order_id.shopify_order_id:
            res.update({'shopify_instance_id': order_id.shopify_instance_id.id, 'is_shopify_delivery_order': True})
        return res

    def _action_assign(self, force_qty=False):
        # We inherited the base method here to set the instance values in picking while the picking type is dropship.
        res = super(StockMove, self)._action_assign(force_qty)

        for picking in self.picking_id:
            sale_id = picking.sudo().sale_id
            if not picking.shopify_instance_id and sale_id and sale_id.shopify_instance_id:
                picking.write(
                    {'shopify_instance_id': sale_id.shopify_instance_id.id, 'is_shopify_delivery_order': True})
        return res

    def auto_process_stock_move(self):
        """
        This method is used to check if lot/serial product are available in stock move.
        if stock is received then assign and done that stock moves
        @author: Yagnik joshi @Emipro Technologies Pvt. Ltd on date 30 November 2023 .
        """
        move_ids = self.prepre_query_to_get_stock_move_ept()
        moves = self.browse(move_ids)
        for move in moves:
            try:
                move.move_line_ids.unlink()
                move._action_assign()
                move._set_quantity_done(move.product_uom_qty)
                move._action_done()
            except Exception as error:
                message = "Receive error while assign stock to stock move(%s) of shipped order, Error is:  (%s)" % (
                    move, error)
                _logger.info(message)
        return True

    def prepre_query_to_get_stock_move_ept(self):
        """
        This method is used to prepare a query to get stock move
        @author: Yagnik Joshi @Emipro Technologies Pvt. Ltd on date 30 November 2023 .
        """
        sm_query = """
                            SELECT
                                sm.id as move_id,
                                so.id as so_id
                            FROM 
                                stock_move  as sm
                            INNER JOIN
                                sale_order_line as sol on sol.id = sm.sale_line_id 
                            INNER JOIN
                                sale_order as so on so.id = sol.order_id
                            INNER JOIN
                                product_product as pp on pp.id = sm.product_id
                            INNER JOIN
                                product_template as pt on pt.id = pp.product_tmpl_id
                            WHERE
                                picking_id is null AND
                                sale_line_id is not null AND
                                so.shopify_order_id is not null AND
                                sm.state in ('confirmed','partially_available','assigned')                       
                            limit 100
                           """
        self._cr.execute(sm_query)
        result = self._cr.dictfetchall()
        move_ids = [data.get('move_id') for data in result]
        return move_ids
