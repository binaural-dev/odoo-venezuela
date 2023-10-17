from odoo import fields, models, api, _
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    bi_igtf = fields.Monetary(string="BI IGTF", help="subtotal with igtf", store=True, copy=False)
    is_two_percentage = fields.Boolean(string="Is two percentage", default=False, store=True, copy=False)
    amount_paid = fields.Monetary(string="Paid", default=0.00, help="Paid", store=True, copy=False)
    amount_to_pay_igtf = fields.Monetary(
        string="IGTF Paid",
        default=0.00,
        help="IGTF Paid",
        compute="_compute_amount_to_pay_igtf",
        store=True,
        copy=False,
    )

    amount_residual_igtf = fields.Monetary(
        string="IGTF Residual",
        default=0.00,
        help="IGTF Residual",
        compute="_compute_amount_residual_igtf",
        copy=False,
    )

    @api.depends("tax_totals")
    def _compute_amount_to_pay_igtf(self):
        """
        Compute the amount to pay of the IGTF
        """
        for move in self:
            move.amount_to_pay_igtf = 0
            if move.invoice_line_ids and move.is_invoice(include_receipts=True) and move.tax_totals:
                move.amount_to_pay_igtf = move.tax_totals["igtf"]["igtf_amount"] - move.amount_paid

    @api.depends(
        "amount_total", "amount_residual", "amount_residual_igtf", "amount_to_pay_igtf", "bi_igtf"
    )
    def _compute_amount_residual_igtf(self):
        for record in self:
            record.amount_residual_igtf = record.amount_residual + record.amount_to_pay_igtf

    @api.depends(
        "bi_igtf",
    )
    def _compute_tax_totals(self):
        return super()._compute_tax_totals()

    def button_draft(self):
        """
        When the user click on the button draft, we need to delete the igtf
        """
        for record in self:
            record.bi_igtf = 0
            record.is_two_percentage = False
        return super().button_draft()
