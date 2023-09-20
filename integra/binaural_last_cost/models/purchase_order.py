from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def button_confirm(self):
        """
        After the normal flow of the confirm button, updates the latest_price and the
        last_latest_standard_price of the product (and its template if the products variants are not
        active) of each line having the field update_latest_standard_price as True.

        We need the last_latest_standard_price to be able to return the latest price to its previous
        value if the purchase order is cancelled.
        """
        res = super().button_confirm()

        for line in self._get_lines_with_updatable_latest_standard_price():
            product = line.product_id
            latest_standard_price = line.latest_standard_price
            price_per_udm = line.price_per_udm
            
            product.last_latest_standard_price = latest_standard_price
            product.latest_standard_price = price_per_udm

            variants_are_active = product.get_variants_are_active()
            if not variants_are_active:
                product.product_tmpl_id.last_latest_standard_price = latest_standard_price
                product.product_tmpl_id.latest_standard_price = price_per_udm

        return res

    def button_cancel(self):
        """
        After the normal flow of the cancel button, updates the latest_price of the product
        (and its template if the product variants are not active) of each line having the field
        update_latest_standard_price as True.

        We need to return the latest price to its previous value when the purchase order is
        cancelled.
        """
        super().button_cancel()

        for line in self._get_lines_with_updatable_latest_standard_price():
            product = line.product_id
            template = product.product_tmpl_id
            template_last_latest_standard_price = template.last_latest_standard_price
            
            product_last_latest_standard_price = product.last_latest_standard_price
            product.latest_standard_price = product_last_latest_standard_price

            variants_are_active = product.get_variants_are_active()
            if not variants_are_active:
                template.latest_standard_price = template_last_latest_standard_price
                
        return True

    def _get_lines_with_updatable_latest_standard_price(self):
        return self.mapped("order_line").filtered(
            lambda line: line.update_latest_standard_price
        )