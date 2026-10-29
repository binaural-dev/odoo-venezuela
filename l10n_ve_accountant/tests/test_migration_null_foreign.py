# Ticket #15729: migration 17.0.0.0.56 left foreign_balance NULL when one side was NULL,
# and 17.0.0.0.66 repairs the lines it damaged.
import importlib.util
from pathlib import Path

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"


def _load(version, name):
    spec = importlib.util.spec_from_file_location(
        name, MIGRATIONS / version / "post-migration.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@tagged("post_install", "-at_install", "l10n_ve_migration_null_foreign")
class TestMigrationNullForeign(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mig56 = _load("17.0.0.0.56", "l10n_ve_accountant_mig_56_null")
        cls.mig66null = _load("17.0.0.0.66", "l10n_ve_accountant_mig_66_null")
        cls.vef = cls.env.ref("base.VEF")
        cls.usd = cls.env.ref("base.USD")
        cls.company = cls.env.ref("base.main_company")
        cls.company.write({"currency_id": cls.vef.id, "currency_foreign_id": cls.usd.id})
        cls.env["res.currency.rate"].create({
            "name": fields.Date.today(), "currency_id": cls.usd.id,
            "inverse_company_rate": 50.0, "company_id": cls.company.id,
        })
        cls.acc_rec = cls._acc("2993", "Null Receivable", "asset_receivable", True)
        cls.acc_other = cls._acc("2994", "Null Other", "income", False)
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", cls.company.id)], limit=1
        ) or cls.env["account.journal"].create({
            "name": "General Mig65", "code": "GM65", "type": "general", "company_id": cls.company.id,
        })
        cls.partner = cls.env["res.partner"].create({"name": "Mig65 Partner"})

    @classmethod
    def _acc(cls, code, name, atype, reconcile):
        return cls.env["account.account"].search([
            ("code", "=", code), ("company_id", "=", cls.company.id)], limit=1
        ) or cls.env["account.account"].create({
            "code": code, "name": name, "account_type": atype,
            "company_id": cls.company.id, "reconcile": reconcile,
        })

    def _entry(self, receivable_debit, amount=100.0):
        rec = {"account_id": self.acc_rec.id, "partner_id": self.partner.id}
        oth = {"account_id": self.acc_other.id}
        if receivable_debit:
            rec.update(debit=amount, credit=0.0)
            oth.update(debit=0.0, credit=amount)
        else:
            rec.update(debit=0.0, credit=amount)
            oth.update(debit=amount, credit=0.0)
        move = self.env["account.move"].create({
            "move_type": "entry", "journal_id": self.journal.id,
            "date": fields.Date.today(),
            "line_ids": [Command.create(rec), Command.create(oth)],
        })
        move.action_post()
        return move, move.line_ids.filtered(lambda l: l.account_id == self.acc_rec)

    def _sql(self, query, params=()):
        """Raw write: flush pending ORM values first and drop the cache afterwards,
        otherwise the next flush overwrites the SQL change with cached values."""
        self.env.flush_all()
        self.env.cr.execute(query, params)
        self.env.invalidate_all()

    def _row(self, line_id):
        self.env.flush_all()
        self.env.cr.execute(
            """SELECT foreign_debit, foreign_credit, foreign_balance,
                      foreign_amount_residual, foreign_amount_residual_currency
                 FROM account_move_line WHERE id = %s""", [line_id])
        return self.env.cr.fetchone()

    # --- 17.0.0.0.56 -------------------------------------------------
    def test_56_rounding_keeps_balance_when_one_side_is_null(self):
        move, line = self._entry(True)
        self._sql("""UPDATE account_move_line SET foreign_debit = 1.23456, foreign_credit = NULL,
                      foreign_balance = NULL WHERE id = %s""", [line.id])
        self.mig56._do_sql_rounding(
            self.env.cr, self.company, 2, ("posted",))
        fd, fc, fb, *_ = self._row(line.id)
        self.assertEqual((fd, fc, fb), (1.23, 0.0, 1.23))

    # --- 17.0.0.0.66 -------------------------------------------------
    def test_65_repairs_null_balance(self):
        move, line = self._entry(True)
        fd = self._row(line.id)[0]
        self.assertAlmostEqual(fd, 2.0, places=2)
        self._sql("""UPDATE account_move_line SET foreign_balance = NULL,
                      foreign_amount_residual = NULL, foreign_amount_residual_currency = NULL
                WHERE id = %s""", [line.id])
        self.mig66null.migrate(self.env.cr, "17.0.0.0.65")
        fd, fc, fb, residual, residual_currency = self._row(line.id)
        self.assertAlmostEqual(fb, 2.0, places=2)
        self.assertAlmostEqual(residual, 2.0, places=2)
        self.assertAlmostEqual(residual_currency, 2.0, places=2)

    def test_65_rebuilds_partials_and_zero_residual(self):
        _, debit_line = self._entry(True)
        _, credit_line = self._entry(False)
        (debit_line + credit_line).reconcile()
        partial = self.env["account.partial.reconcile"].search(
            [("debit_move_id", "=", debit_line.id)])
        self.assertTrue(partial)
        self._sql("""UPDATE account_move_line SET foreign_balance = NULL,
                      foreign_amount_residual = NULL, foreign_amount_residual_currency = NULL
                WHERE id = %s""", [debit_line.id])
        # Stale amount, as left behind by the 0.0.56 rebuild that skipped NULL lines.
        self._sql("""UPDATE account_partial_reconcile SET credit_foreign_amount_currency = 99.0
                WHERE id = %s""", [partial.id])
        self.mig66null.migrate(self.env.cr, "17.0.0.0.65")
        self.env.invalidate_all()
        partial = partial.browse(partial.id)
        self.assertAlmostEqual(partial.credit_foreign_amount_currency, 2.0, places=2)
        self.assertAlmostEqual(partial.foreign_amount, 2.0, places=2)
        fd, fc, fb, residual, _ = self._row(debit_line.id)
        self.assertAlmostEqual(fb, 2.0, places=2)
        self.assertAlmostEqual(residual, 0.0, places=2)

    def test_65_skips_locked_period(self):
        move, line = self._entry(True)
        self._sql("UPDATE account_move_line SET foreign_balance = NULL WHERE id = %s", [line.id])
        self.company.tax_lock_date = fields.Date.today()
        self.mig66null.migrate(self.env.cr, "17.0.0.0.65")
        self.assertIsNone(self._row(line.id)[2])

    def test_65_is_idempotent(self):
        move, line = self._entry(True)
        self._sql("UPDATE account_move_line SET foreign_balance = NULL WHERE id = %s", [line.id])
        self.mig66null.migrate(self.env.cr, "17.0.0.0.65")
        first = self._row(line.id)
        self.mig66null.migrate(self.env.cr, "17.0.0.0.65")
        self.assertEqual(self._row(line.id), first)

    def test_66_rebuilds_several_partials_pro_rata(self):
        """A bill paid in two instalments: each partial gets its share, the last absorbs the rounding."""
        _, debit_line = self._entry(True, amount=300.0)
        _, credit_1 = self._entry(False, amount=100.0)
        _, credit_2 = self._entry(False, amount=200.0)
        (debit_line + credit_1 + credit_2).reconcile()
        partials = self.env["account.partial.reconcile"].search(
            [("debit_move_id", "=", debit_line.id)], order="amount, id")
        self.assertEqual(len(partials), 2)
        self._sql("""UPDATE account_move_line SET foreign_balance = NULL,
                      foreign_amount_residual = NULL, foreign_amount_residual_currency = NULL
                WHERE id = %s""", [debit_line.id])
        self._sql("""UPDATE account_partial_reconcile SET credit_foreign_amount_currency = 99.0
                WHERE id IN %s""", [tuple(partials.ids)])
        self.mig66null.migrate(self.env.cr, "17.0.0.0.65")
        self.env.invalidate_all()
        partials = partials.browse(partials.ids).sorted(lambda p: (p.amount, p.id))
        self.assertAlmostEqual(partials[0].credit_foreign_amount_currency, 2.0, places=2)  # 100 Bs / 50
        self.assertAlmostEqual(partials[1].credit_foreign_amount_currency, 4.0, places=2)  # 200 Bs / 50
        self.assertAlmostEqual(sum(partials.mapped("credit_foreign_amount_currency")), 6.0, places=2)
        self.assertAlmostEqual(self._row(debit_line.id)[3], 0.0, places=2)

    def test_66_does_not_touch_partial_whose_other_side_is_locked(self):
        move_open, debit_line = self._entry(True)
        move_locked, credit_line = self._entry(False)
        (debit_line + credit_line).reconcile()
        partial = self.env["account.partial.reconcile"].search(
            [("debit_move_id", "=", debit_line.id)])
        locked_date = fields.Date.subtract(fields.Date.today(), days=10)
        self._sql("UPDATE account_move SET date = %s WHERE id = %s", [locked_date, move_locked.id])
        self._sql("UPDATE account_move_line SET foreign_balance = NULL WHERE id = %s", [debit_line.id])
        self._sql("""UPDATE account_partial_reconcile SET foreign_amount = 99.0,
                      credit_foreign_amount_currency = 55.0 WHERE id = %s""", [partial.id])
        stale_credit = 55.0
        self.company.tax_lock_date = locked_date
        self.mig66null.migrate(self.env.cr, "17.0.0.0.65")
        self.env.cr.execute(
            "SELECT foreign_amount, credit_foreign_amount_currency FROM account_partial_reconcile WHERE id = %s",
            [partial.id])
        foreign_amount, credit_foreign = self.env.cr.fetchone()
        self.assertEqual(foreign_amount, 99.0)
        self.assertEqual(credit_foreign, stale_credit)

    def test_66_residual_of_null_line_in_locked_period_is_not_recomputed(self):
        """A line with a NULL residual that was never in the repaired set is still left alone if locked."""
        move, line = self._entry(True)
        self._sql("""UPDATE account_move_line SET foreign_amount_residual = NULL,
                      foreign_amount_residual_currency = NULL WHERE id = %s""", [line.id])
        self.company.tax_lock_date = fields.Date.today()
        self.mig66null.migrate(self.env.cr, "17.0.0.0.65")
        self.env.cr.execute(
            "SELECT foreign_amount_residual FROM account_move_line WHERE id = %s", [line.id])
        self.assertIsNone(self.env.cr.fetchone()[0])
