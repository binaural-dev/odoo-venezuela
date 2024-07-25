from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    @api.ondelete(at_uninstall=False)
    def unlink_reconcile(self):
        if self.env.company.pos_unreconcile_moves:
            return True
        session_ids = self.env["pos.session"].search([("state", "=", "opened")])
        for record in self:
            invoice_ids = session_ids.order_ids.account_move
            for move in (record.debit_move_id + record.credit_move_id):
                if move.move_id in invoice_ids:
                    raise ValidationError(
                        _(
                            "You cannot reconcile a payment linked to a POS session that is still open"
                        )
                    )
