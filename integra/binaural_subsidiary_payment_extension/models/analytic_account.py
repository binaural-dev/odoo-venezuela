from odoo import api, fields, models


class AccountAnalyticAccount(models.Model):
    _inherit = "account.analytic.account"

    tax_authorities_logo = fields.Image(max_width=128, max_height=128)
    tax_authorities_name = fields.Char()
    economic_activity_number = fields.Char()
    municipality_id = fields.Many2one("res.country.municipality")
    municipal_supplier_retentions_sequence_id = fields.Many2one(
        "ir.sequence", string="Municipal supplier retentions sequence"
    )
    use_subsidiary_with_multiple_municipalities = fields.Boolean(
        related="company_id.use_subsidiary_with_multiple_municipalities"
    )
