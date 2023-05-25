from odoo import api, models, _
from odoo.exceptions import ValidationError
from collections import defaultdict

from odoo import _, api, models
from odoo.exceptions import ValidationError


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.constrains("barcode")
    def _check_barcode_uniqueness(self):
        """
        This function was overwritten to add the multicompany filter

        --- Original --
        With GS1 nomenclature, products and packagings use the same pattern. Therefore, we need
        to ensure the uniqueness between products' barcodes and packagings' ones"""
        all_barcode = [b for b in self.mapped("barcode") if b]
        domain = [("barcode", "in", all_barcode), ("company_id", "=", self.company_id.id)]
        matched_products = self.sudo().search(domain, order="id")

        if len(matched_products) > len(all_barcode):
            products_by_barcode = defaultdict(list)
            for product in matched_products:
                products_by_barcode[product.barcode].append(product)

            duplicates_as_str = "\n".join(
                _(
                    '- Barcode "%s" already assigned to product(s): %s',
                    barcode,
                    ", ".join(p.display_name for p in products),
                )
                for barcode, products in products_by_barcode.items()
                if len(products) > 1
            )
            raise ValidationError(_("Barcode(s) already assigned:\n\n%s", duplicates_as_str))

        if self.env["product.packaging"].search(domain, order="id", limit=1):
            raise ValidationError(_("A packaging already uses the barcode"))
