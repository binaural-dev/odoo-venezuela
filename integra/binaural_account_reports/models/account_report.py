from odoo import api, fields, models, _
from odoo.tools.misc import formatLang, format_date


class AccountReport(models.Model):
    _inherit = "account.report"

    usd = fields.Boolean(string="USD", default=False)

    @api.model
    def format_value(self, value, currency=False, blank_if_zero=True, figure_type=None, digits=1):
        """
        Ensure that if the report is in USD, the amount is displayed in its appropiate format.
        Everything else is the same as the original method.
        """
        if figure_type == "none":
            return value

        if value is None:
            return ""

        if figure_type == "monetary":
            # If the report is in USD, we want to display the amount in its appropiate format
            usd_report = True if (self.env.context.get("usd_report") or self.usd) else False
            currency = currency or (
                self.env.ref("base.USD") if usd_report else self.env.ref("base.VEF")
            )
            digits = None
        elif figure_type == "integer":
            currency = None
            digits = 0
        elif figure_type in ("date", "datetime"):
            return format_date(self.env, value)
        else:
            currency = None

        if self.is_zero(value, currency=currency, figure_type=figure_type, digits=digits):
            if blank_if_zero:
                return ""
            # don't print -0.0 in reports
            value = abs(value)

        if self._context.get("no_format"):
            return value

        formatted_amount = formatLang(self.env, value, currency_obj=currency, digits=digits)

        if figure_type == "percentage":
            return f"{formatted_amount}%"

        return formatted_amount


class AccountReportCustomHandler(models.AbstractModel):
    _inherit = "account.report.custom.handler"

    def _get_is_foreign_currency(self):
        """
        Gets if the report is in foreign currency.

        Returns
        -------
        bool
            True if the report is in foreign currency, False otherwise.
        """
        foreign_currency_id = self.env.company.currency_foreign_id.id
        base_vef_id = self.env["ir.model.data"]._xmlid_to_res_id(
            "base.VEF", raise_if_not_found=False
        )
        usd_report = self.env.context.get("usd_report", False)

        return (foreign_currency_id != base_vef_id and usd_report) or (
            foreign_currency_id == base_vef_id and not usd_report
        )
