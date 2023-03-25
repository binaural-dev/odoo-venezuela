from odoo import models, fields, api, Command, _

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
    retention_id = fields.Many2one("account.retention", ondelete="cascade")

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

    def unlink(self):
        for payment in self:
            if any(isinstance(id, models.NewId) for id in self.retention_line_ids.ids):
                payment.retention_line_ids = False
            else:
                payment.retention_line_ids = Command.clear()
        return super().unlink()

    def compute_retention_amount_from_retention_lines(self):
        """
        Compute the amount from the retention lines.
        """
        for payment in self:
            payment.amount = sum(payment.retention_line_ids.mapped("retention_amount"))

    def compute_retention_amount_from_retention_islr_lines(self):
        """
        Compute the amount from the retention lines.
        """
        base_currency_is_vef = self.env.company.currency_id == self.env.ref(
                "base.VEF"
            )
        for payment in self:
            if base_currency_is_vef:
                payment.amount = sum(payment.retention_line_ids.mapped("retention_amount"))
            else:
                payment.amount = sum(payment.retention_line_ids.mapped("foreign_retention_amount"))

