from odoo import models
from odoo.osv import expression


class StockQuant(models.Model):
    _inherit = "stock.quant"

    def _domain_location_id(self):
        domain = super()._domain_location_id()
        if not domain:
            return

        list_domain = [*self.env.user.subsidiary_ids.ids, False]
        domain = expression.AND(
            [
                domain,
                [("warehouse_id.subsidiary_id", "in", list_domain)],
            ]
        )
        return domain
