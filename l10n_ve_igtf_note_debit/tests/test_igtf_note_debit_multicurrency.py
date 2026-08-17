from odoo.tests import tagged, Form
from odoo.tools import float_compare
from odoo import fields

from odoo.addons.l10n_ve_igtf.tests.test_igtf_common_partner_formal_VEF import IGTFTestCommon


@tagged("igtf_note_debit", "-at_install", "post_install")
class TestIgtfNoteDebitMulticurrency(IGTFTestCommon):
    """Reutiliza el fixture real de `l10n_ve_igtf` (partner 'formal', diarios
    IGTF en USD y EUR, cuentas de anticipo, etc.) para probar el flujo nuevo
    de Nota de Débito con facturas en distintas monedas (lista de precios
    USD / EUR) pagadas a través de diarios marcados `is_igtf = True` --
    exactamente el mismo camino real (`Form.from_action` + `action_create_payments`)
    que ya usan los tests de `l10n_ve_igtf`, para que el resultado sea
    comparable línea a línea con el flujo legado.
    """

    def setUp(self):
        super().setUp()

        self.igtf_note_debit_product = self.env["product.product"].create({
            "name": "Percepción de IGTF (ND automática)",
            "type": "service",
            "taxes_id": [(6, 0, [self.tax_iva_exent.id])],
        })
        self.debit_sale_journal = self.Journal.create({
            "name": "ND Forma Libre (test)",
            "code": "NDFL",
            "type": "sale",
            "is_debit": True,
            "company_id": self.company.id,
        })
        self.company.write({
            "igtf_note_debit_mode": "debit_note",
            "igtf_note_debit_product_id": self.igtf_note_debit_product.id,
        })

    def _register_payment(self, invoice, journal, amount, include_igtf_in_payment=None):
        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = journal
            pay_form.amount = amount
            pay_form.save()
            if include_igtf_in_payment is not None:
                pay_form.igtf_note_debit_include_in_payment = include_igtf_in_payment
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        return self.env["account.payment"].browse(action.get("res_id"))

    def _assert_debit_note_generated(self, invoice, payment, expected_igtf_amount_foreign_curr):
        # El asiento del propio pago NO debe llevar la línea IGTF embebida
        # (eso es justamente lo que reemplaza este flujo).
        self.assertEqual(
            len(payment.move_id.line_ids), 2,
            "Con el modo 'debit_note', el asiento del pago debe tener solo "
            "2 líneas (banco + cliente) -- sin línea IGTF embebida.",
        )
        self.assertFalse(
            payment.move_id.line_ids.filtered(
                lambda l: l.account_id in (self.acc_igtf_cli, self.acc_igtf_prov)
            ),
            "No debe existir línea de IGTF en el asiento del pago bajo el flujo de ND.",
        )

        debit_notes = invoice.debit_note_ids.filtered(
            lambda dn: dn.l10n_ve_igtf_note_debit_origin
        )
        self.assertEqual(len(debit_notes), 1, "Debe generarse exactamente una ND de IGTF.")
        debit_note = debit_notes[0]

        self.assertEqual(debit_note.state, "posted")
        self.assertEqual(debit_note.origin_payment_to_pay_igtf, payment.move_id)

        # La ND se emite SIEMPRE en VEF (moneda de la compañía), sin
        # importar la moneda de la factura de origen.
        self.assertEqual(
            debit_note.currency_id, self.currency_vef,
            "La Nota de Débito de IGTF debe emitirse siempre en VEF.",
        )

        igtf_lines = debit_note.invoice_line_ids.filtered(
            lambda l: l.product_id == self.igtf_note_debit_product
        )
        self.assertEqual(len(igtf_lines), 1)

        expected_igtf_amount_vef = payment.currency_id._convert(
            expected_igtf_amount_foreign_curr, self.currency_vef, self.company, fields.Date.today(),
        )
        self.assertEqual(
            float_compare(igtf_lines.price_unit, expected_igtf_amount_vef, precision_digits=2), 0,
            f"Monto de la ND incorrecto: esperado {expected_igtf_amount_vef} VEF "
            f"(equivalente a {expected_igtf_amount_foreign_curr} {payment.currency_id.name}), "
            f"encontrado {igtf_lines.price_unit}",
        )

        # Forzar el cómputo de `compute_bi_igtf` (base imponible de IGTF) --
        # debe seguir resolviendo un valor coherente aun cuando el IGTF de
        # la factura ya no viene de una línea embebida sino de esta ND.
        self.assertGreaterEqual(invoice.bi_igtf, 0.0)
        self.assertGreaterEqual(invoice.foreign_bi_igtf, 0.0)

        return debit_note

    def test_usd_invoice_partial_payment_generates_debit_note(self):
        """Factura en USD (lista de precios en dólares), pagada parcialmente
        a través del diario IGTF en USD -- espejo exacto de
        `test01_payment_from_invoice_with_igtf_journal` de `l10n_ve_igtf`,
        pero verificando el flujo de ND en vez de la línea embebida."""
        invoice = self._create_invoice_usd(1000.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        payment = self._register_payment(invoice, self.bank_journal_usd, 600.00)

        self.assertEqual(payment.state, "paid")
        self.assertEqual(float_compare(payment.amount, 600.00, precision_digits=2), 0)
        self._assert_debit_note_generated(invoice, payment, expected_igtf_amount_foreign_curr=18.0)

    def test_eur_invoice_full_payment_generates_debit_note(self):
        """Factura en EUR, pagada en su totalidad a través del diario IGTF
        en EUR."""
        invoice = self._create_invoice_eur(500.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        payment = self._register_payment(invoice, self.bank_journal_eur, 500.00)

        self.assertEqual(payment.state, "paid")
        # 3% de 500 = 15.00
        self._assert_debit_note_generated(invoice, payment, expected_igtf_amount_foreign_curr=15.0)

    def test_usd_invoice_separate_vef_payment_mode(self):
        """Con el check "Incluir IGTF en el pago" desmarcado en el wizard,
        el pago del cliente cubre SOLO la factura (sin IGTF incluido en el
        monto), y el IGTF se cobra con un segundo `account.payment`, en VEF,
        creado y conciliado automáticamente contra la ND."""
        self.company.write({
            "igtf_note_debit_vef_journal_id": self.bank_journal_bs.id,
        })

        invoice = self._create_invoice_usd(1000.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        payment = self._register_payment(
            invoice, self.bank_journal_usd, 1000.00, include_igtf_in_payment=False,
        )

        # El pago cubre solo la factura -- sin residual pendiente por IGTF.
        self.assertEqual(payment.state, "paid")
        self.assertEqual(float_compare(payment.amount, 1000.00, precision_digits=2), 0)
        self.assertEqual(
            len(payment.move_id.line_ids), 2,
            "El pago no debe incluir ninguna línea/monto de IGTF.",
        )

        debit_notes = invoice.debit_note_ids.filtered(lambda dn: dn.l10n_ve_igtf_note_debit_origin)
        self.assertEqual(len(debit_notes), 1)
        debit_note = debit_notes[0]
        self.assertEqual(debit_note.currency_id, self.currency_vef)

        expected_igtf_vef = self.currency_usd._convert(
            30.0, self.currency_vef, self.company, fields.Date.today(),
        )
        igtf_lines = debit_note.invoice_line_ids.filtered(
            lambda l: l.product_id == self.igtf_note_debit_product
        )
        self.assertEqual(
            float_compare(igtf_lines.price_unit, expected_igtf_vef, precision_digits=2), 0,
        )

        # La ND debe quedar conciliada (pagada) por el pago aparte en VEF,
        # no por el pago original de la factura.
        self.assertEqual(debit_note.payment_state, "paid")
        vef_payments = self.env["account.payment"].search([
            ("journal_id", "=", self.bank_journal_bs.id),
            ("currency_id", "=", self.currency_vef.id),
            ("memo", "like", debit_note.name),
        ])
        self.assertTrue(vef_payments, "Debe existir un pago aparte en VEF por el IGTF.")
        self.assertEqual(vef_payments.state, "paid")

    def test_vef_journal_without_igtf_does_not_generate_debit_note(self):
        """Control negativo: pagar por un diario que NO es IGTF (VEF local)
        no debe generar ninguna ND, ni con el modo 'debit_note' activo."""
        invoice = self._create_invoice_vef(1000.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        payment = self._register_payment(invoice, self.bank_journal_bs, 1000.00)

        self.assertEqual(payment.state, "paid")
        self.assertFalse(
            invoice.debit_note_ids.filtered(lambda dn: dn.l10n_ve_igtf_note_debit_origin),
            "Un diario sin IGTF no debe generar Nota de Débito.",
        )
