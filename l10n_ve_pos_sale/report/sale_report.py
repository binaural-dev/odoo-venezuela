from odoo import models


class SaleReport(models.Model):
    _inherit = "sale.report"

    def _available_additional_pos_fields(self):
        res = super()._available_additional_pos_fields()
        rate = self._case_value_or_one("pos.foreign_currency_rate")
        res.update({
            "foreign_currency_id": """
                (SELECT rc.foreign_currency_id FROM res_company rc WHERE rc.id = pos.company_id)
            """,
            "foreign_untaxed_total": f"""
                SUM(SIGN(l.qty) * SIGN(l.price_unit) * ABS(l.price_subtotal))
                * MIN({rate})
            """,
            "foreign_total_billed": f"""
                SUM(SIGN(l.qty) * SIGN(l.price_unit) * ABS(l.price_subtotal_incl))
                * MIN({rate})
            """,
        })
        return res
