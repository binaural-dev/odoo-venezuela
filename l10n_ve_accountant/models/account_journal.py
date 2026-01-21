from odoo.exceptions import UserError
from odoo import api, models, _, fields
import logging

_logger = logging.getLogger(__name__)


class AccountJournal(models.Model):
    _inherit = "account.journal"

    # ESTA HERENCIA NO SE IMPORTARÁ PORQUE ESTÁ GENERANDO ERROR, AL SOLUCIONAR, VOLVER A AGREGAR EN EN IMPORT

    @api.model_create_multi
    def create(self, vals_list):

        for vals in vals_list:
            self._validate_support_user_group(vals)

        return super().create(vals_list)

    is_purchase_international = fields.Boolean(string="International purchase",default=False)

    @api.constrains('is_purchase_international')
    def _check_single_international_purchase_journal(self):
        
        for record in self:
            if record.is_purchase_international:
                domain = [
                    ('is_purchase_international', '=', True),
                    ('id', '!=', record.id),
                ]
                
                if self.search_count(domain) > 0:
                    raise ValidationError(
                        _("An International Purchase Journal is already enabled. Only one is allowed.")
                    )


    def write(self, vals):
        for record in self:
            if "type" in vals:
                record._validate_support_user_group(vals)
        return super().write(vals)

    def _validate_support_user_group(self, vals):
        user = self.env.user
        is_support_user = user.has_group("l10n_ve_accountant.group_support_user")

        if not is_support_user:
            if vals["type"] not in ["bank", "general", "cash"]:

                raise UserError(
                    _(
                        f"You do not have permissions to create/update a journal with this type."
                    )
                )

        return
