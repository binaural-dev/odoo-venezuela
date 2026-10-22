from unittest.mock import patch

from odoo.tests import tagged, TransactionCase
from odoo.exceptions import UserError
from odoo import Command, fields


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
        cls.env.ref("base.VEF").active = True
        cls.company.write({
            "currency_id": cls.env.ref("base.VEF").id,
            "foreign_currency_id": cls.env.ref("base.USD").id,
            "country_id": cls.company.country_id.id or cls.env.ref("base.ve").id,
        })
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
        bank_journals = cls.env["account.journal"].search(
            [("type", "in", ("bank", "cash")), ("company_id", "=", cls.company.id)]
        )
        for journal in bank_journals.filtered("default_account_id"):
            journal.inbound_payment_method_line_ids.payment_account_id = journal.default_account_id
            journal.outbound_payment_method_line_ids.payment_account_id = journal.default_account_id
        cls.bank_journal = bank_journals[:1]
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

    def _create_invoice(self, currency=None):
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            **({"currency_id": currency.id} if currency else {}),
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

    def _usd_bank_journal(self):
        """Diario de banco en USD: la ND de IGTF siempre es en VEF (moneda de la
        compañía), así que un pago en USD obliga a cruzar monedas distintas."""
        usd = self.env.ref("base.USD")
        usd.write({
            "active": True,
            "rate_ids": [Command.create({"name": fields.Date.today(), "company_rate": 1 / 40.0})],
        })
        account = self.env["account.account"].create({
            "name": "Banco USD (unit test ND IGTF)", "code": "BUSDNDI01",
            "account_type": "asset_cash", "currency_id": usd.id,
        })
        return self.env["account.journal"].create({
            "name": "Banco USD (unit test ND IGTF)", "type": "bank", "code": "BUSDN",
            "currency_id": usd.id, "company_id": self.company.id,
            "default_account_id": account.id,
            "inbound_payment_method_line_ids": [(5, 0, 0), (0, 0, {
                "name": "Manual",
                "payment_method_id": self.env.ref("account.account_payment_method_manual_in").id,
                "payment_account_id": account.id,
            })],
            "outbound_payment_method_line_ids": [(5, 0, 0), (0, 0, {
                "name": "Manual",
                "payment_method_id": self.env.ref("account.account_payment_method_manual_out").id,
                "payment_account_id": account.id,
            })],
        })

    def test_debit_note_settlement_keeps_the_payment_accounting_rate(self):
        """Al saldar la ND de IGTF (en VEF) contra el remanente de su pago en USD no se aplica la tasa del widget
        (`l10n_ve_widget_rates`): conserva la tasa contable del pago; si no, una ND emitida días después generaría
        un diferencial que antes no existía. Control: el mismo cruce sobre una factura normal en VEF sí la usa."""
        move_model = type(self.env["account.move"])
        line_model = type(self.env["account.move.line"])
        original_assign = move_model.js_assign_outstanding_line
        original_residuals = line_model._prepare_move_line_residual_amounts
        debit_note_assignments = []
        widget_rates_seen = []

        def spy_assign(record, line_id):
            if record.l10n_ve_igtf_note_debit_origin:
                debit_note_assignments.append(record.id)
            return original_assign(record, line_id)

        def spy_residuals(record, *args, **kwargs):
            widget_rates_seen.append(record.env.context.get("l10n_ve_widget_rates"))
            return original_residuals(record, *args, **kwargs)

        self._activate_debit_note_mode()
        usd_journal = self._usd_bank_journal()
        invoice = self._create_invoice()
        payment = self.env["account.payment"].create({
            "payment_type": "inbound", "partner_type": "customer", "partner_id": self.partner.id,
            "amount": 5.0, "currency_id": self.env.ref("base.USD").id, "journal_id": usd_journal.id,
        })
        payment.action_post()
        debit_note = invoice.prepare_igtf_payment_debit_note(3.0, invoice, payment)

        with patch.object(move_model, "js_assign_outstanding_line", spy_assign), \
                patch.object(line_model, "_prepare_move_line_residual_amounts", spy_residuals):
            invoice.settle_igtf_debit_note(debit_note, payment, include_in_payment=True)

        self.assertTrue(
            debit_note_assignments,
            "El test debía ejercitar el cruce de la ND por `js_assign_outstanding_line`",
        )
        self.assertTrue(widget_rates_seen, "La conciliación debía pasar por `_prepare_move_line_residual_amounts`")
        self.assertFalse(any(widget_rates_seen), "La ND de IGTF no debe usar la tasa del widget")

        widget_rates_seen.clear()
        control_invoice = self._create_invoice(currency=self.env.ref("base.VEF"))
        control_payment = self.env["account.payment"].create({
            "payment_type": "inbound", "partner_type": "customer", "partner_id": self.partner.id,
            "amount": 5.0, "currency_id": self.env.ref("base.USD").id, "journal_id": usd_journal.id,
        })
        control_payment.action_post()
        control_line = control_payment.move_id.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        with patch.object(line_model, "_prepare_move_line_residual_amounts", spy_residuals):
            control_invoice.js_assign_outstanding_line(control_line.id)
        self.assertTrue(any(widget_rates_seen), "El cruce normal debía usar la tasa del widget")

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

    def _orphan_vef_cross_applied_to_invoice(self):
        """Factura en VEF cruzada con un cruce de anticipo publicado al que se le vació el pago origen.
        Devuelve (factura, cruce, parcial)."""
        advance_account = self.env["account.account"].create({
            "name": "Anticipo (prueba huérfano)", "code": "2399ORF",
            "account_type": "liability_current", "company_ids": [Command.set([self.company.id])],
        })
        receivable = self.partner.property_account_receivable_id
        misc_journal = self.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", self.company.id)], limit=1,
        )
        cross = self.env["account.move"].create({
            "is_advance_move": True,
            "move_type": "entry",
            "journal_id": misc_journal.id,
            "date": fields.Date.context_today(self.env.user),
            "partner_id": self.partner.id,
            "origin_payment_advanced_payment_id": self._create_payment(amount=100.0).id,
            "line_ids": [
                Command.create({"account_id": advance_account.id, "debit": 100.0, "credit": 0.0,
                                "partner_id": self.partner.id}),
                Command.create({"account_id": receivable.id, "debit": 0.0, "credit": 100.0,
                                "partner_id": self.partner.id}),
            ],
        })
        cross.action_post()
        cross.origin_payment_advanced_payment_id = False
        invoice = self._create_invoice()
        invoice_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        cross_line = cross.line_ids.filtered(lambda l: l.account_id == receivable)
        (invoice_line + cross_line).reconcile()
        partial = (cross_line.matched_debit_ids | cross_line.matched_credit_ids)[:1]
        self.assertTrue(partial)
        return invoice, cross, partial

    def test_orphan_vef_cross_is_not_treated_as_direct_payment_in_debit_note_mode(self):
        """Un cruce de anticipo VEF sin pago origen no es un pago directo: la base lo cancela, así que la ND de
        IGTF debe reversarse (`create_note_credit_igtf`) igual que con un cruce que conserva su pago origen."""
        self._activate_debit_note_mode()
        invoice, cross, partial = self._orphan_vef_cross_applied_to_invoice()

        move_model = type(invoice)
        calls = []
        original = move_model.create_note_credit_igtf

        def spy(record, partial_id):
            calls.append(partial_id)
            return original(record, partial_id)

        with patch.object(move_model, "create_note_credit_igtf", spy):
            invoice.remove_igtf_from_account_move(partial.id)

        self.assertEqual(calls, [partial.id])
        self.assertEqual(cross.state, "cancel")

    def test_orphan_vef_cross_reverses_the_igtf_debit_note(self):
        """De punta a punta: la ND de IGTF ligada al cruce huérfano se reversa con una NC publicada y el cruce
        se cancela."""
        self._activate_debit_note_mode()
        invoice, cross, partial = self._orphan_vef_cross_applied_to_invoice()
        other_payment = self._create_payment(amount=3.0)
        invoice.prepare_igtf_payment_debit_note(3.0, invoice, other_payment)
        debit_note = invoice.debit_note_ids
        self.assertEqual(len(debit_note), 1)
        debit_note.origin_payment_to_pay_igtf = cross

        invoice.remove_igtf_from_account_move(partial.id)

        reversals = debit_note.reversal_move_ids
        self.assertEqual(len(reversals), 1, "La ND de IGTF debe quedar reversada por una NC")
        self.assertEqual(reversals.state, "posted")
        self.assertEqual(cross.state, "cancel")
