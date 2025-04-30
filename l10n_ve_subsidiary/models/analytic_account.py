from odoo import _, api, fields, models
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)

class AccountAnalitycAccount(models.Model):
    _inherit = "account.analytic.account"

    is_subsidiary = fields.Boolean(default=False)

    @api.constrains('company_id')
    def _check_company_consistency(self):
        super()._check_company_consistency()

        for record in self:
            if record.is_subsidiary and not record.company_id:
                raise UserError(_("This analytical account is used for subsidiaries. The company must be specified."))

    def _on_create_assign_subsidiary_to_base_admin(self, res_ids):
        base_admin_user = self.env.ref('base.user_admin')

        for record in res_ids:
            if not record.is_subsidiary:
                continue

            base_admin_user.write({'subsidiary_ids': [(4, record.id)]})

    def _on_unlink_remove_subsidiary_to_base_admin(self):
        self.ensure_one()

        base_admin_user = self.env.ref('base.user_admin')
        base_admin_user.write({'subsidiary_ids': [(3, self.id)]})

    @api.model_create_multi
    def create(self, vals_list):
        res_ids = super().create(vals_list)

        self._on_create_assign_subsidiary_to_base_admin(res_ids)

        return res_ids

    def unlink(self):
        for record in self:
            record._on_unlink_remove_subsidiary_to_base_admin()
        super().unlink()