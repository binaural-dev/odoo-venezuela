from odoo import api, fields, models


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    foreign_currency_rate = fields.Float(related="order_id.foreign_currency_rate")
    foreign_price = fields.Float(string="Foreign Price", digits=0)
    foreign_subtotal = fields.Float(string="Foreign Subtotal", digits=0)
    foreign_total = fields.Float(string="Foreign Total", digits=0)

    @api.model
    def _load_pos_data_fields(self, config):
        """Odoo 19 replacement for the Odoo 17 ``_export_for_ui``
        hook (removed in commit ``2a5f1abf2e98 [IMP] pos_*: refactoring
        with related models part 2``).

        We extend the base Odoo 19 field list with the Venezuelan
        foreign-currency contract. ``foreign_currency_rate`` is a
        related field on the order header, but it MUST be listed
        here too so the read-back payload exposes it on every line
        (the frontend computes per-line values from it).
        """
        res = super()._load_pos_data_fields(config) or []
        for name in (
            "foreign_price",
            "foreign_subtotal",
            "foreign_total",
            "foreign_currency_rate",
        ):
            if name not in res:
                res.append(name)
        return res

    def _prepare_refund_data(self, refund_order, PosPackOperationLot):
        """Odoo 19 keeps this hook; we just inject ``foreign_price``
        so the refund line preserves the Venezuelan contract (refund
        flow is the only path that recreates order lines from a
        source order and would otherwise drop the value).
        """
        res = super()._prepare_refund_data(refund_order, PosPackOperationLot)
        res["foreign_price"] = self.foreign_price
        return res
