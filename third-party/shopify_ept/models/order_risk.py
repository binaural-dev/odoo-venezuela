# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ShopifyOrderRisk(models.Model):
    _name = "shopify.order.risk"
    _description = 'Shopify Order Risk'

    name = fields.Char("Order Id", required=True)
    risk_id = fields.Char()
    cause_cancel = fields.Boolean(default=False)
    display = fields.Boolean(default=False)
    message = fields.Text()
    recommendation = fields.Selection([('cancel', 'This order should be cancelled by the merchant'),
                                       ('investigate',
                                        'This order might be fraudulent and needs further investigation'),
                                       ('accept', 'This check found no indication of fraud')
                                       ], default='accept')
    score = fields.Float()
    source = fields.Char()
    odoo_order_id = fields.Many2one("sale.order", string="Order")

    def shopify_create_risk_in_order(self, risk_result, order):
        """This method used to create a risk, if found risk in Shopify order when import orders from Shopify to Odoo.
            :param risk_result: Response of risk API call.
            :param order: Record of sale order.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 11/11/2019.
            Task Id : 157350
        """
        flag = True
        for risk_id in risk_result:
            risk = risk_id.to_dict()
            if risk.get('recommendation') != 'accept':
                flag = False
            vals = self.prepare_vals_for_risk_order(risk, order)
            self.create(vals)
        return flag

    def prepare_vals_for_risk_order(self, risk, order):
        """ This method is used to prepare a vals for the create record of risk order.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 16 October 2020 .
        """
        vals = {'name': risk.get('order_id'), 'risk_id': risk.get('id'),
                'cause_cancel': risk.get('cause_cancel'),
                'display': risk.get('display'),
                'message': risk.get('message'),
                'recommendation': risk.get('recommendation'),
                'score': risk.get('score'),
                'source': risk.get('source'),
                'odoo_order_id': order.id
                }
        return vals
