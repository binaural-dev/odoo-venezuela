from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.l10n_ve_accountant.tests.test_indexed_payments import TestIndexedPayments

RATE = 40.0


@tagged("post_install", "-at_install", "l10n_ve_igtf_refund_payment_sign")
class TestIgtfRefundPaymentSign(TestIndexedPayments):
    """
    Pagar una nota de crédito (NC) desde el wizard debe generar un asiento de
    pago cuyos apuntes cumplan account_move_line_check_amount_currency_balance_sign.

    El bloque "FIX balances when diference is decimal" de
    account.payment._prepare_move_line_default_vals elegía el signo del balance
    por partner_type: una NC de cliente (pago outbound) o una NC de proveedor
    (pago inbound) quedaban con balance y amount_currency de signos opuestos.

    Cada caso fija la fecha de la NC igual a la del pago, que es la condición
    para que el bloque se ejecute.
    """

    def setUp(self):
        super().setUp()
        self.company.igtf_percentage = 3.0
        self.invoice_date = self.payment_date
        self._set_rate(self.currency_usd, self.payment_date, RATE)

        self.account_payable = self.env["account.account"].create({
            "name": "Payable",
            "code": "210000",
            "account_type": "liability_payable",
            "company_ids": [(6, 0, [self.company.id])],
            "reconcile": True,
        })
        self.account_expense = self.env["account.account"].create({
            "name": "Expense",
            "code": "500000",
            "account_type": "expense",
            "company_ids": [(6, 0, [self.company.id])],
        })
        igtf_customer = self.env["account.account"].create({
            "name": "IGTF Customer",
            "code": "236000",
            "account_type": "liability_current",
            "company_ids": [(6, 0, [self.company.id])],
        })
        igtf_supplier = self.env["account.account"].create({
            "name": "IGTF Supplier",
            "code": "510000",
            "account_type": "expense",
            "company_ids": [(6, 0, [self.company.id])],
        })
        self.company.write({
            "customer_account_igtf_id": igtf_customer.id,
            "supplier_account_igtf_id": igtf_supplier.id,
        })
        self.partner.write({
            "property_account_payable_id": self.account_payable.id,
            "default_advance_customer_account_id": igtf_customer.id,
            "default_advance_supplier_account_id": igtf_supplier.id,
        })
        self.purchase_journal = self.env["account.journal"].sudo().create({
            "name": "Purchase Test",
            "code": "PRTST",
            "type": "purchase",
            "company_id": self.company.id,
            "default_account_id": self.account_expense.id,
        })

        # Cada diario con sus propias líneas de método de pago: las de
        # TestIndexedPayments se reasignan al último diario que las usa.
        self.journal_vef = self._make_bank_journal("BVEF", self.currency_vef)
        self.journal_usd = self._make_bank_journal("BUSD", self.currency_usd)
        self.journal_usd_igtf = self._make_bank_journal("BIGTF", self.currency_usd, is_igtf=True)

    # -- helpers --------------------------------------------------------------

    def _make_bank_journal(self, code, currency, is_igtf=False):
        manual_in = self.env.ref("account.account_payment_method_manual_in")
        manual_out = self.env.ref("account.account_payment_method_manual_out")
        return self.env["account.journal"].sudo().create({
            "name": f"Bank {code}",
            "type": "bank",
            "code": code,
            "currency_id": currency.id,
            "is_igtf": is_igtf,
            "company_id": self.company.id,
            "default_account_id": self.account_bank.id,
            "inbound_payment_method_line_ids": [Command.create({
                "name": f"In {code}",
                "payment_method_id": manual_in.id,
                "payment_account_id": self.account_bank.id,
            })],
            "outbound_payment_method_line_ids": [Command.create({
                "name": f"Out {code}",
                "payment_method_id": manual_out.id,
                "payment_account_id": self.account_bank.id,
            })],
        })

    def _create_document(self, move_type, amount, currency, lines=1):
        """`lines` splits `amount` into that many equal product lines: each
        line is converted and rounded on its own, which is what makes the
        invoice's balance differ by a cent from the payment's."""
        is_sale = move_type.startswith("out_")
        move = self.env["account.move"].create({
            "move_type": move_type,
            "partner_id": self.partner.id,
            "journal_id": (self.sale_journal if is_sale else self.purchase_journal).id,
            "currency_id": currency.id,
            "invoice_date": self.invoice_date,
            "date": self.invoice_date,
            "invoice_line_ids": [Command.create({
                "product_id": self.product.id,
                "quantity": 1.0,
                "price_unit": amount / lines,
                "account_id": (self.account_income if is_sale else self.account_expense).id,
                "tax_ids": [Command.set([self.test_tax.id if is_sale else self.test_purchase_tax.id])],
            }) for _line in range(lines)],
        })
        move.with_context(move_action_post_alert=True).action_post()
        return move

    def _pay(self, moves, journal, currency, amount=None, group=False):
        """Registra el pago por el wizard y devuelve los pagos creados."""
        last_id = self.env["account.payment"].search([], order="id desc", limit=1).id or 0
        wizard = self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=moves.ids, active_id=moves[:1].id,
        ).create({
            "journal_id": journal.id,
            "currency_id": currency.id,
            "payment_date": self.payment_date,
        })
        wizard.is_igtf = bool(journal.is_igtf)
        if group:
            wizard.group_payment = True
        if amount is not None:
            wizard.amount = amount
        wizard.action_create_payments()
        return self.env["account.payment"].search([("id", ">", last_id)])

    def _assert_payments_consistent(self, payments, payment_type, amount=None):
        """`amount` is the expected payment amount; where the journal has no
        IGTF it is the document's, with no 3% added."""
        self.assertTrue(payments, "El wizard debe crear al menos un pago.")
        for payment in payments:
            self.assertEqual(payment.payment_type, payment_type)
            if not payment.journal_id.is_igtf:
                self.assertEqual(payment.igtf_amount, 0.0, "Un diario sin IGTF no debe cobrar IGTF.")
                if amount is not None:
                    self.assertAlmostEqual(payment.amount, amount, places=2)
            lines = payment.move_id.line_ids
            self.assertEqual(
                payment.currency_id.round(sum(lines.mapped("balance"))), 0.0,
                "El asiento del pago debe cuadrar.",
            )
            for line in lines:
                if line.currency_id == line.company_currency_id:
                    self.assertAlmostEqual(
                        line.amount_currency, line.balance, places=2,
                        msg="En moneda de la compañía amount_currency debe igualar al balance.",
                    )
                else:
                    # Strict: a 0 * x product would let an inverted sign through.
                    self.assertGreater(
                        line.amount_currency * line.balance, 0,
                        "amount_currency y balance deben tener el mismo signo.",
                    )

    def _assert_settled(self, moves):
        for move in moves:
            self.assertIn(move.payment_state, ("paid", "in_payment"))

    # -- notas de crédito de cliente (pago outbound) --------------------------

    def test_01_customer_refund_usd_paid_in_vef_no_igtf(self):
        refund = self._create_document("out_refund", 100.0, self.currency_usd)
        payments = self._pay(refund, self.journal_vef, self.currency_vef)
        self._assert_payments_consistent(payments, "outbound", 100.0 * RATE)
        self._assert_settled(refund)

    def test_02_customer_refund_usd_paid_in_usd_journal_no_igtf(self):
        refund = self._create_document("out_refund", 100.0, self.currency_usd)
        payments = self._pay(refund, self.journal_usd, self.currency_usd)
        self._assert_payments_consistent(payments, "outbound", 100.0)
        self._assert_settled(refund)

    def test_03_customer_refund_usd_paid_in_usd_journal_with_igtf(self):
        refund = self._create_document("out_refund", 100.0, self.currency_usd)
        payments = self._pay(refund, self.journal_usd_igtf, self.currency_usd)
        self._assert_payments_consistent(payments, "outbound")

    def test_04_customer_refund_usd_partial_in_vef_no_igtf(self):
        refund = self._create_document("out_refund", 100.0, self.currency_usd)
        payments = self._pay(refund, self.journal_vef, self.currency_vef, amount=30.0 * RATE)
        self._assert_payments_consistent(payments, "outbound", 30.0 * RATE)
        self.assertEqual(refund.payment_state, "partial")

    def test_05_two_customer_refunds_grouped_in_vef_no_igtf(self):
        refunds = (
            self._create_document("out_refund", 100.0, self.currency_usd)
            | self._create_document("out_refund", 55.5, self.currency_usd)
        )
        payments = self._pay(refunds, self.journal_vef, self.currency_vef, group=True)
        self.assertEqual(len(payments), 1, "Las NC del mismo cliente se agrupan en un solo pago.")
        self._assert_payments_consistent(payments, "outbound", 155.5 * RATE)
        self._assert_settled(refunds)

    def test_06a_customer_refund_vef_paid_in_usd_journal_with_igtf(self):
        refund = self._create_document("out_refund", 102630.95, self.currency_vef)
        payments = self._pay(refund, self.journal_usd_igtf, self.currency_usd)
        self._assert_payments_consistent(payments, "outbound")

    def test_06b_customer_refund_vef_paid_in_vef(self):
        refund = self._create_document("out_refund", 102630.95, self.currency_vef)
        payments = self._pay(refund, self.journal_vef, self.currency_vef)
        self._assert_payments_consistent(payments, "outbound", 102630.95)
        self._assert_settled(refund)

    # -- notas de crédito de proveedor (pago inbound) -------------------------

    def test_07_supplier_refund_usd_paid_in_vef_no_igtf(self):
        refund = self._create_document("in_refund", 100.0, self.currency_usd)
        payments = self._pay(refund, self.journal_vef, self.currency_vef)
        self._assert_payments_consistent(payments, "inbound", 100.0 * RATE)
        self._assert_settled(refund)

    def test_07b_supplier_refund_vef_paid_in_vef(self):
        refund = self._create_document("in_refund", 102630.95, self.currency_vef)
        payments = self._pay(refund, self.journal_vef, self.currency_vef)
        self._assert_payments_consistent(payments, "inbound", 102630.95)
        self._assert_settled(refund)

    # -- regresión: facturas normales -----------------------------------------

    def test_08a_customer_invoice_usd_paid_in_vef_no_igtf(self):
        invoice = self._create_document("out_invoice", 100.0, self.currency_usd)
        payments = self._pay(invoice, self.journal_vef, self.currency_vef)
        self._assert_payments_consistent(payments, "inbound", 100.0 * RATE)
        self._assert_settled(invoice)

    def test_08b_customer_invoice_usd_paid_in_usd_journal_with_igtf(self):
        invoice = self._create_document("out_invoice", 100.0, self.currency_usd)
        payments = self._pay(invoice, self.journal_usd_igtf, self.currency_usd)
        self._assert_payments_consistent(payments, "inbound")

    def test_08c_customer_invoice_vef_paid_in_vef(self):
        invoice = self._create_document("out_invoice", 102630.95, self.currency_vef)
        payments = self._pay(invoice, self.journal_vef, self.currency_vef)
        self._assert_payments_consistent(payments, "inbound", 102630.95)
        self._assert_settled(invoice)

    def test_08d_supplier_bill_vef_paid_in_vef(self):
        bill = self._create_document("in_invoice", 102630.95, self.currency_vef)
        payments = self._pay(bill, self.journal_vef, self.currency_vef)
        self._assert_payments_consistent(payments, "outbound", 102630.95)
        self._assert_settled(bill)

    # -- tolerancia de redondeo del balance (moneda de la compañía) -----------

    def _activate_currency(self, xmlid, rate):
        currency = self.env.ref(xmlid)
        currency.active = True
        self._set_rate(currency, self.payment_date, rate)
        return currency

    def _receivable_payable_balance(self, payments):
        lines = payments.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type in ("asset_receivable", "liability_payable")
        )
        return abs(sum(lines.mapped("balance")))

    def test_09_full_payment_matches_residual_exactly_in_any_currency(self):
        """El balance (siempre en la moneda de la compañía) del pago total cubre
        el residual de la factura sin diferencia de redondeo, sea cual sea la
        moneda del documento y la del diario, incluso con tasas de muchos decimales."""
        cc = self.company.currency_id
        eur = self._activate_currency("base.EUR", 39.1234)
        self._set_rate(self.currency_usd, self.payment_date, 36.4567)
        journal_eur = self._make_bank_journal("BEUR", eur)
        cases = [
            (self.currency_usd, 33.33, self.journal_vef, self.currency_vef),
            (self.currency_usd, 33.33, self.journal_usd, self.currency_usd),
            (eur, 77.77, self.journal_vef, self.currency_vef),
            (eur, 77.77, journal_eur, eur),
            (self.currency_vef, 1234.56, self.journal_vef, self.currency_vef),
        ]
        for doc_currency, amount, journal, pay_currency in cases:
            for move_type in ("out_invoice", "in_invoice"):
                with self.subTest(doc=doc_currency.name, pay=pay_currency.name, type=move_type):
                    doc = self._create_document(move_type, amount, doc_currency)
                    residual = abs(doc.amount_residual_signed)
                    payments = self._pay(doc, journal, pay_currency)
                    self.assertEqual(
                        cc.compare_amounts(self._receivable_payable_balance(payments), residual), 0,
                        "El balance del pago debe igualar el residual de la factura.",
                    )
                    self._assert_settled(doc)

    def test_12_one_cent_rounding_gap_in_company_currency_is_snapped(self):
        """Tres líneas de 10.00 USD a 36.4567: la factura suma 3 x 364.57 =
        1093.71 VEF y el pago de 30.00 USD convierte a 1093.70. Ese centavo de
        redondeo, igual al de VEF, se ajusta para que el pago cubra el residual."""
        cc = self.company.currency_id
        eur = self._activate_currency("base.EUR", 36.4567)
        self._set_rate(self.currency_usd, self.payment_date, 36.4567)
        journal_eur = self._make_bank_journal("BEUR", eur)
        for move_type in ("out_invoice", "in_invoice"):
            for currency, journal in ((self.currency_usd, self.journal_usd), (eur, journal_eur)):
                with self.subTest(type=move_type, currency=currency.name):
                    doc = self._create_document(move_type, 30.0, currency, lines=3)
                    residual_vef = abs(doc.amount_residual_signed)
                    self.assertEqual(residual_vef, 1093.71, "Fixture: 3 líneas redondeadas por separado.")
                    payments = self._pay(doc, journal, currency)
                    self.assertEqual(
                        cc.compare_amounts(self._receivable_payable_balance(payments), residual_vef), 0,
                    )
                    self._assert_settled(doc)

    def test_13_rounding_gap_is_not_snapped_when_invoice_date_differs_from_payment_date(self):
        """El ajuste solo corre cuando la fecha de la factura es la del pago.
        Con la misma tasa y el mismo desfase de 0.01 del caso anterior, una
        factura de otro día no se ajusta."""
        cc = self.company.currency_id
        previous_day = fields.Date.subtract(self.payment_date, days=1)
        self._set_rate(self.currency_usd, previous_day, 36.4567)
        self._set_rate(self.currency_usd, self.payment_date, 36.4567)
        self.invoice_date = previous_day
        doc = self._create_document("out_invoice", 30.0, self.currency_usd, lines=3)
        self.assertEqual(abs(doc.amount_residual_signed), 1093.71)
        payments = self._pay(doc, self.journal_usd, self.currency_usd)
        self.assertEqual(
            cc.compare_amounts(self._receivable_payable_balance(payments), 1093.70), 0,
            "Con fechas distintas el balance del pago no se ajusta al residual.",
        )
