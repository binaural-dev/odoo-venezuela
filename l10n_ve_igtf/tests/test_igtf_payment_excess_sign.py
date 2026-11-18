from odoo.tests import Form, tagged

from .test_igtf_common_providers_formal_VEF import IGTFTestCommon


@tagged("post_install", "-at_install", "l10n_ve_igtf")
class TestIgtfPaymentExcessSign(IGTFTestCommon):
    """Excedente de un pago a proveedor en divisa con IGTF: el asiento "RESTANTE DE PAGO EN
    DIVISA" lleva el excedente al debe de la cuenta de anticipo de proveedor (activo), con la
    contrapartida al haber de la cuenta por pagar, y queda disponible como anticipo."""

    def setUp(self):
        super().setUp()
        # Diario de compras sin moneda fija para poder registrar facturas en USD.
        self.Journal.create({
            "name": "Compras multimoneda", "type": "purchase", "code": "CMM",
            "company_id": self.company.id, "sequence": 1,
        })

    def test_supplier_excess_goes_to_advance_debit(self):
        bill = self._create_invoice_usd(1000.00)
        bill.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, bill.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.amount = 1500.00
        action = pay_form.record.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))

        self.assertEqual(len(payment.advanced_move_ids), 1, "Debe crearse el asiento de restante.")
        residual_move = payment.advanced_move_ids
        advance_line = residual_move.line_ids.filtered(lambda l: l.account_id == self.advance_supp_acc)
        payable_line = residual_move.line_ids.filtered(lambda l: l.account_id == self.acc_payable)
        self.assertGreater(advance_line.balance, 0, "El anticipo a proveedor va al debe.")
        self.assertLess(payable_line.balance, 0, "La cuenta por pagar del restante va al haber.")
        self.assertAlmostEqual(advance_line.amount_currency, 470.00, places=2)

        bill_2 = self._create_invoice_usd(400.00)
        bill_2.with_context(move_action_post_alert=True).action_post()
        widget = bill_2.invoice_outstanding_credits_debits_widget_advance_payment or {}
        self.assertIn(
            residual_move.id,
            [content.get("move_id") for content in widget.get("content") or []],
            "El excedente debe aparecer como anticipo disponible en la siguiente factura.",
        )
