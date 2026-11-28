"""``end-migrate.py`` drops the plan of the merge of the payment methods once every
module that reads it has run its ``post-migrate.py``, whatever order they ran in."""

import importlib.util

from odoo.tests import TransactionCase, tagged
from odoo.tools import file_path


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, file_path(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged("post_install", "-at_install", "l10n_ve_pos", "pos_method_merge_end")
class TestPosMethodMergeEndMigration(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        cls.usd = cls.env.ref("base.USD")
        cls.usd.active = True
        journal = cls.env["account.journal"].create(
            {"name": "Cash merge end", "code": "CME", "type": "cash", "company_id": cls.company.id}
        )
        cls.cash = cls.env["pos.payment.method"].create(
            {
                "name": "Cash merge end",
                "type": "cash",
                "company_id": cls.company.id,
                "journal_id": journal.id,
                "currency_ids": [(6, 0, cls.usd.ids)],
            }
        )
        cls.setting = cls.env["pos.payment.method.currency"].create(
            {"payment_method_id": cls.cash.id, "currency_id": cls.usd.id}
        )
        cls.end = _load("l10n_ve_pos/migrations/20.0.1.0.0/end-migrate.py", "pos_end_migrate")

    def _plan(self, done=True):
        cr = self.env.cr
        cr.execute("DROP TABLE IF EXISTS l10n_ve_pos_method_merge")
        cr.execute(
            """
            CREATE TABLE l10n_ve_pos_method_merge (
                id SERIAL PRIMARY KEY, config_id INTEGER, keeper_id INTEGER NOT NULL,
                old_id INTEGER NOT NULL, currency_id INTEGER, cross_journal INTEGER,
                cross_account_journal INTEGER, apply_igtf BOOLEAN DEFAULT FALSE,
                done BOOLEAN DEFAULT FALSE
            )
            """
        )
        cr.execute(
            "INSERT INTO l10n_ve_pos_method_merge "
            "(keeper_id, old_id, currency_id, apply_igtf, done) VALUES (%s, %s, %s, TRUE, %s)",
            (self.cash.id, self.cash.id + 1000, self.usd.id, done),
        )

    def _table_exists(self):
        self.env.cr.execute("SELECT to_regclass('l10n_ve_pos_method_merge')")
        return bool(self.env.cr.fetchone()[0])

    def _installed(self, name):
        module = self.env["ir.module.module"].search([("name", "=", name), ("state", "=", "installed")])
        return bool(module)

    def test_table_is_dropped_when_the_plan_is_applied(self):
        self._plan()
        self.end.migrate(self.env.cr, "19.0.1.0.0")
        self.assertFalse(self._table_exists())

    def test_table_is_kept_when_the_plan_was_not_applied(self):
        self._plan(done=False)
        self.end.migrate(self.env.cr, "19.0.1.0.0")
        self.assertTrue(self._table_exists())

    def test_table_is_kept_while_a_reader_has_not_migrated(self):
        reader = self.env["ir.module.module"].search(
            [("name", "in", list(self.end.READERS)), ("state", "=", "installed")], limit=1
        )
        if not reader:
            self.skipTest("neither l10n_ve_pos_igtf nor l10n_ve_pos_mf is installed")
        self._plan()
        self.env.cr.execute(
            "UPDATE ir_module_module SET latest_version = '19.0.9.9' WHERE id = %s", (reader.id,)
        )
        self.end.migrate(self.env.cr, "19.0.1.0.0")
        self.assertTrue(self._table_exists())

    def test_fresh_install_does_nothing(self):
        self._plan()
        self.end.migrate(self.env.cr, False)
        self.assertTrue(self._table_exists())

    def test_without_the_plan_does_nothing(self):
        self.env.cr.execute("DROP TABLE IF EXISTS l10n_ve_pos_method_merge")
        self.end.migrate(self.env.cr, "19.0.1.0.0")
        self.assertFalse(self._table_exists())

    def test_readers_find_the_table_in_any_order(self):
        if not (self._installed("l10n_ve_pos_igtf") and self._installed("l10n_ve_pos_mf")):
            self.skipTest("l10n_ve_pos_igtf and l10n_ve_pos_mf are needed")
        igtf = _load("l10n_ve_pos_igtf/migrations/20.0.1.0.0/post-migrate.py", "igtf_post")
        fiscal = _load("l10n_ve_pos_mf/migrations/20.0.1.0.0/post-migrate.py", "mf_post")
        for readers in ((igtf, fiscal), (fiscal, igtf)):
            self._plan()
            self.env.flush_all()
            for reader in readers:
                reader.migrate(self.env.cr, "19.0.1.0.0")
                self.assertTrue(self._table_exists())
            self.env.invalidate_all()
            self.assertTrue(self.setting.apply_igtf)
            self.setting.apply_igtf = False
            self.env.flush_all()
        self.end.migrate(self.env.cr, "19.0.1.0.0")
        self.assertFalse(self._table_exists())
