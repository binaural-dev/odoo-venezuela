

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import config


class AccountMove(models.Model):
    _inherit = "account.move"

    def fields_get(self, allfields=None, attributes=None):
        res = super().fields_get(allfields=allfields, attributes=attributes)
        for record in self:
            editable = record.can_edit_pricelist  # O tu lógica de grupo
            if 'pricelist_id' in res:
                res['pricelist_id']['readonly'] = not editable
        return res

    can_edit_pricelist = fields.Boolean(
        string="Puede editar lista de precios",
        compute="_compute_can_edit_pricelist",
    )
    
    def _compute_can_edit_pricelist(self):
        for move in self:
            move.can_edit_pricelist = self.env.user.has_group("l10n_ve_price_list.group_pricelist_change_permission")
