from odoo import api, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.model
    def check_account_type(self, account_type: str) -> bool:
        """Evaluates which type is the account on the move
        line.

        Parameters
        ----------
        account_type : str
            The type of the account

        Returns
        -------
        bool
            True if the given parameter matches, False otherwise.
        """

        self.ensure_one()
        return self.account_id.account_type == account_type
