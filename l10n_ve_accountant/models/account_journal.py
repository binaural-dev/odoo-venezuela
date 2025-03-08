from odoo.exceptions import UserError
from odoo import api, models, _

class AccountJournal(models.Model):
    _inherit = "account.journal"

    @api.model
    def create(self, vals):
        for record in self:
            record._validate_user_group(vals)
        return super().create(vals)
    
    def write(self, vals):
        for record in self:
            if "type" in vals:
                record._validate_user_group(vals)
        return super().write(vals)
    
    def _validate_user_group(self,vals):
        user = self.env.user
        is_support_user = user.has_group('l10n_ve_accountant.group_support_user')

        if not is_support_user:

            if not (vals['type'] in ['bank','general','cash']):
                raise UserError(_(f"You do not have permissions to create/update a journal with this type."))
            return

        return
