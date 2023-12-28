from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    scan_barcode_scale_by_price = fields.Boolean()
    scan_barcode_scale_by_price_with_tax = fields.Boolean()

    def write(self, vals):
        res = super().write(vals)
        if vals.get("scan_barcode_scale_by_price", False):
            self.env["product.template"].set_barcode_products_with_plu()
        return res
