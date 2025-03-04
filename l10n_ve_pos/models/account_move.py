from odoo import fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    def button_draft(self):
        """
        Validate if the journal entry is linked to a POS session that is still opened
        """
        pos_session_opened = self.env["pos.session"].search(
            [("state", "=", "opened"), ("company_id", "=", self.env.company.id)]
        )
        for pos_session in pos_session_opened:
            all_related_moves = pos_session._get_related_account_moves()
            if (
                self.id in all_related_moves.mapped(lambda x: x.id)
                and not self.env.company.pos_move_to_draft
            ):
                raise UserError(
                    _("You cannot modify a journal entry linked to a POS session that is still opened")
                )
        return super().button_draft()

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    pos_order_line_ids = fields.Many2many("pos.order.line")
