from odoo import fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    pos_cross_session_id = fields.Many2one(
        "pos.session",
        string="PoS Cross Session",
        readonly=True,
        copy=False,
        index="btree_not_null",
        help="PoS session whose cross move this is.",
    )
    pos_cross_payment_method_id = fields.Many2one(
        "pos.payment.method",
        string="PoS Cross Payment Method",
        readonly=True,
        copy=False,
        help="Payment method whose money this PoS cross move takes to the real journal.",
    )
    pos_cross_real_statement_line_ids = fields.One2many(
        "account.bank.statement.line",
        "pos_cross_real_move_id",
        string="PoS Cross Statement Lines",
        readonly=True,
    )

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        posted.filtered(
            lambda move: move.pos_cross_payment_method_id and move.pos_cross_session_id
        )._post_pos_cross()
        return posted

    def _post_pos_cross(self):
        """Lo que sigue a publicar un cruce del PdV, al crearlo (con
        ``pos_post_cross_moves``) o cuando contabilidad publica el borrador: su
        línea de extracto en el diario real, conciliada contra él
        (``pos.session._create_cross_real_statement_lines``). Un módulo que
        concilia otras líneas contra el cruce lo extiende."""
        for move in self:
            move.pos_cross_session_id.sudo()._create_cross_real_statement_lines(
                move.pos_cross_payment_method_id, move
            )

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
