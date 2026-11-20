from odoo import Command
from odoo.tests import tagged, Form

from odoo.addons.l10n_ve_igtf.tests.test_igtf_common_partner_formal_VEF import IGTFTestCommon


@tagged("igtf_note_debit", "-at_install", "post_install")
class TestIgtfNoteDebitInstallments(IGTFTestCommon):
    """Regresión: `compute_bi_igtf` bajo 'debit_note' con facturas a cuotas
    (2+ líneas de CxC). Antes del fix usaba `factura_line.id` sobre todas las
    líneas y lanzaba 'Expected singleton' al registrar un pago real."""

    def setUp(self):
        super().setUp()
        # Mismo setup que `test_igtf_note_debit_advance_payment`.
        self.company.write({"account_fiscal_country_id": self.company.country_id.id})
        self.igtf_note_debit_product = self.env["product.product"].create({
            "name": "Percepción de IGTF (ND cuotas test)",
            "type": "service",
            "taxes_id": [(6, 0, [self.tax_iva_exent.id])],
            "supplier_taxes_id": [(6, 0, self.product.supplier_taxes_id.ids)],
        })
        self.debit_sale_journal = self.Journal.create({
            "name": "ND Forma Libre (cuotas test)",
            "code": "NDFLC",
            "type": "sale",
            "is_debit": True,
            "company_id": self.company.id,
        })
        self.company.write({
            "igtf_note_debit_mode": "debit_note",
            "igtf_note_debit_product_id": self.igtf_note_debit_product.id,
        })

    def _create_payment_term_2_installments(self):
        """Plazo de pago de 2 cuotas (30% / 70%) a distintos vencimientos."""
        return self.env["account.payment.term"].create({
            "name": "IGTF ND test 30/70",
            "line_ids": [
                Command.create({
                    "value": "percent", "value_amount": 30.0,
                    "delay_type": "days_after", "nb_days": 15,
                }),
                Command.create({
                    "value": "percent", "value_amount": 70.0,
                    "delay_type": "days_after", "nb_days": 45,
                }),
            ],
        })

    def _create_posted_invoice_vef(self, amount, payment_term=None):
        invoice = self._create_invoice_vef(amount)
        if payment_term:
            invoice.invoice_payment_term_id = payment_term
        invoice.with_context(move_action_post_alert=True).action_post()
        return invoice

    def _pay_from_invoice_vef(self, invoice, amount, full=False):
        """Pago real (línea de banco) por el flujo de la factura, diario VEF sin IGTF.

        Con cuotas, el asistente propone por defecto solo la siguiente y el
        `Form` pisa el monto (`installments_mode` es invisible y no se puede
        escribir ahí). Con `full=True` se crea el asistente por ORM con
        `installments_mode='full'`.
        """
        if full:
            wizard = self.env["account.payment.register"].with_context(
                **invoice.action_register_payment()["context"],
            ).create({
                "journal_id": self.bank_journal_bs.id,
                "installments_mode": "full",
                "amount": amount,
            })
            action = wizard.action_create_payments()
            return self.env["account.payment"].browse(action.get("res_id"))
        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_bs
            pay_form.save()
            pay_form.amount = amount
            pay_form.save()
        action = pay_form.record.action_create_payments()
        return self.env["account.payment"].browse(action.get("res_id"))

    def _receivable_lines(self, invoice):
        return invoice.line_ids.filtered(lambda l: l.account_id == self.acc_receivable)

    def test_two_installments_partial_payment_debit_note_mode(self):
        """Factura a 2 cuotas + pago parcial real en modo 'debit_note': no debe
        lanzar 'Expected singleton'. Sin IGTF no hay base ni ND."""
        payment_amount = 400.00
        invoice = self._create_posted_invoice_vef(
            1000.00, self._create_payment_term_2_installments())
        self.assertEqual(len(self._receivable_lines(invoice)), 2)

        self._pay_from_invoice_vef(invoice, payment_amount)

        invoice = self.env["account.move"].browse(invoice.id)
        percentage = self.company.igtf_percentage / 100
        expected_top = (abs(invoice.amount_total_signed) - payment_amount) * percentage
        self.assertEqual(invoice.payment_state, "partial")
        self.assertAlmostEqual(invoice.bi_igtf, 0.0, 2)
        self.assertAlmostEqual(invoice.igtf_top_aply, expected_top, 2)
        self.assertFalse(
            invoice.debit_note_ids.filtered(lambda dn: dn.l10n_ve_igtf_note_debit_origin),
            "Un pago por diario sin IGTF no debe generar ND.",
        )

    def test_two_installments_full_payment_debit_note_mode(self):
        """Factura a 2 cuotas pagada completa en modo 'debit_note'."""
        invoice = self._create_posted_invoice_vef(
            1000.00, self._create_payment_term_2_installments())
        self.assertEqual(len(self._receivable_lines(invoice)), 2)

        self._pay_from_invoice_vef(invoice, 1000.00, full=True)

        invoice = self.env["account.move"].browse(invoice.id)
        self.assertIn(invoice.payment_state, ("paid", "in_payment"))
        self.assertAlmostEqual(invoice.bi_igtf, 0.0, 2)
        self.assertAlmostEqual(invoice.igtf_top_aply, 0.0, 2)

    def test_single_installment_control_debit_note_mode(self):
        """Control: 1 sola cuota (1 línea de CxC) da el mismo resultado que antes."""
        payment_amount = 400.00
        invoice = self._create_posted_invoice_vef(1000.00)
        self.assertEqual(len(self._receivable_lines(invoice)), 1)

        self._pay_from_invoice_vef(invoice, payment_amount)

        invoice = self.env["account.move"].browse(invoice.id)
        percentage = self.company.igtf_percentage / 100
        expected_top = (abs(invoice.amount_total_signed) - payment_amount) * percentage
        self.assertEqual(invoice.payment_state, "partial")
        self.assertAlmostEqual(invoice.bi_igtf, 0.0, 2)
        self.assertAlmostEqual(invoice.igtf_top_aply, expected_top, 2)
