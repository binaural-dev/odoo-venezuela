from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = "res.partner"

    withholding_type_id = fields.Many2one("account.withholding.type", string="Withholding Type")
