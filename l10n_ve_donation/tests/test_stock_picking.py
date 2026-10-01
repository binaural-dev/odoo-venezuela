from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TestDonationCommon


@tagged('l10n_ve_donation', 'stock_picking', '-at_install', 'post_install')
class TestStockPicking(TestDonationCommon):
    """Donation given for several products at once, via an outgoing
    picking (code='outgoing'). Coexists with stock.scrap (a single
    product per record)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Some environments leave default_location_src_id/dest_id unset on
        # existing picking types (e.g. a fresh DB where stock's own location
        # data loaded after the warehouse's operation types were created) --
        # force a recompute so these tests don't depend on that pre-existing
        # state.
        cls.picking_type_donation._compute_default_location_src_id()
        cls.picking_type_donation._compute_default_location_dest_id()
        cls.location_stock = cls.picking_type_donation.default_location_src_id

        cls.product_donation_a = cls.env["product.product"].create({
            "name": "Donation Product A",
            "type": "product",
            "categ_id": cls.product_categ.id,
            "standard_price": 25.0,
        })
        cls.product_donation_b = cls.env["product.product"].create({
            "name": "Donation Product B",
            "type": "product",
            "categ_id": cls.product_categ.id,
            "standard_price": 10.0,
        })
        for product in (cls.product_donation_a, cls.product_donation_b):
            cls.env["stock.quant"].create({
                "product_id": product.id,
                "location_id": cls.location_stock.id,
                "quantity": 100.0,
            })

    def _create_donation_delivery(self, products_qty, partner=None, donation_reason=None):
        picking_type = self.picking_type_donation
        move_vals = [
            Command.create({
                "name": product.name,
                "product_id": product.id,
                "product_uom_qty": qty,
                "product_uom": product.uom_id.id,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": picking_type.default_location_dest_id.id,
            })
            for product, qty in products_qty
        ]
        picking = self.env["stock.picking"].create({
            "picking_type_id": picking_type.id,
            "location_id": picking_type.default_location_src_id.id,
            "location_dest_id": picking_type.default_location_dest_id.id,
            "partner_id": partner.id if partner else False,
            "donation_reason": donation_reason,
            "move_ids": move_vals,
        })
        return picking

    def _confirm_and_set_done_qty(self, picking):
        picking.action_confirm()
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True

    def test_01_validate_without_partner_or_reason_fails(self):
        """An outgoing donation picking without a recipient or a reason
        fails on button_validate."""
        picking = self._create_donation_delivery([(self.product_donation_a, 5)])
        self._confirm_and_set_done_qty(picking)
        with self.assertRaises(UserError):
            picking.button_validate()

    def test_02_validate_with_reason_succeeds(self):
        """With a donation reason (no recipient), validation succeeds."""
        picking = self._create_donation_delivery(
            [(self.product_donation_a, 5)], donation_reason="Medication for patient"
        )
        self._confirm_and_set_done_qty(picking)
        picking.button_validate()
        self.assertEqual(picking.state, "done")

    def test_03_validate_with_partner_succeeds(self):
        """With a recipient (no reason), validation succeeds."""
        picking = self._create_donation_delivery([(self.product_donation_a, 5)], partner=self.partner)
        self._confirm_and_set_done_qty(picking)
        picking.button_validate()
        self.assertEqual(picking.state, "done")

    def test_04_certificate_lists_every_product(self):
        """A picking with several distinct products: the certificate/line
        data list every one of them."""
        picking = self._create_donation_delivery(
            [(self.product_donation_a, 5), (self.product_donation_b, 3)],
            partner=self.partner,
        )
        self._confirm_and_set_done_qty(picking)
        picking.button_validate()

        line_data = picking._get_donation_product_lines()
        self.assertEqual(len(line_data), 2)
        products = {row["line"].product_id for row in line_data}
        self.assertEqual(products, {self.product_donation_a, self.product_donation_b})

        report = self.env.ref("l10n_ve_donation.action_donation_delivery_certificate")
        html, _report_type = report._render_qweb_html(report.report_name, picking.ids)
        self.assertIn(self.product_donation_a.name.encode(), html)
        self.assertIn(self.product_donation_b.name.encode(), html)

    def test_05_reprint_same_number_and_data(self):
        """Reprinting the certificate twice gives the same number and the
        same data, even if the product's cost changes afterward."""
        picking = self._create_donation_delivery([(self.product_donation_a, 5)], partner=self.partner)
        self._confirm_and_set_done_qty(picking)
        picking.button_validate()

        report = self.env.ref("l10n_ve_donation.action_donation_delivery_certificate")
        html_1, _t1 = report._render_qweb_html(report.report_name, picking.ids)

        self.product_donation_a.standard_price = 999.0

        html_2, _t2 = report._render_qweb_html(report.report_name, picking.ids)

        self.assertEqual(html_1, html_2)
        self.assertIn(picking.name.encode(), html_1)

    def test_06_normal_picking_no_special_behavior(self):
        """A normal picking (_is_donation_delivery() False) does not require
        anything or trigger any special behavior."""
        normal_picking_type = self.env["stock.picking.type"].search([
            ("warehouse_id", "=", self.warehouse_normal.id),
            ("code", "=", "outgoing"),
        ], limit=1)
        normal_picking_type._compute_default_location_src_id()
        normal_picking_type._compute_default_location_dest_id()
        self.env["stock.quant"].create({
            "product_id": self.product_donation_a.id,
            "location_id": normal_picking_type.default_location_src_id.id,
            "quantity": 10.0,
        })
        picking = self.env["stock.picking"].create({
            "picking_type_id": normal_picking_type.id,
            "location_id": normal_picking_type.default_location_src_id.id,
            "location_dest_id": normal_picking_type.default_location_dest_id.id,
            "move_ids": [
                Command.create({
                    "name": self.product_donation_a.name,
                    "product_id": self.product_donation_a.id,
                    "product_uom_qty": 1,
                    "product_uom": self.product_donation_a.uom_id.id,
                    "location_id": normal_picking_type.default_location_src_id.id,
                    "location_dest_id": normal_picking_type.default_location_dest_id.id,
                })
            ],
        })
        self.assertFalse(picking._is_donation_delivery())
        self._confirm_and_set_done_qty(picking)
        picking.button_validate()
        self.assertEqual(picking.state, "done")

    def test_07_receipt_picking_not_confused_with_delivery(self):
        """A RECEIPT picking marked with the shared flag
        (is_donation_picking_type=True, code='incoming') confirms that
        _is_donation_delivery() returns False -- it is not confused with the
        outgoing direction."""
        receipt_picking_type = self.env["stock.picking.type"].create({
            "name": "Donation Receipt Test",
            "code": "incoming",
            "sequence_code": "TDONRCV2",
            "warehouse_id": self.warehouse_donation.id,
            "company_id": self.company.id,
            "is_donation_picking_type": True,
        })
        receipt_picking_type._compute_default_location_src_id()
        receipt_picking_type._compute_default_location_dest_id()
        picking = self.env["stock.picking"].create({
            "picking_type_id": receipt_picking_type.id,
            "location_id": receipt_picking_type.default_location_src_id.id,
            "location_dest_id": receipt_picking_type.default_location_dest_id.id,
        })
        self.assertFalse(picking._is_donation_delivery())

    def test_08_real_time_valuation_delivery_with_partner_posts_correctly(self):
        """A donation delivery with a recipient set must validate
        successfully even when the product's category uses automated
        (real_time) valuation -- a common real-world setup for product
        categories. `stock_account._generate_valuation_lines_data` stamps the
        picking's partner (the beneficiary) on every line of the generated
        valuation account.move; `_check_partner_donation()` (line-level
        validation) rejects any line that is not the company. The header
        must still show the real beneficiary, and every line must show the
        company."""
        real_time_categ = self.env["product.category"].create({
            "name": "Real Time Donation Category",
            "property_valuation": "real_time",
            "property_cost_method": "standard",
            "property_stock_account_input_categ_id": self.env["account.account"].create({
                "name": "Stock Input Test",
                "code": "120101",
                "account_type": "asset_current",
                "company_id": self.company.id,
            }).id,
            "property_stock_account_output_categ_id": self.env["account.account"].create({
                "name": "Stock Output Test",
                "code": "120102",
                "account_type": "asset_current",
                "company_id": self.company.id,
            }).id,
            "property_stock_valuation_account_id": self.env["account.account"].create({
                "name": "Stock Valuation Test",
                "code": "120103",
                "account_type": "asset_current",
                "company_id": self.company.id,
            }).id,
            "property_stock_journal": self.journal_general.id,
        })
        product = self.env["product.product"].create({
            "name": "Real Time Donation Product",
            "type": "product",
            "categ_id": real_time_categ.id,
            "standard_price": 20.0,
        })
        self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": self.location_stock.id,
            "quantity": 10.0,
        })

        picking = self._create_donation_delivery([(product, 2)], partner=self.partner)
        self._confirm_and_set_done_qty(picking)
        picking.button_validate()
        self.assertEqual(picking.state, "done")

        valuation_move = picking.move_ids.stock_valuation_layer_ids.account_move_id
        self.assertTrue(valuation_move)
        self.assertEqual(valuation_move.partner_id, self.partner)
        company_partner = self.env.company.partner_id
        for line in valuation_move.line_ids:
            self.assertEqual(line.partner_id, company_partner)
