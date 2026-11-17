from odoo.tests import Form, tagged

from .test_igtf_common_partner_formal_VEF import IGTFTestCommon


@tagged("post_install", "-at_install", "l10n_ve_igtf")
class TestIgtfWithoutPartnerAdvanceAccount(IGTFTestCommon):
    """El IGTF depende del diario y del tipo de contribuyente, no de que el contacto tenga
    cuentas de anticipo propias: si no las tiene, se usan las de la compania."""

    def setUp(self):
        super().setUp()
        # Diario de ventas sin moneda fija para poder emitir facturas en USD.
        self.Journal.create({
            "name": "Ventas multimoneda", "type": "sale", "code": "VMM",
            "company_id": self.company.id, "sequence": 1,
        })
        self.partner_without_accounts = self.env["res.partner"].create({
            "name": "Cliente sin cuentas de anticipo",
            "vat": "J999",
            "property_account_receivable_id": self.acc_receivable.id,
            "property_account_payable_id": self.acc_payable.id,
            "taxpayer_type": "formal",
        })
        # Se vacian a proposito: el default del campo toma las de la compania.
        self.partner_without_accounts.write({
            "default_advance_customer_account_id": False,
            "default_advance_supplier_account_id": False,
        })

    def test_check_does_not_require_partner_advance_account(self):
        partner = self.partner_without_accounts
        self.assertTrue(partner._check_igtf_apply_improved("out_invoice", self.company))
        self.assertTrue(partner._check_igtf_apply_improved("in_invoice", self.company))

    def test_check_uses_document_company(self):
        """En ventas decide el tipo de contribuyente de la compania del documento, no el de
        la compania activa."""
        partner = self.partner_without_accounts
        ordinary_company = self.env["res.company"].new({"taxpayer_type": "ordinary"})
        self.assertFalse(partner._check_igtf_apply_improved("out_invoice", ordinary_company))
        self.assertTrue(partner._check_igtf_apply_improved("out_invoice", self.company))

    def test_advance_account_falls_back_to_company(self):
        partner = self.partner_without_accounts
        self.assertEqual(
            partner._get_advance_account("customer", self.company), self.company.advance_customer_account_id
        )
        self.assertEqual(
            partner._get_advance_account("supplier", self.company), self.company.advance_supplier_account_id
        )
        self.assertEqual(
            self.partner._get_advance_account("customer", self.company), self.partner.default_advance_customer_account_id
        )

    def test_payment_register_applies_igtf_without_partner_advance_account(self):
        """Factura en USD de un contacto sin cuentas de anticipo, pagada con un diario en
        USD con IGTF: el asistente activa el IGTF."""
        self.partner = self.partner_without_accounts
        invoice = self._create_invoice_usd(100.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            self.assertTrue(pay_form.is_igtf, "El IGTF debe activarse con un diario en USD con IGTF.")
