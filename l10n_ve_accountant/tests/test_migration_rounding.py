import importlib.util
from pathlib import Path

from odoo.tests import TransactionCase, tagged
from odoo import fields, Command

MIG_56 = Path(__file__).resolve().parent.parent / "migrations" / "17.0.0.0.56" / "post-migration.py"


def _load_migration_56():
    spec = importlib.util.spec_from_file_location("l10n_ve_accountant_mig_56", MIG_56)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@tagged("post_install", "-at_install", "l10n_ve_accountant")
class TestMigrationRounding(TransactionCase):

    def setUp(self):
        super().setUp()
        self.mod = _load_migration_56()
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")
        self.company.write({
            "currency_id": self.currency_vef.id,
            "currency_foreign_id": self.currency_usd.id,
        })
        self.env["res.currency.rate"].create({
            "name": fields.Date.today(), "currency_id": self.currency_usd.id,
            "inverse_company_rate": 50.0, "company_id": self.company.id,
        })

        self.acc_rec = self._acc("2990", "Mig Receivable", "asset_receivable", reconcile=True)
        self.acc_inc = self._acc("4990", "Mig Income", "income")
        self.sale_journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].create({
            "name": "Sales Mig", "code": "SMIG", "type": "sale",
            "company_id": self.company.id, "default_account_id": self.acc_inc.id,
        })
        self.general_journal = self.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].create({
            "name": "General Mig", "code": "GMIG", "type": "general",
            "company_id": self.company.id,
        })
        self.partner = self.env["res.partner"].create({
            "name": "Mig Partner", "property_account_receivable_id": self.acc_rec.id,
        })
        self.product = self.env["product.product"].create({
            "name": "Mig Product", "type": "service",
            "property_account_income_id": self.acc_inc.id,
        })

    def _acc(self, code, name, atype, reconcile=False):
        acc = self.env["account.account"].search([
            ("code", "=", code), ("company_id", "=", self.company.id),
        ], limit=1)
        if not acc:
            acc = self.env["account.account"].create({
                "code": code, "name": name, "account_type": atype,
                "company_id": self.company.id, "reconcile": reconcile,
            })
        return acc

    def _posted_move(self):
        inv = self.env["account.move"].with_context(check_move_validity=False).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_vef.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [Command.create({
                "product_id": self.product.id, "name": "Mig Line",
                "quantity": 1.0, "price_unit": 100.0,
                "account_id": self.acc_inc.id,
            })],
        })
        inv.with_context(move_action_post_alert=True).action_post()
        self.env.flush_all()
        return inv

    def _dirty(self, move_id, value=1.23456):
        self.env.cr.execute(
            "UPDATE account_move_line SET foreign_debit = %s, foreign_credit = 0.0 "
            "WHERE move_id = %s",
            (value, move_id),
        )

    def _line_value(self, move_id, account):
        self.env.cr.execute(
            "SELECT foreign_debit, foreign_credit FROM account_move_line "
            "WHERE move_id = %s AND account_id = %s",
            (move_id, account.id),
        )
        return self.env.cr.fetchone()

    def test_rounding_skips_locked_period(self):
        inv = self._posted_move()
        self._dirty(inv.id)

        self.company.tax_lock_date = fields.Date.today()
        self.mod._do_sql_rounding(
            self.env.cr, self.company, self.currency_usd.id, 2, ("posted",),
        )
        self.assertEqual(
            self._line_value(inv.id, self.acc_inc), (1.23456, 0.0),
            "locked period must be skipped by the rounding",
        )

        self.company.tax_lock_date = False
        self.mod._do_sql_rounding(
            self.env.cr, self.company, self.currency_usd.id, 2, ("posted",),
        )
        self.assertEqual(
            self._line_value(inv.id, self.acc_inc), (1.23, 0.0),
            "unlocked period must be rounded",
        )

    def test_rounding_skips_excluded_moves(self):
        inv = self._posted_move()
        self._dirty(inv.id)

        self.mod._do_sql_rounding(
            self.env.cr, self.company, self.currency_usd.id, 2, ("posted",),
            excluded_move_ids=[inv.id],
        )
        self.assertEqual(
            self._line_value(inv.id, self.acc_inc), (1.23456, 0.0),
            "excluded (reconciled) moves must not be rounded",
        )

        self.mod._do_sql_rounding(
            self.env.cr, self.company, self.currency_usd.id, 2, ("posted",),
        )
        self.assertEqual(
            self._line_value(inv.id, self.acc_inc), (1.23, 0.0),
            "move without exclusion must be rounded",
        )

    def test_reconciled_move_ids_detected_after_settlement(self):
        inv = self._posted_move()
        self.assertNotIn(
            inv.id, self.mod._reconciled_move_ids(
                self.env.cr, self.company, ("posted",)),
            "move must not be detected as reconciled before settlement",
        )

        rec_line = inv.line_ids.filtered(
            lambda l: l.account_id == self.acc_rec)[:1]
        self.assertTrue(rec_line)

        settle_vef = rec_line.amount_currency
        other = self.env["account.move"].with_context(check_move_validity=False).create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "currency_id": self.currency_vef.id,
            "line_ids": [
                Command.create({"account_id": self.acc_rec.id, "credit": settle_vef,
                                "debit": 0.0, "name": "pay"}),
                Command.create({"account_id": self.acc_inc.id, "debit": settle_vef,
                                "credit": 0.0, "name": "x"}),
            ],
        })
        other.action_post()
        self.env.flush_all()
        pay_line = other.line_ids.filtered(
            lambda l: l.account_id == self.acc_rec)[:1]
        (rec_line + pay_line).reconcile()
        self.env.flush_all()

        self.assertIn(
            inv.id, self.mod._reconciled_move_ids(
                self.env.cr, self.company, ("posted",)),
            "move must be detected as reconciled after settlement",
        )

    def test_balance_repair_after_rounding(self):
        inv = self._posted_move()
        lines = inv.line_ids[:2]
        self.assertEqual(len(lines), 2)
        self.env.cr.execute(
            "UPDATE account_move_line "
            "SET foreign_debit = CASE WHEN id = %(a)s THEN 1.239 ELSE 0.0 END, "
            "    foreign_credit = CASE WHEN id = %(b)s THEN 1.217 ELSE 0.0 END "
            "WHERE move_id = %(m)s",
            {"m": inv.id, "a": lines[0].id, "b": lines[1].id},
        )

        self.mod._do_sql_rounding(
            self.env.cr, self.company, self.currency_usd.id, 2, ("posted",),
        )
        self.mod._check_and_fix_balance(
            self.env.cr, self.company, ("posted",),
        )

        self.env.cr.execute(
            "SELECT SUM(foreign_debit) - SUM(foreign_credit) "
            "FROM account_move_line WHERE move_id = %s",
            (inv.id,),
        )
        delta = self.env.cr.fetchone()[0]
        self.assertLessEqual(
            abs(delta or 0.0), 0.001,
            "move must remain balanced after rounding + repair, got delta=%s" % delta,
        )
