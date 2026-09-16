# -*- coding: utf-8 -*-
from odoo.tests import tagged, Form
from odoo import fields

from .test_common_purchase_book_igtf_usd_provider_formal import IGTFTestCommonPurchaseBook


@tagged("igtf_payment_difference_sign", "post_install", "-at_install")
class TestPaymentDifferenceAmountCurrencySign(IGTFTestCommonPurchaseBook):
    """Regresión: 'Error de validación de divisa secundaria al registrar pago
    con diferencia' (factura de proveedor 00007468, Club de Barquisimeto).

    account.move.line trae un CHECK SQL (check_amount_currency_balance_sign)
    que exige que balance y amount_currency tengan el mismo signo en cada
    línea. Al registrar un pago con "Diferencia de pago" en la divisa
    secundaria (VEF), la línea de contrapartida y la de diferencia de pago se
    recalculan en varios _inherit encadenados (l10n_ve_accountant con la tasa
    manual, el wizard core con la tasa oficial) y podían quedar con signos
    cruzados, bloqueando la creación del pago.
    """

    def test_fix_amount_currency_sign_flips_only_mismatched_lines(self):
        """Unit test del guard: solo invierte el signo de amount_currency
        cuando no coincide con el de balance, y deja todo lo demás intacto."""
        payment = self.env["account.payment"]
        vals = [
            # balance negativo (se acredita), amount_currency mal puesto en positivo
            {"debit": 0.0, "credit": 100.0, "amount_currency": 500.0, "currency_id": self.currency_vef.id},
            # balance positivo (se carga), amount_currency ya viene correcto (negativo -> debía ser positivo, mal puesto)
            {"debit": 100.0, "credit": 0.0, "amount_currency": -500.0, "currency_id": self.currency_vef.id},
            # ya consistente, no debe tocarse
            {"debit": 0.0, "credit": 50.0, "amount_currency": -250.0, "currency_id": self.currency_vef.id},
            # balance cero: amount_currency no debe tocarse pase lo que pase
            {"debit": 10.0, "credit": 10.0, "amount_currency": 37.0, "currency_id": self.currency_vef.id},
            # amount_currency cero: no debe tocarse
            {"debit": 20.0, "credit": 0.0, "amount_currency": 0.0, "currency_id": self.currency_vef.id},
        ]

        payment._fix_amount_currency_sign(vals)

        self.assertEqual(vals[0]["amount_currency"], -500.0)
        self.assertEqual(vals[1]["amount_currency"], 500.0)
        self.assertEqual(vals[2]["amount_currency"], -250.0)
        self.assertEqual(vals[3]["amount_currency"], 37.0)
        self.assertEqual(vals[4]["amount_currency"], 0.0)

        for line in vals:
            balance = line.get("debit", 0.0) - line.get("credit", 0.0)
            amount_currency = line["amount_currency"]
            self.assertTrue(
                balance == 0.0 or amount_currency == 0.0 or (balance > 0) == (amount_currency > 0),
                f"signo inconsistente: balance={balance} amount_currency={amount_currency}",
            )

    def test_vendor_payment_with_difference_in_secondary_currency(self):
        """Reproduce el escenario del ticket: factura en USD (moneda de la
        compañía), pago desde un diario en VEF (divisa secundaria, sin IGTF
        porque no es una divisa extranjera), dejando una "Diferencia de
        pago" reconciliada contra una cuenta de ajuste. El pago debe poder
        crearse y todas las líneas del asiento deben quedar con balance y
        amount_currency del mismo signo.
        """
        acc_diff = self.get_or_create_account(
            "6901", "expense", "Diferencia en Pagos"
        )

        invoice = self._create_invoice_usd(1000.0)
        invoice.with_context(move_action_post_alert=True).action_post()

        action_data = invoice.action_register_payment()
        with Form(
            self.env["account.payment.register"].with_context(**action_data["context"])
        ) as pay_form:
            pay_form.journal_id = self.bank_journal_bs
            pay_form.payment_date = fields.Date.today()
            pay_form.foreign_currency_id = self.currency_vef
            # Tasa manual distinta de la tasa oficial (self.rate) usada por el
            # wizard core al convertir la línea de "Diferencia de pago" -- es
            # justo el escenario que mezcla dos tasas en el mismo asiento.
            pay_form.foreign_rate = self.rate + 5.0
            pay_form.save()
            pay_form.payment_difference_handling = "reconcile"
            pay_form.writeoff_account_id = acc_diff
            # Deja una pequeña diferencia de pago respecto al monto sugerido.
            pay_form.amount = pay_form.amount - 5.0

        action = pay_form.record.action_create_payments()
        payment = self.env["account.payment"].browse(action["res_id"])

        for line in payment.move_id.line_ids:
            self.assertTrue(
                line.balance == 0.0
                or line.amount_currency == 0.0
                or (line.balance > 0) == (line.amount_currency > 0),
                f"{line.name!r}: balance={line.balance} amount_currency={line.amount_currency}",
            )

        total_debit = sum(payment.move_id.line_ids.mapped("debit"))
        total_credit = sum(payment.move_id.line_ids.mapped("credit"))
        self.assertAlmostEqual(total_debit, total_credit, 2)
