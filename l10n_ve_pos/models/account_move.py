from odoo import fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    is_pos_cross_move = fields.Boolean(copy=False, readonly=True)
    def button_draft(self):
        """
        Validate if the journal entry is linked to a POS session that is still opened
        """
        if self.env.company.pos_move_to_draft:
            return super().button_draft()

        pos_session_opened = self.env["pos.session"].search(
            [("state", "=", "opened"), ("company_id", "=", self.env.company.id)]
        )
        for pos_session in pos_session_opened:
            all_related_move_ids = pos_session._get_related_account_moves().ids
            for move in self:
                if move.id in all_related_move_ids:
                    raise UserError(
                        _("You cannot modify a journal entry linked to a POS session that is still opened")
                    )
        return super().button_draft()

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    pos_order_line_ids = fields.Many2many("pos.order.line")
