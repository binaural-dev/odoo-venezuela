from odoo import models, fields, api, _


class AccountAssetDonation(models.Model):
    _inherit = "account.asset"

    def set_to_close(self, invoice_line_ids, date=None, message=None):
        """Override to pass the disposal message via context so _get_disposal_moves
        can use it as the ref of the account.move when it's a donation disposal."""
        self = self.with_context(donation_disposal_message=message)
        return super().set_to_close(
            invoice_line_ids=invoice_line_ids, date=date, message=message
        )

    def _get_disposal_moves(self, invoice_lines_list, disposal_date):
        """Override to use the disposal reason from the wizard as the ref
        of the account.move when the asset is being disposed as a donation."""
        move_ids = super()._get_disposal_moves(invoice_lines_list, disposal_date)

        disposal_message = self.env.context.get("donation_disposal_message")
        if disposal_message and move_ids:
            moves = self.env["account.move"].browse(move_ids)
            moves.filtered(lambda m: m.state == "draft").write(
                {"ref": disposal_message}
            )

        return move_ids
