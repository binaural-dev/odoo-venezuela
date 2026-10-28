from odoo import api, models


class PosLoadMixin(models.AbstractModel):
    _inherit = "pos.load.mixin"

    @api.model
    def _pos_stock_dependent_models(self):
        """Models whose PoS data carries the stock of the PoS warehouse:
        ``product.product`` (``qty_available`` / ``free_qty``) and
        ``product.template``, whose loaded ids decide which variants load."""
        return {"product.template", "product.product"}

    def _last_server_date_to_load(self):
        """No ``write_date`` filter for the stock-dependent data when the PoS
        hides products without stock.

        The limited load only brings what changed after the browser cache, and
        a stock move does not change the ``write_date`` of the product: a new
        session or opening the PoS from the backend kept the stock of the last
        full load. ``pos.session.load_data`` sets the context.
        """
        if (
            self.env.context.get("pos_reload_stock_dependent_data")
            and self._name in self._pos_stock_dependent_models()
        ):
            return False
        return super()._last_server_date_to_load()
