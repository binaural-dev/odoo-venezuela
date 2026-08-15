from odoo.tests import tagged, TransactionCase
from odoo.exceptions import UserError
from odoo import Command


@tagged("post_install", "-at_install")
class TestIgtfNoteDebitUnit(TransactionCase):
    """Tests unitarios que llaman directo a los métodos de negocio de
    `account_move.py` (sin pasar por el wizard/Form UI) para cubrir ramas
    puntuales que son difíciles/lentas de alcanzar con un flujo de pago
    completo: computes, validaciones y ramas de configuración."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create({"name": "Cliente IGTF Unit Test"})

        cls.exempt_sale_tax = cls.env["account.tax"].create({
            "name": "Exento Venta (unit test)", "amount": 0.0,
            "amount_type": "percent", "type_tax_use": "sale",
            "company_id": cls.company.id,
        })
        cls.exempt_purchase_tax = cls.env["account.tax"].create({
            "name": "Exento Compra (unit test)", "amount": 0.0,
            "amount_type": "percent", "type_tax_use": "purchase",
            "company_id": cls.company.id,
        })
        cls.igtf_product = cls.env["product.product"].create({
            "name": "Percepción IGTF (unit test)",
            "type": "service",
            "taxes_id": [(6, 0, [cls.exempt_sale_tax.id])],
            "supplier_taxes_id": [(6, 0, [cls.exempt_purchase_tax.id])],
        })
        cls.debit_journal = cls.env["account.journal"].create({
            "name": "ND IGTF Unit Test",
            "type": "sale",
            "code": "NDIU",
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
            "name": "Producto de prueba (unit test)",
            "type": "service",
            "list_price": 100.0,
            "taxes_id": [(6, 0, [cls.exempt_sale_tax.id])],
            "supplier_taxes_id": [(6, 0, [cls.exempt_purchase_tax.id])],
            "property_account_income_id": income_account.id if income_account else False,
        })

    def _create_invoice(self):
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "invoice_line_ids": [Command.create({
                "product_id": self.sale_product.id,
                "quantity": 1,
                "price_unit": 100.0,
                "tax_ids": [(6, 0, [self.exempt_sale_tax.id])],
            })],
        })
        invoice.with_context(move_action_post_alert=True).action_post()
        return invoice

    def _create_payment(self, amount=103.0):
        payment = self.env["account.payment"].create({
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner.id,
            "amount": amount,
            "journal_id": self.bank_journal.id,
        })
        payment.action_post()
        return payment

    def _activate_debit_note_mode(self):
        self.company.write({
            "igtf_note_debit_mode": "debit_note",
            "igtf_note_debit_product_id": self.igtf_product.id,
        })

    # -- compute_has_pending_igtf_debit_note ---------------------------

    def test_has_pending_igtf_debit_note_false_without_debit_notes(self):
        invoice = self._create_invoice()
        self.assertFalse(invoice.has_pending_igtf_debit_note)

    def test_has_pending_igtf_debit_note_true_when_posted_unpaid(self):
        self._activate_debit_note_mode()
        invoice = self._create_invoice()
        payment = self._create_payment()
        debit_note = invoice.prepare_igtf_payment_debit_note(3.0, invoice, payment)
        self.assertTrue(invoice.has_pending_igtf_debit_note)
        self.assertEqual(debit_note.state, "posted")

    def test_has_pending_igtf_debit_note_false_when_paid(self):
        self._activate_debit_note_mode()
        invoice = self._create_invoice()
        payment = self._create_payment()
        debit_note = invoice.prepare_igtf_payment_debit_note(3.0, invoice, payment)
        invoice.settle_igtf_debit_note(debit_note, payment, include_in_payment=True)
        invoice = self.env["account.move"].browse(invoice.id)
        self.assertFalse(invoice.has_pending_igtf_debit_note)

    # -- prepare_igtf_payment_debit_note --------------------------------

    def test_prepare_debit_note_raises_without_product_configured(self):
        invoice = self._create_invoice()
        payment = self._create_payment()
        # La propia restricción de compañía ya impide guardar 'debit_note'
        # sin producto -- se fuerza el estado inconsistente con `sudo` +
        # `skip_check` para probar la guarda de `prepare_igtf_payment_debit_note`
        # en el método en sí (defensa en profundidad).
        self.company.with_context(skip_check=True).write({
            "igtf_note_debit_mode": "debit_note",
            "igtf_note_debit_product_id": False,
        })
        with self.assertRaises(UserError):
            invoice.prepare_igtf_payment_debit_note(3.0, invoice, payment)

    # -- settle_igtf_debit_note -----------------------------------------

    def test_settle_igtf_debit_note_noop_without_debit_note(self):
        invoice = self._create_invoice()
        payment = self._create_payment()
        # No debe lanzar ni hacer nada si `debit_note` es un recordset vacío.
        self.assertIsNone(
            invoice.settle_igtf_debit_note(self.env["account.move"], payment)
        )

    def test_settle_igtf_debit_note_defaults_to_company_setting(self):
        """Sin pasar `include_in_payment`, debe usar el default de compañía."""
        self._activate_debit_note_mode()
        self.company.write({"igtf_note_debit_include_in_payment_default": True})
        invoice = self._create_invoice()
        payment = self._create_payment()
        debit_note = invoice.prepare_igtf_payment_debit_note(3.0, invoice, payment)

        outstanding_line = payment.move_id.line_ids.filtered(
            lambda l: l.account_type in ("asset_receivable", "liability_payable") and not l.reconciled
        )[:1]
        invoice.settle_igtf_debit_note(debit_note, payment, outstanding_line=outstanding_line)
        debit_note = self.env["account.move"].browse(debit_note.id)
        self.assertEqual(debit_note.payment_state, "paid")

    # -- _settle_igtf_debit_note_with_vef_payment ------------------------

    def test_settle_with_vef_payment_auto_search_journal_when_not_configured(self):
        """Sin `igtf_note_debit_vef_journal_id` configurado, debe
        auto-buscar un diario banco/caja en VEF que no sea IGTF."""
        self._activate_debit_note_mode()
        self.company.write({
            "igtf_note_debit_vef_journal_id": False,
            "currency_id": self.env.ref("base.VEF").id,
        })
        invoice = self._create_invoice()
        payment = self._create_payment()
        debit_note = invoice.prepare_igtf_payment_debit_note(3.0, invoice, payment)

        vef_payment = invoice._settle_igtf_debit_note_with_vef_payment(debit_note, payment)
        self.assertTrue(vef_payment, "Debe auto-encontrar un diario VEF y crear el pago aparte.")
        self.assertIn(vef_payment.state, ("posted", "paid"))

    def test_settle_with_vef_payment_raises_without_any_valid_journal(self):
        self._activate_debit_note_mode()
        # Todos los diarios banco/caja de la compañía quedan marcados IGTF
        # para forzar que no exista ningún candidato válido.
        self.env["account.journal"].search([
            ("company_id", "=", self.company.id),
            ("type", "in", ("bank", "cash")),
        ]).write({"is_igtf": True})
        self.company.write({"igtf_note_debit_vef_journal_id": False})

        invoice = self._create_invoice()
        payment = self._create_payment()
        debit_note = invoice.prepare_igtf_payment_debit_note(3.0, invoice, payment)

        with self.assertRaises(UserError):
            invoice._settle_igtf_debit_note_with_vef_payment(debit_note, payment)

    # -- _create_advance_payment_move ------------------------------------

    def test_create_advance_payment_move_passthrough_in_inline_mode(self):
        """Con modo 'inline', debe delegar directo a `super()` (que a su
        vez exige que exista un anticipo real -- lanza UserError igual,
        pero desde la implementación heredada, no la nuestra)."""
        self.company.write({"igtf_note_debit_mode": "inline"})
        invoice = self._create_invoice()
        payment = self._create_payment()
        lines = payment.move_id.line_ids.filtered(
            lambda l: l.account_type in ("asset_receivable", "liability_payable")
        )
        with self.assertRaises(UserError):
            invoice._create_advance_payment_move(100.0, lines)

    def test_create_advance_payment_move_raises_without_advance_amount_in_widget(self):
        """En modo 'debit_note', si el widget de anticipo no reconoce el
        `move_id` de las líneas pasadas (caso típico al llamarlo fuera del
        flujo real de conciliación), debe lanzar UserError explicando que
        no se encontró el monto de anticipo a aplicar."""
        self._activate_debit_note_mode()
        invoice = self._create_invoice()
        payment = self._create_payment()
        lines = payment.move_id.line_ids.filtered(
            lambda l: l.account_type in ("asset_receivable", "liability_payable")
        )
        with self.assertRaises(UserError):
            invoice._create_advance_payment_move(100.0, lines)

    # -- create_note_credit_igtf / remove_igtf_from_account_move --------

    def _reconcile_invoice_with_payment(self, invoice, payment):
        invoice_line = invoice.line_ids.filtered(
            lambda l: l.account_type in ("asset_receivable", "liability_payable")
        )
        payment_line = payment.move_id.line_ids.filtered(
            lambda l: l.account_type in ("asset_receivable", "liability_payable")
        )
        (invoice_line + payment_line).reconcile()
        partial = invoice_line.matched_debit_ids or invoice_line.matched_credit_ids
        return partial[:1]

    def test_create_note_credit_igtf_noop_without_any_debit_notes(self):
        """Si la factura reconciliada NO tiene ninguna ND asociada (pago
        normal, sin modo 'debit_note' activo al momento del cruce), debe
        salir silenciosamente (solo loggea error) sin lanzar excepción."""
        invoice = self._create_invoice()
        payment = self._create_payment(amount=100.0)
        partial = self._reconcile_invoice_with_payment(invoice, payment)
        self.assertTrue(partial)
        # No debe lanzar -- simplemente no hace nada.
        self.assertIsNone(invoice.create_note_credit_igtf(partial.id))

    def test_create_note_credit_igtf_noop_when_no_matching_debit_note(self):
        """Si la factura tiene Notas de Débito, pero NINGUNA vinculada al
        pago que se está desconciliando (`origin_payment_to_pay_igtf` no
        coincide), debe salir sin reversar nada."""
        self._activate_debit_note_mode()
        invoice = self._create_invoice()
        other_payment = self._create_payment(amount=103.0)
        # ND real, pero vinculada a un pago DISTINTO del que se conciliará.
        invoice.prepare_igtf_payment_debit_note(3.0, invoice, other_payment)

        payment = self._create_payment(amount=100.0)
        partial = self._reconcile_invoice_with_payment(invoice, payment)
        self.assertTrue(partial)
        self.assertIsNone(invoice.create_note_credit_igtf(partial.id))

    def test_settle_with_vef_payment_returns_empty_when_debit_note_already_paid(self):
        """Si la ND ya no tiene línea CxC abierta (ya está saldada), debe
        devolver un recordset vacío sin crear pago."""
        self._activate_debit_note_mode()
        self.company.write({"igtf_note_debit_vef_journal_id": self.bank_journal.id})
        invoice = self._create_invoice()
        payment = self._create_payment()
        debit_note = invoice.prepare_igtf_payment_debit_note(3.0, invoice, payment)

        outstanding_line = payment.move_id.line_ids.filtered(
            lambda l: l.account_type in ("asset_receivable", "liability_payable") and not l.reconciled
        )[:1]
        invoice.settle_igtf_debit_note(debit_note, payment, include_in_payment=True, outstanding_line=outstanding_line)
        debit_note = self.env["account.move"].browse(debit_note.id)
        self.assertEqual(debit_note.payment_state, "paid")

        result = invoice._settle_igtf_debit_note_with_vef_payment(debit_note, payment)
        self.assertFalse(result)
