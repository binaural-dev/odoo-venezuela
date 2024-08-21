from odoo import api, fields, models, _
from odoo.exceptions import UserError

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

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
            if "currency_id" in rec._fields and rec.currency_id == rec.currency_foreign_id:
                raise UserError(
                    _("The currency foreign must be different from the currency of the company")
                )

    @api.onchange("currency_foreign_id")
    def currency_foreign_id_onchange_(self):
        self = self.with_company(self.company_id)
        for rec in self:
            if "currency_id" in rec._fields and rec.currency_id == rec.currency_foreign_id:
                raise UserError(
                    _("The currency foreign must be different from the currency of the company")
                )
