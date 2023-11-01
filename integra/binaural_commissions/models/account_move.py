from odoo import api, fields, models, _


class AccountMove(models.Model):
    _inherit = "account.move"

    commission_invoice = fields.Many2one(
        "account.move",
        string="Invoice Commission",
    )
    collection_days = fields.Integer(compute="_compute_collection_days", store=True)
    total_commission = fields.Float(compute="_compute_total_commission_of_invoice", store=True)
    # discount_invoice = fields.Many2many(
    #     "account.move", "reversal_move_id", "move_id", compute="_compute_discount_invoice"
    # )
    commission_payment_state = fields.Selection(
        [("not_paid", "not paid"), ("process", "in process"), ("paid", "paid")],
        # compute="_compute_paid_seller",
        store=True,
        help="Payment State (Commission Invoice)",
    )

    commission_discount = fields.Float(
        # compute="_compute_discount_invoice",
        store=True,
        help="Discount of corrective payments",
    )

    def show_invoice_resume(self):
        return True
