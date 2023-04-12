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

    def export_file(self, options, file_generator):
        """
        Sends the usd_report variable to the request (this way in the controller we can tell if
        the report we are gonna export is in USD or not).
        """
        res = super().export_file(options, file_generator)
        res["data"]["usd_report"] = self.env.context.get("usd_report", False)
        return res


class AccountReportCustomHandler(models.AbstractModel):
    _inherit = "account.report.custom.handler"

    def _get_amount_rows_query(self):
        """
        Computes the string that should go as the rows of the amounts on the queries of the amounts
        from the account move lines. This depends on the action that was used for calling the
        report, as this is the way we know if the user is consulting it on the base or the foreign
        currency.

        Returns
        -------
        string
            The piece of SQL code that goes on the position of the amounts rows for the query.
        """
        report_in_foreign_currency = self.get_is_foreign_currency()
        amounts_query = {
            True: """
                ROUND(account_move_line.foreign_debit, currency_table.precision)   AS debit,
                ROUND(account_move_line.foreign_credit, currency_table.precision)  AS credit,
                ROUND(account_move_line.foreign_balance, currency_table.precision) AS balance
            """,
            False: """
                ROUND(account_move_line.debit * currency_table.rate, currency_table.precision)   AS debit,
                ROUND(account_move_line.credit * currency_table.rate, currency_table.precision)  AS credit,
                ROUND(account_move_line.balance * currency_table.rate, currency_table.precision) AS balance
            """,
        }
        return amounts_query[report_in_foreign_currency]

    def _get_sums_amount_rows_query(self):
        """
        Computes the string that should go as the rows of the amounts on the queries of the amounts
        sums from the account move lines. This depends on the action that was used for calling the
        report, as this is the way we know if the user is consulting it on the base or the foreign
        currency.

        Returns
        -------
        string
            The piece of SQL code that goes on the position of the sums of the amounts rows for the
            query.
        """
        report_in_foreign_currency = self.get_is_foreign_currency()
        amounts_query = {
            True: """
                COALESCE(SUM(ROUND(account_move_line.foreign_debit, currency_table.precision)), 0.0) AS debit,
                COALESCE(SUM(ROUND(account_move_line.foreign_credit, currency_table.precision)), 0.0) AS credit,
                COALESCE(SUM(ROUND(account_move_line.foreign_balance, currency_table.precision)), 0.0) AS balance
            """,
            False: """
                SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
            """,
        }
        return amounts_query[report_in_foreign_currency]

    @api.model
    def get_is_foreign_currency(self):
        """
        Computes if the report is in foreign currency.

        Returns
        -------
        bool
            Whether the report is in foreign currency or not.
        """
        foreign_currency_id = self.env.company.currency_foreign_id.id
        base_vef_id = self.env["ir.model.data"]._xmlid_to_res_id(
            "base.VEF", raise_if_not_found=False
        )
        usd_report = self.env.context.get("usd_report", False)

        return (foreign_currency_id != base_vef_id and usd_report) or (
            foreign_currency_id == base_vef_id and not usd_report
        )
