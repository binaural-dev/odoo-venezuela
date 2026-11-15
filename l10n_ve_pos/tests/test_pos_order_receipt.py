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
