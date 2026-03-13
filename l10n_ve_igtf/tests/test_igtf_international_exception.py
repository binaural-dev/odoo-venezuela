"""
Tests para verificar que el IGTF NO se aplica cuando la factura pertenece
a un diario con is_purchase_international = True.

Casos cubiertos:
    1. Pago IGTF sobre factura de compra INTERNACIONAL → sin IGTF
    2. Pago IGTF sobre factura de compra NACIONAL       → IGTF normal
"""
from odoo.tests import tagged, TransactionCase


@tagged("post_install", "-at_install", "l10n_ve_igtf")
class TestIgtfInternationalException(TransactionCase):
    """Verify that the IGTF international-purchase exception works correctly."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        company = cls.env.company
        if not company.account_fiscal_country_id:
            company.account_fiscal_country_id = cls.env.ref("base.ve").id

        # ── Cuenta IGTF compras ──────────────────────────────────────────────
        cls.igtf_account = cls.env["account.account"].create({
            "name": "IGTF Test Account",
            "code": "TEST.IGTF.001",
            "account_type": "expense",
            "company_ids": [(4, company.id)],
        })

        # Configura cuentas IGTF en la compañía (necesarias para el cálculo)
        company.write({
            "supplier_account_igtf_id": cls.igtf_account.id,
            "customer_account_igtf_id": cls.igtf_account.id,
        })

        # ── Diario de pago con IGTF activo  ─────────────────────────────────
        cls.igtf_payment_journal = cls.env["account.journal"].create({
            "name": "Bank IGTF Test",
            "type": "bank",
            "code": "BIGTFTEST",
            "is_igtf": True,
            "currency_id": cls.env.ref("base.USD").id,
        })

        # ── Diario de factura INTERNACIONAL (is_purchase_international=True) ─
        cls.international_journal = cls.env["account.journal"].create({
            "name": "Compras Internacionales Test",
            "type": "purchase",
            "code": "CINTTEST",
            "is_purchase_international": True,
        })

        # ── Diario de factura NACIONAL (is_purchase_international=False) ─────
        cls.national_journal = cls.env["account.journal"].create({
            "name": "Compras Nacionales Test",
            "type": "purchase",
            "code": "CNACTEST",
            "is_purchase_international": False,
        })

        # ── Cuentas por Pagar / Cobrar para el Partner ───────────────────────
        cls.payable_account = cls.env["account.account"].create({
            "name": "Payable Test",
            "code": "TEST.PAY.001",
            "account_type": "liability_payable",
            "company_ids": [(4, company.id)],
            "reconcile": True,
        })
        cls.receivable_account = cls.env["account.account"].create({
            "name": "Receivable Test",
            "code": "TEST.REC.001",
            "account_type": "asset_receivable",
            "company_ids": [(4, company.id)],
            "reconcile": True,
        })

        # ── Partner de prueba ────────────────────────────────────────────────
        cls.partner = cls.env["res.partner"].create({
            "name": "Proveedor Test IGTF",
            "company_type": "company",
            "taxpayer_type": "special",
            "property_account_payable_id": cls.payable_account.id,
            "property_account_receivable_id": cls.receivable_account.id,
        })

        # ── Producto de prueba ───────────────────────────────────────────────
        cls.product = cls.env["product.product"].create({
            "name": "Producto Test IGTF",
            "type": "service",
            "default_code": "SRV_IGTF",
        })

        # ── Impuesto de prueba ───────────────────────────────────────────────
        cls.tax_group = cls.env["account.tax.group"].create({
            "name": "Tax Group Test",
            "country_id": company.account_fiscal_country_id.id or cls.env.ref("base.ve").id,
        })
        cls.tax = cls.env["account.tax"].create({
            "name": "Tax 16%",
            "amount_type": "percent",
            "amount": 16.0,
            "type_tax_use": "purchase",
            "tax_group_id": cls.tax_group.id,
            "company_id": company.id,
            "country_id": cls.tax_group.country_id.id,
        })

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _make_invoice(self, journal):
        """Create and post a vendor invoice using the given journal."""
        invoice = self.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": self.partner.id,
            "journal_id": journal.id,
            "invoice_line_ids": [(0, 0, {
                "name": "Servicio Internacional",
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 100.0,
                "account_id": self.igtf_account.id,
                "tax_ids": [(4, self.tax.id)],
            })],
        })
        invoice.action_post()
        return invoice

    def _build_register_wizard(self, invoice):
        """Return an account.payment.register wizard for the given invoice."""
        return self.env["account.payment.register"].with_context(
            active_model="account.move",
            active_id=invoice.id,
            active_ids=[invoice.id],
        ).create({
            "journal_id": self.igtf_payment_journal.id,
        })

    # ── Tests ─────────────────────────────────────────────────────────────────

    def test_01_igtf_skipped_for_international_invoice(self):
        """IGTF must NOT be activated when any invoice has is_purchase_international=True."""
        invoice = self._make_invoice(self.international_journal)
        wizard = self._build_register_wizard(invoice)

        # Force onchange evaluation
        wizard._compute_check_igtf()

        self.assertFalse(
            wizard.is_igtf,
            "IGTF should be False for an international-purchase invoice, "
            "even if the payment journal has is_igtf=True."
        )

    def test_02_igtf_applied_for_national_invoice(self):
        """IGTF MUST be activated normally for a national-purchase invoice."""
        invoice = self._make_invoice(self.national_journal)
        wizard = self._build_register_wizard(invoice)

        # Force onchange evaluation
        wizard._compute_check_igtf()

        # NOTE: is_igtf will be True only if partner's taxpayer_type qualifies.
        # Since we set taxpayer_type='special', it should be True.
        self.assertTrue(
            wizard.is_igtf,
            "IGTF should be True for a national-purchase invoice when the "
            "payment journal has is_igtf=True and partner is a special taxpayer."
        )

    def test_03_international_invoice_has_no_igtf_flag(self):
        """Verify is_purchase_international field is correctly read from journal."""
        invoice = self._make_invoice(self.international_journal)
        self.assertTrue(
            invoice.journal_id.is_purchase_international,
            "The international journal must have is_purchase_international=True."
        )

    def test_04_national_invoice_has_no_international_flag(self):
        """Verify national journal does NOT have is_purchase_international set."""
        invoice = self._make_invoice(self.national_journal)
        self.assertFalse(
            invoice.journal_id.is_purchase_international,
            "The national journal must have is_purchase_international=False."
        )
