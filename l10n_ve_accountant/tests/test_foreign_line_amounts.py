from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_accountant", "foreign_line_amounts")
class TestForeignLineAmounts(TransactionCase):
    """The alternate amounts of the lines must add up to the alternate totals of the move.

    Regression covered here: the line total used to be derived from the base currency ratio
    price_total / price_subtotal, which carries the base currency rounding and gets amplified by
    the exchange rate (0.42 USD + IVA 16% at a rate of 725.747 was off by 2.03 Bs).
    """

    # Rate and amounts taken from the reported invoice 000056 / control number 00-000633.
    RATE = 725.747
    PRICE_TAXED = 0.42
    PRICE_EXEMPT = 1.99

    def setUp(self):
        super().setUp()

        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        if not self.currency_vef.active:
            self.currency_vef.active = True
        self.company = self.env.company

        # Only write what really differs: l10n_ve_rate forbids changing currency_foreign_id once
        # the company has journal items in that currency.
        company_vals = {}
        if self.company.currency_id != self.currency_usd:
            company_vals["currency_id"] = self.currency_usd.id
        if self.company.currency_foreign_id != self.currency_vef:
            company_vals["currency_foreign_id"] = self.currency_vef.id
        if self.company.tax_calculation_rounding_method != "round_per_line":
            company_vals["tax_calculation_rounding_method"] = "round_per_line"
        if company_vals:
            self.company.write(company_vals)

        # Today, so that fiscal lock dates or digital invoice sequences of the database the
        # tests run on do not reject the posting.
        self.invoice_date = fields.Date.context_today(self.env.user)
        rate = self.env["res.currency.rate"].search([
            ("name", "=", self.invoice_date),
            ("currency_id", "=", self.currency_vef.id),
            ("company_id", "=", self.company.id),
        ], limit=1)
        if rate:
            rate.company_rate = self.RATE
        else:
            self.env["res.currency.rate"].create({
                "name": self.invoice_date,
                "currency_id": self.currency_vef.id,
                "company_rate": self.RATE,
                "company_id": self.company.id,
            })

        self.tax_iva16 = self.env["account.tax"].create({
            "name": "IVA 16% Ventas (test)",
            "amount": 16.0,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "company_id": self.company.id,
        })
        self.tax_exempt = self.env["account.tax"].create({
            "name": "Exento Ventas (test)",
            "amount": 0.0,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "company_id": self.company.id,
        })

        self.product = self.env["product.product"].create({
            "name": "Producto moneda alterna",
            "type": "service",
            "list_price": 1.0,
            "company_id": False,
        })
        self.partner = self.env["res.partner"].create({
            "name": "Cliente moneda alterna",
            "customer_rank": 1,
            "company_id": False,
        })
        self.sale_journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].create({
            "name": "Ventas moneda alterna",
            "code": "VMAT",
            "type": "sale",
            "company_id": self.company.id,
        })

    # ------------------------------------------------------------------ helpers

    def _create_invoice(self, line_defs, move_type="out_invoice"):
        return self.env["account.move"].create({
            "move_type": move_type,
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "invoice_date": self.invoice_date,
            "date": self.invoice_date,
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "name": line.get("name", "Linea"),
                    "quantity": line.get("qty", 1.0),
                    "price_unit": line["price"],
                    "discount": line.get("discount", 0.0),
                    "tax_ids": [Command.set(line.get("taxes", []))],
                })
                for line in line_defs
            ],
        })

    def _assert_lines_match_totals(self, invoice, msg=""):
        """sum(lines) must equal the alternate totals exposed by tax_totals."""
        totals = invoice.tax_totals
        vef = self.currency_vef

        sum_subtotal = sum(invoice.invoice_line_ids.mapped("foreign_subtotal"))
        sum_total = sum(invoice.invoice_line_ids.mapped("foreign_price_total"))

        self.assertEqual(
            vef.round(sum_subtotal),
            vef.round(totals["foreign_amount_untaxed"]),
            "The alternate subtotals of the lines must add up to foreign_amount_untaxed. %s" % msg,
        )
        self.assertEqual(
            vef.round(sum_total),
            vef.round(totals["foreign_amount_total"]),
            "The alternate totals of the lines must add up to foreign_amount_total. %s" % msg,
        )

    def _foreign_tax_amount(self, invoice):
        return sum(
            group["tax_group_amount"]
            for groups in invoice.tax_totals["groups_by_foreign_subtotal"].values()
            for group in groups
        )

    # ------------------------------------------------------------------- tests

    def test_reported_case_taxed_plus_exempt_line(self):
        """0.42 USD with IVA 16% + 1.99 USD exempt at a rate of 725.747."""
        invoice = self._create_invoice([
            {"name": "Con IVA", "price": self.PRICE_TAXED, "taxes": self.tax_iva16.ids},
            {"name": "Exento", "price": self.PRICE_EXEMPT, "taxes": self.tax_exempt.ids},
        ])

        self.assertAlmostEqual(invoice.foreign_inverse_rate, self.RATE, places=3)

        taxed_line, exempt_line = invoice.invoice_line_ids

        # Base currency amounts: the IVA of 0.0672 USD is rounded to 0.07, and that rounding is
        # what used to leak into the alternate total.
        self.assertAlmostEqual(taxed_line.price_subtotal, 0.42, places=2)
        self.assertAlmostEqual(taxed_line.price_total, 0.49, places=2)

        self.assertAlmostEqual(taxed_line.foreign_subtotal, 304.81, places=2)
        self.assertAlmostEqual(taxed_line.foreign_price_total, 353.58, places=2)
        self.assertAlmostEqual(exempt_line.foreign_subtotal, 1444.24, places=2)
        self.assertAlmostEqual(exempt_line.foreign_price_total, 1444.24, places=2)

        # The line total is the alternate taxable base plus the alternate IVA, not the base
        # currency total times the rate (which would be 355.62).
        self.assertAlmostEqual(self._foreign_tax_amount(invoice), 48.77, places=2)
        self.assertAlmostEqual(
            taxed_line.foreign_price_total,
            taxed_line.foreign_subtotal + self._foreign_tax_amount(invoice),
            places=2,
        )

        self.assertAlmostEqual(invoice.tax_totals["foreign_amount_untaxed"], 1749.05, places=2)
        self.assertAlmostEqual(invoice.tax_totals["foreign_amount_total"], 1797.82, places=2)
        self._assert_lines_match_totals(invoice)

    def test_posted_invoice_matches_foreign_total_billed(self):
        invoice = self._create_invoice([
            {"name": "Con IVA", "price": self.PRICE_TAXED, "taxes": self.tax_iva16.ids},
            {"name": "Exento", "price": self.PRICE_EXEMPT, "taxes": self.tax_exempt.ids},
        ])
        invoice.with_context(move_action_post_alert=True, skip_unidigital=True).action_post()
        self.assertEqual(invoice.state, "posted")

        sum_total = sum(invoice.invoice_line_ids.mapped("foreign_price_total"))
        self.assertEqual(
            self.currency_vef.round(sum_total),
            self.currency_vef.round(invoice.foreign_total_billed),
            "The alternate totals of the lines must add up to foreign_total_billed",
        )

    def test_posted_invoice_foreign_entry_is_balanced(self):
        invoice = self._create_invoice([
            {"name": "Con IVA", "price": self.PRICE_TAXED, "taxes": self.tax_iva16.ids},
            {"name": "Exento", "price": self.PRICE_EXEMPT, "taxes": self.tax_exempt.ids},
        ])
        invoice.with_context(move_action_post_alert=True, skip_unidigital=True).action_post()

        foreign_debit = sum(invoice.line_ids.mapped("foreign_debit"))
        foreign_credit = sum(invoice.line_ids.mapped("foreign_credit"))
        self.assertTrue(
            self.currency_vef.is_zero(foreign_debit - foreign_credit),
            "The journal entry must be balanced in the alternate currency: %s vs %s"
            % (foreign_debit, foreign_credit),
        )

    def test_discount_and_quantity(self):
        invoice = self._create_invoice([
            {"name": "IVA con descuento", "price": 3.33, "qty": 3.0, "discount": 10.0,
             "taxes": self.tax_iva16.ids},
            {"name": "Exento cantidad", "price": 0.77, "qty": 7.0, "taxes": self.tax_exempt.ids},
        ])
        self._assert_lines_match_totals(invoice, "(discount + quantity)")

        discounted = invoice.invoice_line_ids[0]
        expected_base = self.currency_vef.round(
            discounted.foreign_price * (1 - 0.10) * 3.0
        )
        self.assertAlmostEqual(discounted.foreign_subtotal, expected_base, places=2)

    def test_credit_note(self):
        refund = self._create_invoice(
            [
                {"name": "Con IVA", "price": self.PRICE_TAXED, "taxes": self.tax_iva16.ids},
                {"name": "Exento", "price": self.PRICE_EXEMPT, "taxes": self.tax_exempt.ids},
            ],
            move_type="out_refund",
        )
        self._assert_lines_match_totals(refund, "(credit note)")

    def test_line_without_taxes(self):
        invoice = self._create_invoice([
            {"name": "Sin impuestos", "price": 1.23, "qty": 2.0, "taxes": []},
        ])
        line = invoice.invoice_line_ids

        expected = self.currency_vef.round(line.foreign_price * 2.0)
        self.assertAlmostEqual(line.foreign_subtotal, expected, places=2)
        self.assertAlmostEqual(line.foreign_price_total, expected, places=2)
        self._assert_lines_match_totals(invoice, "(no taxes)")
