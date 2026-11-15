import importlib.util

from odoo.tests import TransactionCase, tagged
from odoo.tools import file_path


@tagged("post_install", "-at_install", "l10n_ve_pos_mf")
class TestFiscalCode(TransactionCase):
    """The fiscal printer code of a payment depends on the method and on the
    currency the customer paid with (ADR-023: one cash method for bolivares,
    dollars and euros)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vef = cls.env.ref("base.VEF")
        cls.usd = cls.env.ref("base.USD")
        cls.eur = cls.env.ref("base.EUR")
        for currency in (cls.vef, cls.usd, cls.eur):
            currency.active = True
        journal = cls.env["account.journal"].create(
            {"name": "Cash fiscal code", "code": "CFC", "type": "cash"}
        )
        cls.cash = cls.env["pos.payment.method"].create(
            {
                "name": "Efectivo",
                "journal_id": journal.id,
                "type": "cash",
                "code_fiscal_printer": "01",
                "currency_ids": [(6, 0, (cls.vef | cls.usd | cls.eur).ids)],
            }
        )
        cls.Setting = cls.env["pos.payment.method.currency"]
        cls.Setting.create(
            {
                "payment_method_id": cls.cash.id,
                "currency_id": cls.usd.id,
                "code_fiscal_printer": "20",
            }
        )
        cls.Setting.create(
            {"payment_method_id": cls.cash.id, "currency_id": cls.eur.id}
        )

    def test_01_code_of_the_currency_setting(self):
        self.assertEqual(self.cash._get_fiscal_code(self.usd), "20")

    def test_02_currency_without_code_uses_the_method(self):
        self.assertEqual(self.cash._get_fiscal_code(self.eur), "01")

    def test_03_currency_without_setting_uses_the_method(self):
        self.assertEqual(self.cash._get_fiscal_code(self.vef), "01")
        self.assertEqual(self.cash._get_fiscal_code(), "01")

    def test_04_payment_in_foreign_currency(self):
        payment = self.env["pos.payment"].new(
            {"payment_method_id": self.cash.id, "foreign_currency_id": self.usd.id}
        )
        self.assertEqual(payment._get_fiscal_code(), "20")

    def test_04b_credit_note_code_of_a_pos_payment(self):
        move = self.env["account.move"]
        if not hasattr(move, "_mf_pos_payment_fiscal_code"):
            self.skipTest("l10n_ve_account_mf is not installed")
        values = {"payment_method_id": self.cash.id}
        usd = self.env["pos.payment"].new({**values, "foreign_currency_id": self.usd.id})
        eur = self.env["pos.payment"].new({**values, "foreign_currency_id": self.eur.id})
        bs = self.env["pos.payment"].new(values)
        self.assertEqual(move._mf_pos_payment_fiscal_code(usd), "20")
        self.assertEqual(move._mf_pos_payment_fiscal_code(eur), "01")
        self.assertEqual(move._mf_pos_payment_fiscal_code(bs), "01")

    def test_05_setting_is_loaded_in_the_pos(self):
        fields_list = self.Setting._load_pos_data_fields(self.env["pos.config"])
        self.assertIn("code_fiscal_printer", fields_list)

    def test_06_migration_carries_the_code_of_the_merged_methods(self):
        cr = self.env.cr
        journal = self.cash.journal_id
        old = self.env["pos.payment.method"].create(
            {
                "name": "Efectivo EUR old",
                "journal_id": journal.id,
                "type": "cash",
                "code_fiscal_printer": "21",
            }
        )
        cr.execute(
            """
            CREATE TABLE IF NOT EXISTS l10n_ve_pos_method_merge (
                id SERIAL PRIMARY KEY, config_id INTEGER, keeper_id INTEGER NOT NULL,
                old_id INTEGER NOT NULL, currency_id INTEGER, cross_journal INTEGER,
                cross_account_journal INTEGER, apply_igtf BOOLEAN DEFAULT FALSE,
                done BOOLEAN DEFAULT FALSE)
            """
        )
        cr.execute(
            "INSERT INTO l10n_ve_pos_method_merge (keeper_id, old_id, currency_id, done) "
            "VALUES (%s, %s, %s, TRUE)",
            (self.cash.id, old.id, self.eur.id),
        )
        path = file_path("l10n_ve_pos_mf/migrations/20.0.1.0.0/post-migrate.py")
        spec = importlib.util.spec_from_file_location("post_migrate_pos_mf", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.migrate(cr, "19.0.3.1.3")
        self.env.invalidate_all()
        self.assertEqual(self.cash._get_fiscal_code(self.eur), "21")
        self.assertEqual(self.cash._get_fiscal_code(self.usd), "20")
        cr.execute("SELECT to_regclass('l10n_ve_pos_method_merge')")
        self.assertTrue(cr.fetchone()[0], "the end script of l10n_ve_pos drops the plan")
