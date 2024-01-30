from odoo import api, fields, models, _

import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    commission_invoice = fields.Many2one(
        "account.move",
        string="Invoice Commission",
    )
    collection_days = fields.Integer(compute="_compute_collection_days")
    total_commission = fields.Float(compute="_compute_total_commission_of_invoice")
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

    commission_invoice_date_field = fields.Char(readonly=True, copy=False)
    compute_commission_when = fields.Char(readonly=True, copy=False)

    def show_invoice_resume(self):
        return True

    @api.depends("amount_residual")
    def _compute_total_commission_of_invoice(self):
        for record in self:
            total = 0
            for line in record.invoice_line_ids:
                if line.sale_line_ids.commission_policy_line_image_ids:
                    commission = line.sale_line_ids.get_amount_commission_policy_line_image(
                        self.collection_days
                    )
                    total += line.price_subtotal * (commission / 100)
            record.total_commission = total

    @api.depends("invoice_date_due", "invoice_date")
    def _compute_collection_days(self):
        for record in self:
            days = 0
            date_from = record._get_commission_date_from()
            date_to = record._get_commission_date_to()
            if date_from and date_to:
                days = (date_to - date_from).days
            record.collection_days = abs(days)

    def _get_commission_date_from(self):
        self.ensure_one()
        invoice_date_field = self.commission_invoice_date_field
        return self[invoice_date_field]

    def _get_commission_date_to(self):
        self.ensure_one()
        payment_type = self.compute_commission_when
        if payment_type == "invoice_is_fully_paid":
            return self.last_payment_date
        if payment_type == "invoice_first_payment":
            return self.first_payment_date

        return False
