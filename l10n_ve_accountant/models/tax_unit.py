from odoo import api, models, fields, _
from odoo.exceptions import UserError

class TaxUnit(models.Model):
    _name = "tax.unit"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Tax Unit"

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )
    
    name = fields.Char(string="Description", help="Tax Unit Description", required=True, store=True)
    value = fields.Float(help="Tax unit value", required=True, store=True, tracking=True)
    status = fields.Boolean(default=True, string="Active?", store=True, tracking=True)

   