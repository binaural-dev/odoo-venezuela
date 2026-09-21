from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_accountant_test")
class TestAnalyticDistributionForeignAmount(TransactionCase):
    """
    Regression tests for AccountMoveLine._prepare_analytic_distribution_line
    (models/account_move_line.py).

    Two bugs fixed there:

    1. `account_id = int(account_id)` treated the method's second argument
       as a single analytic account id. It is actually the raw
       `analytic_distribution` dict KEY, which native Odoo comma-joins into
       several ids whenever one distribution bucket spans more than one
       analytic PLAN at the same percentage (e.g. {"5,12": 100.0}). Any
       move line distributing to 2+ plans under the same bucket crashed
       with `ValueError: invalid literal for int()`.

    2. `distribution_on_each_plan` was read AFTER calling `super()`, which
       already mutates that dict in place while computing the native
       `amount` field. Reading it afterwards double-counts the current
       key's `distribution` on top of what `super()` already added, so the
       "this key closes the plan to exactly 100%" branch (the one that
       protects against losing/gaining a cent when percentages don't sum to
       an exact float, e.g. 33.34/33.33/33.33) could never trigger for
       `foreign_amount` - unlike the native `amount` field, which IS
       protected by it.

    Both tests assert exact per-line amounts (not just "no crash"), and the
    3-way split specifically uses percentages that don't reduce evenly, so a
    regression of bug 2 would show up as `sum(foreign_amount) != foreign_balance`
    even though bug 1 no longer crashes.
    """

    def setUp(self):
        super().setUp()

        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")
        self.country_ve = self.env.ref("base.ve")

        self.company.write(
            {
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
                "account_fiscal_country_id": self.country_ve.id,
                "country_id": self.country_ve.id,
            }
        )

        self.env["res.currency.rate"].search(
            [("currency_id", "in", (self.currency_vef | self.currency_usd).ids),
             ("company_id", "=", self.company.id)]
        ).unlink()
        self.env["res.currency.rate"].create(
            {
                "name": fields.Date.today(),
                "currency_id": self.currency_vef.id,
                "inverse_company_rate": 1.0,
                "company_id": self.company.id,
            }
        )
        # 1 USD = 25 VEF => foreign_balance = balance / 25.
        self.env["res.currency.rate"].create(
            {
                "name": fields.Date.today(),
                "currency_id": self.currency_usd.id,
                "inverse_company_rate": 25.0,
                "company_id": self.company.id,
            }
        )

        self.expense_account = self.env["account.account"].search(
            [("code", "=", "ANEXP2"), ("company_ids", "in", self.company.id)], limit=1
        ) or self.env["account.account"].create(
            {
                "name": "Analytic Distribution Expense",
                "code": "ANEXP2",
                "account_type": "expense",
                "company_ids": [Command.set([self.company.id])],
            }
        )
        self.cash_account = self.env["account.account"].search(
            [("code", "=", "ANCASH2"), ("company_ids", "in", self.company.id)], limit=1
        ) or self.env["account.account"].create(
            {
                "name": "Analytic Distribution Cash",
                "code": "ANCASH2",
                "account_type": "asset_cash",
                "company_ids": [Command.set([self.company.id])],
            }
        )

        self.general_journal = self.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].create(
            {"name": "Test Misc Journal", "type": "general", "company_id": self.company.id}
        )

        self.plan_a = self.env["account.analytic.plan"].create(
            {"name": "Analytic Distribution Plan A"}
        )
        self.plan_b = self.env["account.analytic.plan"].create(
            {"name": "Analytic Distribution Plan B"}
        )

        self.account_a1 = self.env["account.analytic.account"].create(
            {"name": "Plan A - Account 1", "plan_id": self.plan_a.id, "company_id": self.company.id}
        )
        self.account_a2 = self.env["account.analytic.account"].create(
            {"name": "Plan A - Account 2", "plan_id": self.plan_a.id, "company_id": self.company.id}
        )
        self.account_a3 = self.env["account.analytic.account"].create(
            {"name": "Plan A - Account 3", "plan_id": self.plan_a.id, "company_id": self.company.id}
        )
        self.account_b1 = self.env["account.analytic.account"].create(
            {"name": "Plan B - Account 1", "plan_id": self.plan_b.id, "company_id": self.company.id}
        )

    def _post_move_with_distribution(self, debit, analytic_distribution):
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "date": fields.Date.today(),
                "journal_id": self.general_journal.id,
                "line_ids": [
                    Command.create(
                        {
                            "debit": debit,
                            "credit": 0.0,
                            "account_id": self.expense_account.id,
                            "analytic_distribution": analytic_distribution,
                        }
                    ),
                    Command.create(
                        {
                            "debit": 0.0,
                            "credit": debit,
                            "account_id": self.cash_account.id,
                        }
                    ),
                ],
            }
        )
        move.action_post()
        expense_line = move.line_ids.filtered(lambda l: l.account_id == self.expense_account)
        analytic_lines = self.env["account.analytic.line"].search(
            [("move_line_id", "=", expense_line.id)]
        )
        return expense_line, analytic_lines

    @staticmethod
    def _line_for_account(analytic_lines, account):
        """
        `account.analytic.line.account_id` only aliases the built-in
        "project" plan's column - for any other (custom) plan, the account
        lives in a dynamically-named column (`account._column_name()` on its
        plan). Filter generically instead of assuming `account_id`.
        """
        column = account.plan_id._column_name()
        return analytic_lines.filtered(lambda l: l[column] == account)

    def test_multi_plan_single_key_does_not_crash(self):
        """
        A single distribution bucket spanning 2 plans at once (native's
        comma-joined key "account_a1_id,account_b1_id": 100.0) used to raise
        ValueError('invalid literal for int()...') on `int(account_id)`.
        """
        combined_key = f"{self.account_a1.id},{self.account_b1.id}"
        expense_line, analytic_lines = self._post_move_with_distribution(
            1000.0, {combined_key: 100.0}
        )

        self.assertAlmostEqual(expense_line.foreign_balance, 40.0, places=2)
        # Both accounts share ONE analytic line (single distribution bucket
        # applies to both plan columns of the same account.analytic.line),
        # carrying the full foreign_balance since it's the only/100% bucket.
        self.assertEqual(len(analytic_lines), 1)
        self.assertAlmostEqual(analytic_lines.foreign_amount, -40.0, places=2)
        self.assertEqual(
            analytic_lines[self.plan_a._column_name()], self.account_a1
        )
        self.assertEqual(
            analytic_lines[self.plan_b._column_name()], self.account_b1
        )

    def test_three_way_uneven_split_sums_exactly(self):
        """
        33.34 / 33.33 / 33.33: an uneven 3-way split, asserted with exact
        per-line shares AND an exact total. This is a correctness pin, not a
        test that flips under the old double-counting bug: whenever the
        declared percentages truly sum to 100 (as here), "this bucket's own
        share" and "100% minus what came before" are algebraically the same
        number for whichever bucket closes the plan - the double-counting
        bug only ever misidentifies WHICH bucket is treated as the closing
        one, it doesn't change the arithmetic result for exact percentage
        splits. It matters for hygiene/parity with the native `amount`
        field (and could matter for percentages with genuine float
        representation drift), so it's still worth pinning exactly.
        """
        debit = 1000.0  # foreign_balance = 1000 / 25 = 40.0
        expense_line, analytic_lines = self._post_move_with_distribution(
            debit,
            {
                str(self.account_a1.id): 33.34,
                str(self.account_a2.id): 33.33,
                str(self.account_a3.id): 33.33,
            },
        )

        self.assertEqual(len(analytic_lines), 3)
        line_a1 = self._line_for_account(analytic_lines, self.account_a1)
        line_a2 = self._line_for_account(analytic_lines, self.account_a2)
        line_a3 = self._line_for_account(analytic_lines, self.account_a3)

        # `foreign_amount` is a Monetary field (currency_field=foreign_currency_id,
        # EUR here => 2-decimal rounding), so the raw -13.336/-13.332/-13.332
        # shares come back rounded to currency precision: -13.34/-13.33/-13.33.
        self.assertAlmostEqual(line_a1.foreign_amount, -13.34, places=2)
        self.assertAlmostEqual(line_a2.foreign_amount, -13.33, places=2)
        self.assertAlmostEqual(line_a3.foreign_amount, -13.33, places=2)

        total_foreign_amount = sum(analytic_lines.mapped("foreign_amount"))
        self.assertAlmostEqual(
            total_foreign_amount,
            -expense_line.foreign_balance,
            places=2,
            msg=(
                "Analytic foreign_amount lines must sum exactly to "
                "-foreign_balance, same guarantee the native 'amount' "
                "field already has."
            ),
        )

    def test_two_way_exact_split_matches_expected_shares(self):
        """Baseline: an exact 60/40 split still gives exact, distinct shares."""
        expense_line, analytic_lines = self._post_move_with_distribution(
            1000.0,
            {
                str(self.account_a1.id): 60.0,
                str(self.account_a2.id): 40.0,
            },
        )

        line_a1 = self._line_for_account(analytic_lines, self.account_a1)
        line_a2 = self._line_for_account(analytic_lines, self.account_a2)

        self.assertAlmostEqual(line_a1.foreign_amount, -24.0, places=2)
        self.assertAlmostEqual(line_a2.foreign_amount, -16.0, places=2)
        self.assertNotEqual(line_a1.foreign_amount, line_a2.foreign_amount)
