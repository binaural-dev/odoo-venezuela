from odoo import models


class ValidateAccountMove(models.TransientModel):
    _inherit = "validate.account.move"

    def validate_move(self):
        # "Confirm them now" (`force_post`) posts through `_post`, which does not
        # run the date checks of `action_post`.
        self.move_ids._check_dates_not_in_future()
        return super().validate_move()
