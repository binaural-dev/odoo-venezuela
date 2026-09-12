from odoo import api, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.constrains("product_id", "price_unit", "quantity", "discount")
    def _check_refund_line_against_origin(self):
        """A write() on the line itself does not trigger the parent
        account.move constrains on invoice_line_ids, so the same check
        (see account.move._check_refund_against_origin) is repeated here.
        """
        moves = self.mapped("move_id").filtered(
            lambda m: m.move_type in ("out_refund", "in_refund") and m.reversed_entry_id
        )
        if moves:
            moves._check_refund_against_origin()
