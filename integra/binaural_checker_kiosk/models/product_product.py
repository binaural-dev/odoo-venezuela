from odoo import api, fields, models
from odoo.tools import float_is_zero
import logging

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = 'product.product' 
    
    @api.model
    def all_scan_search(self, barcode):
        
        product = None
        
        char_fields_products = self.env.company.sh_search_char_field_product
        
        for char_fields in char_fields_products:
            product = self.env["product.product"].search([(
                char_fields.name, "=", barcode
            )], limit=1)
            
            if product:
                break
        else:
            return super().all_scan_search(barcode)
        
        res = super().all_scan_search(barcode)
        
        foreign_currency = self.env.company.currency_foreign_id
        rate = self.env["res.currency.rate"].search([
            ("currency_id", "=", foreign_currency.id),
            ("company_id", "=", self.env.company.id)
        ], limit=1)
        foreign_currency_name = foreign_currency.name
        foreign_currency_symbol = foreign_currency.symbol or ""
        last_currency_rate = rate.company_rate or 1
        currency_symbol = product.currency_id.symbol
        currency_name = product.currency_id.name
        
        price = product.list_price * last_currency_rate
        iva = price * product.taxes_id.amount / 100
        iva_rounded = round(iva, 2)
        price_with_iva = iva + price
        price_with_iva = round(price_with_iva, 2)
        
        sale_price = round(price, 2)

        foreign_sale_price = (
            str(round(price_with_iva / last_currency_rate, 2))
            .replace(".",",")
        )
        quantity_product_dict = res.get("sh_product_stock")
        quantity_product = ""
        for qty in quantity_product_dict[0].values():
            quantity_product = qty
        res.update({
            "price_with_iva": (
                f"{str(price_with_iva).replace('.', ',')} {foreign_currency_symbol}" 
            ),
            "sh_product_sale_price": f"BI = {str(sale_price).replace('.', ',')} {foreign_currency_symbol}",
            "iva": f"IVA = {str(iva_rounded).replace('.', ',')} {foreign_currency_symbol}",
            "foreign_sale_price_with_iva": f"{currency_name} {currency_symbol}{foreign_sale_price}",
            "product_qty": quantity_product,
            "company_logo": self.env.company.logo
        })

        
        return res
        
        