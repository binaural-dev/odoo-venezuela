from odoo import api, fields, models, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    module_subsidiary = fields.Boolean(
        string="Subsidiary",
        readonly=False,
    )

    module_analytical_accounts_subsidiary = fields.Boolean(
        string="Use Analytical Accounts as Subsidiary",
        readonly=False,
    )

    module_analytical_accounts_cost_subsidiary = fields.Boolean(
        related="Using Analytical Accounts as Cost Center and Subsidiary", 
        readonly=False
    )