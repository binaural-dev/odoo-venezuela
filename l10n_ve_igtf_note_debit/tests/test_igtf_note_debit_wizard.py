from odoo.tests import tagged, Form
from odoo.tools import float_compare
from odoo import fields

from odoo.addons.l10n_ve_igtf.tests.test_igtf_common_partner_formal_VEF import IGTFTestCommon


@tagged("igtf_note_debit", "-at_install", "post_install")
class TestIgtfNoteDebitWizard(IGTFTestCommon):
    """Cobertura de las ramas restantes de `account.payment.register`
    (wizard) y del passthrough de `account.payment` en modo 'inline'."""

    def setUp(self):
        super().setUp()

        self.igtf_note_debit_product = self.env["product.product"].create({
            "name": "Percepción de IGTF (ND wizard test)",
            "type": "service",
            "taxes_id": [(6, 0, [self.tax_iva_exent.id])],
        })
        self.debit_sale_journal = self.Journal.create({
            "name": "ND Forma Libre (wizard test)",
            "code": "NDFLW",
            "type": "sale",
            "is_debit": True,
            "company_id": self.company.id,
        })

    def test_inline_mode_payment_uses_legacy_embedded_igtf_line(self):
        """Con el modo 'inline' (default de la compañía), el wizard y
        `account.payment._create_igtf_moves_in_payments` deben delegar
        siempre a `super()` -- comportamiento legado intacto."""
        self.assertEqual(self.company.igtf_note_debit_mode, "inline")

        invoice = self._create_invoice_usd(1000.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.save()
            pay_form.amount = 600.00
            pay_form.save()
        action = pay_form.record.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))

        self.assertEqual(payment.state, "paid")
        # Flujo legado: la línea de IGTF va embebida en el propio asiento.
        self.assertTrue(
            payment.move_id.line_ids.filtered(
                lambda l: l.account_id in (self.acc_igtf_cli, self.acc_igtf_prov)
            ),
            "En modo 'inline' el IGTF debe seguir viniendo embebido en el asiento del pago.",
        )
        self.assertFalse(invoice.debit_note_ids)

    def _activate_debit_note_mode(self):
        self.company.write({
            "igtf_note_debit_mode": "debit_note",
            "igtf_note_debit_product_id": self.igtf_note_debit_product.id,
        })

    def test_toggle_checkbox_without_manual_amount_recomputes_amount(self):
        """Si el usuario NO edita `amount` a mano, desmarcar 'Incluir IGTF
        en el Importe' sí debe recalcular el monto (a partir del saldo de
        la factura, sin IGTF) -- a diferencia del caso donde el usuario ya
        había tecleado un monto manual (ver test de multicurrency)."""
        self._activate_debit_note_mode()
        invoice = self._create_invoice_usd(1000.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.save()
            # No se toca `amount` -- sigue en su valor por defecto (full
            # amount con IGTF incluido, dado que el checkbox arranca True).
            pay_form.igtf_note_debit_include_in_payment = False

        wizard = pay_form.record
        self.assertEqual(
            float_compare(wizard.amount, wizard.amount_without_difference, precision_digits=2), 0,
            "Sin edición manual, el monto debe recalcularse al desmarcar el checkbox.",
        )

    def test_partial_payment_with_separate_vef_mode_computes_payment_difference(self):
        """Pago PARCIAL (no de contado) con 'Incluir IGTF en el pago'
        desmarcado -- ejercita la rama de `_compute_payment_difference`
        para `installments_mode != 'full'`."""
        self._activate_debit_note_mode()
        self.company.write({"igtf_note_debit_vef_journal_id": self.bank_journal_bs.id})

        invoice = self._create_invoice_usd(1000.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.save()
            pay_form.amount = 400.00
            pay_form.save()
            pay_form.igtf_note_debit_include_in_payment = False

        wizard = pay_form.record
        # No debe reventar -- el compute debe resolver un valor numérico
        # tanto si el monto coincide con una cuota (`installments_mode !=
        # 'full'`) como si no (fallback a 'full').
        self.assertIsInstance(wizard.payment_difference, float)

        action = wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))
        self.assertEqual(payment.state, "paid")
        self.assertEqual(
            float_compare(payment.amount, 400.00, precision_digits=2), 0,
        )

    def _create_two_usd_invoices(self):
        invoices = self.env["account.move"]
        for _ in range(2):
            invoice = self._create_invoice_usd(1000.00)
            invoice.with_context(move_action_post_alert=True).action_post()
            invoices |= invoice
        return invoices

    def test_multi_invoice_payment_ungrouped_generates_debit_note_per_invoice(self):
        """Pago SIN agrupar de VARIAS facturas a la vez (un `account.payment`
        distinto por factura, `group_payment=False`) -- cada factura debe
        recibir su propia ND, atribuida al pago que realmente la cubrió."""
        self._activate_debit_note_mode()
        invoices = self._create_two_usd_invoices()

        lines_to_pay = invoices.line_ids.filtered(
            lambda l: l.account_id.account_type in ("asset_receivable", "liability_payable")
            and not l.reconciled
        )
        action = lines_to_pay.action_register_payment()
        ctx = dict(action["context"], active_model="account.move.line", active_ids=lines_to_pay.ids)

        with Form(self.env["account.payment.register"].with_context(ctx)) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.save()
            pay_form.group_payment = False
            pay_form.save()

        wizard = pay_form.record
        action = wizard.action_create_payments()
        payments = self.env["account.payment"].search(action.get("domain", []))
        self.assertEqual(len(payments), 2, "Sin agrupar, debe crearse un pago por factura.")

        for invoice in invoices:
            debit_notes = invoice.debit_note_ids.filtered(lambda dn: dn.l10n_ve_igtf_note_debit_origin)
            self.assertEqual(
                len(debit_notes), 1,
                f"Cada factura del pago sin agrupar debe tener su propia ND (factura {invoice.name}).",
            )
            self.assertEqual(invoice.payment_state, "paid")
            # Cada ND debe estar atribuida al pago real que cubrió ESA
            # factura (no siempre la primera del batch).
            own_payment = payments.filtered(lambda p: invoice in p.reconciled_invoice_ids)
            self.assertEqual(debit_notes.origin_payment_to_pay_igtf, own_payment.move_id)

    def test_multi_invoice_payment_grouped_generates_single_debit_note(self):
        """Pago AGRUPADO de varias facturas (`group_payment=True`, un solo
        `account.payment` cubriendo ambas) -- espejo del flujo legado
        (`test15` de `l10n_ve_igtf`, que embebe una única línea de IGTF
        agregada): en modo ND debe generarse una única Nota de Débito por
        el IGTF total, atribuida a una de las dos facturas del grupo."""
        self._activate_debit_note_mode()
        invoices = self._create_two_usd_invoices()

        lines_to_pay = invoices.line_ids.filtered(
            lambda l: l.account_id.account_type in ("asset_receivable", "liability_payable")
            and not l.reconciled
        )
        action = lines_to_pay.action_register_payment()
        ctx = dict(action["context"], active_model="account.move.line", active_ids=lines_to_pay.ids)

        with Form(self.env["account.payment.register"].with_context(ctx)) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.save()
            pay_form.group_payment = True
            pay_form.save()

        wizard = pay_form.record
        action = wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))

        self.assertEqual(len(payment.reconciled_invoice_ids), 2, "El pago agrupado debe cubrir ambas facturas.")
        self.assertEqual(payment.state, "paid")
        for invoice in invoices:
            self.assertEqual(invoice.payment_state, "paid")

        all_debit_notes = invoices.debit_note_ids.filtered(lambda dn: dn.l10n_ve_igtf_note_debit_origin)
        self.assertEqual(
            len(all_debit_notes), 1,
            "Un pago agrupado debe generar UNA sola ND por el IGTF total, no una por factura.",
        )
        self.assertEqual(all_debit_notes.origin_payment_to_pay_igtf, payment.move_id)
