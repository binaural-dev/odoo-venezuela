from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


@tagged("post_install", "-at_install", "l10n_ve_account_fiscalyear_closing")
class TestAccountFiscalyearClosing(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")

        self.journal = self.env['account.journal'].create({
            'name': 'Sales Journal',
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
        self.account_expense = self.env["account.account"].create({
            "name": "Test Expense",
            "code": "TST02",
            "account_type": "expense",
            "company_ids": [(6, 0, [self.company.id])]
        })
        self.account_equity = self.env["account.account"].create({
            "name": "Equity",
            "code": "EQ01",
            "account_type": "equity_unaffected",
            "company_ids": [(6, 0, [self.company.id])],
        })

    def _create_move_with_balance(self, account, debit=0.0, credit=0.0, date="2025-06-01"):
        move = self.env["account.move"].create({
            "company_id": self.company.id,
            "state": "posted",
            "date": date,
            "journal_id": self.journal.id,
        })
        self.env["account.move.line"].create({
            "move_id": move.id,
            "account_id": account.id,
            "debit": debit,
            "credit": credit,
            "company_id": self.company.id,
            "date": date,
        })
        return move

    def _create_fyc(self, closing_grouping="account"):
        fyc = self.env["account.fiscalyear.closing"].create({
            "name": "FY Closing",
            "company_id": self.company.id,
            "date_start": "2025-01-01",
            "date_end": "2025-12-31",
            "date_opening": "2026-01-01",
            "closing_grouping": closing_grouping,
        })
        return fyc

    def _create_config(self, fyc, name, code, account, move_type="closing", date="2025-12-31"):
        config = self.env["account.fiscalyear.closing.config"].create({
            "name": name,
            "code": code,
            "fyc_id": fyc.id,
            "journal_id": self.journal.id,
            "date": date,
            "move_type": move_type,
            "enabled": True,
        })
        self.env["account.fiscalyear.closing.mapping"].create({
            "name": "Map",
            "src_accounts": account.code,
            "dest_account_id": self.account_equity.id,
            "fyc_config_id": config.id,
        })
        return config

    # --- Tests existentes ---

    def test_onchange_l_map(self):
        fyc = self._create_fyc()
        config = self._create_config(fyc, "Config", "CFG01", self.account_income)
        config.l_map = True
        result = config.onchange_l_map()
        self.assertIn("mapping_ids", result.get("value", {}))

    def test_move_prepare(self):
        fyc = self._create_fyc()
        config = self._create_config(fyc, "Config", "CFG01", self.account_income)
        move_lines = [{"name": "Test Line", "debit": 100, "credit": 0}]
        result = config.move_prepare(move_lines)
        self.assertEqual(result["ref"], config.name)
        self.assertEqual(result["journal_id"], self.journal.id)
        self.assertEqual(result["line_ids"][0][2]["name"], "Test Line")

    def test_mapping_move_lines_get(self):
        fyc = self._create_fyc()
        config = self._create_config(fyc, "Config", "CFG01", self.account_income)
        mapping = config.mapping_ids[0]
        move_lines, rate = config._mapping_move_lines_get(self.account_income.code, mapping)
        self.assertIsInstance(move_lines, list)
        self.assertIsInstance(rate, float)

    def test_draft_moves_check(self):
        fyc = self._create_fyc()
        self._create_config(fyc, "Config", "CFG01", self.account_income)
        move = self.env["account.move"].create({
            "company_id": self.company.id,
            "state": "draft",
            "date": "2025-06-01",
            "journal_id": self.journal.id,
        })
        fyc.check_draft_moves = True
        with self.assertRaises(ValidationError):
            fyc.draft_moves_check()

    def test_move_line_prepare(self):
        fyc = self._create_fyc()
        config = self._create_config(fyc, "Config", "CFG01", self.account_income)
        mapping = config.mapping_ids[0]
        move = self._create_move_with_balance(self.account_income, debit=100)
        line = move.line_ids[0]
        balance, move_line, rate = mapping.move_line_prepare(
            self.account_income, self.env["account.move.line"].browse([line.id])
        )
        self.assertIsInstance(move_line, dict)
        self.assertIsInstance(balance, (int, float))
        self.assertIsInstance(rate, float)

    def test_account_lines_get(self):
        fyc = self._create_fyc()
        config = self._create_config(fyc, "Config", "CFG01", self.account_income)
        mapping = config.mapping_ids[0]
        self._create_move_with_balance(self.account_income, debit=100)
        lines = mapping.account_lines_get(self.account_income)
        self.assertIsInstance(lines, list)

    def test_account_partners_get(self):
        fyc = self._create_fyc()
        config = self._create_config(fyc, "Config", "CFG01", self.account_income)
        mapping = config.mapping_ids[0]
        partners = mapping.account_partners_get(self.account_income)
        self.assertIsInstance(partners, list)

    # --- New grouping tests ---

    def test_calculate_account_grouping(self):
        """1 entry per account (default) — should create 2 moves (income + expense)."""
        fyc = self._create_fyc(closing_grouping="account")
        self._create_config(fyc, "Income Config", "CFG01", self.account_income)
        self._create_config(fyc, "Expense Config", "CFG02", self.account_expense)
        self._create_move_with_balance(self.account_income, debit=0, credit=1000)
        self._create_move_with_balance(self.account_expense, debit=500, credit=0)

        fyc.move_config_ids = [(6, 0, fyc.move_config_ids.ids)]
        fyc.check_draft_moves = False
        result = fyc.calculate()
        self.assertTrue(result)
        self.assertEqual(len(fyc.move_ids), 2)

    def test_calculate_single_grouping(self):
        """1 single entry — should create 1 move with all accounts."""
        fyc = self._create_fyc(closing_grouping="single")
        fyc.single_date = "2025-12-31"
        fyc.single_journal_id = self.journal.id
        self._create_config(fyc, "Income Config", "CFG01", self.account_income)
        self._create_config(fyc, "Expense Config", "CFG02", self.account_expense)
        self._create_move_with_balance(self.account_income, debit=0, credit=1000)
        self._create_move_with_balance(self.account_expense, debit=500, credit=0)

        fyc.move_config_ids = [(6, 0, fyc.move_config_ids.ids)]
        fyc.check_draft_moves = False
        result = fyc.calculate()
        self.assertTrue(result)
        self.assertEqual(len(fyc.move_ids), 1)

    def test_calculate_config_grouping(self):
        """1 entry per configuration — should create 2 moves (1 per config)."""
        fyc = self._create_fyc(closing_grouping="config")
        self._create_config(fyc, "Income Config", "CFG01", self.account_income)
        self._create_config(fyc, "Expense Config", "CFG02", self.account_expense)
        self._create_move_with_balance(self.account_income, debit=0, credit=1000)
        self._create_move_with_balance(self.account_expense, debit=500, credit=0)

        fyc.move_config_ids = [(6, 0, fyc.move_config_ids.ids)]
        fyc.check_draft_moves = False
        result = fyc.calculate()
        self.assertTrue(result)
        self.assertEqual(len(fyc.move_ids), 2)

    def test_calculate_move_balance(self):
        """Verifies the generated move is balanced (debit = credit)."""
        fyc = self._create_fyc(closing_grouping="single")
        fyc.single_date = "2025-12-31"
        fyc.single_journal_id = self.journal.id
        self._create_config(fyc, "Income Config", "CFG01", self.account_income)
        self._create_config(fyc, "Expense Config", "CFG02", self.account_expense)
        self._create_move_with_balance(self.account_income, debit=0, credit=1000)
        self._create_move_with_balance(self.account_expense, debit=500, credit=0)

        fyc.move_config_ids = [(6, 0, fyc.move_config_ids.ids)]
        fyc.check_draft_moves = False
        fyc.calculate()
        move = fyc.move_ids[0]
        total_debit = sum(move.line_ids.mapped("debit"))
        total_credit = sum(move.line_ids.mapped("credit"))
        self.assertAlmostEqual(total_debit, total_credit, places=2)

    def test_aggregate_balances(self):
        """_aggregate_balances sums balances from different subsidiaries."""
        fyc = self._create_fyc()
        raw = [
            {"account_id": self.account_income.id, "balance": 600.0, "foreign_balance": 0.0, "analytic_account_id": 1},
            {"account_id": self.account_income.id, "balance": 400.0, "foreign_balance": 0.0, "analytic_account_id": 2},
        ]
        result = fyc._aggregate_balances(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["balance"], 1000.0)
        self.assertFalse(result[0]["analytic_account_id"])
