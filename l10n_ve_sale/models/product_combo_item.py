from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductComboItem(models.Model):
    _inherit = 'product.combo.item'

    item_type = fields.Selection(
        selection=[
            ('principal', 'Principal'),
            ('percentage', 'Percentage'),
            ('fixed_price', 'Fixed Price'),
        ],
        string="Item Type",
        required=True,
        default="principal",
    )

    percentage = fields.Float(
        string="Percentage (%)",
        digits=(16, 2),
        default=0.0,
    )

    @api.constrains('item_type', 'percentage')
    def _check_percentage_value(self):
        for item in self:
            if item.item_type == 'percentage' and (item.percentage < 0 or item.percentage > 100):
                raise ValidationError(_("The percentage for the item must be between 0 and 100."))
