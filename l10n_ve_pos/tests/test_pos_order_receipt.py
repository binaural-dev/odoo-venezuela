"""Receipt data of the localization built by the server (``pos.order.receipt``):
the Python mirror of ``generate_printer_data.js``. The cashier receipt shows the
same rows: tax letter and foreign amount of each line, TOTAL in foreign
currency and the customer address."""

from types import SimpleNamespace

from odoo.tests import tagged

from .test_pos_session_accounting_common import TestPosSessionClosingBase


@tagged("post_install", "-at_install", "l10n_ve_pos", "pos_order_receipt")
class TestPosOrderReceipt(TestPosSessionClosingBase):
    def _order(self):
        session = self._open_session()
        self.company.partner_id.write({"street": "Calle Receipt 1", "city": "Caracas"})
        return self._create_paid_order(session, method=self.cash_method, name="OL/R/1")

    def test_taxed_line_has_the_letter_and_the_foreign_amount(self):
        order = self._order()
        line = order.order_receipt_generate_data()["lines"][0]
        self.assertEqual(line["aliquot_type"], "(G)")
        foreign = order.config_id.foreign_currency_id
        display = (
            order.lines.price_subtotal_incl
            if order.config_id.iface_tax_included == "total"
            else order.lines.price_subtotal
        )
        self.assertEqual(
            line["foreign_price_subtotal_incl"],
            order._order_receipt_format_currency(order._amount_to_foreign(display), foreign),
        )

    def test_line_without_tax_is_exempt(self):
        order = self._order()
        no_tax = self.env["account.tax"]
        line = SimpleNamespace(
            tax_ids=no_tax,
            product_id=SimpleNamespace(with_company=lambda company: SimpleNamespace(taxes_id=no_tax)),
        )
        self.assertEqual(order._order_receipt_aliquot_type(line), "(E)")

    def test_line_with_zero_tax_is_exempt(self):
        order = self._order()
        zero = self.tax.copy({"name": "Zero receipt", "amount": 0.0})
        order.lines.tax_ids = zero
        line = order.order_receipt_generate_data()["lines"][0]
        self.assertEqual(line["aliquot_type"], "(E)")

    def test_total_in_foreign_currency(self):
        order = self._order()
        prices = order.order_receipt_generate_data()["extra_data"]["prices"]
        self.assertEqual(
            prices["foreign_total_amount"],
            order._order_receipt_format_currency(
                order.foreign_amount_total, order.config_id.foreign_currency_id
            ),
        )

    def test_rendered_receipt_has_the_localization_rows(self):
        order = self._order()
        html = str(order.order_receipt_generate_html())
        self.assertIn("(G)", html)
        self.assertIn("Calle Receipt 1", html)
        self.assertIn('name="foreign_total"', html)

    def _foreign_payment_order(self, method=None):
        order = self._order()
        payment = order.payment_ids
        if method:
            payment.payment_method_id = method
        payment.write(
            {
                "foreign_currency_id": self.payment_currency.id,
                "amount_currency": payment.amount / 36.5,
            }
        )
        return order

    def test_payment_in_the_register_currency_prints_as_core(self):
        order = self._order()
        payment = order.order_receipt_generate_data()["payments"][0]
        self.assertEqual(payment["payment_method_data"]["name"], self.cash_method.name)
        self.assertEqual(
            payment["amount"],
            order._order_receipt_format_currency(order.payment_ids.amount, order.currency_id),
        )

    def test_payment_in_another_currency_prints_the_currency_and_the_amount_in_the_register(self):
        order = self._foreign_payment_order()
        payment = order.order_receipt_generate_data()["payments"][0]
        self.assertEqual(
            payment["payment_method_data"]["name"],
            "%s (%s)" % (self.cash_method.name, self.payment_currency.name),
        )
        self.assertEqual(
            payment["amount"],
            order._order_receipt_format_currency(order.payment_ids.amount, order.currency_id),
        )

    def test_any_method_in_another_currency_follows_the_same_rule(self):
        order = self._foreign_payment_order(method=self.bank_method)
        payment = order.order_receipt_generate_data()["payments"][0]
        self.assertEqual(
            payment["payment_method_data"]["name"],
            "%s (%s)" % (self.bank_method.name, self.payment_currency.name),
        )

    def test_rendered_receipt_prints_the_payment_line_of_the_other_currency(self):
        html = str(self._foreign_payment_order().order_receipt_generate_html())
        self.assertIn("%s (%s)" % (self.cash_method.name, self.payment_currency.name), html)

    def test_customer_vat_prints_without_label(self):
        order = self._order()
        order.partner_id.with_context(no_vat_validation=True).vat = "J123456789"
        html = str(order.order_receipt_generate_html())
        self.assertRegex(html, r"<div[^>]*>\s*J123456789\s*</div>")

    def _order_with_change(self):
        order = self._foreign_payment_order()
        order.amount_return = 25.0
        order.add_payment(
            {
                "name": "return",
                "pos_order_id": order.id,
                "amount": -25.0,
                "payment_method_id": self.cash_method.id,
                "payment_date": order.date_order,
                "is_change": True,
            }
        )
        return order

    def test_change_payment_is_not_a_payment_line(self):
        data = self._order_with_change().order_receipt_generate_data()
        self.assertEqual(len(data["payments"]), 1)

    def test_change_is_given_in_the_register_currency(self):
        order = self._order_with_change()
        data = order.order_receipt_generate_data()
        self.assertEqual(data["order"]["amount_return_currency"], 0)
        self.assertEqual(
            data["extra_data"]["prices"]["change_amount"],
            order._order_receipt_format_currency(25.0, order.currency_id),
        )

    def test_rendered_receipt_prints_the_formatted_change(self):
        order = self._order_with_change()
        html = str(order.order_receipt_generate_html())
        self.assertIn(order._order_receipt_format_currency(25.0, order.currency_id), html)
        self.assertNotIn(">25.0<", html)

    def test_no_change_row_without_change(self):
        order = self._order()
        self.assertFalse(order.order_receipt_generate_data()["extra_data"]["prices"]["change_amount"])
        self.assertNotIn('name="change"', str(order.order_receipt_generate_html()))
