from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
# Note: Run these tests after the l10n_ve_accountant module has been migrated to Odoo 18.
# The functionality of account fiscal year closing depends on features provided by l10n_ve_accountant.
# Ensure l10n_ve_accountant migration is complete and stable before executing these tests.
@tagged("post_install", "-at_install", "l10n_ve_account_fiscalyear_closing")
class TestAccountFiscalyearClosing(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        
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

    def test_calculate(self):
        move = self.env["account.move"].create({
            "company_id": self.company.id,
            "state": "posted",
            "date": "2025-06-01",
            "journal_id": self.journal.id,
        })
        self.env["account.move.line"].create({
            "move_id": move.id,
            "account_id": self.account_income.id,
            "debit": 100,
            "credit": 0,
            "company_id": self.company.id,
            "date": "2025-06-01",
        })
        self.fyc.move_config_ids = [(6, 0, [self.config.id])]
        self.fyc.check_draft_moves = False
        result = self.fyc.calculate()
        self.assertTrue(result)

    def test_move_line_prepare(self):
        # Simula líneas de cuenta
        move = self.env["account.move"].create({
            "company_id": self.company.id,
            "state": "posted",
            "date": "2025-06-01",
            "journal_id": self.journal.id,
        })
        line = self.env["account.move.line"].create({
            "move_id": move.id,
            "account_id": self.account_income.id,
            "debit": 100,
            "credit": 0,
            "company_id": self.company.id,
            "date": "2025-06-01",
            "foreign_debit": 0,
            "foreign_credit": 0,
            "foreign_currency_id": self.env.ref("base.VEF").id,
        })
        balance, move_line, rate = self.mapping.move_line_prepare(self.account_income, self.env["account.move.line"].browse([line.id]))
        self.assertIsInstance(move_line, dict)
        self.assertIsInstance(balance, (int, float))
        self.assertIsInstance(rate, float)

    def test_account_lines_get(self):
        lines = self.mapping.account_lines_get(self.account_income)
        self.assertIsInstance(lines, list)

    def test_account_partners_get(self):
        partners = self.mapping.account_partners_get(self.account_income)
        self.assertIsInstance(partners, list)