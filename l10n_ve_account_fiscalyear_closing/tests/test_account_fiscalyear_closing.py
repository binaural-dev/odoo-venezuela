from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
@tagged("post_install", "-at_install", "l10n_ve_account_fiscalyear_closing")
class TestAccountFiscalyearClosing(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        # VEF is inactive by default on a fresh DB that doesn't use the VE
        # chart template; posting a move on an inactive currency raises a
        # UserError, so tests that actually post (action_post) need it on.
        self.env.ref("base.VEF").active = True

        self.journal = self.env['account.journal'].create({
            'name': 'Diario de Ventas',
            'code': 'VEN',
            'type': 'sale',
            'company_id': self.company.id,
        })
        self.account_income = self.env["account.account"].create({
            "name": "Test Income",
            "code": "TST01",
            "account_type": "income",
            "company_ids": [(6, 0, [self.company.id])]
        })
        self.account_equity = self.env["account.account"].create({
            "name": "Equity",
            "code": "EQ01",
            "account_type": "equity_unaffected",
            "company_ids": [(6, 0, [self.company.id])],
        })
        self.fyc = self.env["account.fiscalyear.closing"].create({
            "name": "FY Closing",
            "company_id": self.company.id,
            "date_start": "2025-01-01",
            "date_end": "2025-12-31",
            "date_opening": "2026-01-01",
        })
        self.config = self.env["account.fiscalyear.closing.config"].create({
            "name": "Config",
            "code": "CFG01",
            "fyc_id": self.fyc.id,
            "journal_id": self.journal.id,
            "date": "2025-12-31",
            "move_type": "closing",
            "enabled": True,
        })
        self.mapping = self.env["account.fiscalyear.closing.mapping"].create({
            "name": "Map",
            "src_accounts": self.account_income.code,
            "dest_account_id": self.account_equity.id,
            "fyc_config_id": self.config.id,
        })

    def test_onchange_l_map(self):
        self.config.l_map = True
        result = self.config.onchange_l_map()
        self.assertIn("mapping_ids", result.get("value", {}))

    def test_move_prepare(self):
        move_lines = [{"name": "Test Line", "debit": 100, "credit": 0}]
        result = self.config.move_prepare(move_lines)
        self.assertEqual(result["ref"], self.config.name)
        self.assertEqual(result["journal_id"], self.journal.id)
        self.assertEqual(result["line_ids"][0][2]["name"], "Test Line")

    def test_mapping_move_lines_get(self):
        move_lines, rate = self.config._mapping_move_lines_get(self.account_income.code, self.mapping)
        self.assertIsInstance(move_lines, list)
        self.assertIsInstance(rate, float)

    def test_draft_moves_check(self):
        move = self.env["account.move"].create({
            "company_id": self.company.id,
            "state": "draft",
            "date": "2025-06-01",
            "journal_id": self.journal.id,
        })
        self.fyc.check_draft_moves = True
        with self.assertRaises(ValidationError):
            self.fyc.draft_moves_check()

    def _create_posted_move(self, extra_line_vals=None):
        """Odoo does not allow creating a move directly in the 'posted'
        state (``account.move.create`` raises a ``UserError``: "You cannot
        create a move already in the posted state. Please create a draft
        move and post it after."). Build a balanced draft move with the
        income line plus a counterpart on the equity account and post it
        through ``action_post`` instead."""
        line_vals = {
            "account_id": self.account_income.id,
            "debit": 100,
            "credit": 0,
            "date": "2025-06-01",
        }
        if extra_line_vals:
            line_vals.update(extra_line_vals)
        move = self.env["account.move"].create({
            "company_id": self.company.id,
            "date": "2025-06-01",
            "journal_id": self.journal.id,
            "line_ids": [
                (0, 0, line_vals),
                (
                    0,
                    0,
                    {
                        "account_id": self.account_equity.id,
                        "debit": 0,
                        "credit": 100,
                        "date": "2025-06-01",
                    },
                ),
            ],
        })
        move.action_post()
        self.assertEqual(move.state, "posted")
        return move

    def test_calculate(self):
        self._create_posted_move()
        self.fyc.move_config_ids = [(6, 0, [self.config.id])]
        self.fyc.check_draft_moves = False
        result = self.fyc.calculate()
        self.assertTrue(result)

    def test_calculate_ignores_mapping_dest_account_and_uses_global_equity(self):
        # The VE calculate() completely replaces the base module's flow: it
        # resolves ONE global equity_unaffected account for the whole
        # closing (see calculate()'s dest_account lookup) and ignores each
        # mapping's own dest_account_id entirely, unlike the OCA base
        # module's moves_create()/_mapping_move_lines_get(). Point the
        # mapping at an unrelated account to prove it has no effect.
        unrelated_account = self.env["account.account"].create(
            {
                "name": "Unrelated destination (must be ignored)",
                "code": "UNREL01",
                "account_type": "expense",
                "company_ids": [(6, 0, [self.company.id])],
            }
        )
        self.mapping.dest_account_id = unrelated_account.id
        self._create_posted_move()
        self.fyc.move_config_ids = [(6, 0, [self.config.id])]
        self.fyc.check_draft_moves = False

        result = self.fyc.calculate()
        self.assertTrue(result)

        result_lines = self.env["account.move.line"].search(
            [("move_id.fyc_id", "=", self.fyc.id), ("name", "=", "Result")]
        )
        self.assertEqual(len(result_lines), 1)
        # The mapping's own dest_account_id (unrelated_account, an expense
        # account) must have no effect: calculate() always resolves its own
        # single global equity_unaffected account for the company instead.
        self.assertNotEqual(result_lines.account_id, unrelated_account)
        self.assertEqual(result_lines.account_id.account_type, "equity_unaffected")

    def test_calculate_raises_when_nothing_to_close(self):
        # account_income has no moves at all in setUp, so the mapped
        # account never has a balance: calculate() must not silently mark
        # the closing as "calculated" with 0 moves generated.
        self.fyc.move_config_ids = [(6, 0, [self.config.id])]
        self.fyc.check_draft_moves = False
        with self.assertRaisesRegex(
            UserError, "No fiscal closing entries were generated"
        ):
            self.fyc.calculate()
        self.assertEqual(len(self.fyc.move_ids), 0)
        self.assertEqual(self.fyc.state, "draft")

    def test_button_calculate_does_not_mark_calculated_when_empty(self):
        self.fyc.move_config_ids = [(6, 0, [self.config.id])]
        self.fyc.check_draft_moves = False
        with self.assertRaisesRegex(
            UserError, "No fiscal closing entries were generated"
        ):
            self.fyc.button_calculate()
        self.assertEqual(self.fyc.state, "draft")
        self.assertFalse(self.fyc.calculation_date)

    def test_move_line_prepare(self):
        # Simula líneas de cuenta
        move = self._create_posted_move(
            extra_line_vals={
                "foreign_debit": 0,
                "foreign_credit": 0,
                "foreign_currency_id": self.env.ref("base.VEF").id,
            }
        )
        line = move.line_ids.filtered(lambda x: x.account_id == self.account_income)
        self.assertEqual(len(line), 1)
        balance, move_line, rate = self.mapping.move_line_prepare(self.account_income, line)
        self.assertIsInstance(move_line, dict)
        self.assertAlmostEqual(balance, 100.0)
        # move_line_prepare builds the *closing* (reversal) line: a positive
        # source balance (debit=100, credit=0 -> balance=100) is closed out
        # with a credit line, so "debit" stays False and "credit" is 100.0.
        self.assertEqual(move_line["debit"], False)
        self.assertEqual(move_line["credit"], 100.0)
        self.assertIsInstance(rate, float)
        # foreign_debit/foreign_credit are computed fields (see
        # l10n_ve_accountant account_move_line._compute_foreign_debit_credit):
        # the explicit 0 passed at create() is not honored, they are derived
        # from the move currency vs. the company's foreign_currency_id. With
        # the default test company setup both currencies produce the same
        # foreign_balance as the base balance, so rate = |balance/balance| = 1.0
        self.assertAlmostEqual(rate, 1.0)

    def test_account_lines_get(self):
        lines = self.mapping.account_lines_get(self.account_income)
        self.assertIsInstance(lines, list)

    def test_account_partners_get(self):
        partners = self.mapping.account_partners_get(self.account_income)
        self.assertIsInstance(partners, list)