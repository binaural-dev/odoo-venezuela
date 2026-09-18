import logging

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestAccountMoveLineFixedDiscount(TransactionCase):
    """Tests for the fixed-amount discount on invoice lines.

    `discount_fixed` is translated into the native `discount` (%) field
    ONLY through `_onchange_discount_fixed` -- exactly like the form does
    when a user types into the field. There is no create()/write() override:
    writing `discount_fixed` by code (imports, other modules, RPC) does NOT
    touch `discount`, same as native Odoo behaves for any other onchange-only
    field. Once `discount` is set (by the onchange, or directly), everything
    downstream (price_subtotal, price_total, taxes,
    foreign_subtotal/foreign_price_total) behaves exactly as native Odoo.
    """

    def setUp(self):
        super().setUp()
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.currency_eur = self.env.ref("base.EUR")
        self.currency_eur.active = True
        self.currency_vef.active = True

        self.company = self.env.ref("base.main_company")
        self.company.write(
            {
                "currency_id": self.currency_usd.id,
                "foreign_currency_id": self.currency_vef.id,
                "discount_type": "amount",
            }
        )

        # Foreign-amount computes (_compute_foreign_price/_compute_foreign_subtotal
        # in l10n_ve_accountant) convert through res.currency.rate, NOT through
        # account.move's foreign_rate/foreign_inverse_rate fields -- those are
        # only a display/manual-entry mechanism. 1 USD = 38 VEF here.
        today = fields.Date.today()
        self.env["res.currency.rate"].create(
            {
                "name": today,
                "currency_id": self.currency_usd.id,
                "inverse_company_rate": 1.0,
                "company_id": self.company.id,
            }
        )
        self.env["res.currency.rate"].create(
            {
                "name": today,
                "currency_id": self.currency_vef.id,
                "inverse_company_rate": 1.0 / 38.0,
                "company_id": self.company.id,
            }
        )

        self.tax_iva16 = self.env["account.tax"].create(
            {
                "name": "IVA 16% Fixed Discount",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "sale",
            }
        )

        self.product = self.env["product.product"].create(
            {
                "name": "Producto Prueba Descuento Fijo",
                "type": "service",
                "list_price": 100,
                "taxes_id": [Command.set([self.tax_iva16.id])],
            }
        )

        self.partner_a = self.env["res.partner"].create(
            {"name": "Test Partner Fixed Discount", "customer_rank": 1}
        )

        sequence = self.env["ir.sequence"].create(
            {
                "name": "Secuencia Factura Descuento Fijo",
                "code": "account.move",
                "prefix": "INVFD/",
                "padding": 8,
                "number_next_actual": 2,
            }
        )
        self.journal = self.env["account.journal"].create(
            {
                "name": "Diario Ventas Descuento Fijo",
                "code": "VFD",
                "type": "sale",
                "sequence_id": sequence.id,
                "company_id": self.company.id,
            }
        )

    # ── helpers ──────────────────────────────────────────────────────

    def _create_invoice(self, price_unit, quantity=1, currency=None,
                         foreign_rate=38.0, foreign_inverse_rate=38.0, taxes=True):
        """Creates an invoice with discount=0, no discount_fixed involved --
        the starting point every test brings to onchange-simulation time."""
        currency = currency or self.currency_usd
        line_vals = {
            "product_id": self.product.id,
            "quantity": quantity,
            "price_unit": price_unit,
            # product_id defaults tax_ids from the product's own taxes_id if
            # this key is omitted -- must clear explicitly for a tax-free line.
            "tax_ids": [Command.set([self.tax_iva16.id])] if taxes else [Command.clear()],
        }

        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "currency_id": currency.id,
                "foreign_currency_id": self.currency_vef.id,
                "foreign_rate": foreign_rate,
                "foreign_inverse_rate": foreign_inverse_rate,
                "manually_set_rate": True,
                "invoice_date": fields.Date.today(),
                "journal_id": self.journal.id,
                "invoice_line_ids": [Command.create(line_vals)],
            }
        )
        return move, move.invoice_line_ids.filtered(lambda l: l.product_id)

    def _apply_discount_fixed_via_onchange(self, line, discount_fixed):
        """Reproduces exactly what the web form does: the user edits
        discount_fixed, the onchange computes the equivalent discount (%) on
        an in-memory copy, and saving persists both fields together."""
        line_new = line.new(origin=line)
        line_new.discount_fixed = discount_fixed
        line_new._onchange_discount_fixed()
        computed_discount = line_new.discount
        line.write({"discount_fixed": discount_fixed, "discount": computed_discount})
        return computed_discount

    # ── the sync only happens via onchange, never via write() alone ────

    def test_writing_discount_fixed_alone_does_not_touch_discount(self):
        """Writing discount_fixed by code (no onchange involved, e.g. an
        import or another module) must NOT recompute discount -- there is no
        create()/write() override doing that translation anymore."""
        move, line = self._create_invoice(price_unit=100.0)
        self.assertEqual(line.discount, 0.0)

        line.write({"discount_fixed": 20.0})

        self.assertEqual(line.discount_fixed, 20.0)
        self.assertEqual(line.discount, 0.0)

    def test_creating_line_with_discount_fixed_alone_does_not_touch_discount(self):
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "currency_id": self.currency_usd.id,
                "foreign_currency_id": self.currency_vef.id,
                "foreign_rate": 38.0,
                "foreign_inverse_rate": 38.0,
                "manually_set_rate": True,
                "invoice_date": fields.Date.today(),
                "journal_id": self.journal.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 100.0,
                            "discount_fixed": 20.0,
                            "tax_ids": [Command.set([self.tax_iva16.id])],
                        }
                    )
                ],
            }
        )
        line = move.invoice_line_ids.filtered(lambda l: l.product_id)
        self.assertEqual(line.discount_fixed, 20.0)
        self.assertEqual(line.discount, 0.0)

    # ── percentage conversion correctness (via the onchange) ───────────

    def test_discount_fixed_converts_to_correct_percentage_usd(self):
        """20 fixed on a 100 unit price is exactly 20%."""
        move, line = self._create_invoice(price_unit=100.0)
        discount = self._apply_discount_fixed_via_onchange(line, 20.0)
        self.assertEqual(discount, 20.0)
        self.assertEqual(line.discount, 20.0)

    def test_discount_fixed_converts_to_correct_percentage_arbitrary_ratio(self):
        """37.5 fixed on a 150 unit price is 25%, regardless of currency."""
        move, line = self._create_invoice(price_unit=150.0)
        discount = self._apply_discount_fixed_via_onchange(line, 37.5)
        self.assertEqual(discount, 25.0)

    def test_discount_fixed_in_foreign_line_currency(self):
        """The line's own currency (VEF) is used for the ratio, not the
        company currency: 380 fixed on a 3800 VEF unit price is 10%."""
        move, line = self._create_invoice(
            price_unit=3800.0, currency=self.currency_vef
        )
        discount = self._apply_discount_fixed_via_onchange(line, 380.0)
        self.assertEqual(discount, 10.0)

    def test_discount_fixed_in_third_currency_eur(self):
        """Any currency works the same way: the percentage only depends on
        the discount_fixed/price_unit ratio, both expressed in that currency."""
        move, line = self._create_invoice(price_unit=80.0, currency=self.currency_eur)
        discount = self._apply_discount_fixed_via_onchange(line, 8.0)
        self.assertEqual(discount, 10.0)

    def test_discount_fixed_respects_product_price_precision_not_currency(self):
        """price_unit uses the 'Product Price' decimal precision (6 digits in
        this project), which is finer than the currency's own decimals (2).
        discount_fixed must be compared/rounded with that same precision, or
        the computed percentage drifts from the exact ratio.
        1.111111 / 3.333333 -> exactly 33.33%, only reachable if
        discount_fixed keeps 6 decimals instead of being rounded to 2."""
        move, line = self._create_invoice(price_unit=3.333333)
        discount = self._apply_discount_fixed_via_onchange(line, 1.111111)
        self.assertEqual(discount, 33.33)

    def test_discount_fixed_zero_gives_zero_percentage(self):
        move, line = self._create_invoice(price_unit=100.0)
        discount = self._apply_discount_fixed_via_onchange(line, 0.0)
        self.assertEqual(discount, 0.0)

    def test_discount_fixed_with_zero_price_unit_does_not_divide_by_zero(self):
        """price_unit=0 on a persisted line is blocked by this module's own
        zero-price constraint (unrelated to discount_fixed) -- so the
        division-by-zero guard is checked on a detached .new() record."""
        line_new = self.env["account.move.line"].new(
            {"price_unit": 0.0, "discount_fixed": 10.0}
        )
        line_new._onchange_discount_fixed()
        self.assertEqual(line_new.discount, 0.0)

    # ── native totals (price_subtotal / price_total) stay correct ──────

    def test_price_subtotal_matches_native_percentage_discount(self):
        """A line with discount_fixed=20 on price_unit=100 (i.e. 20%) must
        produce the exact same price_subtotal/price_total as a line created
        directly with discount=20."""
        move_fixed, line_fixed = self._create_invoice(price_unit=100.0)
        self._apply_discount_fixed_via_onchange(line_fixed, 20.0)

        move_percent = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "currency_id": self.currency_usd.id,
                "foreign_currency_id": self.currency_vef.id,
                "foreign_rate": 38.0,
                "foreign_inverse_rate": 38.0,
                "manually_set_rate": True,
                "invoice_date": fields.Date.today(),
                "journal_id": self.journal.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 100.0,
                            "discount": 20.0,
                            "tax_ids": [Command.set([self.tax_iva16.id])],
                        }
                    )
                ],
            }
        )
        line_percent = move_percent.invoice_line_ids.filtered(
            lambda l: l.product_id
        )

        self.assertEqual(line_fixed.price_subtotal, line_percent.price_subtotal)
        self.assertEqual(line_fixed.price_total, line_percent.price_total)
        # 100 * (1 - 0.20) = 80 untaxed, 80 * 1.16 = 92.8 with 16% IVA.
        self.assertEqual(line_fixed.price_subtotal, 80.0)
        self.assertEqual(line_fixed.price_total, 92.8)

    def test_price_subtotal_with_quantity_and_no_taxes(self):
        """discount_fixed is subtracted from the line's gross subtotal
        (price_unit * quantity), not from price_unit alone."""
        move, line = self._create_invoice(price_unit=50.0, quantity=2, taxes=False)
        self._apply_discount_fixed_via_onchange(line, 20.0)
        # gross: 50*2 = 100; 100 - 20 = 80.
        self.assertEqual(line.price_subtotal, 80.0)
        self.assertEqual(line.price_total, 80.0)

    def test_acceptance_scenario_quantity_two_with_tax(self):
        """Exact numbers from the business requirement: qty=2, price=$50
        (gross $100), fixed discount $20, IVA 16% -> BI $80, IVA $12.80,
        Total $92.80."""
        move, line = self._create_invoice(price_unit=50.0, quantity=2, taxes=True)
        self._apply_discount_fixed_via_onchange(line, 20.0)
        self.assertEqual(line.discount, 20.0)
        self.assertEqual(line.price_subtotal, 80.0)
        self.assertEqual(line.price_total, 92.8)

    # ── foreign currency amounts stay in sync ───────────────────────

    def test_foreign_subtotal_stays_in_sync_with_fixed_discount(self):
        """foreign_subtotal/foreign_price_total must reflect the same %
        discount as the native price_subtotal/price_total, converted at the
        line's foreign rate."""
        move, line = self._create_invoice(
            price_unit=100.0, foreign_rate=38.0, foreign_inverse_rate=38.0
        )
        self._apply_discount_fixed_via_onchange(line, 20.0)

        self.assertEqual(line.discount, 20.0)
        # foreign_price = price_unit converted to VEF at rate 38 -> 3800.
        self.assertEqual(line.foreign_price, 3800.0)
        # 3800 * (1 - 0.20) = 3040 untaxed, * 1.16 = 3526.4 with tax.
        self.assertEqual(line.foreign_subtotal, 3040.0)
        self.assertEqual(line.foreign_price_total, 3526.4)

    def test_foreign_subtotal_updates_when_discount_fixed_reapplied(self):
        move, line = self._create_invoice(price_unit=100.0)
        self.assertEqual(line.discount, 0.0)
        self.assertEqual(line.foreign_subtotal, 3800.0)
        self.assertEqual(line.foreign_price_total, 4408.0)  # 3800*1.16

        self._apply_discount_fixed_via_onchange(line, 25.0)

        self.assertEqual(line.discount, 25.0)
        # 3800 * (1 - 0.25) = 2850 untaxed, * 1.16 = 3306 with tax.
        self.assertEqual(line.foreign_subtotal, 2850.0)
        self.assertEqual(line.foreign_price_total, 3306.0)

    def test_foreign_subtotal_matches_native_percentage_discount_line(self):
        """Cross-check: fixed-discount line and a directly-percent-discounted
        line must produce identical foreign amounts too, not just native."""
        move_fixed, line_fixed = self._create_invoice(
            price_unit=200.0, foreign_rate=40.0, foreign_inverse_rate=40.0
        )
        self._apply_discount_fixed_via_onchange(line_fixed, 50.0)  # 50/200 = 25%

        move_percent = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "currency_id": self.currency_usd.id,
                "foreign_currency_id": self.currency_vef.id,
                "foreign_rate": 40.0,
                "foreign_inverse_rate": 40.0,
                "manually_set_rate": True,
                "invoice_date": fields.Date.today(),
                "journal_id": self.journal.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 200.0,
                            "discount": 25.0,
                            "tax_ids": [Command.set([self.tax_iva16.id])],
                        }
                    )
                ],
            }
        )
        line_percent = move_percent.invoice_line_ids.filtered(
            lambda l: l.product_id
        )

        self.assertEqual(line_fixed.foreign_subtotal, line_percent.foreign_subtotal)
        self.assertEqual(line_fixed.foreign_price_total, line_percent.foreign_price_total)

    # ── per-line correctness when several lines are involved ───────────

    def test_onchange_uses_each_line_own_price_unit(self):
        """Applying the onchange on lines with different price_unit must use
        each line's own price, not a shared one."""
        move, _ = self._create_invoice(price_unit=100.0)
        move.write(
            {
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 50.0,
                            "tax_ids": [Command.set([self.tax_iva16.id])],
                        }
                    )
                ]
            }
        )
        lines = move.invoice_line_ids.filtered(lambda l: l.product_id)
        line_100 = lines.filtered(lambda l: l.price_unit == 100.0)
        line_50 = lines.filtered(lambda l: l.price_unit == 50.0)

        self._apply_discount_fixed_via_onchange(line_100, 10.0)
        self._apply_discount_fixed_via_onchange(line_50, 10.0)

        self.assertEqual(line_100.discount, 10.0)  # 10/100
        self.assertEqual(line_50.discount, 20.0)  # 10/50
