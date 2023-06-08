from odoo import api, fields, models
from odoo.tools import float_is_zero
import logging
_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = 'product.product' 
    
    @api.model
    def all_scan_search(self, barcode):
        
        product = None
        
        for char_fields in self.env.company.sh_search_char_field_product:
            product = self.env["product.product"].search([(
                char_fields.name, "=", barcode
            )], limit=1)
            
            if product:
                break
        else:
            return super().all_scan_search(barcode)
        
        res = super().all_scan_search(barcode)
        iva = product.list_price * product.taxes_id.amount / 100
        iva_rounded = round(iva, 2)
        price_with_iva = iva + product.list_price
        price_with_iva = round(price_with_iva, 2)
        
        sale_price = round(product.list_price, 2)
        currency_symbol = product.currency_id.symbol
        foreign_currency = self.env.company.currency_foreign_id
        foreign_currency_name = foreign_currency.name
        foreign_currency_symbol = foreign_currency.symbol
        foreign_currency_rates = foreign_currency.rate_ids.sorted(key=lambda rate: rate.name, reverse=True)
        last_currency_rate = foreign_currency_rates[0]
        
        foreign_sale_price = (
            str(round(last_currency_rate.company_rate / price_with_iva, 2))
            .replace(".",",")
        )
        
        res.update({
            "price_with_iva": (
                f"{str(price_with_iva).replace('.', ',')} {currency_symbol}" 
                if not float_is_zero(product.taxes_id.amount, precision_rounding=2)
                else False
            ),
            "sh_product_sale_price": f"BI = {str(sale_price).replace('.', ',')} {currency_symbol}",
            "iva": f"IVA = {str(iva_rounded).replace('.', ',')} {currency_symbol}",
            "foreign_sale_price_with_iva": f"{foreign_currency_name} {foreign_currency_symbol}{foreign_sale_price}",
        })
        
        return res
        
        