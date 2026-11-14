from odoo import api, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _load_pos_data_fields(self, config):
        """Odoo 20 loader contract: extend the read with ``free_qty`` and
        ``qty_available`` for the Venezuelan PoS UI warehouse views.
        """
        res = super()._load_pos_data_fields(config)
        for name in ("free_qty", "qty_available"):
            if name not in res:
                res.append(name)
        return res

    @api.model
    def _load_pos_data_read(self, records, config):
        """Odoo 20 loader contract:

        * ``lst_price`` is NOT converted here: the core already converts it
          to the PoS config currency (``_convert_pos_data_currency``). The
          Odoo 17 conversion kept here converted it twice.
        * Compute ``free_qty`` / ``qty_available`` in the source location of
          the PoS operation type (and its children), the stock
          ``pos.config.check_stock_availability`` ("Cantidad en 0") checks:
          the grid shows what the PoS can sell. The O17 ``warehouse`` key was
          ignored by ``stock`` and the quantity summed every warehouse; the
          whole warehouse would miss a source location outside of it. Do not
          add ``warehouse_id`` too: ``stock`` intersects both.
        """
        location = config.picking_type_id.default_location_src_id
        if location:
            records = records.with_context(location=location.id)
        res = super()._load_pos_data_read(records, config) or []
        return self._sort_available_products(res)

    def _sort_available_products(self, products):
        """Match the legacy Odoo 17 contract: sort by ``qty_available``
        descending when the company enables
        ``pos_show_just_products_with_available_qty``."""
        if not self.env.company.pos_show_just_products_with_available_qty:
            return products
        return sorted(products, key=lambda x: x.get("qty_available", 0.0), reverse=True)
