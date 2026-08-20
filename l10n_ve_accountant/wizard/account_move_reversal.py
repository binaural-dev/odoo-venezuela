from odoo import models


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    def _prepare_default_reversal(self, move):
        values = super()._prepare_default_reversal(move)
        if move.move_type == "out_invoice":
            values.pop("invoice_date", None)
            values["invoice_date_display"] = self.date
        return values
