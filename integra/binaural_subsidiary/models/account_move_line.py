from odoo import api, models, _
from odoo.exceptions import UserError


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.constrains("analytic_distribution")
    def _check_one_subsidiary_per_analytic_distribution(self):
        for line in (line for line in self if line.move_id.is_invoice(include_receipts=True)):
            if not line.analytic_distribution:
                continue
            analytic_accounts = self.env["account.analytic.account"].browse(
                (int(account_id) for account_id in line.analytic_distribution.keys())
            )
            if len([account for account in analytic_accounts if account.is_subsidiary]) > 1:
                raise UserError(_("The invoice's lines should have just one subsidairy"))

    def reconcile(self):
        self._distribute_subsidiaries_analytic_accounts()
        return super().reconcile()

    def _distribute_subsidiaries_analytic_accounts(self, distribute_on_asset_cash_account=False):
        """
        Distribute the analytic accounts that are subsidiaries on the statement line or the asset
        cash account line.

        This method is called when reconciling a statement line and when validating a bank
        statement (see bank_rec_widget.py), so it's basically being used twice when validating a
        bank statement, once for setting the analytic accounts on the statement line when the
        reconciliation is being made and once for setting the analytic accounts on the asset cash
        account line, after the lines have been reconciled.

        The idea is to distribute the amount of the payment lines on the bank statement line
        according to the percentage of the analytic accounts that are subsidiaries. For example:

        10102001 BBVA                   1000
        10102006 Payments to reconcile           500
        10102006 Payments to reconcile           500

        If the payment lines have different subsidiaries, the analytic accounts will be
        distributed on the statement line like this:

        {1: 50%, 2: 50%}

        Params
        ------
        distribute_on_asset_cash_account: bool
            Whether to distribute the analytic accounts on the asset cash account line or the
            statement line. If False, the analytic accounts will be distributed on the statement
            line. If True, the analytic accounts will be distributed on the asset cash account
            line.
        """
        if not distribute_on_asset_cash_account:
            line_to_change = self.filtered(lambda l: l.statement_line_id)
        else:
            line_to_change = self.filtered(lambda l: l.account_id.account_type == "asset_cash")
        
        for line_to in line_to_change:
            move_line_with_statement_analytic_distribution = line_to.analytic_distribution or {}
            if not line_to:
                continue
            balance_to_distribute = abs(line_to.amount_residual)
            AnalyticAccount = self.env["account.analytic.account"]
            for line in self.filtered(lambda l: l.analytic_distribution and l.id != line_to.id):
                line_analytic_distribution = line.analytic_distribution
                if not line_analytic_distribution:
                    continue
                for analytic_account_id, percentage in line_analytic_distribution.items():
                    if not AnalyticAccount.browse(int(analytic_account_id)).is_subsidiary:
                        continue
                    # When the method is being called on the reconciliation of a statement line, the
                    # amount of the statement is alreade the one being reconciled, so we use the
                    # full percentage.
                    percentage_to_add = (
                        abs(line.balance) * percentage / balance_to_distribute
                        if distribute_on_asset_cash_account
                        else 100.0
                    )

                    if (
                        distribute_on_asset_cash_account
                        and analytic_account_id in move_line_with_statement_analytic_distribution
                    ):
                        move_line_with_statement_analytic_distribution[
                            analytic_account_id
                        ] += percentage_to_add
                        continue
                    move_line_with_statement_analytic_distribution[
                        analytic_account_id
                    ] = percentage_to_add
                if not line_analytic_distribution:
                    continue
            line_to.analytic_distribution = move_line_with_statement_analytic_distribution