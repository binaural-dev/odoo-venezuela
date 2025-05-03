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

    group_analytic_accounting_related = fields.Boolean(
        related='group_analytic_accounting',
        config_parameter="l10n_ve_subsidiary.group_analytic_accounting_related",
    )
