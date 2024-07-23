from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class StockLocation(models.Model):
    _name = "stock.location"
    _inherit = ["stock.location", "mail.thread", "mail.activity.mixin"]

    priority = fields.Integer(string="Priority", default=10, tracking=True)

    @api.constrains("priority")
    def _check_priority(self):
        for location in self:
            if location.priority < 0:
                raise ValidationError(_("The priority must be greater than 0."))
