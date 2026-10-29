# Ticket #15694: migration 17.0.0.0.66 equalises the CxP USD amount of posted vendor bills.
import importlib.util
import os
from pathlib import Path
from unittest import mock

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


@tagged("post_install", "-at_install", "l10n_ve_migration_vendor_bill_foreign")
class TestMigrationVendorBillForeignAmounts(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mig66 = _load("17.0.0.0.66", "l10n_ve_accountant_mig_66")
        cls.vef = cls.env.ref("base.VEF")
        cls.usd = cls.env.ref("base.USD")
        cls.company = cls.env.ref("base.main_company")
        cls.company.write({"currency_id": cls.vef.id, "currency_foreign_id": cls.usd.id})
        cls.env["res.currency.rate"].create({
            "name": fields.Date.today(), "currency_id": cls.usd.id,
            "inverse_company_rate": 50.0, "company_id": cls.company.id,
        })
        cls.partner = cls.env["res.partner"].create({"name": "Mig66 Vendor"})
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", cls.company.id)], limit=1)
        cls.product = cls.env["product.product"].create({"name": "Svc Mig66", "type": "service"})
        cls.tax = cls.env["account.tax"].create({
            "name": "IVA 16 Mig66", "amount": 16.0, "amount_type": "percent",
            "type_tax_use": "purchase", "company_id": cls.company.id,
        })

    def _bill(self, prices=(5000.0,)):
        bill = self.env["account.move"].create({
            "move_type": "in_invoice", "partner_id": self.partner.id,
            "journal_id": self.journal.id, "invoice_date": fields.Date.today(),
            "invoice_line_ids": [Command.create({
                "product_id": self.product.id, "name": "Line", "quantity": 1,
                "price_unit": price, "tax_ids": [Command.set(self.tax.ids)],
            }) for price in prices],
        })
        bill.action_post()
        return bill

    def _pt(self, bill):
        return bill.line_ids.filtered(lambda l: l.display_type == "payment_term")

    def _sql(self, query, params=()):
        self.env.flush_all()
        self.env.cr.execute(query, params)
        self.env.invalidate_all()

    def _break_pt(self, bill, amount=0.0):
        self._sql("""UPDATE account_move_line SET foreign_debit = 0, foreign_credit = %s,
                      foreign_balance = %s WHERE id = %s""", [amount, -amount, self._pt(bill).id])

    def _row(self, line):
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT foreign_credit, foreign_balance FROM account_move_line WHERE id = %s", [line.id])
        return self.env.cr.fetchone()

    def _migrate(self):
        self.mig66.migrate(self.env.cr, "17.0.0.0.65")
        self.env.invalidate_all()

    def test_fixes_cxp_in_zero_usd(self):
        bill = self._bill()
        self._break_pt(bill, 0.0)
        self._migrate()
        credit, balance = self._row(self._pt(bill))
        self.assertAlmostEqual(credit, 116.0, places=2)  # 5800 Bs / 50
        self.assertAlmostEqual(balance, -116.0, places=2)
        self.assertAlmostEqual(sum(bill.line_ids.mapped("foreign_balance")), 0.0, places=2)

    def test_fixes_stale_amount(self):
        bill = self._bill()
        self._break_pt(bill, 90.0)
        self._migrate()
        self.assertAlmostEqual(self._row(self._pt(bill))[0], 116.0, places=2)

    def test_dry_run_changes_nothing(self):
        bill = self._bill()
        self._break_pt(bill, 0.0)
        with mock.patch.dict(os.environ, {"DRY_RUN": "1"}):
            self._migrate()
        self.assertAlmostEqual(self._row(self._pt(bill))[0], 0.0, places=2)

    def test_skips_locked_period(self):
        bill = self._bill()
        self._break_pt(bill, 0.0)
        self.company.tax_lock_date = fields.Date.today()
        self._migrate()
        self.assertAlmostEqual(self._row(self._pt(bill))[0], 0.0, places=2)

    def test_leaves_balanced_bill_and_is_idempotent(self):
        bill = self._bill()
        before = self._row(self._pt(bill))
        self._migrate()
        self.assertEqual(self._row(self._pt(bill)), before)
        self._break_pt(bill, 0.0)
        self._migrate()
        first = self._row(self._pt(bill))
        self._migrate()
        self.assertEqual(self._row(self._pt(bill)), first)

    def test_rebuilds_partials_and_residual(self):
        bill = self._bill()
        pt = self._pt(bill)
        other = self.env["account.account"].search([
            ("company_id", "=", self.company.id), ("account_type", "=", "expense")], limit=1)
        entry = self.env["account.move"].create({
            "move_type": "entry", "journal_id": self.env["account.journal"].search(
                [("type", "=", "general"), ("company_id", "=", self.company.id)], limit=1).id,
            "date": fields.Date.today(),
            "line_ids": [
                Command.create({"account_id": pt.account_id.id, "partner_id": self.partner.id,
                                "debit": 5800.0, "credit": 0.0}),
                Command.create({"account_id": other.id, "debit": 0.0, "credit": 5800.0}),
            ],
        })
        entry.action_post()
        (pt + entry.line_ids.filtered(lambda l: l.account_id == pt.account_id)).reconcile()
        partial = self.env["account.partial.reconcile"].search([("credit_move_id", "=", pt.id)])
        self.assertTrue(partial)
        self._break_pt(bill, 0.0)
        self._sql("""UPDATE account_partial_reconcile SET debit_foreign_amount_currency = 0
                      WHERE id = %s""", [partial.id])
        self._migrate()
        partial = partial.browse(partial.id)
        self.assertAlmostEqual(partial.debit_foreign_amount_currency, 116.0, places=2)
        self.env.cr.execute(
            "SELECT foreign_amount_residual FROM account_move_line WHERE id = %s", [pt.id])
        self.assertAlmostEqual(self.env.cr.fetchone()[0], 0.0, places=2)
