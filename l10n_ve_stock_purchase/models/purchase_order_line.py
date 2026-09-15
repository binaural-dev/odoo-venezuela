from odoo import fields, models


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    alternate_code = fields.Char(
        related="product_id.alternate_code",
        string="Alternate Code",
        help=(
            "Alternate code of the product, taken from the product form. "
            "Shown here for reference only; edit it on the product itself."
        ),
    )
