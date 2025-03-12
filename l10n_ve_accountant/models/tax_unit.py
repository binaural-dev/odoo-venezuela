from odoo import api, models, fields, _


class TaxUnit(models.Model):
    _name = "tax.unit"
    _description = "Tax Unit"

    name = fields.Char(string="Description", help="Tax Unit Description", required=True, store=True)
    value = fields.Float(help="Tax unit value", required=True, store=True)
    status = fields.Boolean(default=True, string="Active?", store=True)
