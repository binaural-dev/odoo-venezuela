# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    warehouse_id_ept = fields.Many2one('stock.warehouse')

    def _prepare_procurement_values(self, group_id=False):
        """
        This method sets a warehouse based on the sale order line warehouse.
        So it will create Delivery orders based on order line level sets warehouse-wise.
        """
        values = super(SaleOrderLine, self)._prepare_procurement_values(group_id)
        if self.warehouse_id_ept:
            values['warehouse_id'] = self.warehouse_id_ept
        return values
