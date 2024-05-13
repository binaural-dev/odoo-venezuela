from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.shopify.instance"

    def create_pricelist(self, shop_currency):
        """
        This method creates pricelist from currency of the Shopify store.
        @author: Maulik Barad on Date 25-Sep-2020.
        @param shop_currency: Currency got from shopify store.
        """
        currency_obj = self.env["res.currency"]
        pricelist_obj = self.env["product.pricelist"]

        currency_id = currency_obj.search([("name", "=", shop_currency)], limit=1)

        if not currency_id:
            currency_id = currency_obj.search([("name", "=", shop_currency), ("active", "=", False)], limit=1)
            currency_id.write({"active": True})
        if not currency_id:
            currency_id = self.env.user.currency_id

        price_list_name = self.name + " " + "PriceList"
        pricelist = pricelist_obj.search([("name", "=", price_list_name),
                                          ("currency_id", "=", currency_id.id),
                                          ("company_id", "=", self.shopify_company_id.id)],
                                         limit=1)
        if not pricelist:
            pricelist = pricelist_obj.create({"name": price_list_name,
                                              "currency_id": currency_id.id,
                                              "company_id": self.shopify_company_id.id})

        _logger.warning("PRICELIIIIIIIST %s", pricelist.id)
        return pricelist.id
