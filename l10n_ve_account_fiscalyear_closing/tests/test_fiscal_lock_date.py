from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "l10n_ve_account_fiscalyear_closing")
class TestFiscalyearClosingLockDate(TransactionCase):
    """Cover ``_check_fiscal_lock_date``, called at the start of
    ``calculate()``: it must raise a ``ValidationError`` instead of letting
    Odoo silently move a closing move's date past the company's fiscal lock
    date for the journal."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Diario de cierre",
                "code": "CLK",
                "type": "general",
                "company_id": cls.company.id,
            }
        )
        cls.account_income = cls.env["account.account"].create(
            {
                "name": "Test Income lock",
                "code": "LCK01",
                "account_type": "income",
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )
        cls.account_equity = cls.env["account.account"].create(
            {
                "name": "Equity lock",
                "code": "LCK02",
                "account_type": "equity_unaffected",
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )

    def _create_closing_with_config(
        self,
        config_date,
        journal=None,
        enabled=True,
        code="CFGLOCK",
        date_start="2025-01-01",
        date_end="2025-12-31",
        date_opening="2026-01-01",
        name="FY Closing lock test",
    ):
        fyc = self.env["account.fiscalyear.closing"].create(
            {
                "name": name,
                "company_id": self.company.id,
                "date_start": date_start,
                "date_end": date_end,
                "date_opening": date_opening,
            }
        )
        config = self.env["account.fiscalyear.closing.config"].create(
            {
                "name": "Config lock",
                "code": code,
                "fyc_id": fyc.id,
                "journal_id": (journal or self.journal).id,
                "date": config_date,
                "move_type": "closing",
                "enabled": enabled,
            }
        )
        self.env["account.fiscalyear.closing.mapping"].create(
            {
                "name": "Map lock",
                "src_accounts": self.account_income.code,
                "dest_account_id": self.account_equity.id,
                "fyc_config_id": config.id,
            }
        )
        return fyc

    def _post_income_balance(self, date, amount=100.0, journal=None):
        """Post a balanced move crediting account_income, so a closing
        config mapping that account has something real to close. Needed
        since calculate() now raises UserError when a run produces zero
        moves (see test_calculate.py / the "nothing to close" check)."""
        move = self.env["account.move"].create(
            {
                "company_id": self.company.id,
                "journal_id": (journal or self.journal).id,
                "date": date,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "account_id": self.account_income.id,
                            "debit": 0,
                            "credit": amount,
                            "date": date,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "account_id": self.account_equity.id,
                            "debit": amount,
                            "credit": 0,
                            "date": date,
                        },
                    ),
                ],
            }
        )
        move.action_post()
        return move

    def test_calculate_raises_when_date_within_lock_period(self):
        """If the configured move date is on/before the company's fiscal
        lock date, calculate() must raise ValidationError instead of
        silently letting Odoo move the date forward."""
        self.company.fiscalyear_lock_date = "2025-12-31"
        fyc = self._create_closing_with_config("2025-12-31")
        with self.assertRaises(ValidationError):
            fyc.calculate()

    def test_calculate_succeeds_when_date_after_lock_period(self):
        """If the configured move date is strictly after the lock date, the
        lock-date check must not block calculate()."""
        self.company.fiscalyear_lock_date = "2025-06-30"
        self._post_income_balance("2025-08-01")
        fyc = self._create_closing_with_config("2025-12-31")
        result = fyc.calculate()
        self.assertTrue(result)
        self.assertEqual(len(fyc.move_ids), 1)

    def test_button_calculate_form_raises_on_locked_period(self):
        """Fill the fiscal year closing wizard through its real Form (using
        onchange_year) and confirm that button_calculate raises when the
        journal's fiscal period is locked, instead of moving the date."""
        self.company.fiscalyear_lock_date = "2025-12-31"
        fyc_form = Form(self.env["account.fiscalyear.closing"])
        fyc_form.year = 2025
        fyc = fyc_form.save()
        self.env["account.fiscalyear.closing.config"].create(
            {
                "name": "Config from form",
                "code": "CFGFORM",
                "fyc_id": fyc.id,
                "journal_id": self.journal.id,
                "date": fyc.date_end,
                "move_type": "closing",
                "enabled": True,
            }
        )
        with self.assertRaises(ValidationError):
            fyc.button_calculate()

    def test_calculate_raises_when_date_equals_lock_date_exactly(self):
        """The check is inclusive (``config.date <= lock_date``): a config
        date exactly equal to the lock date must still block calculate()."""
        self.company.fiscalyear_lock_date = "2025-10-15"
        fyc = self._create_closing_with_config("2025-10-15")
        with self.assertRaises(ValidationError):
            fyc.calculate()

    def test_calculate_succeeds_when_date_is_one_day_after_lock_date(self):
        """The boundary right after the lock date must not raise: only
        dates on/before the lock date are blocked."""
        self.company.fiscalyear_lock_date = "2025-10-15"
        self._post_income_balance("2025-10-16")
        fyc = self._create_closing_with_config("2025-10-16")
        result = fyc.calculate()
        self.assertTrue(result)
        self.assertEqual(len(fyc.move_ids), 1)

    def test_disabled_config_with_locked_date_does_not_block(self):
        """``_check_fiscal_lock_date`` only iterates over
        ``move_config_ids.filtered("enabled")``: a disabled config whose date
        falls inside the locked period must not raise, and must not create
        any move either since ``calculate()`` also filters by "enabled". A
        second, enabled config with a real balance is added so the overall
        run still produces a move (otherwise calculate() would raise for
        having generated nothing at all, which is a separate concern from
        the one this test covers).

        The source move must be created and posted BEFORE the lock date is
        set: Odoo's own account.move.create() silently shifts a move's date
        forward to (lock_date + 1) when it is created on/before the current
        lock date, which would push this move's date out of the closing's
        date range and make _get_balances find nothing."""
        fyc = self._create_closing_with_config("2025-12-31", enabled=False)
        other_account = self.env["account.account"].create(
            {
                "name": "Other income lock",
                "code": "LCK03",
                "account_type": "income",
                "company_ids": [(6, 0, [self.company.id])],
            }
        )
        other_move = self.env["account.move"].create(
            {
                "company_id": self.company.id,
                "journal_id": self.journal.id,
                "date": "2025-11-01",
                "line_ids": [
                    (0, 0, {"account_id": other_account.id, "debit": 0, "credit": 50.0, "date": "2025-11-01"}),
                    (0, 0, {"account_id": self.account_equity.id, "debit": 50.0, "credit": 0, "date": "2025-11-01"}),
                ],
            }
        )
        other_move.action_post()
        self.company.fiscalyear_lock_date = "2025-12-31"
        other_config = self.env["account.fiscalyear.closing.config"].create(
            {
                "name": "Config lock enabled",
                "code": "CFGLOCK2",
                "fyc_id": fyc.id,
                "journal_id": self.journal.id,
                # Must be strictly after fiscalyear_lock_date (2025-12-31):
                # this config is enabled, so unlike CFGLOCK it IS checked by
                # _check_fiscal_lock_date, and must not be blocked by it.
                "date": "2026-01-05",
                "move_type": "closing",
                "enabled": True,
            }
        )
        self.env["account.fiscalyear.closing.mapping"].create(
            {
                "name": "Map lock 2",
                "src_accounts": other_account.code,
                "dest_account_id": self.account_equity.id,
                "fyc_config_id": other_config.id,
            }
        )

        result = fyc.calculate()
        self.assertTrue(result)
        # The disabled config was never processed: no lock-date error, no
        # move of its own.
        disabled_config = fyc.move_config_ids.filtered(lambda c: c.code == "CFGLOCK")
        self.assertFalse(disabled_config.move_id)
        # The enabled config, mapping a different account, did generate a
        # move: calculate() did not raise "nothing to close" overall.
        self.assertEqual(len(fyc.move_ids), 1)

    def test_multiple_journals_with_different_lock_dates(self):
        """``_get_user_fiscal_lock_date`` combines the generic fiscal lock
        date with a journal-type-specific one (``sale_lock_date`` /
        ``purchase_lock_date``). A ``sale`` journal locked further into the
        future than the generic fiscal lock date must still block
        calculate(), even though a ``general`` journal with only the generic
        lock date would be fine for the same config date."""
        sale_journal = self.env["account.journal"].create(
            {
                "name": "Diario de ventas cierre",
                "code": "CLKS",
                "type": "sale",
                "company_id": self.company.id,
            }
        )
        # Generic lock date allows 2025-11-01 (config date is after it), but
        # the sale-specific lock date extends the restriction further.
        self.company.fiscalyear_lock_date = "2025-06-30"
        self.company.sale_lock_date = "2025-11-30"
        self._post_income_balance("2025-11-01")
        # A config on the general journal (no sale-specific lock applies)
        # with a date after the generic lock succeeds on its own.
        fyc_general = self._create_closing_with_config(
            "2025-11-01",
            journal=self.journal,
            code="CFGGEN",
            name="FY Closing lock test (general)",
        )
        result = fyc_general.calculate()
        self.assertTrue(result)
        self.assertEqual(len(fyc_general.move_ids), 1)

        # The same date on the sale journal is still inside the
        # sale-specific locked period and must raise. Use a non-overlapping
        # date range so ``_check_period_overlap`` does not interfere with
        # this (unrelated) lock-date check.
        fyc_sale = self._create_closing_with_config(
            "2025-11-01",
            journal=sale_journal,
            code="CFGSALE",
            date_start="2024-01-01",
            date_end="2024-12-31",
            date_opening="2025-01-01",
            name="FY Closing lock test (sale)",
        )
        with self.assertRaises(ValidationError):
            fyc_sale.calculate()
