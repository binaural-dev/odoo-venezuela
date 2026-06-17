from odoo import api, models, fields, _
from odoo.exceptions import UserError

class TaxUnit(models.Model):
    _name = "tax.unit"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Tax Unit"

    name = fields.Char(string="Description", help="Tax Unit Description", required=True, store=True)
    value = fields.Float(help="Tax unit value", required=True, store=True)
    status = fields.Boolean(default=False, string="Active?", store=True)

   