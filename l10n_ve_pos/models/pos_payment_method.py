from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    is_foreign_currency = fields.Boolean(default=False)

    cross_account_journal = fields.Many2one(
        "account.journal", domain=[("type", "=", "general")]
    )

    cross_journal = fields.Many2one(
        "account.journal", domain=[("type", "in", ("bank", "cash"))]
    )

    apply_one_cross_move = fields.Boolean(default=False)

    @api.constrains("apply_one_cross_move")
    def _check_apply_one_cross_move(self):
        for record in self:
            if record.split_transactions:
                raise ValidationError(
                    _(
                        "You cannot select 'Apply a single adjustment entry' if the 'Identify customer' option is enabled."
                    )
                )
