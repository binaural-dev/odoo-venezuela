from odoo import api, fields, models


class StockLocation(models.Model):
    _inherit = "stock.location"

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        if self.env.user.is_required_subsidiary:
            args = [] if args is None else args
            args.append(
                [
                    "location_id.warehouse_id.subsidiary_id",
                    "in",
                    [*self.env.user.subsidiary_ids.ids, False],
                ]
            )
        return super().name_search(name, args, operator, limit)
