from odoo import fields, models

class AccountFiscalyearClosingAbstract(models.AbstractModel):
    _inherit = "account.fiscalyear.closing.abstract"

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company.id)
