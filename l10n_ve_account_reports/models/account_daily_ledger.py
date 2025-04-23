from odoo import models


class AccountDailyLedger(models.AbstractModel):
    _inherit = "account.general.ledger.report.handler"
    _name = "account.daily.ledger.report.handler"
    _description = "Daily Ledger Custom Handler"

    def _get_query_sums(self, report, options):
        """
        Override to set strict range to True so the report will not show the opening balance of the
        account.
        """
        options.setdefault("general_ledger_strict_range", True)
        return super()._get_query_sums(report, options)

    def _get_account_title_line(self, report, options, account, has_lines, eval_dict):
        """
        Override to set has_lines to False so the report lines will not be foldable.
        """
        has_lines = False
        return super()._get_account_title_line(report, options, account, has_lines, eval_dict)
