from odoo import api, fields, models


class IrRule(models.Model):
    _inherit = "ir.rule"

    @api.model
    def _eval_context(self):
        eval_context = super()._eval_context()
        eval_context["subsidiary_ids"] = self.env.user.subsidiary_ids.ids
        return eval_context
