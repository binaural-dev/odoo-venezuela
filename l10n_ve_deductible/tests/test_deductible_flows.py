from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, TransactionCase, tagged

from .common import AssertMixin, ensure_ve_base


@tagged("post_install", "-at_install", "l10n_ve_deductible")
class TestDeductibleFlows(AssertMixin, TransactionCase):
    """Posting, payments, form flow, several taxes and report rendering, for
    both rounding methods and both bill currencies (VEF base / USD alternate,
    recent market rates)."""

    RATES = (0.00116565386887513, 0.001166853246500782)
    METHODS = ("round_per_line", "round_globally")
    LINES = [(10.3333, 3), (7.1249, 7), (0.9999, 13), (123.4567, 1), (3.3333, 9)]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ensure_ve_base(cls.env)
        cls.env.ref("product.decimal_price").digits = 4
        cls.vef = cls.env.ref("base.VEF")
        cls.usd = cls.env.ref("base.USD")
        cls.company = cls.env.company
        cls.company.write(
            {"use_deductible": True, "discount_type": "percent"}
        )
        cls.partner = cls.env["res.partner"].create({"name": "Proveedor Flujos"})
        cls.exempt = cls.env["account.tax"].create(
            {"name": "Ex Flow", "amount_type": "percent", "amount": 0.0, "type_tax_use": "purchase"}
        )
        cls.exempt2 = cls.env["account.tax"].create(
            {"name": "Ex Flow 2", "amount_type": "percent", "amount": 0.0, "type_tax_use": "purchase"}
        )
        cls.general = cls.env["account.tax"].create(
            {"name": "IVA Flow", "amount_type": "percent", "amount": 16.0, "type_tax_use": "purchase"}
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Prod Flow", "supplier_taxes_id": [Command.set(cls.exempt.ids)]}
        )

    def _set_rate(self, rate):
        Rate = self.env["res.currency.rate"]
        Rate.search([("name", "=", fields.Date.today()), ("company_id", "=", self.company.id)]).unlink()
        Rate.create({"name": fields.Date.today(), "currency_id": self.vef.id,
                     "rate": 1.0, "company_id": self.company.id})
        Rate.create({"name": fields.Date.today(), "currency_id": self.usd.id,
                     "rate": rate, "company_id": self.company.id})

    def _bill(self, currency, taxes=None, lines=None, **vals):
        taxes = taxes or self.exempt
        return self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "currency_id": currency.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create({"product_id": self.product.id, "name": f"L{i}",
                                    "quantity": q, "price_unit": p,
                                    "tax_ids": [Command.set(taxes.ids)]})
                    for i, (p, q) in enumerate(lines or self.LINES)
                ],
                **vals,
            }
        )

    def _combos(self):
        for method in self.METHODS:
            for currency in (self.usd, self.vef):
                for rate in self.RATES:
                    yield method, currency, rate

    def _setup_combo(self, method, rate):
        self.company.tax_calculation_rounding_method = method
        self._set_rate(rate)

    DEDUCTIBLES = (
        {"global_deductible_type": "percent", "global_deductible_percent": 12.5},
        {"global_deductible_type": "amount", "global_deductible_amount": 77.77},
    )

    def test_post_balanced_in_every_combination(self):
        for method, currency, rate in self._combos():
            for deductible in self.DEDUCTIBLES:
                with self.subTest(method=method, currency=currency.name, rate=rate, **deductible):
                    self._setup_combo(method, rate)
                    bill = self._bill(currency, is_deductible=True, **deductible)
                    bill.action_post()
                    self.assertEqual(bill.state, "posted")
                    self.assertEqual(
                        round(sum(bill.line_ids.mapped("debit")), 2),
                        round(sum(bill.line_ids.mapped("credit")), 2),
                    )
                    payable = bill.line_ids.filtered(
                        lambda l: l.account_id.account_type == "liability_payable"
                    )
                    self.assertEqual(
                        round(abs(sum(payable.mapped("balance"))), 2),
                        round(abs(bill.amount_total_signed), 2),
                    )
                    self.assertTrue(bill.tax_totals.get("is_deductible"))
                    with self.assertRaisesMsg(UserError, "draft bills"):
                        bill.write({"global_deductible_percent": 5.0})
                    with self.assertRaisesMsg(UserError, "draft bills"):
                        bill.write({"is_deductible": False})
                    bill.button_draft()
                    bill.is_deductible = False
                    self.assertFalse(any(bill.invoice_line_ids.mapped("global_deductible_discount_percent")))

    def test_pay_posted_bill(self):
        journal = self.env["account.journal"].search(
            [("type", "in", ("bank", "cash")), ("company_id", "=", self.company.id)], limit=1
        )
        self.assertTrue(journal, "the clean DB must have a bank journal")
        for method, currency, rate in self._combos():
            with self.subTest(method=method, currency=currency.name, rate=rate):
                self._setup_combo(method, rate)
                bill = self._bill(currency, is_deductible=True, **self.DEDUCTIBLES[1])
                bill.action_post()
                account = self.env["account.account"].search(
                    [("account_type", "in", ("asset_cash", "asset_current")),
                     ("company_ids", "in", self.company.ids)], limit=1)
                journal.outbound_payment_method_line_ids.payment_account_id = account
                wizard = self.env["account.payment.register"].with_context(
                    active_model="account.move", active_ids=bill.ids
                ).create({"journal_id": journal.id})
                wizard.action_create_payments()
                self.assertIn(bill.payment_state, ("paid", "in_payment"))
                self.assertEqual(bill.amount_residual, 0.0)

    def test_two_exempt_taxes_on_a_line(self):
        for method, currency, rate in self._combos():
            with self.subTest(method=method, currency=currency.name, rate=rate):
                self._setup_combo(method, rate)
                taxes = self.exempt | self.exempt2
                mine = self._bill(taxes=taxes, currency=currency, is_deductible=True,
                                  global_deductible_type="percent", global_deductible_percent=12.5)
                native = self.env["account.move"].create(
                    {
                        "move_type": "in_invoice", "partner_id": self.partner.id,
                        "currency_id": currency.id, "invoice_date": fields.Date.today(),
                        "invoice_line_ids": [
                            Command.create({"product_id": self.product.id, "name": "n",
                                            "quantity": q, "price_unit": p, "discount": 12.5,
                                            "tax_ids": [Command.set(taxes.ids)]})
                            for p, q in self.LINES
                        ],
                    }
                )
                self.assertEqual(mine.amount_untaxed, native.amount_untaxed)
                self.assertEqual(mine.amount_total_signed, native.amount_total_signed)
                self.assertEqual(
                    mine.invoice_line_ids.mapped("balance"), native.invoice_line_ids.mapped("balance")
                )

    def test_taxed_line_rejected_in_every_combination(self):
        for method, currency, rate in self._combos():
            with self.subTest(method=method, currency=currency.name, rate=rate):
                self._setup_combo(method, rate)
                with self.assertRaisesMsg(ValidationError, "exempt tax"):
                    self._bill(currency, taxes=self.general, is_deductible=True,
                               global_deductible_type="percent", global_deductible_percent=10.0)
                bill = self._bill(currency)
                bill.invoice_line_ids[0].tax_ids = self.general
                with self.assertRaisesMsg(ValidationError, "exempt tax"):
                    bill.write({"is_deductible": True, "global_deductible_type": "percent",
                                "global_deductible_percent": 10.0})

    def test_company_exempt_tax_is_accepted(self):
        """A tax that is not a 0% percent tax is accepted as exempt only when
        it is the one configured as the company's purchase exempt aliquot."""
        self._setup_combo("round_globally", self.RATES[0])
        configured = self.env["account.tax"].create(
            {"name": "Exento config", "amount_type": "fixed", "amount": 0.0,
             "type_tax_use": "purchase"}
        )
        with self.assertRaisesMsg(ValidationError, "exempt tax"):
            self._bill(self.usd, taxes=configured, is_deductible=True,
                       global_deductible_type="percent", global_deductible_percent=10.0)
        self.company.exent_aliquot_purchase = configured
        bill = self._bill(self.usd, taxes=configured, is_deductible=True,
                          global_deductible_type="percent", global_deductible_percent=10.0)
        self.assertTrue(bill.is_deductible)

    def test_form_flow_in_every_combination(self):
        for method, currency, rate in self._combos():
            with self.subTest(method=method, currency=currency.name, rate=rate):
                self._setup_combo(method, rate)
                form = Form(self.env["account.move"].with_context(default_move_type="in_invoice"))
                form.partner_id = self.partner
                form.invoice_date = fields.Date.today()
                form.currency_id = currency
                for price, qty in self.LINES[:3]:
                    with form.invoice_line_ids.new() as line:
                        line.product_id = self.product
                        line.quantity = qty
                        line.price_unit = price
                form.is_deductible = True
                form.global_deductible_type = "amount"
                form.global_deductible_amount = 20.0
                with form.invoice_line_ids.edit(0) as line:
                    line.price_unit = 50.1234
                with form.invoice_line_ids.new() as line:
                    line.product_id = self.product
                    line.quantity = 2
                    line.price_unit = 8.7654
                live_total = form.tax_totals["total_amount_currency"]
                bill = form.save()
                self.assertEqual(round(live_total, 2), round(bill.amount_total, 2))
                self.assertTrue(bill.is_deductible)
                direct = self._bill(
                    currency,
                    lines=[(l.price_unit, l.quantity) for l in bill.invoice_line_ids],
                    is_deductible=True, global_deductible_type="amount", global_deductible_amount=20.0,
                )
                self.assertEqual(bill.amount_untaxed, direct.amount_untaxed)
                self.assertEqual(bill.amount_total_signed, direct.amount_total_signed)
                with Form(bill) as f:
                    f.is_deductible = False
                plain = self._bill(
                    currency, lines=[(l.price_unit, l.quantity) for l in bill.invoice_line_ids]
                )
                self.assertEqual(bill.amount_untaxed, plain.amount_untaxed)
                self.assertEqual(bill.amount_total_signed, plain.amount_total_signed)
                self.assertEqual(bill.invoice_line_ids.mapped("balance"),
                                 plain.invoice_line_ids.mapped("balance"))
                self.assertFalse(any(bill.invoice_line_ids.mapped("global_deductible_discount_percent")))
                self.assertFalse(bill.tax_totals.get("is_deductible"))

    def test_edit_prices_and_add_lines_in_every_combination(self):
        for method, currency, rate in self._combos():
            with self.subTest(method=method, currency=currency.name, rate=rate):
                self._setup_combo(method, rate)
                bill = self._bill(currency, is_deductible=True, **self.DEDUCTIBLES[1])
                bill.invoice_line_ids[0].price_unit = 55.5555
                bill.write({"invoice_line_ids": [Command.create(
                    {"product_id": self.product.id, "name": "N", "quantity": 4, "price_unit": 19.9876,
                     "tax_ids": [Command.set(self.exempt.ids)]})]})
                lines = [(l.price_unit, l.quantity) for l in bill.invoice_line_ids]
                direct = self._bill(currency, lines=lines, is_deductible=True, **self.DEDUCTIBLES[1])
                self.assertEqual(bill.amount_untaxed, direct.amount_untaxed)
                self.assertEqual(bill.amount_total_signed, direct.amount_total_signed)
                self.assertEqual(bill.invoice_line_ids.mapped("balance"),
                                 direct.invoice_line_ids.mapped("balance"))
                bill.is_deductible = False
                plain = self._bill(currency, lines=lines)
                self.assertEqual(bill.amount_total_signed, plain.amount_total_signed)
                self.assertEqual(bill.invoice_line_ids.mapped("balance"),
                                 plain.invoice_line_ids.mapped("balance"))

    def test_free_form_report_shows_deductible_rows(self):
        for method, currency, rate in self._combos():
            with self.subTest(method=method, currency=currency.name, rate=rate):
                self._setup_combo(method, rate)
                bill = self._bill(currency, is_deductible=True, **self.DEDUCTIBLES[1])
                plain = self._bill(currency)
                (bill | plain).action_post()
                report = "l10n_ve_invoice.template_invoice_free_form_l10n_ve_invoice"
                Report = self.env["ir.actions.report"]
                html = Report._render_qweb_html(report, bill.ids)[0].decode()
                html_plain = Report._render_qweb_html(report, plain.ids)[0].decode()
                self.assertIn("Subtotal sin deducible", html)
                self.assertIn("Desc.%", html)
                self.assertIn(bill.tax_totals["formatted_deductible_amount_ves"].replace("\xa0", " "),
                              html.replace("\xa0", " ").replace("&nbsp;", " "))
                self.assertNotIn("Subtotal sin deducible", html_plain)
                self.assertNotIn("Desc.%", html_plain)
