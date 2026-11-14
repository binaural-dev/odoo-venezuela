from odoo import models


class AccountAsset(models.Model):
    _inherit = "account.asset"

    def set_to_close(self, invoice_line_ids, date=None, message=None):
        self = self.with_context(disposal_message=message)
        return super(AccountAsset, self).set_to_close(invoice_line_ids, date=date, message=message)


class AccountAssetVariant(models.Model):
    _inherit = "account.asset.variant"

    def _get_disposal_moves(self, invoice_lines_list, disposal_date):
        """Write the disposal message on the moves of a donated asset.

        In Odoo 20 the disposal moves are created by the variant of the asset (R-42), which
        ``account.asset.set_to_close`` reaches through ``current_selected_variant_id``.
        """
        move_ids = super()._get_disposal_moves(invoice_lines_list, disposal_date)
        message = self.env.context.get("disposal_message")
        if message and move_ids:
            moves = self.env["account.move"].browse(move_ids)
            moves.write({"ref": message})
            moves.line_ids.write({"name": message})
        return move_ids
