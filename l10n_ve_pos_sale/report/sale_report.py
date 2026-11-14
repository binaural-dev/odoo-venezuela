from odoo import models
from odoo.tools import SQL


class SaleReport(models.Model):
    _inherit = "sale.report"

    def _select_pos_dict(self, table):
        """Alternate currency measures of the lines that come from the POS, at
        the rate the order was sold with (``pos.order.foreign_currency_rate``)."""
        rate = self._case_value_or_one(table.order_id.foreign_currency_rate)
        return super()._select_pos_dict(table) | {
            "foreign_currency_id": SQL(
                "(SELECT rc.foreign_currency_id FROM res_company rc WHERE rc.id = %s)",
                table.order_id.company_id,
            ),
            "foreign_untaxed_total": SQL(
                "SUM(SIGN(%s) * SIGN(%s) * ABS(%s)) * MIN(%s)",
                table.qty,
                table.price_unit,
                table.price_subtotal,
                rate,
            ),
            "foreign_total_billed": SQL(
                "SUM(SIGN(%s) * SIGN(%s) * ABS(%s)) * MIN(%s)",
                table.qty,
                table.price_unit,
                table.price_subtotal_incl,
                rate,
            ),
        }
