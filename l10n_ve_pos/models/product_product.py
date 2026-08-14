from odoo import api, fields, models
from odoo.tools import float_compare
import logging
_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _load_pos_data_fields(self, config):
        """Odoo 19 loader contract: extend the read with ``free_qty`` and
        ``qty_available`` for the Venezuelan PoS UI warehouse views.
        """
        res = super()._load_pos_data_fields(config)
        for name in ("free_qty", "qty_available"):
            if name not in res:
                res.append(name)
        return res

    @api.model
    def _load_pos_data_read(self, records, config):
        """Odoo 19 loader contract:

        * Convert ``lst_price`` to the PoS config currency when it differs
          from the company currency.
        * Propagate the PoS warehouse context so ``free_qty`` /
          ``qty_available`` are computed against the right warehouse.
        * Enrich the payload with the full ``categ`` object and a boolean
          ``image_128`` flag (matches the legacy Odoo 17 contract).
        """
        warehouse_id = config.picking_type_id.warehouse_id.id
        records = records.with_context(warehouse=warehouse_id)
        res = super()._load_pos_data_read(records, config) or []

        company_currency = config.company_id.currency_id
        pos_currency = config.currency_id
        if pos_currency != company_currency:
            today = fields.Date.today()
            for product in res:
                product['lst_price'] = company_currency._convert(
                    product['lst_price'],
                    pos_currency,
                    config.company_id,
                    today,
                )

        categ_records = self.env['product.category']._load_pos_data_read(
            self.env['product.category'].search([]),
            config,
        )
        product_category_by_id = {category['id']: category for category in categ_records}

        for product in res:
            categ_id = product['categ_id'][0] if product.get('categ_id') else None
            if categ_id in product_category_by_id:
                product['categ'] = product_category_by_id[categ_id]
            product['image_128'] = bool(product.get('image_128'))

        return self._sort_available_products(res)

    def _sort_available_products(self, products):
        """Match the legacy Odoo 17 contract: sort by ``qty_available``
        descending when the company enables
        ``pos_show_just_products_with_available_qty``."""
        if not self.env.company.pos_show_just_products_with_available_qty:
            return products
        return sorted(products, key=lambda x: x.get("qty_available", 0.0), reverse=True)
