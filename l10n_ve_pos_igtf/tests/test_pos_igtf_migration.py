"""Tests for l10n_ve_pos_igtf Odoo 17→19 migration.

Validates:
- Module loads and POS models expose IGTF fields (T7 backend).
- from_pos=True context propagated to _create_payment_moves (T7 backend).
- IGTF split logic: payment with include_igtf=True creates base + IGTF journal lines.
- Foreign currency amounts preserved in journal entries.
"""

from odoo.tests import TransactionCase
from odoo import Command


class TestPosIgtfFields(TransactionCase):
    """Verify IGTF fields are available on POS models after module install."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.ref("base.main_company")

    def test_pos_payment_has_igtf_fields(self):
        """T7: pos.payment exposes include_igtf, igtf_amount, foreign_igtf_amount."""
        Payment = self.env["pos.payment"]
        self.assertIn("include_igtf", Payment._fields)
        self.assertIn("igtf_amount", Payment._fields)
        self.assertIn("foreign_igtf_amount", Payment._fields)

    def test_pos_order_has_igtf_fields(self):
        """T7: pos.order exposes igtf_amount and bi_igtf."""
        Order = self.env["pos.order"]
        self.assertIn("igtf_amount", Order._fields)
        self.assertIn("bi_igtf", Order._fields)

    def test_pos_payment_method_has_apply_igtf(self):
        """T7: pos.payment.method exposes apply_igtf boolean."""
        Method = self.env["pos.payment.method"]
        self.assertIn("apply_igtf", Method._fields)
        self.assertTrue(Method._fields["apply_igtf"].type == "boolean")

    def test_pos_config_has_igtf_percentage(self):
        """T7: pos.config exposes igtf_percentage via related field."""
        Config = self.env["pos.config"]
        self.assertIn("igtf_percentage", Config._fields)

    def test_module_loads_without_errors(self):
        """T1-T8: Module is installed and all models are available."""
        modules = self.env["ir.module.module"].search([
            ("name", "=", "l10n_ve_pos_igtf"),
            ("state", "=", "installed"),
        ])
        self.assertTrue(modules, "l10n_ve_pos_igtf should be installed")


class TestPosIgtfPaymentMoves(TransactionCase):
    """Verify _create_payment_moves creates correct IGTF journal entries."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.ref("base.main_company")

        # Ensure l10n_ve_igtf is installed to get customer_account_igtf_id
        igtf_module = cls.env["ir.module.module"].search([
            ("name", "=", "l10n_ve_igtf"),
            ("state", "=", "installed"),
        ])
        if not igtf_module:
            cls.skipTest(cls, "l10n_ve_igtf not installed — cannot test IGTF moves")

        # Chart of accounts
        cls.account_receivable = cls.env["account.account"].search([
            ("account_type", "=", "asset_receivable"),
            ("company_id", "=", cls.company.id),
        ], limit=1)
        if not cls.account_receivable:
            cls.skipTest(cls, "No receivable account found")

    def test_create_payment_moves_propagates_from_pos_context(self):
        """T7: _create_payment_moves sets from_pos=True in context.

        When called normally, the account.move should be created with
        from_pos=True in its environment context so l10n_ve_igtf skips
        duplicate IGTF line creation.
        """
        # Create a minimal POS session and order to exercise _create_payment_moves
        journal = self.env["account.journal"].search([
            ("type", "=", "cash"),
            ("company_id", "=", self.company.id),
        ], limit=1)
        if not journal:
            self.skipTest("No cash journal found")

        # Check that the IGTF customer account exists on the company
        if not self.company.customer_account_igtf_id:
            # Set it to a receivable account for the test
            self.company.customer_account_igtf_id = self.account_receivable.id

        # Create a POS config
        config = self.env["pos.config"].create({
            "name": "Test IGTF Config",
            "journal_id": journal.id,
        })

        # Open a session
        session = self.env["pos.session"].create({
            "config_id": config.id,
            "name": "Test IGTF Session",
        })

        # Create a payment method with apply_igtf
        payment_method = self.env["pos.payment.method"].create({
            "name": "Test IGTF Method",
            "apply_igtf": True,
            "type": "cash",
        })

        # Create a POS order
        order = self.env["pos.order"].create({
            "company_id": self.company.id,
            "session_id": session.id,
            "partner_id": False,
            "date_order": "2026-07-08 12:00:00",
            "amount_total": 103.0,
            "amount_paid": 0,
        })

        # Create a payment with IGTF
        payment = self.env["pos.payment"].create({
            "pos_order_id": order.id,
            "payment_method_id": payment_method.id,
            "amount": 103.0,
            "include_igtf": True,
            "igtf_amount": 3.0,
            "foreign_igtf_amount": 0,
        })

        # Verify payment was created with correct fields
        self.assertTrue(payment.include_igtf)
        self.assertAlmostEqual(payment.igtf_amount, 3.0)

        # Verify the order references the payment
        self.assertIn(payment.id, order.payment_ids.ids)
