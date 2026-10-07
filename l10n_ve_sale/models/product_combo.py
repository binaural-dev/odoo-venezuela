from odoo import api, fields, models


class ProductCombo(models.Model):
    _inherit = 'product.combo'

    price_distribution = fields.Selection(
        selection=[
            ('native', 'Price Proration'),
            ('by_item_type', 'Price Distribution'),
        ],
        string="Price Calculation",
        required=True,
        default='native',
        help=(
            "Price Proration: the share of the combo price for this option is "
            "the one Odoo calculates (prorated by base price) and it is split "
            "equally among the chosen items.\n"
            "Price Distribution: that share is split among the chosen items "
            "according to their Item Type (principal, percentage or fixed price)."
        ),
    )

    @api.constrains('price_distribution', 'combo_item_ids')
    def _check_price_distribution_of_combo_products(self):
        self.env['product.template'].sudo().search(
            [('combo_ids', 'in', self.ids)]
        )._validate_combo_price_distribution()

