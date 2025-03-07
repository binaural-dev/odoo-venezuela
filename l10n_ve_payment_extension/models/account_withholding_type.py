from odoo import models, fields, api, _


class TypeWithholding(models.Model):
    _name = "account.withholding.type"
    _description = "Type Withholding"
    _order = "create_date desc"
    _sql_constraints = [
        ("unique_name", "UNIQUE(name)", "You cannot add withholdings with the same name"),
        ("unique_value", "UNIQUE(value)", "You can not add withholdings with the same Value"),
    ]

    def case_upper(self, string,field_name):
        if string:
            result = {
                'value': {
                    field_name: str(string).strip().upper()
                }
            }
            return result

    name = fields.Char(store=True)
    value = fields.Float(store=True)
    state = fields.Boolean(default=True, string="Active", store=True)

    @api.onchange("name")
    def upper_name(self):
        return self.case_upper(self.name, "name")

    @api.onchange("value")
    def onchange_template_id(self):
        res = {}
        if self.value:
            res = {
                "warning": {
                    "title": (_("Warning")),
                    "message": (_("Remember to use comma (,) as decimal separator.")),
                }
            }

        if res:
            return res
