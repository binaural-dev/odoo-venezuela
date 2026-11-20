from odoo import api, models


class PosLoadMixin(models.AbstractModel):
    _inherit = "pos.load.mixin"

    @api.model
    def _pos_stock_dependent_models(self):
        """Models whose PoS data carries the stock of the PoS source location:
        ``product.product`` (``qty_available`` / ``free_qty``) and
        ``product.template``, whose loaded ids decide which variants load."""
        return {"product.template", "product.product"}

    @api.model
    def load_pos_data_force_loading(self):
        """Load the stock-dependent data whole, whatever the browser cache has,
        when the PoS hides products without stock.

        Core only sends what changed after the browser cache
        (``write_date``), and a stock move does not change the ``write_date``
        of the product: a new session or opening the PoS from the backend kept
        the stock of the last full load. ``pos.session.load_data`` sets the
        context.
        """
        if (
            self.env.context.get("pos_reload_stock_dependent_data")
            and self._name in self._pos_stock_dependent_models()
        ):
            return True
        return super().load_pos_data_force_loading()
