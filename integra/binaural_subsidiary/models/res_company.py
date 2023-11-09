from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    subsidiary = fields.Boolean(
        string="Subsidiary",
        readonly=False,
    )

    analytical_accounts_subsidiary = fields.Boolean(
        string="Use Analytical Accounts as Subsidiary",
        readonly=False,
    )

    analytical_accounts_cost_subsidiary = fields.Boolean(
        string="Using Analytical Accounts as Cost Center and Subsidiary", 
        readonly=False,
    )
    
