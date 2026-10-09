from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_pos", "foreign_amount")
class TestLockForeignAmount(TransactionCase):
    """
    Regression tests for pos.session._lock_foreign_amount (Ticket #13055).

    Context: the "monto alterno" (foreign_debit/foreign_credit) of a POS
    combined/split payment line is a computed field. pos_session.py fixes its
    value once, at session-close time, by writing it directly and setting
    not_foreign_recalculate=True. That flag only protects the value while the
    exact same account.move.line record survives untouched: if the line is
    ever recreated (e.g. an asiento reset to draft and reposted to "fix"
    something unrelated), the new line starts with not_foreign_recalculate
    False, and account.move.line._compute_foreign_debit_credit falls back to
    `debit * foreign_inverse_rate` using whatever rate the move has *at that
    later moment* -- not the rate(s) of the original POS payment(s) -- which
    is exactly how a correct amount (e.g. $683,19) turned into a wildly wrong
    one (e.g. $13.640.153,61) in the reported bug.

    The fix also pins foreign_debit_adjustment/foreign_credit_adjustment,
    which _compute_foreign_debit_credit honors unconditionally, regardless of
    not_foreign_recalculate. These tests exercise that mechanism directly,
    without needing to spin up a full POS session.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.currency_usd = cls.env.ref("base.USD")
        cls.currency_vef = cls.env.ref("base.VEF")
        cls.company = cls.env.ref("base.main_company")
        cls.company.write(
            {
                "currency_id": cls.currency_usd.id,
                "currency_foreign_id": cls.currency_vef.id,
            }
        )

        cls.account_a = cls.env["account.account"].create(
            {
                "name": "Test Receivable A",
                "code": "TST001",
                "account_type": "asset_current",
            }
        )
        cls.account_b = cls.env["account.account"].create(
            {
                "name": "Test Receivable B",
                "code": "TST002",
                "account_type": "asset_current",
            }
        )
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", cls.company.id)], limit=1
        ) or cls.env["account.journal"].create(
            {
                "name": "Test Misc Ops",
                "type": "general",
                "code": "TMISC",
                "company_id": cls.company.id,
            }
        )

        # Rate deliberately different from the historical/pinned amount used in
        # each test, so a value coming from the buggy generic recompute
        # (debit * foreign_inverse_rate) is unmistakably distinct from the
        # correct, pinned "monto alterno".
        cls.foreign_rate = 50.0
        cls.foreign_inverse_rate = 0.02  # 1 / 50

    def _create_move(self, debit_amount=1000.0):
        move = self.env["account.move"].create(
            {
                "journal_id": self.journal.id,
                "manually_set_rate": True,
                "foreign_rate": self.foreign_rate,
                "foreign_inverse_rate": self.foreign_inverse_rate,
                "line_ids": [
                    Command.create(
                        {
                            "name": "Debit line",
                            "account_id": self.account_a.id,
                            "currency_id": self.company.currency_id.id,
                            "debit": debit_amount,
                            "credit": 0.0,
                        }
                    ),
                    Command.create(
                        {
                            "name": "Credit line",
                            "account_id": self.account_b.id,
                            "currency_id": self.company.currency_id.id,
                            "debit": 0.0,
                            "credit": debit_amount,
                        }
                    ),
                ],
            }
        )
        debit_line = move.line_ids.filtered(lambda l: l.debit > 0)
        credit_line = move.line_ids.filtered(lambda l: l.credit > 0)
        return move, debit_line, credit_line

    def test_lock_foreign_amount_pins_debit_and_credit(self):
        """_lock_foreign_amount must set the raw amount, the flag and the
        durable adjustment field on both sides of the entry."""
        _move, debit_line, credit_line = self._create_move()
        pinned_amount = 42.5

        self.env["pos.session"]._lock_foreign_amount(debit_line, pinned_amount)
        self.env["pos.session"]._lock_foreign_amount(credit_line, pinned_amount)

        self.assertTrue(debit_line.not_foreign_recalculate)
        self.assertAlmostEqual(debit_line.foreign_debit, pinned_amount)
        self.assertAlmostEqual(debit_line.foreign_debit_adjustment, pinned_amount)
        self.assertAlmostEqual(debit_line.foreign_credit, 0.0)

        self.assertTrue(credit_line.not_foreign_recalculate)
        self.assertAlmostEqual(credit_line.foreign_credit, pinned_amount)
        self.assertAlmostEqual(credit_line.foreign_credit_adjustment, pinned_amount)

    def test_pinned_amount_survives_flag_loss(self):
        """
        This is the actual bug fix: if not_foreign_recalculate is ever lost on
        an already-pinned line (e.g. because the line was recreated by a
        generic repost/recompute flow), the amount must stay correct instead
        of silently falling back to debit * foreign_inverse_rate.
        """
        _move, debit_line, _credit_line = self._create_move()
        pinned_amount = 42.5

        self.env["pos.session"]._lock_foreign_amount(debit_line, pinned_amount)
        self.assertAlmostEqual(debit_line.foreign_debit, pinned_amount)

        # Simulate the flag being lost (e.g. a fresh line created without
        # going through pos_session.py) and force a recompute, as would
        # happen when any of the real @api.depends fields changes.
        debit_line.not_foreign_recalculate = False
        debit_line._compute_foreign_debit_credit()

        self.assertAlmostEqual(
            debit_line.foreign_debit,
            pinned_amount,
            msg="foreign_debit_adjustment should have kept the historical "
            "amount even though not_foreign_recalculate was reset.",
        )

    def test_without_the_fix_the_amount_would_be_corrupted(self):
        """
        Documents the bug being fixed: pinning only foreign_debit +
        not_foreign_recalculate (the old behaviour, without the adjustment
        field) does NOT survive the flag being lost -- the generic recompute
        overwrites it with debit * foreign_inverse_rate, reproducing the
        reported regression (a correct amount replaced by an unrelated one).
        """
        _move, debit_line, _credit_line = self._create_move(debit_amount=1000.0)
        pinned_amount = 42.5

        # Old (buggy) protection: raw value + flag, no adjustment field.
        debit_line.not_foreign_recalculate = True
        debit_line.foreign_debit = pinned_amount
        self.assertAlmostEqual(debit_line.foreign_debit, pinned_amount)

        debit_line.not_foreign_recalculate = False
        debit_line._compute_foreign_debit_credit()

        expected_wrong_amount = 1000.0 * self.foreign_inverse_rate  # 20.0
        self.assertNotAlmostEqual(debit_line.foreign_debit, pinned_amount)
        self.assertAlmostEqual(debit_line.foreign_debit, expected_wrong_amount)
