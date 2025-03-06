from odoo import api, models, fields, _


class TypePerson(models.Model):
    _name = "type.person"
    _description = "Type Person"

    name = fields.Char(string="Description", required=True, store=True)
    state = fields.Boolean(default=True, string="Active?", store=True)
