"""Migration of ``apply_igtf`` from the payment method to its currency settings (ADR-023)."""

import importlib.util
import os

from odoo.tests import TransactionCase, tagged

import odoo.addons.l10n_ve_pos_igtf as module

MIGRATION = os.path.join(
    os.path.dirname(module.__file__), "migrations", "20.0.1.0.0", "post-migrate.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("l10n_ve_pos_igtf_post_migrate", MIGRATION)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


@tagged("post_install", "-at_install", "l10n_ve_pos_igtf")
class TestPosIgtfDataMigration(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        cls.usd = cls.env.ref("base.USD")
        cls.eur = cls.env.ref("base.EUR")
        cls.usd.active = True
        cls.eur.active = True
        cls.cash = cls.env["pos.payment.method"].create(
            {
                "name": "Cash",
                "type": "cash",
                "company_id": cls.company.id,
                "journal_id": cls.env["account.journal"]
                .search([("type", "=", "cash"), ("company_id", "=", cls.company.id)], limit=1)
                .id,
                "currency_ids": [(6, 0, (cls.usd | cls.eur).ids)],
            }
        )
        cls.Setting = cls.env["pos.payment.method.currency"]
        cls.usd_setting = cls.Setting.create(
            {"payment_method_id": cls.cash.id, "currency_id": cls.usd.id}
        )
        cls.eur_setting = cls.Setting.create(
            {"payment_method_id": cls.cash.id, "currency_id": cls.eur.id}
        )

    def _plan(self, rows, done=True):
        self.env.cr.execute("DROP TABLE IF EXISTS l10n_ve_pos_method_merge")
        self.env.cr.execute(
            """
            CREATE TABLE l10n_ve_pos_method_merge (
                id SERIAL PRIMARY KEY, config_id INTEGER, keeper_id INTEGER NOT NULL,
                old_id INTEGER NOT NULL, currency_id INTEGER, cross_journal INTEGER,
                cross_account_journal INTEGER, apply_igtf BOOLEAN DEFAULT FALSE,
                done BOOLEAN DEFAULT FALSE
            )
            """
        )
        for keeper, old, currency, apply_igtf in rows:
            self.env.cr.execute(
                "INSERT INTO l10n_ve_pos_method_merge "
                "(keeper_id, old_id, currency_id, apply_igtf, done) VALUES (%s, %s, %s, %s, %s)",
                (keeper, old, currency, apply_igtf, done),
            )

    def _table_exists(self):
        self.env.cr.execute("SELECT to_regclass('l10n_ve_pos_method_merge')")
        return bool(self.env.cr.fetchone()[0])

    def _migrate(self):
        self.env.flush_all()
        _load_migration().migrate(self.env.cr, "19.0.1.5.0")
        self.Setting.invalidate_model()

    def test_flag_goes_to_the_setting_of_the_merged_currency(self):
        self._plan(
            [
                (self.cash.id, self.cash.id + 1000, self.usd.id, True),
                (self.cash.id, self.cash.id + 1001, self.eur.id, False),
            ]
        )

        self._migrate()

        self.assertTrue(self.usd_setting.apply_igtf)
        self.assertFalse(self.eur_setting.apply_igtf)
        self.assertTrue(self._table_exists(), "the end script of l10n_ve_pos drops it")

    def test_flag_is_kept_when_any_old_method_of_the_pair_had_it(self):
        self._plan(
            [
                (self.cash.id, self.cash.id + 1000, self.usd.id, False),
                (self.cash.id, self.cash.id + 1001, self.usd.id, True),
            ]
        )

        self._migrate()

        self.assertTrue(self.usd_setting.apply_igtf)

    def test_plan_not_applied_yet_is_kept(self):
        self._plan([(self.cash.id, self.cash.id + 1000, self.usd.id, True)], done=False)

        self._migrate()

        self.assertFalse(self.usd_setting.apply_igtf)
        self.assertTrue(self._table_exists())

    def test_nothing_to_do_without_the_plan(self):
        self.env.cr.execute("DROP TABLE IF EXISTS l10n_ve_pos_method_merge")

        self._migrate()

        self.assertFalse(self.usd_setting.apply_igtf)

    def test_fresh_install_has_nothing_to_migrate(self):
        self._plan([(self.cash.id, self.cash.id, self.usd.id, True)])

        _load_migration().migrate(self.env.cr, False)

        self.assertTrue(self._table_exists())
