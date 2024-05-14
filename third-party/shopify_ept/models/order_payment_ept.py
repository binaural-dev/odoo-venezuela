# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ShopifyOrderPayment(models.Model):
    _name = 'shopify.order.payment.ept'
    _description = "Shopify Order Payment"

    order_id = fields.Many2one("sale.order", string="Sale Order", copy=False)
    workflow_id = fields.Many2one("sale.workflow.process.ept", string="Auto Sales Workflow", copy=False)
    payment_gateway_id = fields.Many2one("shopify.payment.gateway.ept", string="Payment Gateway", copy=False)
    amount = fields.Float()
    remaining_refund_amount = fields.Float(help="Remaining refund amount in Shopify Store.")
    payment_transaction_id = fields.Char(help="It is used for a refund.")
    is_fully_refunded = fields.Boolean(help="It is to identify that it is fully refunded in the Shopify store.",
                                       default=False)
    refund_amount = fields.Float(help="How much do you want to refund in the store")
    is_want_to_refund = fields.Boolean(
        help="If mark: It will refund the amount in store which you choice. "
             "If unmarked: It will not refund the amount in store which you choice",
        default=False)

    @api.onchange('refund_amount')
    def _onchange_refund_amount(self):
        """
        This method is used to check the refund amount validation.
        @author: Meera Sidapara @Emipro Technologies Pvt. Ltd on date 26 November 2021 .
        Task_id: 179257
        """
        if self.refund_amount > self.remaining_refund_amount:
            raise UserError(_('The Refund Amount should be less than of Remaining Refund Amount.'))

    @api.onchange('is_want_to_refund')
    def _onchange_is_want_to_refund(self):
        """
        This method is used to check if the refund amount zero then raise the warring message.
        @author: Meera Sidapara @Emipro Technologies Pvt. Ltd on date 26 November 2021 .
        Task_id: 179257
        """
        if self.refund_amount == 0.0:
            raise UserError(_('The Refund Amount should be greater than 0.0'))
