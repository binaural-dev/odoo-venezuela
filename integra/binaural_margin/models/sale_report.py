from odoo import api, fields, models, _


class SaleReport(models.Model):
    _inherit = "sale.report"

    margin_percent = fields.Float(
        "Margin (%)", store=True, group_operator="avg"
    )
    latest_standard_price_margin = fields.Float(
        "Latest Cost Margin",
        store=True,
        group_operator="avg",
    )
    latest_standard_price_margin_percent = fields.Float(
        "Latest Cost Margin (%)",
        store=True,
        group_operator="avg",
    )

    def _select_additional_fields(self):
        res = super()._select_additional_fields()
        res[
            "margin_percent"
        ] = f"""SUM(l.margin_percent
            / {self._case_value_or_one('s.currency_rate')}
            * {self._case_value_or_one('currency_table.rate')})
        """
        res[
            "latest_standard_price_margin"
        ] = f"""SUM(l.latest_standard_price_margin
            / {self._case_value_or_one('s.currency_rate')}
            * {self._case_value_or_one('currency_table.rate')})
        """
        res[
            "latest_standard_price_margin_percent"
        ] = f"""SUM(l.latest_standard_price_margin_percent
            / {self._case_value_or_one('s.currency_rate')}
            * {self._case_value_or_one('currency_table.rate')})
        """
        return res
