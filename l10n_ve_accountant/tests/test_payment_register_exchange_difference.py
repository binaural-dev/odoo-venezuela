from datetime import timedelta

from odoo.tests import TransactionCase, tagged
from odoo import fields, Command


@tagged("post_install", "-at_install", "l10n_ve_accountant")
class TestPaymentRegisterExchangeDifference(TransactionCase):
    """
    Ticket #15626: when the payment difference is marked as fully paid against an exchange
    difference account, the payment entry must carry the difference on that account (with the
    payment date) and the invoices must end fully reconciled without remaining cents.
    """

    # Invoice prices in company currency and payment differences in the alternate currency.
    PRICES = (12345.67, 9876.54, 4567.89, 1234.56)
    DIFFERENCES = (-1.37, 0.83, -0.91, -0.47)

    def setUp(self):
        super().setUp()
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        (self.currency_usd | self.currency_vef).active = True
        self.country_ve = self.env.ref("base.ve")
        self.company = self.env.ref("base.main_company")
        self._setup_company_currencies()

        self.invoice_date = fields.Date.today() - timedelta(days=5)
        self.payment_date = fields.Date.today()
        self._setup_rates()

        Account = self.env["account.account"]
        self.acc_receivable = Account.create({
            "name": "CXC Diferencial", "code": "119901",
            "account_type": "asset_receivable", "reconcile": True,
        })
        self.acc_payable = Account.create({
            "name": "CXP Diferencial", "code": "219901",
            "account_type": "liability_payable", "reconcile": True,
        })
        self.acc_income = Account.create({
            "name": "Ingresos Diferencial", "code": "419901", "account_type": "income",
        })
        self.acc_expense = Account.create({
            "name": "Gastos Diferencial", "code": "519901", "account_type": "expense",
        })
        self.acc_outstanding = Account.create({
            "name": "Pagos pendientes Diferencial", "code": "119902",
            "account_type": "asset_current", "reconcile": True,
        })
        self.acc_exchange_gain = Account.create({
            "name": "Ganancia diferencial cambiario", "code": "429901", "account_type": "income",
        })
        self.acc_exchange_loss = Account.create({
            "name": "Pérdida diferencial cambiario", "code": "529901", "account_type": "expense",
        })
        self.company.write({
            "account_journal_payment_debit_account_id": self.acc_outstanding.id,
            "account_journal_payment_credit_account_id": self.acc_outstanding.id,
            "income_currency_exchange_account_id": self.acc_exchange_gain.id,
            "expense_currency_exchange_account_id": self.acc_exchange_loss.id,
        })

        Journal = self.env["account.journal"]
        self.sale_journal = Journal.create({
            "name": "Ventas Diferencial", "code": "VDIF", "type": "sale",
            "default_account_id": self.acc_income.id,
        })
        self.purchase_journal = Journal.create({
            "name": "Compras Diferencial", "code": "CDIF", "type": "purchase",
            "default_account_id": self.acc_expense.id,
        })
        self.bank_journal_foreign = Journal.create({
            "name": "Banco moneda alterna", "code": "BDIF", "type": "bank",
            "currency_id": self.company.currency_foreign_id.id,
        })

        self.partner = self.env["res.partner"].create({
            "name": "Partner Diferencial",
            "country_id": self.country_ve.id,
            "property_account_receivable_id": self.acc_receivable.id,
            "property_account_payable_id": self.acc_payable.id,
        })
        self.product = self.env["product.product"].create({
            "name": "Servicio Diferencial", "type": "service",
            "taxes_id": [Command.clear()], "supplier_taxes_id": [Command.clear()],
        })

    def _setup_company_currencies(self):
        self.company.write({
            "currency_id": self.currency_vef.id,
            "currency_foreign_id": self.currency_usd.id,
            "account_fiscal_country_id": self.country_ve.id,
            "country_id": self.country_ve.id,
        })

    def _setup_rates(self):
        for date in (self.invoice_date, self.payment_date):
            self.env["res.currency.rate"].create({
                "name": date, "currency_id": self.currency_usd.id,
                "inverse_company_rate": 36.5871, "company_id": self.company.id,
            })

    def _create_move(self, move_type, price_unit):
        is_sale = move_type == "out_invoice"
        move = self.env["account.move"].create({
            "move_type": move_type,
            "partner_id": self.partner.id,
            "journal_id": (self.sale_journal if is_sale else self.purchase_journal).id,
            "currency_id": self.company.currency_id.id,
            "invoice_date": self.invoice_date,
            "date": self.invoice_date,
            "invoice_line_ids": [Command.create({
                "product_id": self.product.id,
                "quantity": 1.0,
                "price_unit": price_unit,
                "account_id": (self.acc_income if is_sale else self.acc_expense).id,
                "tax_ids": [Command.clear()],
            })],
        })
        move.with_context(move_action_post_alert=True).action_post()
        return move

    def _register_payment(self, moves, amount, writeoff_account, group_payment=False):
        wizard = self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=moves.ids,
        ).create({
            "journal_id": self.bank_journal_foreign.id,
            "payment_date": self.payment_date,
            "group_payment": group_payment,
        })
        self.assertEqual(wizard.currency_id, self.company.currency_foreign_id)
        wizard.write({
            "amount": amount,
            "payment_difference_handling": "reconcile",
            "writeoff_account_id": writeoff_account.id,
            "writeoff_label": "Diferencial cambiario",
        })
        self.assertTrue(
            wizard.writeoff_is_exchange_account,
            "The write-off account must be detected as an exchange difference account",
        )
        self.assertTrue(wizard.payment_difference)
        payment_vals = wizard._create_payment_vals_from_wizard(wizard._get_batches()[0])
        self.assertNotIn(
            "force_balance", payment_vals,
            "force_balance is discarded by the liquidity line recomputation, it must be replaced "
            "by an explicit write-off line",
        )
        return wizard._create_payments()

    def _assert_exchange_difference_payment(self, payment, moves, writeoff_account):
        comp_curr = self.company.currency_id
        lines = payment.move_id.line_ids
        self.assertEqual(len(lines), 3, "Liquidity, counterpart and exchange difference lines")

        writeoff_line = lines.filtered(lambda l: l.account_id == writeoff_account)
        self.assertEqual(len(writeoff_line), 1, "The difference must land on the chosen account")
        self.assertEqual(writeoff_line.date, self.payment_date)
        self.assertNotEqual(writeoff_line.date, self.invoice_date)
        self.assertFalse(comp_curr.is_zero(writeoff_line.balance))

        self.assertTrue(comp_curr.is_zero(sum(lines.mapped("balance"))))
        for move in moves:
            self.assertIn(move.payment_state, ("paid", "in_payment"))
            self.assertTrue(comp_curr.is_zero(move.amount_residual), "No remaining cents")
            term_lines = move.line_ids.filtered(
                lambda l: l.account_id.account_type in ("asset_receivable", "liability_payable")
            )
            self.assertTrue(term_lines.full_reconcile_id, "The invoice must be fully reconciled")
            self.assertFalse(
                term_lines.matched_debit_ids.exchange_move_id
                | term_lines.matched_credit_ids.exchange_move_id,
                "The difference must not be posted later as an exchange difference entry",
            )

    def _foreign_amount(self, company_amount, adjust):
        """Amount in the alternate currency equivalent to company_amount, moved by adjust."""
        foreign_curr = self.company.currency_foreign_id
        return foreign_curr.round(
            self.company.currency_id._convert(
                company_amount, foreign_curr, self.company, self.payment_date,
            ) + adjust
        )

    def test_customer_invoice_underpaid(self):
        invoice = self._create_move("out_invoice", self.PRICES[0])
        payment = self._register_payment(
            invoice, self._foreign_amount(invoice.amount_residual, self.DIFFERENCES[0]), self.acc_exchange_loss,
        )
        self._assert_exchange_difference_payment(payment, invoice, self.acc_exchange_loss)

    def test_customer_invoice_overpaid(self):
        invoice = self._create_move("out_invoice", self.PRICES[0])
        payment = self._register_payment(
            invoice, self._foreign_amount(invoice.amount_residual, self.DIFFERENCES[1]), self.acc_exchange_gain,
        )
        self._assert_exchange_difference_payment(payment, invoice, self.acc_exchange_gain)

    def test_vendor_bill_underpaid(self):
        bill = self._create_move("in_invoice", self.PRICES[1])
        payment = self._register_payment(
            bill, self._foreign_amount(bill.amount_residual, self.DIFFERENCES[2]), self.acc_exchange_gain,
        )
        self.assertEqual(payment.payment_type, "outbound")
        self._assert_exchange_difference_payment(payment, bill, self.acc_exchange_gain)

    def test_batch_invoices_grouped_payment(self):
        invoices = self._create_move("out_invoice", self.PRICES[2]) | self._create_move(
            "out_invoice", self.PRICES[3]
        )
        payment = self._register_payment(
            invoices,
            self._foreign_amount(sum(invoices.mapped("amount_residual")), self.DIFFERENCES[3]),
            self.acc_exchange_loss,
            group_payment=True,
        )
        self.assertEqual(len(payment), 1)
        self._assert_exchange_difference_payment(payment, invoices, self.acc_exchange_loss)


@tagged("post_install", "-at_install", "l10n_ve_accountant")
class TestPaymentRegisterExchangeDifferenceUsdCompany(TestPaymentRegisterExchangeDifference):
    """Same scenarios with USD as company currency (multi-currency) paying from a VEF journal."""

    PRICES = (345.67, 276.54, 167.89, 134.56)
    DIFFERENCES = (-37.21, 21.13, -19.09, -17.47)

    def _setup_company_currencies(self):
        self.company.write({
            "currency_id": self.currency_usd.id,
            "currency_foreign_id": self.currency_vef.id,
            "account_fiscal_country_id": self.country_ve.id,
            "country_id": self.country_ve.id,
        })

    def _setup_rates(self):
        for date in (self.invoice_date, self.payment_date):
            self.env["res.currency.rate"].create({
                "name": date, "currency_id": self.currency_vef.id,
                "rate": 36.5871, "company_id": self.company.id,
            })
