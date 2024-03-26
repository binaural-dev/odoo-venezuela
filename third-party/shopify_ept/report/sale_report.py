# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import fields, models
import odoo


class SaleReport(models.Model):
    _inherit = "sale.report"

    shopify_instance_id = fields.Many2one("shopify.instance.ept", "Shopify Instance", copy=False, readonly=True)

    # def _query(self, with_clause='', fields={}, groupby='', from_clause=''):
    #     """ Inherit the query here to add the shopify instance field for group by.
    #         @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 29 September 2020 .
    #         Task_id: 167120
    #     """
    #     fields['shopify_instance_id'] = ", s.shopify_instance_id as shopify_instance_id"
    #     groupby += ', s.shopify_instance_id'
    #     return super(SaleReport, self)._query(with_clause, fields, groupby, from_clause)

    def _select_additional_fields(self):
        res = super()._select_additional_fields()
        res['shopify_instance_id'] = "s.shopify_instance_id"
        return res

    def _group_by_sale(self):
        res = super()._group_by_sale()
        res += """,
            s.shopify_instance_id"""
        return res

    def shopify_sale_report(self):
        """ Base on the odoo version it return the action.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 29 September 2020 .
            Task_id: 167120
        """
        version_info = odoo.service.common.exp_version()
        if version_info.get('server_version') == '16.0':
            action = self.env.ref('shopify_ept.shopify_action_order_report_all').sudo().read()[0]
        else:
            action = self.env.ref('shopify_ept.shopify_sale_report_action_dashboard').sudo().read()[0]

        return action
