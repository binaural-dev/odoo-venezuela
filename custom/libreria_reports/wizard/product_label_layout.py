from odoo import fields, models


class ProductLabelLayout(models.TransientModel):
    _inherit = "product.label.layout"
    _description = "Choose the sheet layout to print the labels"

    print_format = fields.Selection(
        selection_add=[("3x18", "3 x 18")], ondelete={"3x18": "cascade"}
    )
