from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    currency_foreign_id = fields.Many2one(
        "res.currency",
        string="Currency Foreign",
        help="Currency Foreign for the company",
        related="company_id.currency_foreign_id",
        readonly=False,
    )

    @api.constrains("currency_foreign_id")
    def _check_currency_foreign_id(self):
        self = self.with_company(self.company_id)
        for rec in self:
            if rec.currency_id == rec.currency_foreign_id:
                raise UserError(
                    _("The currency foreign must be different from the currency of the company")
                )

    @api.onchange("currency_foreign_id")
    def currency_foreign_id_onchange_(self):
        self = self.with_company(self.company_id)
        for rec in self:
            if rec.currency_id == rec.currency_foreign_id:
                raise UserError(
                    _("The currency foreign must be different from the currency of the company")
                )

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        return res

    def set_values(self):
        res = super(ResConfigSettings, self).set_values()
        return res
