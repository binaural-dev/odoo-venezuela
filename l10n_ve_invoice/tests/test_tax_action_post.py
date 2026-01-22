
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError

@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestInvoiceTaxConstraint(TransactionCase):
    def setUp(self):
        super(TestInvoiceTaxConstraint, self).setUp()
        self.company = self.env.ref("base.main_company")
        self.partner = self.env["res.partner"].create({"name": "Cliente"})
        self.journal = self.env["account.journal"].create({
            "name": "Ventas",
            "type": "sale",
            "code": "VTS",
            "company_id": self.company.id,
        })
        self.account = self.env["account.account"].create({
            "name": "Ventas",
            "code": "700000",
            "account_type": "income",
            "company_ids": [(6, 0, [self.company.id])],
        })
        self.tax = self.env["account.tax"].create({
            "name": "IVA 16%",
            "amount": 16,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "company_id": self.company.id,
        })
        self.product = self.env["product.product"].create({
            "name": "Producto Test",
            "type": "service",
            "list_price": 100,
            "taxes_id": [(6, 0, [self.tax.id])],
        })

    def _create_new_invoice(self, move_type, lines):
        return self.env["account.move"].create({
            "move_type": move_type,
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "invoice_line_ids": lines,
        })

    def test_invoice_with_tax_ok(self):
        """Debe permitir confirmar si todas las líneas de producto tienen impuesto."""
        invoice = self._create_new_invoice("out_invoice", [
            (0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 100,
                "account_id": self.account.id,
                "tax_ids": [(6, 0, [self.tax.id])],
            }),
        ])
        invoice.action_post()  # No debe lanzar excepción

    def test_invoice_without_tax_raises(self):
        """Debe lanzar ValidationError si alguna línea de producto no tiene impuesto."""
        invoice = self._create_new_invoice("out_invoice", [
            (0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 100,
                "account_id": self.account.id,
                "tax_ids": [],
            }),
        ])
        with self.assertRaises(ValidationError):
            invoice.action_post()

    def test_invoice_with_section_and_note_lines(self):
        """Debe ignorar líneas tipo sección y nota aunque no tengan impuesto."""
        invoice = self._create_new_invoice("out_invoice", [
            (0, 0, {
                "name": "Sección",
                "display_type": "line_section",
            }),
            (0, 0, {
                "name": "Nota",
                "display_type": "line_note",
            }),
            (0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 100,
                "account_id": self.account.id,
                "tax_ids": [(6, 0, [self.tax.id])],
            }),
        ])
        invoice.action_post()  # No debe lanzar excepción

    def test_invoice_with_section_and_note_lines_but_product_without_tax(self):
        """Debe lanzar ValidationError si hay línea de producto sin impuesto, aunque existan secciones o notas."""
        invoice = self._create_new_invoice("out_invoice", [
            (0, 0, {
                "name": "Sección",
                "display_type": "line_section",
            }),
            (0, 0, {
                "name": "Nota",
                "display_type": "line_note",
            }),
            (0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 100,
                "account_id": self.account.id,
                "tax_ids": [],
            }),
        ])
        with self.assertRaises(ValidationError):
            invoice.action_post()

    def test_invoice_types(self):
        """Debe validar para todos los tipos de move_type requeridos."""
        for move_type in ("out_invoice", "in_invoice", "out_refund", "in_refund"):
            invoice = self._create_new_invoice(move_type, [
                (0, 0, {
                    "product_id": self.product.id,
                    "quantity": 1,
                    "price_unit": 100,
                    "account_id": self.account.id,
                    "tax_ids": [],
                }),
            ])
            with self.assertRaises(ValidationError):
                invoice.action_post()
            # Ahora con impuesto, debe pasar
            invoice2 = self._create_new_invoice(move_type, [
                (0, 0, {
                    "product_id": self.product.id,
                    "quantity": 1,
                    "price_unit": 100,
                    "account_id": self.account.id,
                    "tax_ids": [(6, 0, [self.tax.id])],
                }),
            ])
            invoice2.action_post()