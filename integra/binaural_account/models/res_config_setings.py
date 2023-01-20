from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    currency_foreign_id = fields.Many2one(
        "res.currency",
        string="Currency Foreign",
        help="Currency Foreign for the company",
        company_dependent=True,
    )

    @api.constrains("currency_foreign_id")
    def _check_currency_foreign_id(self):
        for rec in self:
            if rec.currency_id == rec.currency_foreign_id:
                raise UserError(
                    _("The currency foreign must be different from the currency of the company")
                )

    @api.onchange("currency_foreign_id")
    def currency_foreign_id_onchange_(self):
        for rec in self:
            if rec.currency_id == rec.currency_foreign_id:
                raise UserError(
                    _("The currency foreign must be different from the currency of the company")
                )
