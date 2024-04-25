# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class ShopifyPayoutReportLineEpt(models.Model):
    _name = "shopify.payout.report.line.ept"
    _description = "Shopify Payout Report Line"
    _rec_name = "transaction_id"

    payout_id = fields.Many2one('shopify.payout.report.ept', string="Payout ID", ondelete="cascade")
    transaction_id = fields.Char(string="Transaction ID", help="The unique identifier of the transaction.")
    source_order_id = fields.Char(string="Order Reference ID", help="The id of the Order that this transaction  "
                                                                    "ultimately originated from")
    transaction_type = fields.Selection(
        [('charge', 'Charge'), ('refund', 'Refund'), ('dispute', 'Dispute'),
         ('reserve', 'Reserve'), ('adjustment', 'Adjustment'), ('credit', 'Credit'),
         ('debit', 'Debit'), ('payout', 'Payout'), ('payout_failure', 'Payout Failure'),
         ('payout_cancellation', 'Payout Cancellation'), ('fees', 'Fees'), ('payment_refund', 'Payment Refund')],
        help="The type of the balance transaction", string="Balance Transaction Type")
    currency_id = fields.Many2one('res.currency', string='Currency', help="currency code of the payout.")
    source_type = fields.Selection(
        [('charge', 'Charge'), ('refund', 'Refund'), ('dispute', 'Dispute'),
         ('reserve', 'Reserve'), ('adjustment', 'Adjustment'), ('payout', 'Payout'), ],
        help="The type of the balance transaction", string="Resource Leading Transaction")
    amount = fields.Float(string="Amount", help="The gross amount of the transaction.")
    fee = fields.Float(string="Fees", help="The total amount of fees deducted from the transaction amount.")
    net_amount = fields.Float(string="Net Amount", help="The net amount of the transaction.")
    order_id = fields.Many2one('sale.order', string="Order Reference")
    is_processed = fields.Boolean("Processed?")
    is_remaining_statement = fields.Boolean(string="Is Remaining Statement?")
