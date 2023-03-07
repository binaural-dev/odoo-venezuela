from odoo import api, models, fields, _


class TaxUnit(models.Model):
    _name = "tax.unit"
    _description = "Unidad Tributaria"

    name = fields.Char(string="Description", help="Tax Unit Description", required=True)
    value = fields.Float(help="Tax unit value", required=True)
    status = fields.Boolean(default=True, string="Active?")
