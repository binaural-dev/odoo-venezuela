from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    is_igtf = fields.Boolean(related="module_binaural_igtf")
    customer_account_igtf_id = fields.Many2one("account.account", domain=[("account_type", "=", "liability_current")])
    supplier_account_igtf_id = fields.Many2one("account.account", domain=[("account_type", "=", "expense")])
    igtf_percentage = fields.Float(string="IGTF Percentage", default=3.00)
    taxpayer_type = fields.Selection(
        [
            ("formal", "Formal"),
            ("special", "Special"),
            ("ordinary", "Ordinary"),
        ],
        default="ordinary",
        store=True,
    )