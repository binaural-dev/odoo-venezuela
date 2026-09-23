import logging

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestAccountMoveLineFixedDiscount(TransactionCase):
    """Tests for the fixed-amount discount on invoice lines.

    `discount_fixed` never writes to the native `discount` (%) field --
    there is no onchange or create()/write() translation between the two.
    Instead, price_subtotal/price_total (native) and foreign_subtotal/
    foreign_price_total (l10n_ve_accountant) are computed directly from
    discount_fixed whenever the company's discount_type is 'amount',
    bypassing `discount` entirely for the computation (it stays at its
    default, 0.0). This works identically whether the line is created via
    the form, an import, an RPC call, or any other write() -- there's no
    onchange to bypass.
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

    def _create_invoice(
        self,
        price_unit,
        quantity=1,
        discount_fixed=0.0,
        currency=None,
        foreign_rate=38.0,
        foreign_inverse_rate=38.0,
        taxes=True,
    ):
        currency = currency or self.currency_usd
        line_vals = {
            "product_id": self.product.id,
            "quantity": quantity,
            "price_unit": price_unit,
            "discount_fixed": discount_fixed,
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

    # ── discount (%) is never touched, regardless of how it's written ──

    def test_writing_discount_fixed_alone_does_not_touch_discount(self):
        move, line = self._create_invoice(price_unit=100.0)
        self.assertEqual(line.discount, 0.0)

        line.write({"discount_fixed": 20.0})

        self.assertEqual(line.discount_fixed, 20.0)
        self.assertEqual(line.discount, 0.0)

    def test_creating_line_with_discount_fixed_applies_totals_immediately(self):
        """Unlike the onchange-only approach, discount_fixed applies on
        create() too -- no form interaction needed."""
        move, line = self._create_invoice(price_unit=100.0, discount_fixed=20.0)
        self.assertEqual(line.discount_fixed, 20.0)
        self.assertEqual(line.discount, 0.0)
        self.assertEqual(line.price_subtotal, 80.0)

    # ── discount and discount_fixed are mutually exclusive, per config ──
    # setUp leaves discount_type='amount'; switched to 'percent' where noted.

    def test_amount_mode_writing_discount_fixed_zeroes_out_discount(self):
        move, line = self._create_invoice(price_unit=100.0)
        line.write({"discount_fixed": 30.0})

        self.assertEqual(line.discount_fixed, 30.0)
        self.assertEqual(line.discount, 0.0)

    def test_amount_mode_writing_discount_directly_is_forced_to_zero(self):
        """discount_type='amount' means discount (%) is never the active
        field -- writing it directly gets forced back to 0 regardless."""
        move, line = self._create_invoice(price_unit=100.0)
        line.write({"discount": 20.0})

        self.assertEqual(line.discount, 0.0)

    def test_percent_mode_writing_discount_zeroes_out_discount_fixed(self):
        """Seed discount_fixed while still in 'amount' mode (as it would
        happen before the company switches configuration), then switch to
        'percent' and write discount -- discount_fixed must be cleared."""
        move, line = self._create_invoice(price_unit=100.0, discount_fixed=30.0)
        self.assertEqual(line.discount_fixed, 30.0)

        self.company.discount_type = "percent"
        line.write({"discount": 20.0})

        self.assertEqual(line.discount, 20.0)
        self.assertEqual(line.discount_fixed, 0.0)

    def test_percent_mode_writing_discount_fixed_directly_is_forced_to_zero(self):
        self.company.discount_type = "percent"
        move, line = self._create_invoice(price_unit=100.0)
        line.write({"discount_fixed": 30.0})

        self.assertEqual(line.discount_fixed, 0.0)

    def test_creating_line_in_amount_mode_ignores_discount_given_at_create(self):
        """If both are given together on create() while in 'amount' mode,
        discount is forced to 0 -- the config alone decides, not priority
        between the two values given."""
        move, _ = self._create_invoice(price_unit=50.0)
        line2 = self.env["account.move.line"].create(
            {
                "move_id": move.id,
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 100.0,
                "discount": 15.0,
                "discount_fixed": 40.0,
                "tax_ids": [Command.set([self.tax_iva16.id])],
            }
        )
        self.assertEqual(line2.discount_fixed, 40.0)
        self.assertEqual(line2.discount, 0.0)

    def test_onchange_in_amount_mode_always_zeroes_discount(self):
        """Same exclusivity, simulated through the form's onchange (before
        save) so the UI reflects it immediately."""
        move, line = self._create_invoice(price_unit=100.0, discount_fixed=25.0)

        line_new = line.new(origin=line)
        line_new._onchange_discount_exclusivity()

        self.assertEqual(line_new.discount, 0.0)

    def test_onchange_in_percent_mode_always_zeroes_discount_fixed(self):
        self.company.discount_type = "percent"
        move, line = self._create_invoice(price_unit=100.0)
        line.discount = 20.0

        line_new = line.new(origin=line)
        line_new._onchange_discount_exclusivity()

        self.assertEqual(line_new.discount_fixed, 0.0)

    # ── native totals (price_subtotal / price_total) ────────────────────

    def test_price_subtotal_matches_native_percentage_discount(self):
        """A line with discount_fixed=20 on price_unit=100 (i.e. 20%) must
        produce the exact same price_subtotal/price_total as a line created
        directly with discount=20."""
        move_fixed, line_fixed = self._create_invoice(
            price_unit=100.0, discount_fixed=20.0
        )

        # Native discount (%) is only writable while the company is in
        # 'percent' mode -- switching here doesn't touch line_fixed, whose
        # totals were already computed above.
        self.company.discount_type = "percent"
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
        move, line = self._create_invoice(
            price_unit=50.0, quantity=2, discount_fixed=20.0, taxes=False
        )
        # gross: 50*2 = 100; 100 - 20 = 80.
        self.assertEqual(line.price_subtotal, 80.0)
        self.assertEqual(line.price_total, 80.0)

    def test_acceptance_scenario_quantity_two_with_tax(self):
        """Exact numbers from the business requirement: qty=2, price=$50
        (gross $100), fixed discount $20, IVA 16% -> BI $80, IVA $12.80,
        Total $92.80."""
        move, line = self._create_invoice(
            price_unit=50.0, quantity=2, discount_fixed=20.0, taxes=True
        )
        self.assertEqual(line.discount, 0.0)
        self.assertEqual(line.price_subtotal, 80.0)
        self.assertEqual(line.price_total, 92.8)

    def test_price_subtotal_exact_for_non_round_ratio(self):
        """The case the old %-proxy approach got wrong: a discount_fixed
        whose equivalent percentage isn't exact at 2 decimals must still
        produce an exact Base Imponible, because the tax computation uses
        the unrounded ratio directly instead of a rounded `discount`.
        $25.55 fixed on a $333.33 line (qty=1) -> BI = 333.33 - 25.55 =
        307.78 exactly, not 307.76 (the old ±0.02 drift)."""
        move, line = self._create_invoice(
            price_unit=333.33, discount_fixed=25.55, taxes=False
        )
        self.assertEqual(line.price_subtotal, 307.78)

    def test_discount_fixed_zero_leaves_totals_unaffected(self):
        move, line = self._create_invoice(price_unit=100.0, discount_fixed=0.0)
        self.assertEqual(line.price_subtotal, 100.0)

    def test_discount_fixed_with_zero_price_unit_does_not_divide_by_zero(self):
        line_new = self.env["account.move.line"].new(
            {"price_unit": 0.0, "quantity": 1.0, "discount_fixed": 10.0}
        )
        self.assertEqual(line_new._get_exact_discount_percentage(), 0.0)

    # ── validation: fixed discount can't reach/exceed the line's subtotal ──

    def test_discount_fixed_equal_to_subtotal_raises(self):
        with self.assertRaises(ValidationError):
            self._create_invoice(price_unit=50.0, quantity=2, discount_fixed=100.0)

    def test_discount_fixed_above_subtotal_raises(self):
        with self.assertRaises(ValidationError):
            self._create_invoice(price_unit=10.0, discount_fixed=20.0)

    # ── foreign currency amounts stay in sync ───────────────────────

    def test_foreign_subtotal_stays_in_sync_with_fixed_discount(self):
        """foreign_subtotal/foreign_price_total must reflect the same
        discount as the native price_subtotal/price_total, converted at the
        line's foreign rate."""
        move, line = self._create_invoice(
            price_unit=100.0,
            discount_fixed=20.0,
            foreign_rate=38.0,
            foreign_inverse_rate=38.0,
        )

        self.assertEqual(line.discount, 0.0)
        # foreign_price = price_unit converted to VEF at rate 38 -> 3800.
        self.assertEqual(line.foreign_price, 3800.0)
        # 3800 * (1 - 0.20) = 3040 untaxed, * 1.16 = 3526.4 with tax.
        self.assertEqual(line.foreign_subtotal, 3040.0)
        self.assertEqual(line.foreign_price_total, 3526.4)

    def test_foreign_subtotal_matches_native_percentage_discount_line(self):
        """Cross-check: fixed-discount line and a directly-percent-discounted
        line must produce identical foreign amounts too, not just native."""
        move_fixed, line_fixed = self._create_invoice(
            price_unit=200.0, discount_fixed=50.0,  # 50/200 = 25%
            foreign_rate=40.0, foreign_inverse_rate=40.0,
        )

        self.company.discount_type = "percent"
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
        self.assertEqual(
            line_fixed.foreign_price_total, line_percent.foreign_price_total
        )

    def test_foreign_subtotal_exact_for_non_round_ratio(self):
        """Same precision fix as the native amount, applied to the foreign
        currency side."""
        move, line = self._create_invoice(
            price_unit=333.33, discount_fixed=25.55, taxes=False,
            foreign_rate=38.0, foreign_inverse_rate=38.0,
        )
        # foreign_price = 333.33 * 38 = 12666.54; foreign discount amount
        # equivalent = 25.55 * 38 = 970.9; foreign_subtotal = 12666.54 - 970.9
        # = 11695.64, exactly (no rounding through a 2-decimal % first).
        self.assertEqual(line.foreign_subtotal, 11695.64)

    # ── per-line correctness when several lines are involved ───────────

    def test_each_line_uses_its_own_price_unit(self):
        """Two lines with the same discount_fixed but different price_unit
        must produce different Base Imponibles, each computed against its
        own price_unit * quantity."""
        move, _ = self._create_invoice(price_unit=100.0, discount_fixed=10.0)
        move.write(
            {
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 50.0,
                            "discount_fixed": 10.0,
                            "tax_ids": [Command.set([self.tax_iva16.id])],
                        }
                    )
                ]
            }
        )
        lines = move.invoice_line_ids.filtered(lambda l: l.product_id)
        line_100 = lines.filtered(lambda l: l.price_unit == 100.0)
        line_50 = lines.filtered(lambda l: l.price_unit == 50.0)

        self.assertEqual(line_100.price_subtotal, 90.0)  # 100 - 10
        self.assertEqual(line_50.price_subtotal, 40.0)  # 50 - 10
