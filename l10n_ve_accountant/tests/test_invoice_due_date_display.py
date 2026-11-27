from datetime import timedelta

from odoo import Command, fields
from odoo.tests import Form, TransactionCase, tagged

from .common_rates import set_rate


@tagged("post_install", "-at_install", "l10n_ve_accountant_due_date")
class TestInvoiceDueDateFromInvoiceDate(TransactionCase):
    """Ticket #16673: el vencimiento se cuenta desde la Fecha de factura
    (`invoice_date_display`), no desde la Fecha de tasa (`invoice_date`)."""

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.usd = self.env.ref("base.USD")
        self.company.write({
            "currency_id": self.env.ref("base.VEF").id,
            "foreign_currency_id": self.usd.id,
        })
        self.today = fields.Date.today()
        self.rate_day = self.today - timedelta(days=20)
        self.mid_day = self.today - timedelta(days=10)
        for day, inverse in ((self.today, 40.0), (self.mid_day, 35.0), (self.rate_day, 30.0)):
            set_rate(self.env, self.usd, day, self.company, inverse)
        self.partner = self.env["res.partner"].create({"name": "Cliente Vencimiento"})
        self.product = self.env["product.product"].create({"name": "Producto Vencimiento"})
        self.term_15 = self.env["account.payment.term"].create({
            "name": "15 dias",
            "line_ids": [Command.create({"value": "percent", "value_amount": 100, "delay_type": "days_after", "nb_days": 15})],
        })
        self.term_split = self.env["account.payment.term"].create({
            "name": "50% a 15 y 50% a 30 dias",
            "line_ids": [
                Command.create({"value": "percent", "value_amount": 50, "delay_type": "days_after", "nb_days": 15}),
                Command.create({"value": "percent", "value_amount": 50, "delay_type": "days_after", "nb_days": 30}),
            ],
        })

    def _invoice(self, move_type="out_invoice", display=None, rate=None, term=None):
        vals = {
            "move_type": move_type,
            "partner_id": self.partner.id,
            "invoice_date_display": display or self.today,
            "invoice_payment_term_id": (term or self.term_15).id,
            "invoice_line_ids": [Command.create({
                "product_id": self.product.id, "quantity": 1, "price_unit": 100,
            })],
        }
        if rate:
            vals["invoice_date"] = rate
        return self.env["account.move"].create(vals)

    def _term_lines(self, move):
        return move.line_ids.filtered(
            lambda l: l.account_id.account_type in ("asset_receivable", "liability_payable")
        )

    def test_due_date_counts_from_invoice_date_not_rate_date(self):
        """El caso del ticket: fecha de tasa anterior a la de factura."""
        move = self._invoice(display=self.today, rate=self.rate_day)
        self.assertEqual(move.invoice_date, self.rate_day)
        self.assertEqual(move.invoice_date_due, self.today + timedelta(days=15))
        self.assertEqual(
            self._term_lines(move).mapped("date_maturity"), [self.today + timedelta(days=15)]
        )

    def test_due_date_when_dates_match_is_unchanged(self):
        move = self._invoice(display=self.today)
        self.assertEqual(move.invoice_date_due, self.today + timedelta(days=15))

    def test_posted_invoice_keeps_due_date_from_invoice_date(self):
        move = self._invoice(display=self.today, rate=self.rate_day)
        move.action_post()
        self.assertEqual(move.invoice_date_due, self.today + timedelta(days=15))
        self.assertEqual(
            self._term_lines(move).mapped("date_maturity"), [self.today + timedelta(days=15)]
        )

    def test_vendor_bill_counts_from_invoice_date(self):
        move = self._invoice("in_invoice", display=self.today, rate=self.rate_day)
        self.assertEqual(move.invoice_date_due, self.today + timedelta(days=15))

    def test_note_with_origin_rate_date_counts_from_its_own_date(self):
        """Nota con la fecha de tasa del origen (wizards de NC/ND): su plazo
        no debe contarse desde la fecha de la factura original."""
        for move_type in ("out_refund", "in_refund"):
            move = self._invoice(move_type, display=self.today, rate=self.rate_day)
            self.assertEqual(move.invoice_date_due, self.today + timedelta(days=15), move_type)

    def test_installments_count_from_invoice_date(self):
        move = self._invoice(display=self.today, rate=self.rate_day, term=self.term_split)
        self.assertEqual(
            sorted(self._term_lines(move).mapped("date_maturity")),
            [self.today + timedelta(days=15), self.today + timedelta(days=30)],
        )

    def test_changing_invoice_date_recomputes_due_date(self):
        move = self._invoice(display=self.today, rate=self.rate_day)
        move.invoice_date_display = self.mid_day
        self.assertEqual(move.invoice_date_due, self.mid_day + timedelta(days=15))
        self.assertEqual(
            self._term_lines(move).mapped("date_maturity"), [self.mid_day + timedelta(days=15)]
        )

    def test_changing_rate_date_does_not_move_due_date(self):
        move = self._invoice(display=self.today)
        move.invoice_date = self.mid_day
        self.assertEqual(move.invoice_date_due, self.today + timedelta(days=15))

    def test_form_changing_invoice_date_moves_due_date(self):
        with Form(self.env["account.move"].with_context(default_move_type="out_invoice")) as form:
            form.partner_id = self.partner
            form.invoice_payment_term_id = self.term_15
            with form.invoice_line_ids.new() as line:
                line.product_id = self.product
                line.price_unit = 100
            form.invoice_date_display = self.mid_day
        move = form.save()
        self.assertEqual(move.invoice_date_due, self.mid_day + timedelta(days=15))

    def test_without_payment_term_due_date_is_unchanged(self):
        move = self._invoice(display=self.today, rate=self.rate_day)
        move.invoice_payment_term_id = False
        move.invoice_date_due = self.mid_day
        self.assertEqual(move.invoice_date_due, self.mid_day)

    def test_term_compute_terms_without_context_uses_given_date(self):
        res = self.term_15._compute_terms(
            date_ref=self.rate_day, currency=self.company.currency_id, company=self.company,
            tax_amount=0, tax_amount_currency=0, sign=1,
            untaxed_amount=100, untaxed_amount_currency=100,
        )
        self.assertEqual(
            fields.Date.to_date(res["line_ids"][0]["date"]), self.rate_day + timedelta(days=15)
        )
