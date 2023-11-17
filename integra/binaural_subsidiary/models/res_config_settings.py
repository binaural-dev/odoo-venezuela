from odoo import api, fields, models
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    subsidiary = fields.Boolean(
        related="company_id.subsidiary",
        string="Subsidiary",
        readonly=False,
    )

    analytical_accounts_subsidiary = fields.Boolean(
        related="company_id.analytical_accounts_subsidiary",
        string="Use Analytical Accounts as Subsidiary",
        readonly=False,
    )

    analytical_accounts_cost_subsidiary = fields.Boolean(
        related="company_id.analytical_accounts_cost_subsidiary",
        string="Using Analytical Accounts as Cost Center and Subsidiary",
        readonly=False,
    )
