from odoo import api, models


class ProductPricelist(models.Model):
    _inherit = "product.pricelist"

    @api.depends("name", "currency_id", "company_id", "company_id.name")
    def _compute_display_name(self):
        """Extend the core "Name (Currency)" display name with the
        pricelist's company, so it's identifiable at a glance wherever
        pricelists are listed (e.g. Default (VEF) (Sucursal Caracas)).
        Pricelists with no company (shared across all companies) are left
        as the core computes them.
        """
        super()._compute_display_name()
        for pricelist in self:
            if pricelist.company_id:
                pricelist.display_name = f"{pricelist.display_name} ({pricelist.company_id.name})"
