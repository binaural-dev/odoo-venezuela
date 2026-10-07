from odoo import Command
from odoo.tests import tagged
from odoo.exceptions import ValidationError
from .common import TestDonationCommon


@tagged('l10n_ve_donation', 'stock_scrap', '-at_install', 'post_install')
class TestStockScrap(TestDonationCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.location_stock = cls.warehouse_normal.lot_stock_id
        cls.env["stock.quant"].create({
            "product_id": cls.product_storable.id,
            "location_id": cls.location_stock.id,
            "quantity": 100.0,
        })

    def test_01_scrap_location_domain(self):
        """Domain changes based on is_donation."""
        scrap = self.env["stock.scrap"].create({
            "product_id": self.product_storable.id,
            "scrap_qty": 1,
            "location_id": self.location_stock.id,
        })
        self.assertIn("inventory", scrap.scrap_location_domain)
        scrap.is_donation = True
        scrap._compute_scrap_location_domain()
        self.assertIn("is_donation_warehouse", scrap.scrap_location_domain)

    def test_02_scrap_location_id_donation(self):
        """Scrap location is set to a donation warehouse location when is_donation."""
        scrap = self.env["stock.scrap"].create({
            "product_id": self.product_storable.id,
            "scrap_qty": 1,
            "location_id": self.location_stock.id,
            "is_donation": True,
        })
        scrap._compute_scrap_location_id()
        self.assertTrue(scrap.scrap_location_id)
        self.assertTrue(scrap.scrap_location_id.is_donation_warehouse)

    def test_03_donation_scrap_process(self):
        """Donation scrap creates move and finishes successfully."""
        scrap = self.env["stock.scrap"].create({
            "product_id": self.product_storable.id,
            "scrap_qty": 5,
            "location_id": self.location_stock.id,
            "is_donation": True,
            "donation_reason": "Test donation scrap",
        })
        scrap.scrap_location_id = self.warehouse_donation.lot_stock_id
        scrap.do_scrap()
        self.assertEqual(scrap.state, "done")
        self.assertTrue(scrap.move_ids)

    def test_04_normal_scrap_process(self):
        """Normal scrap delegates to super()."""
        scrap = self.env["stock.scrap"].create({
            "product_id": self.product_storable.id,
            "scrap_qty": 2,
            "location_id": self.location_stock.id,
            "is_donation": False,
        })
        scrap_location = self.env["stock.location"].search([("scrap_location", "=", True)], limit=1)
        scrap.scrap_location_id = scrap_location.id
        scrap.do_scrap()
        self.assertEqual(scrap.state, "done")

    def test_05_stock_move_prepare_account_move_vals(self):
        """_prepare_account_move_vals propagates donation info from scrap.

        `partner_id` is NO LONGER forced to the company:
        stock.scrap has no real contact field for the beneficiary/patient
        (documented limitation), so the header is simply left unset instead
        of duplicating the company as both donor and beneficiary."""
        scrap = self.env["stock.scrap"].create({
            "product_id": self.product_storable.id,
            "scrap_qty": 1,
            "location_id": self.location_stock.id,
            "is_donation": True,
            "donation_reason": "Reason A",
        })
        scrap.scrap_location_id = self.warehouse_donation.lot_stock_id
        move = self.env["stock.move"].create({
            "name": "Test Move",
            "product_id": self.product_storable.id,
            "product_uom_qty": 1,
            "product_uom": self.product_storable.uom_id.id,
            "location_id": self.location_stock.id,
            "location_dest_id": self.warehouse_donation.lot_stock_id.id,
            "scrap_id": scrap.id,
        })
        vals = move._prepare_account_move_vals(
            credit_account_id=self.account_expense.id,
            debit_account_id=self.account_income.id,
            journal_id=self.journal_general.id,
            qty=1,
            description="Desc",
            svl_id=False,
            cost=10,
        )
        self.assertTrue(vals.get("is_donation"))
        self.assertFalse(vals.get("partner_id"))
        self.assertEqual(vals.get("ref"), "Reason A")
        self.assertIn("Reason A", vals.get("ref"))

    def test_06_stock_move_prepare_account_move_vals_no_reason(self):
        """_prepare_account_move_vals with donation but no reason: the `ref`
        already set by the base `vals` (the move's `description`) must be
        preserved, not wiped to `False` -- regression test for the bug where
        the override unconditionally forced `ref` to
        `self.scrap_id.donation_reason`, which is `False` whenever there is
        no reason, silently discarding whatever `ref`/description the core
        `vals` already carried."""
        scrap = self.env["stock.scrap"].create({
            "product_id": self.product_storable.id,
            "scrap_qty": 1,
            "location_id": self.location_stock.id,
            "is_donation": True,
        })
        scrap.scrap_location_id = self.warehouse_donation.lot_stock_id
        move = self.env["stock.move"].create({
            "name": "Test Move 2",
            "product_id": self.product_storable.id,
            "product_uom_qty": 1,
            "product_uom": self.product_storable.uom_id.id,
            "location_id": self.location_stock.id,
            "location_dest_id": self.warehouse_donation.lot_stock_id.id,
            "scrap_id": scrap.id,
        })
        vals = move._prepare_account_move_vals(
            credit_account_id=self.account_expense.id,
            debit_account_id=self.account_income.id,
            journal_id=self.journal_general.id,
            qty=1,
            description="Desc",
            svl_id=False,
            cost=10,
        )
        self.assertTrue(vals.get("is_donation"))
        # No reason -- the description already set by the base vals must be
        # preserved, not overwritten with False.
        self.assertEqual(vals.get("ref"), "Desc")

    def test_07_multi_company_scrap_location_domain(self):
        """Domain MUST filter by current company."""
        company_b = self.env["res.company"].create({"name": "Company B"})
        warehouse_b = self.env["stock.warehouse"].create({
            "name": "Donation WH B",
            "code": "DWHB",
            "company_id": company_b.id,
            "is_donation_warehouse": True,
        })

        scrap_a = self.env["stock.scrap"].create({
            "product_id": self.product_storable.id,
            "scrap_qty": 1,
            "location_id": self.location_stock.id,
            "company_id": self.company.id,
            "is_donation": True,
        })
        scrap_a._compute_scrap_location_domain()

        domain_a = scrap_a.scrap_location_domain
        self.assertIn(f"('company_id', '=', {self.company.id})", domain_a)
        self.assertNotIn(f"('company_id', '=', {company_b.id})", domain_a)
        self.assertIn("('is_donation_warehouse', '=', True)", domain_a)

    def test_08_scrap_certificate_shows_blank_beneficiary(self):
        """Documented limitation (not resolved in this change):
        stock.scrap has no real contact field for the patient/beneficiary,
        so the certificate for a scrap-originated donation move keeps
        showing the beneficiary blank -- no regression vs. before, since the
        header is just left unset instead of forced to the company."""
        move = self.env["account.move"].create({
            "move_type": "entry",
            "is_donation": True,
            "journal_id": self.journal_general.id,
            "ref": "Donación por scrap sin contacto real",
            "line_ids": [
                Command.create({
                    "account_id": self.account_expense.id,
                    "debit": 10,
                    "credit": 0,
                    "partner_id": self.company.partner_id.id,
                }),
                Command.create({
                    "account_id": self.account_income.id,
                    "debit": 0,
                    "credit": 10,
                    "partner_id": self.company.partner_id.id,
                }),
            ],
        })
        self.assertFalse(move.partner_id)
        report = self.env.ref("l10n_ve_donation.action_donation_certificate_account_move")
        html, _report_type = report._render_qweb_html(report.report_name, move.ids)
        self.assertIn(b"__________________", html)
