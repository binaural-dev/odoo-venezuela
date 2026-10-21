from odoo import Command, fields
from odoo.tests import Form

from .common import DeductibleCase, set_usd_rate


class TestDeductibleFlows(DeductibleCase):
    """Confirming, paying, notes, date and rate changes, the form step by step
    and the free-form report, for both rounding methods and both currencies."""

    def _each(self):
        for method, currency in self._combos():
            for values in (self.PERCENT, self.AMOUNT):
                with self.subTest(method=method, currency=currency.name, mode=values["global_deductible_type"]):
                    yield currency, values

    def test_post_and_pay(self):
        for currency, values in self._each():
            doc = self._post(self._doc(currency=currency, **values))
            self.assertEqual(doc.state, "posted")
            self.assertEqual(round(sum(doc.line_ids.mapped("debit")), 2), round(sum(doc.line_ids.mapped("credit")), 2))
            account_lines = doc.line_ids.filtered(lambda line: line.account_id.account_type == self._account_type())
            self.assertEqual(round(abs(sum(account_lines.mapped("balance"))), 2), round(abs(doc.amount_total_signed), 2))
            self.assertTrue(doc.tax_totals.get("is_deductible"))
            self._pay(doc)
            self.assertEqual(doc.amount_residual, 0.0)

    def test_credit_note_keeps_the_deductible(self):
        for currency, values in self._each():
            doc = self._post(self._doc(currency=currency, **values))
            credit, replacement = self._reverse(doc)
            self.assertEqual(credit.move_type, "in_refund" if self.MOVE_TYPE == "in_invoice" else "out_refund")
            self.assertTrue(credit.is_deductible)
            self.assertEqual(credit.state, "posted")
            self.assertEqual(credit.amount_total, doc.amount_total)
            self.assertEqual(credit.invoice_line_ids.mapped("price_subtotal"), doc.invoice_line_ids.mapped("price_subtotal"))
            self.assertEqual(doc.amount_residual, 0.0)
            self.assertTrue(replacement.is_deductible)
            self.assertEqual(replacement.state, "draft")
            self.assertEqual(replacement.global_deductible_type, doc.global_deductible_type)
            self.assertEqual(replacement.amount_untaxed, doc.amount_untaxed)

    def test_credit_and_debit_notes_keep_the_amounts_typed_in_the_lines(self):
        doc = self._doc([(100.0, 1), (200.0, 1), (300.0, 1)], **self.AMOUNT | {"global_deductible_amount": 60.0})
        first = doc.invoice_line_ids.sorted("id")[0]
        doc.invoice_line_ids = [
            Command.update(first.id, {"global_deductible_line_amount": 30.0, "global_deductible_manual": True}),
        ]
        expected = doc.invoice_line_ids.sorted("id").mapped("global_deductible_line_amount")
        self.assertEqual(expected, [30.0, 12.0, 18.0])
        self._post(doc)
        credit, _replacement = self._reverse(doc)
        self.assertEqual(credit.invoice_line_ids.sorted("id").mapped("global_deductible_line_amount"), expected)
        self.assertEqual(credit.amount_total, doc.amount_total)
        note = self._debit(doc, copy_lines=True)
        self.assertEqual(note.invoice_line_ids.sorted("id").mapped("global_deductible_line_amount"), expected)

    def test_draft_credit_note_is_editable_and_a_plain_one_is_not_deductible(self):
        doc = self._post(self._doc(**self.PERCENT))
        credit, _replacement = self._reverse(doc, cancel=False)
        self.assertEqual((credit.state, credit.is_deductible, credit.global_deductible_percent), ("draft", True, 12.5))
        credit.invoice_line_ids[0].quantity = 1
        self.assertLess(credit.amount_total, doc.amount_total)
        self._post(credit)
        with self.assertRaisesMsg(Exception, "draft documents"):
            credit.write({"global_deductible_percent": 5.0})
        plain_credit, _replacement = self._reverse(self._post(self._doc()), cancel=False)
        self.assertFalse(plain_credit.is_deductible)

    def test_debit_note_keeps_the_deductible_only_with_copied_lines(self):
        for currency, values in self._each():
            doc = self._post(self._doc(currency=currency, **values))
            note = self._debit(doc, copy_lines=True)
            self.assertEqual(note.debit_origin_id, doc)
            self.assertTrue(note.is_deductible)
            self.assertEqual(note.amount_total_signed, doc.amount_total_signed)
            self.assertEqual(note.invoice_line_ids.mapped("balance"), doc.invoice_line_ids.mapped("balance"))
        empty = self._debit(self._post(self._doc(**self.AMOUNT)), copy_lines=False)
        self.assertFalse(empty.is_deductible)
        self.assertFalse(empty.invoice_line_ids)

    def test_rate_and_date_change_with_the_deductible_active(self):
        yesterday = fields.Date.subtract(fields.Date.today(), days=1)
        set_usd_rate(self.env, self.RATES[1], yesterday)
        for method in self.METHODS:
            self.company.tax_calculation_rounding_method = method
            with self.subTest(method=method):
                doc = self._doc(**self.AMOUNT)
                doc.invoice_date = yesterday
                self._assert_same(doc, self._doc(invoice_date=yesterday, **self.AMOUNT))
                doc.invoice_date = fields.Date.today()
                self._assert_same(doc, self._doc(**self.AMOUNT))

    def _check_form(self, form, currency, mode, value):
        """What the form shows is what a document created directly gives."""
        shown = []
        for index in range(len(form.invoice_line_ids)):
            with form.invoice_line_ids.edit(index) as line:
                shown.append((line.price_unit, line.quantity, line.price_subtotal))
        key = "global_deductible_amount" if mode == "amount" else "global_deductible_percent"
        direct = self._doc(
            [(price, qty) for price, qty, _subtotal in shown], currency,
            is_deductible=True, global_deductible_type=mode, **{key: value},
        )
        totals = form.tax_totals
        self.assertEqual(round(totals["base_amount_currency"], 2), direct.amount_untaxed)
        self.assertEqual(round(totals["total_amount_currency"], 2), direct.amount_total)
        self.assertEqual([row[2] for row in shown], direct.invoice_line_ids.sorted("id").mapped("price_subtotal"))

    def test_form_stays_consistent_at_every_step(self):
        for method, currency in self._combos():
            for mode, value in (("amount", 20.0), ("percent", 12.5)):
                with self.subTest(method=method, currency=currency.name, mode=mode):
                    form = self._new_form(currency, mode, value, self.LINES[:3])
                    self._check_form(form, currency, mode, value)
                    with form.invoice_line_ids.edit(0) as line:
                        line.price_unit = 50.1234
                    self._check_form(form, currency, mode, value)
                    with form.invoice_line_ids.edit(1) as line:
                        price = line.price_unit
                        line.quantity = 4
                        line.price_unit = price
                    self._check_form(form, currency, mode, value)
                    self._form_line(form, 8.7654, 2)
                    self._check_form(form, currency, mode, value)
                    form.invoice_line_ids.remove(index=1)
                    self._check_form(form, currency, mode, value)
                    new_value = 33.33 if mode == "amount" else 33.0
                    self._set_form_value(form, mode, new_value)
                    self._check_form(form, currency, mode, new_value)
                    doc = form.save()
                    self.assertEqual(doc.move_type, self.MOVE_TYPE)
                    self._assert_same(
                        doc,
                        self._doc(
                            [(line.price_unit, line.quantity) for line in doc.invoice_line_ids], currency,
                            is_deductible=True, global_deductible_type=mode,
                            **{("global_deductible_amount" if mode == "amount" else "global_deductible_percent"): new_value},
                        ),
                    )

    def test_saved_document_edited_in_the_form(self):
        for method in self.METHODS:
            self.company.tax_calculation_rounding_method = method
            with self.subTest(method=method):
                doc = self._doc(self.LINES[:3], **self.AMOUNT | {"global_deductible_amount": 20.0})
                with Form(doc) as form:
                    with form.invoice_line_ids.edit(0) as line:
                        line.price_unit = 77.7777
                    with form.invoice_line_ids.edit(2) as line:
                        line.quantity = 20
                        line.price_unit = 0.9999
                    self._form_line(form, 13.1313, 6)
                    form.global_deductible_amount = 41.41
                self.assertEqual(round(sum(doc.invoice_line_ids.mapped("global_deductible_line_amount")), 2), 41.41)
                lines = [(line.price_unit, line.quantity) for line in doc.invoice_line_ids]
                self._assert_same(doc, self._doc(lines, **self.AMOUNT | {"global_deductible_amount": 41.41}))

    def test_line_amount_typed_in_the_form(self):
        """The amount of each line is editable in the form (fixed amount) and
        the percent column follows what was typed."""
        for method, currency in self._combos():
            with self.subTest(method=method, currency=currency.name):
                doc = self._doc([(100.0, 1), (200.0, 1), (300.0, 1)], currency, **self.AMOUNT | {"global_deductible_amount": 60.0})
                with Form(doc) as form:
                    for index, amount in enumerate((30.0, 20.0, 10.0)):
                        with form.invoice_line_ids.edit(index) as line:
                            line.global_deductible_line_amount = amount
                lines = doc.invoice_line_ids.sorted("id")
                self.assertEqual(lines.mapped("global_deductible_line_amount"), [30.0, 20.0, 10.0])
                self.assertEqual(
                    [round(percent, 6) for percent in lines.mapped("global_deductible_discount_percent")],
                    [30.0, 10.0, round(10.0 / 3, 6)],
                )
                self.assertEqual(doc.amount_untaxed, 540.0)

    def test_typing_one_line_spreads_the_rest_in_the_form(self):
        doc = self._doc([(100.0, 1), (200.0, 1), (300.0, 1)], **self.AMOUNT | {"global_deductible_amount": 60.0})
        with Form(doc) as form:
            with form.invoice_line_ids.edit(0) as line:
                line.global_deductible_line_amount = 30.0
        lines = doc.invoice_line_ids.sorted("id")
        self.assertEqual(lines.mapped("global_deductible_line_amount"), [30.0, 12.0, 18.0])
        self.assertEqual(lines.mapped("global_deductible_manual"), [True, False, False])

    def test_line_amounts_that_do_not_add_up_are_rejected_in_the_form(self):
        doc = self._doc([(100.0, 1), (200.0, 1)], **self.AMOUNT | {"global_deductible_amount": 60.0})
        with self.assertRaisesMsg(Exception, "must add up to the deductible amount"):
            with Form(doc) as form:
                for index, amount in enumerate((50.0, 50.0)):
                    with form.invoice_line_ids.edit(index) as line:
                        line.global_deductible_line_amount = amount

    def test_free_form_report_shows_the_deductible(self):
        report = "l10n_ve_invoice.template_invoice_free_form_l10n_ve_invoice"
        for method, currency in self._combos():
            with self.subTest(method=method, currency=currency.name):
                deductible, plain = self._post(self._doc(currency=currency, **self.AMOUNT) | self._doc(currency=currency))
                Report = self.env["ir.actions.report"]
                html = Report._render_qweb_html(report, deductible.ids)[0].decode()
                html_plain = Report._render_qweb_html(report, plain.ids)[0].decode()
                self.assertIn("Subtotal sin deducible", html)
                self.assertIn("Desc.%", html)
                self.assertNotIn("Subtotal sin deducible", html_plain)


class TestDeductibleFlowsCustomer(TestDeductibleFlows):
    MOVE_TYPE = "out_invoice"
