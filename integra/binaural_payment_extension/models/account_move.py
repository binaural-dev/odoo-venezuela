from odoo import models, fields, api, _

class AccountMoveRetention(models.Model):

    _inherit = "account.move"

    def action_register_payment(self):
        """
        Override the action_register_payment method to add the invoice lines to the payment register.
        """
        res = super().action_register_payment()
        if self.move_type in ["out_invoice", "out_refund"]:
            res["context"]["default_invoice_line_ids"] = self.invoice_line_ids.ids
            res["context"]["default_retention_type"] = self.move_type
        return res
