from odoo import api, fields, models, tools, _

SPLIT_METHOD = [
    ("equal", "Equal"),
    ("by_quantity", "By Quantity"),
    ("by_current_cost_price", "By Current Cost"),
    ("by_weight", "By Weight"),
    ("by_volume", "By Volume"),
    ("by_percentage", "By Percentage"),
]


class StockLandedCostLines(models.Model):
    _inherit = "stock.landed.cost.lines"

    split_method = fields.Selection(
        SPLIT_METHOD,
        string="Split Method",
        required=True,
        help="Equal : Cost will be equally divided.\n"
        "By Quantity : Cost will be divided according to product's quantity.\n"
        "By Current cost : Cost will be divided according to product's current cost.\n"
        "By Weight : Cost will be divided depending on its weight.\n"
        "By Volume : Cost will be divided depending on its volume.\n"
        "By Percentage : Cost will represent the percentage of the total invoice",
    )