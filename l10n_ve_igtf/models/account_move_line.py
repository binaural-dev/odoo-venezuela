from odoo import fields, models


class AccountMoveLineIgtf(models.Model):
    _inherit = "account.move.line"

    is_igtf_residual = fields.Boolean(
        string="IGTF Residual",
        help="Receivable of the customer for the IGTF of a payment in foreign currency. "
        "It is left open to be paid apart from the invoices.",
        copy=False,
    )

    def reconcile(self):
        # The IGTF charged to the customer is paid apart: it is never matched together with the
        # lines of its own payment (the receivable paid to the invoices), as when the payment
        # is reconciled with the invoices it pays.
        own_payment_moves = (self - self.filtered("is_igtf_residual")).move_id
        lines = self.filtered(lambda l: not (l.is_igtf_residual and l.move_id in own_payment_moves))
        return super(AccountMoveLineIgtf, lines).reconcile()
