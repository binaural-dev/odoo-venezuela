from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_sale_discount")
class TestDiscountSchemes(TransactionCase):
    """Discount schemes of a sale order / customer invoice: percentage or
    fixed amount on the lines, or global over the subtotal. Only one scheme
    per document, carried from the order to its invoice."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        base = cls.company.currency_id
        currency = cls.env.ref("base.VEF") if base != cls.env.ref("base.VEF") else cls.env.ref("base.USD")
        currency.active = True
        cls.company.foreign_currency_id = currency
        if not cls.env["res.currency.rate"].search_count(
            [
                ("currency_id", "=", currency.id),
                ("company_id", "=", cls.company.id),
                ("name", "=", fields.Date.today()),
            ]
        ):
            cls.env["res.currency.rate"].create(
                {
                    "currency_id": currency.id,
                    "company_id": cls.company.id,
                    "name": fields.Date.today(),
                    "inverse_company_rate": 50.0,
                }
            )
        cls.partner = cls.env["res.partner"].create({"name": "Discount Partner"})
        cls.tax = cls.env["account.tax"].create(
            {
                "name": "IVA 16% discount tests",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "sale",
            }
        )
        cls.product_a = cls.env["product.product"].create(
            {"name": "Product A", "type": "service", "list_price": 600.0}
        )
        cls.product_b = cls.env["product.product"].create(
            {"name": "Product B", "type": "service", "list_price": 400.0}
        )
        Account = cls.env["account.account"]
        cls.discount_account = Account.create(
            {"code": "DSC001", "name": "Line discounts", "account_type": "expense"}
        )
        cls.global_account = Account.create(
            {"code": "DSC002", "name": "Global discounts", "account_type": "income"}
        )

    def _order(self, prices=(1000.0,)):
        products = [self.product_a, self.product_b]
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": products[i % 2].id,
                            "product_uom_qty": 1,
                            "price_unit": price,
                            "tax_ids": [Command.set(self.tax.ids)],
                        }
                    )
                    for i, price in enumerate(prices)
                ],
            }
        )
        return order

    def _wizard(self, document, scheme, discount_type, value):
        return self.env["l10n_ve.discount.wizard"].create(
            {
                "res_model": document._name,
                "res_id": document.id,
                "scheme": scheme,
                "discount_type": discount_type,
                "value": value,
            }
        )

    # ------------------------------------------------------------------
    def test_fixed_discount_on_line_reduces_base_and_tax(self):
        self.company.discount_type = "amount"
        order = self._order()
        order.order_line.write({"discount_fixed": 100.0})
        self.assertFalse(order.discount_mode)
        self.assertAlmostEqual(order.amount_untaxed, 900.0, 2)
        self.assertAlmostEqual(order.amount_tax, 144.0, 2)
        self.assertAlmostEqual(order.amount_total, 1044.0, 2)

    def test_percent_discount_on_lines_via_wizard(self):
        order = self._order()
        self._wizard(order, "lines", "percent", 10).action_apply()
        self.assertEqual(order.discount_mode, "line_percent")
        self.assertEqual(order.order_line.discount, 10.0)
        self.assertAlmostEqual(order.amount_total, 1044.0, 2)

    def test_fixed_amount_is_split_proportionally(self):
        order = self._order((600.0, 400.0))
        self._wizard(order, "lines", "amount", 100).action_apply()
        shares = order.order_line.sorted("id").mapped("discount_fixed")
        self.assertEqual(shares, [60.0, 40.0])
        self.assertAlmostEqual(order.amount_untaxed, 900.0, 2)
        self.assertAlmostEqual(order.amount_tax, 144.0, 2)

    def test_fixed_amount_split_keeps_exact_sum_with_rounding(self):
        order = self._order((100.0, 100.0, 100.0))
        self._wizard(order, "lines", "amount", 10).action_apply()
        self.assertAlmostEqual(sum(order.order_line.mapped("discount_fixed")), 10.0, 6)

    def test_global_discount_requires_account(self):
        order = self._order()
        self.company.global_discount_account_id = False
        with self.assertRaises(UserError):
            self._wizard(order, "global_subtotal", "percent", 10).action_apply()

    def test_global_subtotal_percent(self):
        self.company.global_discount_account_id = self.global_account
        order = self._order()
        self._wizard(order, "global_subtotal", "percent", 10).action_apply()
        self.assertEqual(order.discount_mode, "global_subtotal")
        self.assertEqual(order.global_discount_percent, 10.0)
        self.assertAlmostEqual(order.amount_untaxed, 900.0, 2)
        self.assertAlmostEqual(order.amount_tax, 144.0, 2)

    def test_global_discount_blocks_line_discount(self):
        self.company.global_discount_account_id = self.global_account
        order = self._order()
        self._wizard(order, "global_subtotal", "percent", 10).action_apply()
        with self.assertRaises(UserError):
            order.order_line.write({"discount": 5.0})

    def test_line_schemes_exclude_each_other(self):
        order = self._order()
        self._wizard(order, "lines", "amount", 50).action_apply()
        self.assertEqual(order.discount_mode, "line_amount")
        with self.assertRaises(UserError):
            order.order_line.write({"discount": 5.0})
        self._wizard(order, "lines", "percent", 10).action_apply()
        self.assertEqual(order.discount_mode, "line_percent")
        with self.assertRaises(UserError):
            order.order_line.write({"discount_fixed": 5.0})

    def test_new_line_inherits_global_percent(self):
        self.company.global_discount_account_id = self.global_account
        order = self._order()
        self._wizard(order, "global_subtotal", "percent", 10).action_apply()
        line = self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": self.product_b.id,
                "price_unit": 200.0,
                "tax_ids": [Command.set(self.tax.ids)],
            }
        )
        self.assertEqual(line.discount, 10.0)

    def test_deleting_all_lines_drops_the_scheme(self):
        self.company.global_discount_account_id = self.global_account
        order = self._order()
        self._wizard(order, "global_subtotal", "percent", 10).action_apply()
        order.order_line.unlink()
        self.assertFalse(order.discount_mode)
        self.assertEqual(order.global_discount_percent, 0.0)

    def test_remove_discount(self):
        order = self._order()
        self._wizard(order, "lines", "percent", 10).action_apply()
        self._wizard(order, "lines", "percent", 10).action_remove()
        self.assertFalse(order.discount_mode)
        self.assertEqual(order.order_line.discount, 0.0)
        self.assertAlmostEqual(order.amount_total, 1160.0, 2)

    def test_fixed_discount_cannot_reach_the_subtotal(self):
        self.company.discount_type = "amount"
        order = self._order()
        with self.assertRaises(ValidationError):
            order.order_line.write({"discount_fixed": 1000.0})

    def test_scheme_and_fixed_discount_travel_to_the_invoice(self):
        order = self._order((600.0, 400.0))
        self._wizard(order, "lines", "amount", 100).action_apply()
        order.action_confirm()
        invoice = order._create_invoices()
        self.assertEqual(invoice.discount_mode, "line_amount")
        self.assertEqual(
            invoice.invoice_line_ids.sorted("id").mapped("discount_fixed"), [60.0, 40.0]
        )
        self.assertAlmostEqual(invoice.amount_untaxed, 900.0, 2)
        self.assertAlmostEqual(invoice.amount_total, 1044.0, 2)

    def test_percent_discount_survives_invoicing_with_amount_company_type(self):
        self.company.discount_type = "amount"
        order = self._order()
        self._wizard(order, "lines", "percent", 10).action_apply()
        order.action_confirm()
        invoice = order._create_invoices()
        self.assertEqual(invoice.invoice_line_ids.discount, 10.0)
        self.assertAlmostEqual(invoice.amount_untaxed, 900.0, 2)

    def test_invoice_allocation_entry_for_fixed_line_discount(self):
        self.company.account_discount_expense_allocation_id = self.discount_account
        order = self._order()
        self._wizard(order, "lines", "amount", 100).action_apply()
        order.action_confirm()
        invoice = order._create_invoices()
        invoice.action_post()
        discount_lines = invoice.line_ids.filtered(lambda l: l.display_type == "discount")
        self.assertEqual(
            discount_lines.filtered(lambda l: l.account_id == self.discount_account).balance,
            100.0,
        )
        self.assertTrue(invoice.currency_id.is_zero(sum(invoice.line_ids.mapped("balance"))))

    def test_invoice_allocation_uses_global_account_for_global_discount(self):
        self.company.account_discount_expense_allocation_id = self.discount_account
        self.company.global_discount_account_id = self.global_account
        order = self._order()
        self._wizard(order, "global_subtotal", "percent", 10).action_apply()
        order.action_confirm()
        invoice = order._create_invoices()
        invoice.action_post()
        by_account = {
            line.account_id: line.balance
            for line in invoice.line_ids.filtered(lambda l: l.display_type == "discount")
        }
        self.assertEqual(by_account.get(self.global_account), 100.0)
        self.assertNotIn(self.discount_account, by_account)

    def test_invoice_wizard_applies_to_customer_invoice_only(self):
        self.company.global_discount_account_id = self.global_account
        order = self._order()
        order.action_confirm()
        invoice = order._create_invoices()
        self._wizard(invoice, "lines", "percent", 10).action_apply()
        self.assertEqual(invoice.discount_mode, "line_percent")
        self.assertAlmostEqual(invoice.amount_untaxed, 900.0, 2)
        bill = self.env["account.move"].create(
            {"move_type": "in_invoice", "partner_id": self.partner.id}
        )
        with self.assertRaises(UserError):
            self._wizard(bill, "lines", "percent", 10).action_apply()

    # ------------------------------------------------------------------
    # Global discount over the total: taxes stay, only the total drops.
    # ------------------------------------------------------------------
    def test_global_total_percent_keeps_tax(self):
        self.company.global_discount_account_id = self.global_account
        order = self._order()
        self._wizard(order, "global_total", "percent", 10).action_apply()
        self.assertEqual(order.discount_mode, "global_total")
        self.assertEqual(order.order_line.discount, 0.0)
        self.assertAlmostEqual(order.amount_untaxed, 1000.0, 2)
        self.assertAlmostEqual(order.amount_tax, 160.0, 2)
        self.assertAlmostEqual(order.amount_total, 1044.0, 2)
        self.assertAlmostEqual(order.tax_totals["global_discount_amount_currency"], 116.0, 2)

    def test_global_total_amount(self):
        self.company.global_discount_account_id = self.global_account
        order = self._order()
        self._wizard(order, "global_total", "amount", 116).action_apply()
        self.assertAlmostEqual(order.amount_tax, 160.0, 2)
        self.assertAlmostEqual(order.amount_total, 1044.0, 2)

    def test_global_total_blocks_line_discount(self):
        self.company.global_discount_account_id = self.global_account
        order = self._order()
        self._wizard(order, "global_total", "percent", 10).action_apply()
        with self.assertRaises(UserError):
            order.order_line.write({"discount": 5.0})

    def test_global_total_invoice_entry(self):
        self.company.global_discount_account_id = self.global_account
        order = self._order()
        self._wizard(order, "global_total", "percent", 10).action_apply()
        order.action_confirm()
        invoice = order._create_invoices()
        self.assertEqual(invoice.discount_mode, "global_total")
        invoice.action_post()
        self.assertAlmostEqual(invoice.amount_untaxed, 1000.0, 2)
        self.assertAlmostEqual(invoice.amount_tax, 160.0, 2)
        self.assertAlmostEqual(invoice.amount_total, 1044.0, 2)
        balances = {}
        for line in invoice.line_ids:
            balances[line.account_id] = balances.get(line.account_id, 0.0) + line.balance
        self.assertAlmostEqual(balances[self.global_account], 116.0, 2)
        receivable = invoice.line_ids.filtered(lambda l: l.display_type == "payment_term")
        self.assertAlmostEqual(sum(receivable.mapped("balance")), 1044.0, 2)
        self.assertAlmostEqual(sum(invoice.line_ids.mapped("balance")), 0.0, 2)

    def test_tax_totals_rows_for_global_subtotal(self):
        self.company.global_discount_account_id = self.global_account
        order = self._order()
        self._wizard(order, "global_subtotal", "percent", 10).action_apply()
        totals = order.tax_totals
        self.assertEqual(totals["global_discount_mode"], "global_subtotal")
        self.assertAlmostEqual(totals["global_discount_amount_currency"], 100.0, 2)
        self.assertIn("formatted_subtotal_before_global_discount", totals)
        self.assertAlmostEqual(totals["base_amount_currency"], 900.0, 2)

    def test_tax_totals_has_no_global_row_for_line_discounts(self):
        order = self._order()
        self._wizard(order, "lines", "percent", 10).action_apply()
        self.assertNotIn("global_discount_mode", order.tax_totals)

    def test_tax_totals_row_for_global_total(self):
        self.company.global_discount_account_id = self.global_account
        order = self._order()
        self._wizard(order, "global_total", "percent", 10).action_apply()
        totals = order.tax_totals
        self.assertEqual(totals["global_discount_mode"], "global_total")
        self.assertAlmostEqual(totals["total_before_global_discount_currency"], 1160.0, 2)
        self.assertAlmostEqual(totals["total_amount_currency"], 1044.0, 2)

    # ------------------------------------------------------------------
    # Parity with the native allocation, cache and report
    # ------------------------------------------------------------------
    def _allocation_entries(self, invoice):
        return sorted(
            (line.account_id.code, round(line.balance, 2), round(line.amount_currency, 2))
            for line in invoice.line_ids.filtered(lambda l: l.display_type == "discount")
        )

    def test_fixed_allocation_matches_the_native_percentage_allocation(self):
        """The allocation of a fixed-amount discount is our copy of the native
        computation: for the same effective discount it must give the very same
        journal items as the native percentage path (guards native upgrades)."""
        self.company.account_discount_expense_allocation_id = self.discount_account
        results = []
        for discount_type, value in (("percent", 10), ("amount", 100)):
            order = self._order((600.0, 400.0))
            self._wizard(order, "lines", discount_type, value).action_apply()
            order.action_confirm()
            invoice = order._create_invoices()
            invoice.action_post()
            results.append(self._allocation_entries(invoice))
        self.assertTrue(results[0])
        self.assertEqual(results[0], results[1])

    def test_global_total_discount_is_cached_and_follows_the_lines(self):
        self.company.global_discount_account_id = self.global_account
        order = self._order((1000.0,))
        order.action_confirm()
        invoice = order._create_invoices()
        invoice._apply_discount("global_total", "percent", 10)
        self.assertAlmostEqual(invoice.global_total_discount, 116.0, 2)
        self.assertAlmostEqual(invoice.amount_total, 1044.0, 2)
        invoice.invoice_line_ids.write({"price_unit": 2000.0})
        self.assertAlmostEqual(invoice.global_total_discount, 232.0, 2)
        self.assertAlmostEqual(invoice.amount_total, 2088.0, 2)
        invoice._remove_discount()
        self.assertAlmostEqual(invoice.global_total_discount, 0.0, 2)

    def test_report_prints_the_global_discount(self):
        self.company.global_discount_account_id = self.global_account
        report = "l10n_ve_invoice.template_invoice_free_form_l10n_ve_invoice"
        for scheme, discount_type, expected in (
            ("global_total", "percent", "Descuento global"),
            ("global_subtotal", "amount", "Descuento global"),
        ):
            with self.subTest(scheme=scheme):
                order = self._order((1000.0,))
                order.action_confirm()
                invoice = order._create_invoices()
                invoice._apply_discount(scheme, discount_type, 100)
                invoice._post()
                html, _fmt = self.env["ir.actions.report"]._render_qweb_html(report, invoice.ids)
                self.assertIn(expected, html.decode())

    # ------------------------------------------------------------------
    # Documents saved before the schemes existed
    # ------------------------------------------------------------------
    def test_legacy_order_keeps_its_percentage_under_an_amount_company(self):
        order = self._order()
        order.order_line.write({"discount": 10.0})
        self.assertFalse(order.discount_mode)
        self.company.discount_type = "amount"
        order.invalidate_recordset(["discount_type"])
        self.assertEqual(order.discount_type, "percent")
        order.order_line.write({"discount": 12.0})
        self.assertEqual(order.order_line.discount, 12.0)
        self.assertAlmostEqual(order.amount_untaxed, 880.0, 2)
        order.action_confirm()
        invoice = order._create_invoices()
        self.assertEqual(invoice.invoice_line_ids.discount, 12.0)
        self.assertEqual(invoice.discount_mode, "line_percent")
        self.assertAlmostEqual(invoice.amount_untaxed, 880.0, 2)
        self.assertEqual(self._order().discount_type, "amount")

    def test_legacy_fixed_order_keeps_its_amount_under_a_percent_company(self):
        self.company.discount_type = "amount"
        order = self._order()
        order.order_line.write({"discount_fixed": 100.0})
        self.company.discount_type = "percent"
        order.invalidate_recordset(["discount_type"])
        self.assertEqual(order.discount_type, "amount")
        order.order_line.write({"discount_fixed": 150.0})
        self.assertEqual(order.order_line.discount_fixed, 150.0)
        self.assertAlmostEqual(order.amount_untaxed, 850.0, 2)
        order.action_confirm()
        invoice = order._create_invoices()
        self.assertEqual(invoice.invoice_line_ids.discount_fixed, 150.0)
        self.assertAlmostEqual(invoice.amount_untaxed, 850.0, 2)

    # ------------------------------------------------------------------
    # Alternate currency of the discount entries
    # ------------------------------------------------------------------
    def _posted_invoice_with(self, scheme, discount_type, value):
        self.company.global_discount_account_id = self.global_account
        self.company.account_discount_expense_allocation_id = self.discount_account
        order = self._order((600.0, 600.0, 400.0))
        order.action_confirm()
        invoice = order._create_invoices()
        invoice._apply_discount(scheme, discount_type, value)
        invoice._post()
        return invoice

    def test_discount_entries_carry_their_alternate_amounts(self):
        """The discount allocation entries get their alternate-currency amounts
        the way the product lines do (alternate gross - alternate subtotal), and
        the entry still adds up in the alternate currency."""
        for scheme, discount_type, value in (
            ("lines", "percent", 30),
            ("lines", "amount", 480),
            ("global_subtotal", "percent", 30),
            ("global_subtotal", "amount", 480),
        ):
            with self.subTest(scheme=scheme, type=discount_type):
                invoice = self._posted_invoice_with(scheme, discount_type, value)
                entries = invoice.line_ids.filtered(lambda l: l.display_type == "discount")
                self.assertTrue(entries)
                expected = entries[0]._get_move_foreign_discount()
                self.assertTrue(expected)
                self.assertAlmostEqual(sum(entries.mapped("foreign_debit")), expected, 2)
                self.assertAlmostEqual(sum(entries.mapped("foreign_credit")), expected, 2)
                self.assertAlmostEqual(
                    sum(invoice.line_ids.mapped("foreign_debit")),
                    sum(invoice.line_ids.mapped("foreign_credit")),
                    2,
                )

    def test_global_total_entry_carries_its_alternate_amount(self):
        invoice = self._posted_invoice_with("global_total", "percent", 30)
        entry = invoice.line_ids.filtered(lambda l: l.display_type == "discount")
        self.assertEqual(len(entry), 1)
        self.assertTrue(entry.foreign_debit)
        self.assertAlmostEqual(entry.foreign_debit, entry._get_move_foreign_discount(), 2)
        self.assertAlmostEqual(
            sum(invoice.line_ids.mapped("foreign_debit")),
            sum(invoice.line_ids.mapped("foreign_credit")),
            2,
        )
