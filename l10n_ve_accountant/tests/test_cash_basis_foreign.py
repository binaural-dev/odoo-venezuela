from odoo import Command, fields
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_accountant_test")
class TestCashBasisForeign(TransactionCase):
    """El asiento de base efectivo (IMBEF) debe traer el monto en moneda
    alterna en TODAS sus lineas, incluidas las de impuesto.

    Caso: factura en USD de 100 + 16% de IVA (tasa 889,5754) con impuesto
    exigible "al pagar". Al cobrar, el core genera el asiento que pasa el IVA
    de la cuenta transitoria a la definitiva.
    """

    RATE = 889.5754
    BASE_USD = 100.0
    TAX_USD = 16.0
    BASE_BS = 88957.54
    TAX_BS = 14233.21

    def setUp(self):
        super().setUp()
        self.usd = self.env.ref("base.USD")
        self.vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")
        self.company.write(
            {
                "currency_id": self.vef.id,
                "foreign_currency_id": self.usd.id,
                "account_fiscal_country_id": self.env.ref("base.ve").id,
                "country_id": self.env.ref("base.ve").id,
                "tax_exigibility": True,
            }
        )
        self.today = fields.Date.today()
        Rate = self.env["res.currency.rate"]
        for currency, value in ((self.vef, 1.0), (self.usd, self.RATE)):
            rate = Rate.search(
                [
                    ("name", "=", self.today),
                    ("currency_id", "=", currency.id),
                    ("company_id", "=", self.company.id),
                ],
                limit=1,
            )
            if rate:
                rate.inverse_company_rate = value
            else:
                Rate.create(
                    {
                        "name": self.today,
                        "currency_id": currency.id,
                        "inverse_company_rate": value,
                        "company_id": self.company.id,
                    }
                )

        Account = self.env["account.account"]

        def account(code, name, account_type, reconcile=False):
            return Account.create(
                {
                    "code": code,
                    "name": name,
                    "account_type": account_type,
                    "reconcile": reconcile,
                    "company_ids": [Command.set(self.company.ids)],
                }
            )

        self.acc_receivable = account(
            "CB1001", "CB Receivable", "asset_receivable", True
        )
        self.acc_income = account("CB4001", "CB Income", "income")
        self.acc_bank = account("CB1002", "CB Bank", "asset_cash")
        self.acc_transition = account(
            "CB2001", "CB IVA por declarar", "liability_current", True
        )
        self.acc_final = account("CB2002", "CB Debito fiscal", "liability_current")
        self.acc_base = account(
            "CB2003", "CB Cuenta transitoria base", "liability_current", True
        )
        self.company.account_cash_basis_base_account_id = self.acc_base

        if not self.company.tax_cash_basis_journal_id:
            self.company.tax_cash_basis_journal_id = self.env[
                "account.journal"
            ].create(
                {
                    "name": "CB Cash Basis",
                    "code": "CBIMB",
                    "type": "general",
                    "company_id": self.company.id,
                }
            )

        tax_group = self.env["account.tax.group"].create(
            {
                "name": "CB Tax Group",
                "company_id": self.company.id,
                "country_id": self.env.ref("base.ve").id,
            }
        )
        repartition = lambda: [  # noqa: E731
            Command.create({"repartition_type": "base"}),
            Command.create(
                {"repartition_type": "tax", "account_id": self.acc_final.id}
            ),
        ]
        self.tax = self.env["account.tax"].create(
            {
                "name": "CB IVA 16% al pagar",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": self.company.id,
                "tax_group_id": tax_group.id,
                "tax_exigibility": "on_payment",
                "cash_basis_transition_account_id": self.acc_transition.id,
                "invoice_repartition_line_ids": repartition(),
                "refund_repartition_line_ids": repartition(),
            }
        )

        self.partner = self.env["res.partner"].create(
            {
                "name": "CB Partner",
                "country_id": self.env.ref("base.ve").id,
                "property_account_receivable_id": self.acc_receivable.id,
            }
        )
        self.sale_journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].create(
            {
                "name": "CB Sales",
                "code": "CBSAL",
                "type": "sale",
                "company_id": self.company.id,
                "default_account_id": self.acc_income.id,
            }
        )
        self.bank_journal = self.env["account.journal"].create(
            {
                "name": "CB Bank",
                "code": "CBBNK",
                "type": "bank",
                "company_id": self.company.id,
                "default_account_id": self.acc_bank.id,
                "currency_id": self.usd.id,
            }
        )
        self.product = self.env["product.product"].create(
            {
                "name": "CB Product",
                "type": "service",
                "list_price": self.BASE_USD,
                "taxes_id": [Command.set(self.tax.ids)],
                "property_account_income_id": self.acc_income.id,
            }
        )

    # ------------------------------------------------------------------
    def _make_invoice(self):
        """Factura creada como la crearia un usuario: con Form."""
        form = Form(
            self.env["account.move"].with_context(default_move_type="out_invoice")
        )
        form.partner_id = self.partner
        form.journal_id = self.sale_journal
        form.currency_id = self.usd
        form.invoice_date = self.today
        with form.invoice_line_ids.new() as line:
            line.product_id = self.product
            line.quantity = 1
            line.price_unit = self.BASE_USD
        invoice = form.save()
        # El impuesto lo propone el producto, como en pantalla.
        self.assertEqual(invoice.invoice_line_ids.tax_ids, self.tax)
        invoice.action_post()
        return invoice

    def _pay(self, invoice, amount=None):
        """Pago registrado con el asistente "Registrar pago", via Form."""
        form = Form(
            self.env["account.payment.register"].with_context(
                active_model="account.move", active_ids=invoice.ids
            )
        )
        form.journal_id = self.bank_journal
        form.payment_date = self.today
        if amount is not None:
            form.amount = amount
        return form.save()._create_payments()

    def _line(self, move, account):
        return move.line_ids.filtered(lambda l: l.account_id == account)

    def _caba_moves(self, invoice):
        return self.env["account.move"].search(
            [("tax_cash_basis_origin_move_id", "=", invoice.id)]
        )

    # ------------------------------------------------------------------
    def test_invoice_entry_amounts(self):
        """1. Factura: IVA en la cuenta transitoria, con monto alterno."""
        invoice = self._make_invoice()
        receivable = self._line(invoice, self.acc_receivable)
        income = self._line(invoice, self.acc_income)
        tax = self._line(invoice, self.acc_transition)

        self.assertEqual(len(invoice.line_ids), 3)
        self.assertAlmostEqual(receivable.debit, self.BASE_BS + self.TAX_BS, 2)
        self.assertAlmostEqual(receivable.amount_currency, 116.0, 2)
        self.assertAlmostEqual(receivable.foreign_debit, 116.0, 2)
        self.assertAlmostEqual(income.credit, self.BASE_BS, 2)
        self.assertAlmostEqual(income.amount_currency, -100.0, 2)
        self.assertAlmostEqual(income.foreign_credit, 100.0, 2)
        self.assertAlmostEqual(tax.credit, self.TAX_BS, 2)
        self.assertAlmostEqual(tax.amount_currency, -16.0, 2)
        self.assertAlmostEqual(tax.foreign_credit, 16.0, 2)

    def test_payment_entry_amounts(self):
        """2. Pago: banco / cuentas por cobrar, sin impuestos."""
        invoice = self._make_invoice()
        payment = self._pay(invoice)
        move = payment.move_id

        self.assertEqual(invoice.payment_state, "paid")
        self.assertEqual(len(move.line_ids), 2)
        bank = self._line(move, self.acc_bank) or move.line_ids.filtered(
            lambda l: l.debit
        )
        receivable = move.line_ids.filtered(
            lambda l: l.account_id == self.acc_receivable
        )
        self.assertAlmostEqual(bank.debit, self.BASE_BS + self.TAX_BS, 2)
        self.assertAlmostEqual(bank.foreign_debit, 116.0, 2)
        self.assertAlmostEqual(receivable.credit, self.BASE_BS + self.TAX_BS, 2)
        self.assertAlmostEqual(receivable.foreign_credit, 116.0, 2)

    def test_cash_basis_entry_has_foreign_amounts_in_all_lines(self):
        """3. IMBEF: las 4 lineas (base e impuesto) con monto alterno."""
        invoice = self._make_invoice()
        self._pay(invoice)

        caba = self._caba_moves(invoice)
        self.assertEqual(len(caba), 1, "Debe generarse un unico asiento IMBEF")
        self.assertEqual(caba.journal_id, self.company.tax_cash_basis_journal_id)
        self.assertEqual(len(caba.line_ids), 4)

        # Lineas de base (cuenta transitoria de base): debe y haber.
        base_lines = self._line(caba, self.acc_base)
        self.assertEqual(len(base_lines), 2)
        base_debit = base_lines.filtered(lambda l: l.debit)
        base_credit = base_lines.filtered(lambda l: l.credit)
        self.assertAlmostEqual(base_debit.debit, self.BASE_BS, 2)
        self.assertAlmostEqual(base_debit.amount_currency, 100.0, 2)
        self.assertAlmostEqual(base_debit.foreign_debit, 100.0, 2)
        self.assertAlmostEqual(base_credit.credit, self.BASE_BS, 2)
        self.assertAlmostEqual(base_credit.amount_currency, -100.0, 2)
        self.assertAlmostEqual(base_credit.foreign_credit, 100.0, 2)

        # Lineas de impuesto: salen de la transitoria y entran a la definitiva.
        tax_from = self._line(caba, self.acc_transition)
        tax_to = self._line(caba, self.acc_final)
        self.assertAlmostEqual(tax_from.debit, self.TAX_BS, 2)
        self.assertAlmostEqual(tax_from.amount_currency, 16.0, 2)
        self.assertAlmostEqual(tax_from.foreign_debit, 16.0, 2)
        self.assertAlmostEqual(tax_from.foreign_balance, 16.0, 2)
        self.assertAlmostEqual(tax_to.credit, self.TAX_BS, 2)
        self.assertAlmostEqual(tax_to.amount_currency, -16.0, 2)
        self.assertAlmostEqual(tax_to.foreign_credit, 16.0, 2)
        self.assertAlmostEqual(tax_to.foreign_balance, -16.0, 2)

        # El asiento cuadra en bolivares y en moneda alterna.
        self.assertAlmostEqual(sum(caba.line_ids.mapped("balance")), 0.0, 2)
        self.assertAlmostEqual(sum(caba.line_ids.mapped("foreign_balance")), 0.0, 2)
        self.assertAlmostEqual(
            sum(caba.line_ids.mapped("foreign_debit")),
            sum(caba.line_ids.mapped("foreign_credit")),
            2,
        )

    def test_cash_basis_entry_partial_payment_is_proportional(self):
        """4. Pago parcial del 50%: el IMBEF mueve la mitad, tambien en alterno."""
        invoice = self._make_invoice()
        self._pay(invoice, amount=58.0)

        caba = self._caba_moves(invoice)
        self.assertEqual(len(caba), 1)
        tax_from = self._line(caba, self.acc_transition)
        tax_to = self._line(caba, self.acc_final)
        self.assertAlmostEqual(tax_from.amount_currency, 8.0, 2)
        self.assertAlmostEqual(tax_from.foreign_debit, 8.0, 2)
        self.assertAlmostEqual(tax_to.amount_currency, -8.0, 2)
        self.assertAlmostEqual(tax_to.foreign_credit, 8.0, 2)
        self.assertAlmostEqual(sum(caba.line_ids.mapped("foreign_balance")), 0.0, 2)
