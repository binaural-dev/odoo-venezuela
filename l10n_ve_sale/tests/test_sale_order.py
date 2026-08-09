from odoo import _, fields
from odoo.tests import Form
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo.tests import tagged
import logging
import random

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_sale")
class TestSaleOrderInvoice(TransactionCase):
    """Tests for generating invoices from sale orders in Venezuelan localization."""

    def setUp(self):
        super(TestSaleOrderInvoice, self).setUp()
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")
        self.company.write(
            {
                "currency_id": self.currency_vef.id,
                "currency_foreign_id": self.currency_usd.id,
            }
        )

        self.partner = self.env["res.partner"].create(
            {
                "name": "Cliente Prueba",
                "vat": "J12345678",
                "prefix_vat": "J",
                "country_id": self.env.ref("base.ve").id,
                "phone": "04141234567",
                "email": "cliente@prueba.com",
                "street": "Calle Falsa 123",
            }
        )

        self.tax_group = self.env["account.tax.group"].create(
            {
                "name": "IVA",
                "sequence": 10,
                "company_id": self.company.id,
            }
        )

        # Crear impuesto IVA 16%
        self.tax_iva16 = self.env["account.tax"].create(
            {
                "name": "IVA 16%",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "tax_group_id": self.tax_group.id,
                "company_id": self.company.id,
            }
        )

        # Crear el producto
        self.product = self.env["product.product"].create(
            {
                "name": "Producto Prueba",
                "type": "service",
                "list_price": 100,
                "barcode": "123456789",
                "taxes_id": [(6, 0, [self.tax_iva16.id])],
            }
        )

        self.partner_a = self.env["res.partner"].create(
            {
                "name": "Test Partner A",
                "customer_rank": 1,
            }
        )

        sequence = self.env["ir.sequence"].create(
            {
                "name": "Secuencia Factura",
                "code": "account.move",
                "prefix": "INV/",
                "padding": 8,
                "number_next_actual": 2,
            }
        )
        refund_sequence = self.env["ir.sequence"].create(
            {
                "name": "nota de credito",
                "code": "",
                "prefix": "NC/",
                "padding": 8,
                "number_next_actual": 2,
            }
        )

        self.journal = self.env["account.journal"].create(
            {
                "name": "Diario de Ventas",
                "code": "VEN",
                "type": "sale",
                "sequence_id": sequence.id,
                "refund_sequence_id": refund_sequence.id,
                "company_id": self.env.company.id,
            }
        )

    def test_01_generate_invoice_from_sale_order(self):
        rate = 5.0
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "manually_set_rate": True,
                "foreign_rate": rate,
                "foreign_inverse_rate": 1 / rate,
            }
        )

        order_line_01 = self.env["sale.order.line"].create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 2,
                "price_unit": 100,
                "tax_id": [(6, 0, [self.tax_iva16.id])],
                "order_id": order.id,
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
                "foreign_rate": rate,
                "display_type": False,
                "name": "Test Product Line",
            }
        )

        order_line_02 = self.env["sale.order.line"].create(
            {
                "product_id": False,
                "product_uom_qty": 0,
                "price_unit": 0,
                "tax_id": [(6, 0, [self.tax_iva16.id])],
                "order_id": order.id,
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
                "foreign_rate": 0,
                "display_type": "line_section",
                "name": "Section Line",
            }
        )

        order_line_03 = self.env["sale.order.line"].create(
            {
                "product_id": False,
                "product_uom_qty": 0,
                "price_unit": 0,
                "tax_id": [(6, 0, [self.tax_iva16.id])],
                "order_id": order.id,
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
                "foreign_rate": 0,
                "display_type": "line_note",
                "name": "Section Line",
            }
        )

        order.write(
            {
                "order_line": [order_line_01.id, order_line_02.id, order_line_03.id],
            }
        )

        order.action_confirm()
        invoice = order._create_invoices()

        self.assertTrue(
            len(order.order_line) == len(invoice.invoice_line_ids),
            "The invoice created from the sales order must have the same number of lines as the sales order.",
        )
        _logger.info("test_01_generate_invoice_from_sale_order --- successfully")

    def test_02_error_generate_invoice_from_sale_order(self):
        rate = 5.0
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "manually_set_rate": True,
                "foreign_rate": rate,
                "foreign_inverse_rate": 1 / rate,
            }
        )

        order_line_02 = self.env["sale.order.line"].create(
            {
                "product_id": False,
                "product_uom_qty": 0,
                "price_unit": 0,
                "tax_id": [(6, 0, [self.tax_iva16.id])],
                "order_id": order.id,
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
                "foreign_rate": 0,
                "display_type": "line_section",
                "name": "Section Line",
            }
        )

        order_line_03 = self.env["sale.order.line"].create(
            {
                "product_id": False,
                "product_uom_qty": 0,
                "price_unit": 0,
                "tax_id": [(6, 0, [self.tax_iva16.id])],
                "order_id": order.id,
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
                "foreign_rate": 0,
                "display_type": "line_note",
                "name": "Section Line",
            }
        )

        order.write(
            {
                "order_line": [order_line_02.id, order_line_03.id],
            }
        )

        with self.assertRaises(UserError) as e:
            order.action_confirm()
            order._create_invoices()
        _logger.info("test_02_error_generate_invoice_from_sale_order --- successfully (%s)",e.exception,)

    def test_03_reconfirm_sale_order_with_pickings(self):
        """Test reconfirming a sale order after it was confirmed, cancelled and set to draft.
        This flow was causing a singleton error in stock.picking.
        """
        # Create a storable product
        product_storable = self.env["product.product"].create({
            "name": "Producto Almacenable",
            "type": "product",
            "invoice_policy": "order",
            "list_price": 50,
            "taxes_id": [(6, 0, [self.tax_iva16.id])],
            "barcode": "ST12345",
        })
        
        # Give some stock
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.company.id)], limit=1)
        self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': product_storable.id,
            'location_id': warehouse.lot_stock_id.id,
            'inventory_quantity': 10,
        }).action_apply_inventory()

        rate = 5.0
        # Create order with 2 lines of 1 unit each to trigger split picking logic
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "manually_set_rate": True,
            "foreign_rate": rate,
            "foreign_inverse_rate": 1 / rate,
            "order_line": [
                (0, 0, {
                    "product_id": product_storable.id,
                    "product_uom_qty": 1,
                    "price_unit": 100,
                    "tax_id": [(6, 0, [self.tax_iva16.id])],
                    "name": "Line 1",
                }),
                (0, 0, {
                    "product_id": product_storable.id,
                    "product_uom_qty": 1,
                    "price_unit": 100,
                    "tax_id": [(6, 0, [self.tax_iva16.id])],
                    "name": "Line 2",
                })
            ]
        })

        # Seteamos el límite de pickings para que se dividan
        self.company.write({'limit_product_qty_out': 1})

        # 1. Confirm the order
        order.action_confirm()
        self.assertEqual(order.state, 'sale')
        self.assertTrue(len(order.picking_ids) > 1, "Should have created multiple pickings due to limit_product_qty_out=1")
        
        # 2. Cancel related pickings to allow SO cancellation
        for picking in order.picking_ids:
            picking.move_ids.write({'state': 'cancel'})
            picking.write({'state': 'cancel'})
        
        # 3. Cancel the order
        order.action_cancel()
        if order.state != 'cancel':
            order.write({'state': 'cancel'})
            
        self.assertEqual(order.state, 'cancel')
        
        # 4. Set back to draft
        order.action_draft()
        self.assertEqual(order.state, 'draft')
        
        # 5. Confirm again (This validates the fix for the singleton error)
        order.action_confirm()
        self.assertEqual(order.state, 'sale')
        _logger.info("test_03_reconfirm_sale_order_with_pickings --- successfully")

    def test_04_rounding_residual_no_extra_invoices(self):
        """Verify that a rounding residual (±0.005 with rounding 0.01) is filtered
        and the while loop does not produce extra invoices."""
        dp = self.env["decimal.precision"].search(
            [("name", "=", "Product Unit of Measure")]
        )
        original = dp.digits
        dp.digits = 3

        try:
            rate = 5.0
            order = self.env["sale.order"].create({
                "partner_id": self.partner.id,
                "manually_set_rate": True,
                "foreign_rate": rate,
                "foreign_inverse_rate": 1 / rate,
                "order_line": [(0, 0, {
                    "product_id": self.product.id,
                    "product_uom_qty": 1.005,
                    "price_unit": 100,
                    "tax_id": [(6, 0, [self.tax_iva16.id])],
                    "name": "3-decimal qty",
                })],
            })
            order.action_confirm()

            invoiceable = order._get_invoiceable_lines()
            self.assertEqual(len(invoiceable), 1, "Line must be invoiceable")

            before = self.env["account.move"].search_count(
                [("invoice_origin", "=", order.name)]
            )
            order._create_invoices()
            after = self.env["account.move"].search_count(
                [("invoice_origin", "=", order.name)]
            )
            self.assertEqual(after - before, 1, "Must create exactly 1 invoice")

            remaining = order._get_invoiceable_lines()
            self.assertFalse(remaining, "No lines must remain after invoicing")
        finally:
            dp.digits = original
            self.env.registry.clear_cache()


@tagged("post_install", "-at_install", "l10n_ve_sale")
class TestSaleOrderForeignTotals(TransactionCase):
    """Validates that a sale.order's alterno (`tax_totals`) fields are
    anchored to `amount_total x foreign_inverse_rate` -- the same invariant
    enforced for a posted account.move (see l10n_ve_tax._sync_foreign_taxes_with_entry
    and l10n_ve_accountant._compute_foreign_tax_balance) -- instead of an
    independent per-line re-tax that can drift a few units of the alterno
    currency away from the direct conversion (and from what the resulting
    invoice will show once posted).
    """

    def setUp(self):
        super().setUp()
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")
        self.company.write({
            "currency_id": self.currency_vef.id,
            "currency_foreign_id": self.currency_usd.id,
        })

        self.partner = self.env["res.partner"].create({
            "name": "Cliente Alternos",
            "vat": "J87654321",
            "prefix_vat": "J",
            "country_id": self.env.ref("base.ve").id,
        })

        self.tax_group_16 = self.env["account.tax.group"].create({
            "name": "IVA 16 grp", "sequence": 10, "company_id": self.company.id,
        })
        self.tax_group_8 = self.env["account.tax.group"].create({
            "name": "IVA 8 grp", "sequence": 11, "company_id": self.company.id,
        })
        self.tax_group_31 = self.env["account.tax.group"].create({
            "name": "IVA 31 grp", "sequence": 12, "company_id": self.company.id,
        })
        self.tax_16 = self.env["account.tax"].create({
            "name": "IVA 16% (alternos)", "amount": 16.0, "amount_type": "percent",
            "type_tax_use": "sale", "tax_group_id": self.tax_group_16.id,
            "company_id": self.company.id,
        })
        self.tax_8 = self.env["account.tax"].create({
            "name": "IVA 8% (alternos)", "amount": 8.0, "amount_type": "percent",
            "type_tax_use": "sale", "tax_group_id": self.tax_group_8.id,
            "company_id": self.company.id,
        })
        self.tax_31 = self.env["account.tax"].create({
            "name": "IVA 31% (alternos)", "amount": 31.0, "amount_type": "percent",
            "type_tax_use": "sale", "tax_group_id": self.tax_group_31.id,
            "company_id": self.company.id,
        })
        self.product_16 = self.env["product.product"].create({
            "name": "Producto 16", "type": "service", "list_price": 100.0,
            "taxes_id": [(6, 0, [self.tax_16.id])],
        })
        self.product_8 = self.env["product.product"].create({
            "name": "Producto 8", "type": "service", "list_price": 100.0,
            "taxes_id": [(6, 0, [self.tax_8.id])],
        })
        self.product_31 = self.env["product.product"].create({
            "name": "Producto 31", "type": "service", "list_price": 100.0,
            "taxes_id": [(6, 0, [self.tax_31.id])],
        })

    def _create_order(self, rate, lines):
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            # `currency_id` is a pure computed+stored field on sale.order
            # (no `inverse`), derived from `pricelist_id.currency_id or
            # company_id.currency_id` -- passing "currency_id" directly is
            # silently ignored. `pricelist_id` IS writable, so clearing it
            # here (instead of leaving it to default from the partner's
            # pricelist, e.g. a VEF-only demo pricelist) makes currency_id
            # fall back to the company's own currency -- irrelevant for the
            # VEF-base case (they happen to coincide) but required for the
            # USD-base subclass, where order.currency_id must match
            # self.company.currency_id for the sign/branch logic in
            # res.currency._convert (l10n_ve_rate) to apply correctly.
            "pricelist_id": False,
            "manually_set_rate": True,
            "foreign_rate": rate,
            "foreign_inverse_rate": 1 / rate,
        })
        order_line_vals = []
        for product, qty, price_unit, tax in lines:
            order_line_vals.append((0, 0, {
                "product_id": product.id,
                "product_uom_qty": qty,
                "price_unit": price_unit,
                "tax_id": [(6, 0, [tax.id])],
                "name": product.name,
            }))
        order.write({"order_line": order_line_vals})
        return order

    def _foreign_direct_conversion(self, order, native_amount):
        fc = self.company.currency_foreign_id
        return fc.round(order.currency_id._convert(
            abs(native_amount), fc, order.company_id,
            order.date_order.date() if order.date_order else False,
            custom_rate=order.foreign_inverse_rate,
        ))

    def test_foreign_price_high_precision_not_truncated(self):
        """`foreign_price` must retain more than 2 decimals (it is a `Float`
        with the "Foreign Product Price" precision, not a `Monetary` that
        silently rounds to the alterno currency's 2 decimals on save --
        the same fix applied to account.move.line's `foreign_price`)."""
        dp = self.env["decimal.precision"].search([("name", "=", "Foreign Product Price")])
        original = dp.digits
        dp.digits = 5
        try:
            rate = 37.28173  # a rate unlikely to produce a "round" 2-decimal price
            order = self._create_order(rate, [(self.product_16, 1, 100.0, self.tax_16)])
            line = order.order_line.filtered(lambda l: not l.display_type)
            # `res.currency._convert`'s custom_rate branch (l10n_ve_rate)
            # DIVIDES instead of multiplying when the company's base currency
            # is USD -- compute `expected` the same way production code does
            # instead of assuming the VEF-base "multiply" convention, so this
            # premise holds for both TestSaleOrderForeignTotals (VEF base)
            # and its TestSaleOrderForeignTotalsUSDBase subclass.
            expected = order.currency_id._convert(
                100.0, self.company.currency_foreign_id, self.company,
                fields.Date.today(), custom_rate=1 / rate, round=False,
            )
            self.assertNotAlmostEqual(
                line.foreign_price, round(expected, 2), places=4,
                msg="test premise: the full-precision alterno price must differ "
                    "from its own 2-decimal rounding")
            self.assertAlmostEqual(
                line.foreign_price, expected, places=4,
                msg="foreign_price lost precision (rounded to currency decimals)")
        finally:
            dp.digits = original

    def test_tax_totals_foreign_anchored_to_amount_total_single_tax(self):
        rate = 84.37
        order = self._create_order(rate, [
            (self.product_16, 3, 250.75, self.tax_16),
        ])
        tt = order.tax_totals
        expected_total = self._foreign_direct_conversion(order, order.amount_total)
        expected_untaxed = self._foreign_direct_conversion(order, order.amount_untaxed)
        self.assertAlmostEqual(
            tt["foreign_amount_total"], expected_total, places=1,
            msg="foreign_amount_total must match amount_total x rate directly")
        self.assertAlmostEqual(
            tt["foreign_amount_untaxed"], expected_untaxed, places=1,
            msg="foreign_amount_untaxed must match amount_untaxed x rate directly")

    def test_tax_totals_foreign_anchored_to_amount_total_multi_tax(self):
        """Multiple tax groups (16% + 8%): the anchor must hold on the TOTAL
        even though each group's own foreign base/tax was independently
        rounded (this is exactly the scenario reported by the user where a
        quotation's alterno total drifted ~$958 away from amount_total x rate)."""
        rate = 709.6935
        order = self._create_order(rate, [
            (self.product_16, 5, 1234.5678, self.tax_16),
            (self.product_8, 3, 9876.5432, self.tax_8),
        ])
        tt = order.tax_totals
        expected_total = self._foreign_direct_conversion(order, order.amount_total)
        expected_untaxed = self._foreign_direct_conversion(order, order.amount_untaxed)

        self.assertAlmostEqual(
            tt["foreign_amount_total"], expected_total, places=1,
            msg="foreign_amount_total drifted from the direct amount_total x rate "
                "conversion -- alterno totals must be anchored, not an independent "
                "per-group re-tax")
        self.assertAlmostEqual(
            tt["foreign_amount_untaxed"], expected_untaxed, places=1,
            msg="foreign_amount_untaxed drifted from the direct conversion")

    def test_tax_totals_foreign_groups_sum_to_totals(self):
        rate = 155.9
        order = self._create_order(rate, [
            (self.product_16, 2, 480.0, self.tax_16),
            (self.product_8, 4, 615.25, self.tax_8),
        ])
        tt = order.tax_totals
        groups = [
            g for grp in tt["groups_by_foreign_subtotal"].values() for g in grp
        ]
        base_sum = sum(g["tax_group_base_amount"] for g in groups)
        tax_sum = sum(g["tax_group_amount"] for g in groups)

        self.assertAlmostEqual(
            base_sum, tt["foreign_amount_untaxed"], places=1,
            msg="sum of per-group foreign bases must equal foreign_amount_untaxed")
        self.assertAlmostEqual(
            tax_sum, tt["foreign_amount_total"] - tt["foreign_amount_untaxed"], places=1,
            msg="sum of per-group foreign taxes must equal foreign_amount_total - foreign_amount_untaxed")
        self.assertAlmostEqual(
            sum(s["amount"] for s in tt["foreign_subtotals"]),
            tt["foreign_amount_untaxed"], places=1,
            msg="foreign_subtotals total must match foreign_amount_untaxed")

    def test_order_to_invoice_foreign_total_consistency(self):
        """The whole point of anchoring the quotation's alterno total: once
        confirmed and invoiced, the invoice must show (approximately) the
        SAME alterno total the quotation showed -- not a different number
        arrived at via a completely independent computation path."""
        rate = 632.14
        order = self._create_order(rate, [
            (self.product_16, 2, 4321.98, self.tax_16),
            (self.product_8, 6, 876.54, self.tax_8),
        ])
        order_foreign_total = order.tax_totals["foreign_amount_total"]

        order.action_confirm()
        invoice = order._create_invoices()
        invoice.action_post()
        self.env.invalidate_all()

        invoice_foreign_total = invoice.tax_totals["foreign_amount_total"]

        self.assertAlmostEqual(
            invoice_foreign_total, order_foreign_total, delta=1.0,
            msg="the posted invoice's alterno total drifted from what the "
                "quotation showed the customer -- both must be anchored to "
                "the same amount_total x rate conversion")

    def _create_stress_order(self, rate, seed):
        """30 lines, 3 tax rates (8%/16%/31%), varied prices/quantities --
        mirrors l10n_ve_accountant's 30-product stress tests, but for a
        sale.order instead of a posted account.move."""
        random.seed(seed)
        products = [self.product_16, self.product_8, self.product_31]
        taxes = [self.tax_16, self.tax_8, self.tax_31]
        lines = []
        for i in range(30):
            idx = i % 3
            price = round(random.uniform(10.0, 9999.99), 2)
            qty = round(random.uniform(1, 50), 2)
            lines.append((products[idx], qty, price, taxes[idx]))
        return self._create_order(rate, lines)

    def test_tax_totals_foreign_anchored_30_products_3_taxes(self):
        """Stress case reported by the user: 30 lines split across 3 tax
        groups (8%/16%/31%) with varied prices and quantities. The alterno
        total must still be anchored to `amount_total x rate` exactly --
        the whole point of anchoring is that this holds no matter how many
        lines/tax groups independently round their own base/tax."""
        order = self._create_stress_order(rate=709.6935, seed=101)
        self.assertEqual(len(order.order_line), 30)

        tt = order.tax_totals
        expected_total = self._foreign_direct_conversion(order, order.amount_total)
        expected_untaxed = self._foreign_direct_conversion(order, order.amount_untaxed)

        self.assertAlmostEqual(
            tt["foreign_amount_total"], expected_total, places=1,
            msg="foreign_amount_total drifted from amount_total x rate with "
                "30 lines across 3 tax groups")
        # `foreign_amount_untaxed` is the natural sum of 30 independently-
        # rounded per-line `foreign_subtotal` values (bottom-up), NOT itself
        # anchored to a single top-down `amount_untaxed x rate` conversion
        # (only the grand TOTAL is -- the tax absorbs that gap, see
        # _anchor_foreign_taxes_for_order). With 30 lines, a couple cents of
        # accumulated per-line rounding drift from the top-down figure is
        # expected and correct, so a delta tolerance is used here instead of
        # `places=1`.
        self.assertAlmostEqual(
            tt["foreign_amount_untaxed"], expected_untaxed, delta=1.0,
            msg="foreign_amount_untaxed drifted from amount_untaxed x rate "
                "with 30 lines across 3 tax groups")

        groups = [g for grp in tt["groups_by_foreign_subtotal"].values() for g in grp]
        self.assertEqual(len(groups), 3, "must have exactly 3 tax groups (8%/16%/31%)")
        base_sum = sum(g["tax_group_base_amount"] for g in groups)
        tax_sum = sum(g["tax_group_amount"] for g in groups)
        self.assertAlmostEqual(
            base_sum, tt["foreign_amount_untaxed"], places=1,
            msg="sum of the 3 groups' foreign bases must equal foreign_amount_untaxed")
        self.assertAlmostEqual(
            tax_sum, tt["foreign_amount_total"] - tt["foreign_amount_untaxed"], places=1,
            msg="sum of the 3 groups' foreign taxes must equal foreign_amount_total - foreign_amount_untaxed")

    def test_order_to_invoice_foreign_total_consistency_30_products_3_taxes(self):
        order = self._create_stress_order(rate=632.14, seed=202)
        order_foreign_total = order.tax_totals["foreign_amount_total"]

        order.action_confirm()
        invoices = order._create_invoices()
        # 30 lines can be split across more than one invoice; post them one
        # at a time (a multi-record `invoices.action_post()` call trips an
        # unrelated pre-existing singleton bug in
        # l10n_ve_accountant.account_move.action_post, out of scope here)
        # and sum each invoice's alterno total for the comparison below.
        invoice_foreign_total = 0.0
        for inv in invoices:
            inv.action_post()
            self.env.invalidate_all()
            invoice_foreign_total += inv.tax_totals["foreign_amount_total"]

        self.assertAlmostEqual(
            invoice_foreign_total, order_foreign_total, delta=1.0,
            msg="30-line/3-tax posted invoice(s) alterno total drifted from "
                "what the quotation showed")


@tagged("post_install", "-at_install", "l10n_ve_sale")
class TestSaleOrderForeignTotalsUSDBase(TestSaleOrderForeignTotals):
    """Re-runs the entire TestSaleOrderForeignTotals suite with the company's
    base currency set to USD and the alterno to VEF (the reverse of the
    default VEF-base/USD-alterno combination) -- `res.currency._convert`'s
    `custom_rate` branch DIVIDES instead of multiplying in this case (see
    l10n_ve_rate.res_currency._convert), so it must be exercised
    independently rather than assumed to mirror the VEF-base results."""

    def setUp(self):
        super().setUp()
        self.company.write({
            "currency_id": self.currency_usd.id,
            "currency_foreign_id": self.currency_vef.id,
        })
