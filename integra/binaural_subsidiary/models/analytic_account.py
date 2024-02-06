from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountAnalitycAccount(models.Model):
    _inherit = "account.analytic.account"

    is_subsidiary = fields.Boolean(default=False)

    @api.constrains('company_id')
    def _check_company_consistency(self):
        super()._check_company_consistency()

        for record in self:
            if record.is_subsidiary and not record.company_id:
                raise UserError(_("This analytical account is used for subsidiaries. The company must be specified."))
