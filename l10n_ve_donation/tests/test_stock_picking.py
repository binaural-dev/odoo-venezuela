import importlib.util
import os
from itertools import count

from odoo import Command, _
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TestDonationCommon


_real_time_seq = count(1)


@tagged('l10n_ve_donation', 'stock_picking', '-at_install', 'post_install')
class TestStockPicking(TestDonationCommon):
    """Donation given for several products at once, via an outgoing
    picking (code='outgoing'). A picking is a donation only when its
    `is_donation` field is set (by the Donations menu context, or by a
    donation sale order), never because of its operation type."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Some environments leave default_location_src_id unset on existing
        # picking types (e.g. a fresh DB where stock's own location data
        # loaded after the warehouse's operation types were created) -- force
        # a recompute so these tests don't depend on that pre-existing state.
        # The destination is not recomputed: the fixture sets the donation
        # location (see `common.py`).
        cls.picking_type_donation._compute_default_location_src_id()
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

    def _create_donation_delivery(
        self, products_qty, partner=None, donation_reason=None, group=None, extra_vals=None, dest_location=None
    ):
        picking_type = self.picking_type_donation
        dest_location = dest_location or picking_type.default_location_dest_id
        move_vals = [
            Command.create({
                "name": product.name,
                "product_id": product.id,
                "product_uom_qty": qty,
                "product_uom": product.uom_id.id,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": dest_location.id,
                "group_id": group.id if group else False,
            })
            for product, qty in products_qty
        ]
        picking = self.env["stock.picking"].create({
            "picking_type_id": picking_type.id,
            "location_id": picking_type.default_location_src_id.id,
            "location_dest_id": dest_location.id,
            "partner_id": partner.id if partner else False,
            "donation_reason": donation_reason,
            "is_donation": True,
            "move_ids": move_vals,
            **(extra_vals or {}),
        })
        return picking

    def _confirm_and_set_done_qty(self, picking):
        picking.action_confirm()
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True

    def _create_real_time_product(self):
        """Storable product (10 units in stock) whose category uses
        automated (real_time) valuation. Account codes are unique per call,
        so it can be called several times in the same test."""
        seq = next(_real_time_seq)
        real_time_categ = self.env["product.category"].create({
            "name": "Real Time Donation Category",
            "property_valuation": "real_time",
            "property_cost_method": "standard",
            "property_stock_account_input_categ_id": self.env["account.account"].create({
                "name": "Stock Input Test",
                "code": f"1211{seq:02d}",
                "account_type": "asset_current",
                "company_id": self.company.id,
            }).id,
            "property_stock_account_output_categ_id": self.env["account.account"].create({
                "name": "Stock Output Test",
                "code": f"1212{seq:02d}",
                "account_type": "asset_current",
                "company_id": self.company.id,
            }).id,
            "property_stock_valuation_account_id": self.env["account.account"].create({
                "name": "Stock Valuation Test",
                "code": f"1213{seq:02d}",
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
        return product

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
        """A normal picking (is_donation False) does not require anything or
        trigger any special behavior."""
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
        self.assertFalse(picking.is_donation)
        self._confirm_and_set_done_qty(picking)
        picking.button_validate()
        self.assertEqual(picking.state, "done")

    def test_07_receipt_picking_not_confused_with_delivery(self):
        """A donation RECEIPT (is_donation=True, code='incoming') does not
        behave like a delivery: validating it without a recipient or a
        reason does not raise the donation delivery error. Other modules may
        require the contact of a receipt (higea_donation does), so what is
        checked is that the delivery error is not the one raised."""
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
            "is_donation": True,
            "move_ids": [
                Command.create({
                    "name": self.product_donation_a.name,
                    "product_id": self.product_donation_a.id,
                    "product_uom_qty": 2,
                    "product_uom": self.product_donation_a.uom_id.id,
                    "location_id": receipt_picking_type.default_location_src_id.id,
                    "location_dest_id": receipt_picking_type.default_location_dest_id.id,
                })
            ],
        })
        self.assertTrue(picking.is_donation)
        self.assertEqual(picking.picking_type_code, "incoming")
        self._confirm_and_set_done_qty(picking)
        delivery_error = _(
            "You must set the recipient (Contact) or the donation reason "
            "to validate a donation delivery."
        )
        try:
            picking.button_validate()
        except UserError as error:
            self.assertNotEqual(error.args[0], delivery_error)
        else:
            self.assertEqual(picking.state, "done")

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
        product = self._create_real_time_product()

        picking = self._create_donation_delivery([(product, 2)], partner=self.partner)
        self._confirm_and_set_done_qty(picking)
        picking.button_validate()
        self.assertEqual(picking.state, "done")

        valuation_move = picking.move_ids.stock_valuation_layer_ids.account_move_id
        self.assertTrue(valuation_move)
        self.assertTrue(valuation_move.is_donation)
        self.assertEqual(valuation_move.partner_id, self.partner)
        company_partner = self.env.company.partner_id
        for line in valuation_move.line_ids:
            self.assertEqual(line.partner_id, company_partner)

    def test_09_donation_menu_context_marks_picking(self):
        """The Donations menu passes `donation_menu` in the context:
        `default_get` returns `is_donation=True`, and a picking created that
        way is a donation without setting the field explicitly. Without the
        context the default is False, even if the operation type has the
        donation flag."""
        picking_type = self.picking_type_donation
        self.assertTrue(picking_type.is_donation_picking_type)
        Picking = self.env["stock.picking"]
        self.assertTrue(Picking.with_context(donation_menu=True).default_get(["is_donation"])["is_donation"])
        self.assertFalse(Picking.default_get(["is_donation"]).get("is_donation"))
        vals = {
            "picking_type_id": picking_type.id,
            "location_id": picking_type.default_location_src_id.id,
            "location_dest_id": picking_type.default_location_dest_id.id,
        }
        self.assertTrue(Picking.with_context(donation_menu=True).create(vals).is_donation)
        self.assertFalse(Picking.create(vals).is_donation)

    def test_10_operation_type_flag_does_not_mark_picking(self):
        """Without the context (nor an explicit value) a picking is NOT a
        donation, even if its operation type has the donation flag, and
        it validates without a recipient or a reason."""
        self.assertTrue(self.picking_type_donation.is_donation_picking_type)
        picking_type = self.picking_type_donation
        picking = self.env["stock.picking"].create({
            "picking_type_id": picking_type.id,
            "location_id": picking_type.default_location_src_id.id,
            "location_dest_id": picking_type.default_location_dest_id.id,
            "move_ids": [
                Command.create({
                    "name": self.product_donation_a.name,
                    "product_id": self.product_donation_a.id,
                    "product_uom_qty": 1,
                    "product_uom": self.product_donation_a.uom_id.id,
                    "location_id": picking_type.default_location_src_id.id,
                    "location_dest_id": picking_type.default_location_dest_id.id,
                })
            ],
        })
        self.assertFalse(picking.is_donation)
        self._confirm_and_set_done_qty(picking)
        picking.button_validate()
        self.assertEqual(picking.state, "done")

    def test_11_delivery_from_donation_sale_does_not_require_recipient(self):
        """A delivery that comes from a donation sale order (sale_id set)
        is excluded from the recipient/reason rule: it validates without
        a contact or a donation reason."""
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "is_donation": True,
            "manually_set_rate": True,
            "foreign_rate": 1.0,
            "foreign_inverse_rate": 1.0,
        })
        group = self.env["procurement.group"].create({"name": "Donation Sale Group", "sale_id": order.id})
        picking = self._create_donation_delivery(
            [(self.product_donation_a, 5)], group=group
        )
        self.assertEqual(picking.sale_id, order)
        self.assertTrue(picking.is_donation)
        self._confirm_and_set_done_qty(picking)
        picking.button_validate()
        self.assertEqual(picking.state, "done")

    def test_12_backorder_keeps_is_donation(self):
        """The backorder of a partially delivered donation keeps the
        donation mark."""
        picking = self._create_donation_delivery([(self.product_donation_a, 5)], partner=self.partner)
        picking.action_confirm()
        move = picking.move_ids
        move.quantity = 2
        move.picked = True
        picking.with_context(skip_backorder=True).button_validate()
        self.assertEqual(picking.state, "done")
        backorder = self.env["stock.picking"].search([("backorder_id", "=", picking.id)])
        self.assertEqual(len(backorder), 1)
        self.assertTrue(backorder.is_donation)

    def _create_donation_sale_group(self):
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "is_donation": True,
            "manually_set_rate": True,
            "foreign_rate": 1.0,
            "foreign_inverse_rate": 1.0,
        })
        return self.env["procurement.group"].create({"name": "Donation Sale Group", "sale_id": order.id})

    def test_13_real_time_donation_delivery_without_sale_under_menu_contexts(self):
        """A donation delivery without sale and with real_time valuation
        validates under the Donations menu context (`donation_menu`) and
        also if a `default_is_donation` leaks in the context: the valuation
        entry is a donation, with the beneficiary as header and the company
        on every line."""
        company_partner = self.env.company.partner_id
        for context in ({"donation_menu": True}, {"default_is_donation": True}):
            with self.subTest(context=context):
                product = self._create_real_time_product()
                picking = self._create_donation_delivery([(product, 2)], partner=self.partner)
                self._confirm_and_set_done_qty(picking)
                picking.with_context(**context).button_validate()
                self.assertEqual(picking.state, "done")
                valuation_move = picking.move_ids.stock_valuation_layer_ids.account_move_id
                self.assertTrue(valuation_move)
                self.assertTrue(valuation_move.is_donation)
                self.assertEqual(valuation_move.partner_id, self.partner)
                for line in valuation_move.line_ids:
                    self.assertEqual(line.partner_id, company_partner)

    def test_14_real_time_delivery_from_donation_sale_under_menu_contexts(self):
        """A delivery that comes from a donation sale order (real_time
        valuation) validates under both contexts and its valuation entry is
        NOT marked as a donation: the `default_is_donation` of the menu
        context used to leak into it and fail with 'must be the company
        partner'."""
        for context in ({"donation_menu": True}, {"default_is_donation": True}):
            with self.subTest(context=context):
                product = self._create_real_time_product()
                picking = self._create_donation_delivery(
                    [(product, 2)], partner=self.partner, group=self._create_donation_sale_group()
                )
                self.assertTrue(picking.sale_id)
                self._confirm_and_set_done_qty(picking)
                picking.with_context(**context).button_validate()
                self.assertEqual(picking.state, "done")
                valuation_move = picking.move_ids.stock_valuation_layer_ids.account_move_id
                self.assertTrue(valuation_move)
                self.assertFalse(valuation_move.is_donation)

    def test_15_migration_marks_pickings_without_sale_of_flagged_types(self):
        """The 17.0.1.0.5 migration marks the pickings without sale order
        whose operation type has the donation flag (created with the previous
        design, where the type made the donation); it leaves the rest alone
        and is idempotent."""
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "migrations", "17.0.1.0.5", "post-migration.py",
        )
        spec = importlib.util.spec_from_file_location("donation_post_migration_17_0_1_0_5", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        flagged_picking = self._create_donation_delivery([(self.product_donation_a, 1)], extra_vals={"is_donation": False})
        sale_picking = self._create_donation_delivery(
            [(self.product_donation_a, 1)],
            group=self._create_donation_sale_group(),
            extra_vals={"is_donation": False},
        )
        normal_type = self.env["stock.picking.type"].search([
            ("warehouse_id", "=", self.warehouse_normal.id),
            ("code", "=", "outgoing"),
        ], limit=1)
        self.assertFalse(normal_type.is_donation_picking_type)
        normal_picking = self.env["stock.picking"].create({
            "picking_type_id": normal_type.id,
            "location_id": normal_type.default_location_src_id.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
        })
        pickings = flagged_picking | sale_picking | normal_picking
        self.assertTrue(sale_picking.sale_id)
        self.assertFalse(any(pickings.mapped("is_donation")))

        for _run in range(2):  # the second run checks idempotency
            pickings.flush_recordset()
            migration.migrate(self.env.cr, "17.0.1.0.4")
            pickings.invalidate_recordset(["is_donation"])
            self.assertTrue(flagged_picking.is_donation)
            self.assertFalse(sale_picking.is_donation)
            self.assertFalse(normal_picking.is_donation)

    def _prepare_delivery_to(self, dest_location, group=None, product=None):
        picking = self._create_donation_delivery(
            [(product or self.product_donation_a, 1)],
            partner=self.partner,
            dest_location=dest_location,
            group=group,
        )
        self._confirm_and_set_done_qty(picking)
        return picking

    def _create_donation_location(self, **vals):
        return self.env["stock.location"].create({
            "name": "Donation Destination Test",
            "usage": "inventory",
            "location_id": self.warehouse_donation.view_location_id.id,
            "valuation_in_account_id": False,
            **vals,
        })

    def test_16_real_time_delivery_to_destination_without_account_is_blocked(self):
        """A donation delivery of a real_time product whose destination has no
        incoming valuation account is blocked, naming the location."""
        location = self._create_donation_location(name="Donations Without Account")
        picking = self._prepare_delivery_to(location, product=self._create_real_time_product())
        self.assertEqual(len(picking._get_donation_delivery_config_errors()), 1)
        with self.assertRaises(UserError) as error:
            picking.button_validate()
        self.assertIn(location.display_name, error.exception.args[0])
        self.assertNotEqual(picking.state, "done")

    def test_17_manual_valuation_delivery_to_destination_without_account_validates(self):
        """With manual_periodic valuation no valuation entry is generated, so
        the incoming account is not required (the usage still is)."""
        self.assertEqual(self.product_donation_a.valuation, "manual_periodic")
        location = self._create_donation_location(name="Donations Without Account Manual")
        picking = self._prepare_delivery_to(location)
        self.assertEqual(picking._get_donation_delivery_config_errors(), [])
        picking.button_validate()
        self.assertEqual(picking.state, "done")

        internal = self._create_donation_location(name="Donations Manual Internal", usage="internal")
        picking = self._prepare_delivery_to(internal)
        self.assertEqual(len(picking._get_donation_delivery_config_errors()), 1)
        with self.assertRaises(UserError):
            picking.button_validate()

    def test_18_delivery_to_destination_not_inventory_is_blocked(self):
        """A donation delivery whose destination is not an `inventory`
        location is blocked, even if it has an account. The account of such a
        location is not evaluated, so there is a single error."""
        product = self._create_real_time_product()
        internal = self._create_donation_location(
            name="Donations Internal", usage="internal", valuation_in_account_id=self.account_expense.id
        )
        picking = self._prepare_delivery_to(internal, product=product)
        self.assertEqual(len(picking._get_donation_delivery_config_errors()), 1)
        with self.assertRaises(UserError) as error:
            picking.button_validate()
        self.assertIn(internal.display_name, error.exception.args[0])

        customers = self.env.ref("stock.stock_location_customers")
        picking = self._prepare_delivery_to(customers, product=product)
        errors = picking._get_donation_delivery_config_errors()
        self.assertEqual(len(errors), 1)
        self.assertIn(customers.display_name, errors[0])
        with self.assertRaises(UserError) as error:
            picking.button_validate()
        self.assertEqual(error.exception.args[0], errors[0])

    def test_19_well_configured_delivery_validates_and_debits_location_account(self):
        """A delivery to a coherent destination validates, the config check
        returns no errors, and the valuation entry debits the incoming
        account of the destination location."""
        product = self._create_real_time_product()
        picking = self._create_donation_delivery([(product, 2)], partner=self.partner)
        self._confirm_and_set_done_qty(picking)
        self.assertEqual(picking._get_donation_delivery_config_errors(), [])
        picking.button_validate()
        self.assertEqual(picking.state, "done")
        valuation_move = picking.move_ids.stock_valuation_layer_ids.account_move_id
        debit_lines = valuation_move.line_ids.filtered(lambda line: line.debit > 0)
        self.assertEqual(debit_lines.account_id, self.location_donation.valuation_in_account_id)

    def test_20_donation_sale_delivery_is_not_affected(self):
        """A delivery that comes from a donation sale order is not checked:
        it validates even if its destination is not coherent."""
        customers = self.env.ref("stock.stock_location_customers")
        picking = self._prepare_delivery_to(
            customers, group=self._create_donation_sale_group(), product=self._create_real_time_product()
        )
        self.assertTrue(picking.sale_id)
        picking.button_validate()
        self.assertEqual(picking.state, "done")

    def test_21_non_donation_delivery_is_not_checked(self):
        """The check only applies to donation deliveries: a normal delivery
        (is_donation False) to Customers validates."""
        customers = self.env.ref("stock.stock_location_customers")
        picking = self._prepare_delivery_to(customers, product=self._create_real_time_product())
        picking.is_donation = False
        picking.button_validate()
        self.assertEqual(picking.state, "done")

    def test_22_move_destination_different_from_picking_header_is_checked(self):
        """The destination of a move that differs from the header of the
        picking is checked too (the valuation entry uses the move's)."""
        bad_location = self._create_donation_location(name="Move Destination Without Account")
        picking = self._create_donation_delivery(
            [(self._create_real_time_product(), 1)], partner=self.partner
        )
        self.assertEqual(picking.location_dest_id, self.location_donation)
        picking.move_ids.location_dest_id = bad_location
        self.assertEqual(picking.location_dest_id, self.location_donation)
        errors = picking._get_donation_delivery_config_errors()
        self.assertEqual(len(errors), 1)
        self.assertIn(bad_location.display_name, errors[0])
        self._confirm_and_set_done_qty(picking)
        with self.assertRaises(UserError):
            picking.button_validate()

    def test_23_cancelled_moves_are_ignored(self):
        """A cancelled move neither requires the account nor adds locations."""
        bad_location = self._create_donation_location(name="Cancelled Move Destination")
        picking = self._create_donation_delivery(
            [(self.product_donation_a, 1), (self._create_real_time_product(), 1)], partner=self.partner
        )
        real_time_move = picking.move_ids.filtered(lambda move: move.product_id.valuation == "real_time")
        real_time_move.location_dest_id = bad_location
        picking.action_confirm()
        self.assertEqual(len(picking._get_donation_delivery_config_errors()), 1)
        real_time_move._action_cancel()
        self.assertEqual(picking._get_donation_delivery_config_errors(), [])

    def test_24_real_time_is_read_with_the_company_of_the_picking(self):
        """The valuation mode is company dependent: it is read with the
        company of the picking, not with the active company of the user. With
        another company as the active one (where the category is manual) a
        real_time delivery to a destination without account is still blocked."""
        company_b = self.env["res.company"].create({"name": "Company B Real Time"})
        product = self._create_real_time_product()
        self.assertEqual(product.valuation, "real_time")
        location = self._create_donation_location(name="Donations Without Account Multi")
        picking = self._prepare_delivery_to(location, product=product)
        self.assertEqual(picking.company_id, self.company)

        multi_company = picking.with_context(
            allowed_company_ids=[company_b.id, self.company.id]
        )
        self.assertEqual(multi_company.env.company, company_b)
        self.assertEqual(product.with_company(company_b).valuation, "manual_periodic")
        self.assertTrue(multi_company._has_real_time_valuation_moves())
        self.assertEqual(len(multi_company._get_donation_delivery_config_errors()), 1)
        with self.assertRaises(UserError):
            multi_company.button_validate()

    def test_25_consumable_in_real_time_category_does_not_require_the_account(self):
        """Only storable products generate valuation entries: a consumable in
        a real_time category does not make the destination account required."""
        storable = self._create_real_time_product()
        consumable = self.env["product.product"].create({
            "name": "Consumable In Real Time Category",
            "type": "consu",
            "categ_id": storable.categ_id.id,
        })
        self.assertEqual(consumable.valuation, "real_time")
        location = self._create_donation_location(name="Donations Without Account Consumable")
        picking = self._prepare_delivery_to(location, product=consumable)
        self.assertFalse(picking._has_real_time_valuation_moves())
        self.assertEqual(picking._get_donation_delivery_config_errors(), [])
        storable_picking = self._prepare_delivery_to(location, product=storable)
        self.assertTrue(storable_picking._has_real_time_valuation_moves())
        self.assertEqual(len(storable_picking._get_donation_delivery_config_errors()), 1)
