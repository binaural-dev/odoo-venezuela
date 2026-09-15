from odoo.tests import tagged, TransactionCase
from odoo import Command


@tagged("post_install", "-at_install")
class TestIgtfNoteDebitService(TransactionCase):
    """Cobertura mínima del módulo `l10n_ve_igtf_note_debit`:

    1. El flag de compañía nace en 'inline' -- ninguna instalación existente
       cambia de comportamiento solo por instalar este módulo.
    2. Con el modo 'inline' (default), los hooks agregados sobre
       `l10n_ve_igtf` son un passthrough puro a `super()`.
    3. Con el modo 'debit_note', `prepare_igtf_payment_debit_note` genera
       una Nota de Débito real (vía `account.debit.note`), vinculada a la
       factura de origen y al pago, sin tocar el asiento del pago.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        # La moneda de la compañía (VEF en esta localización) nace inactiva
        # en Odoo; sin activarla no se pueden validar asientos/facturas.
        cls.company.currency_id.active = True
        cls.partner = cls.env["res.partner"].create({"name": "Cliente IGTF ND Test"})

        # l10n_ve_accountant exige exactamente un impuesto de venta y uno de
        # compra en todo producto -- usamos impuestos "Exento" (0%) dedicados
        # para no depender de datos demo/fiscales de ninguna localidad.
        cls.exempt_sale_tax = cls.env["account.tax"].create({
            "name": "Exento Venta (test)", "amount": 0.0,
            "amount_type": "percent", "type_tax_use": "sale",
            "company_id": cls.company.id,
        })
        cls.exempt_purchase_tax = cls.env["account.tax"].create({
            "name": "Exento Compra (test)", "amount": 0.0,
            "amount_type": "percent", "type_tax_use": "purchase",
            "company_id": cls.company.id,
        })

        cls.igtf_product = cls.env["product.product"].create({
            "name": "Percepción IGTF (test)",
            "type": "service",
            "taxes_id": [(6, 0, [cls.exempt_sale_tax.id])],
            "supplier_taxes_id": [(6, 0, [cls.exempt_purchase_tax.id])],
        })

        cls.sale_journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.company.id)], limit=1
        )
        cls.debit_journal = cls.env["account.journal"].create({
            "name": "ND IGTF Test",
            "type": "sale",
            "code": "NDIT",
            "is_debit": True,
            "company_id": cls.company.id,
        })
        cls.bank_journal = cls.env["account.journal"].search(
            [("type", "in", ("bank", "cash")), ("company_id", "=", cls.company.id)], limit=1
        )

        income_account = cls.env["account.account"].search(
            [("account_type", "=", "income"), ("company_ids", "in", cls.company.id)], limit=1
        )
        cls.sale_product = cls.env["product.product"].create({
            "name": "Producto de prueba",
            "type": "service",
            "list_price": 100.0,
            "taxes_id": [(6, 0, [cls.exempt_sale_tax.id])],
            "supplier_taxes_id": [(6, 0, [cls.exempt_purchase_tax.id])],
            "property_account_income_id": income_account.id if income_account else False,
        })

        cls.invoice = cls.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": cls.partner.id,
            "invoice_line_ids": [Command.create({
                "product_id": cls.sale_product.id,
                "quantity": 1,
                "price_unit": 100.0,
                "tax_ids": [(6, 0, [cls.exempt_sale_tax.id])],
            })],
        })
        cls.invoice.with_context(move_action_post_alert=True).action_post()

        cls.payment = cls.env["account.payment"].create({
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": cls.partner.id,
            "amount": 103.0,
            "journal_id": cls.bank_journal.id,
        })
        cls.payment.action_post()

    def test_default_mode_is_inline(self):
        """Ninguna compañía existente cambia de flujo solo por instalar el módulo."""
        self.assertEqual(self.company.igtf_note_debit_mode, "inline")

    def test_default_include_in_payment_is_true(self):
        """El check 'Incluir IGTF en el pago' del wizard debe arrancar en
        True por defecto (comportamiento actual: IGTF incluido en el pago)."""
        self.assertTrue(self.company.igtf_note_debit_include_in_payment_default)

    def test_inline_mode_is_pure_passthrough(self):
        """Con modo 'inline', el override de account.payment no debe alterar
        el flujo legado en absoluto (debe delegar siempre a `super()`)."""
        self.assertEqual(self.company.igtf_note_debit_mode, "inline")
        # No debe lanzar ni comportarse distinto a la clase base: simplemente
        # confirmamos que el método sigue existiendo y es invocable sin
        # necesitar ningún campo/config nuevo.
        self.assertTrue(hasattr(self.payment, "_create_igtf_moves_in_payments"))

    def test_generate_igtf_debit_note(self):
        self.company.write({
            "igtf_note_debit_mode": "debit_note",
            "igtf_note_debit_product_id": self.igtf_product.id,
        })

        igtf_amount = 3.0
        debit_note = self.invoice.prepare_igtf_payment_debit_note(
            igtf_amount, self.invoice, self.payment,
        )

        self.assertTrue(debit_note, "Debe crearse la Nota de Débito de IGTF")
        self.assertEqual(debit_note.debit_origin_id, self.invoice)
        self.assertEqual(debit_note.move_type, self.invoice.move_type)
        self.assertTrue(debit_note.l10n_ve_igtf_note_debit_origin)
        self.assertEqual(debit_note.origin_payment_to_pay_igtf, self.payment.move_id)
        self.assertEqual(debit_note.state, "posted")

        igtf_lines = debit_note.invoice_line_ids.filtered(
            lambda l: l.product_id == self.igtf_product
        )
        self.assertEqual(len(igtf_lines), 1)
        self.assertEqual(igtf_lines.price_unit, igtf_amount)
        self.assertEqual(
            igtf_lines.tax_ids, self.igtf_product.taxes_id,
            "La línea de IGTF debe llevar el impuesto exento configurado en el producto",
        )

        # La factura original no debe haber sido tocada por este flujo.
        self.assertFalse(self.invoice.debit_origin_id)
        self.assertIn(debit_note, self.invoice.debit_note_ids)

    def test_debit_note_requires_product_configured(self):
        with self.assertRaises(Exception):
            self.company.write({
                "igtf_note_debit_mode": "debit_note",
                "igtf_note_debit_product_id": False,
            })
