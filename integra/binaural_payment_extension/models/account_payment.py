from odoo import models, fields, api, _

class AccountPayment(models.Model):
    _inherit = "account.payment"

    is_retention = fields.Boolean(
        string="Is retention",
        help="Check this box if this payment is a retention",
        default=False,
    )

    payment_type_retention = fields.Selection(
        [
            ("iva", "IVA"),
            ("islr", "ISLR"),
        ],
    )

    retention_line_ids = fields.One2many(
        "account.retention.line",
        "payment_id",
        string="Retention Lines",
        store=True,
    )

    invoice_line_ids = fields.Many2many(
        "account.move.line",
        domain="[('tax_ids', '!=', False)]",
        string="Invoice Lines",
        store=True,
    )

    retention_ref = fields.Char(
        string="Retention reference",
        store=True,
    )

    def compute_retention_amount_from_retention_lines(self):
        """
        Compute the amount from the retention lines.
        """
        for payment in self:
            payment.amount = sum(payment.retention_line_ids.mapped("retention_amount"))
