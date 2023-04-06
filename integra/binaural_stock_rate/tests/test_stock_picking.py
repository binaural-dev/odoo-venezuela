from random import randint, uniform
from datetime import timedelta
import logging

from odoo import Command, fields
from odoo.tests import tagged, Form
from odoo.addons.product.tests.common import TestProductCommon
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)


@tagged("bin", "stock_picking", "post_install", "-at_install")
class TestStockPicking(TestProductCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product_product = cls.env["product.product"]
        cls.model_data = cls.env["ir.model.data"]
        cls.res_currency = cls.env["res.currency"]
        cls.res_partner = cls.env["res.partner"]
        cls.stock_quant = cls.env["stock.quant"]
        cls.currency_rate = cls.env["res.currency.rate"]
        # Origin Documents
        cls.sale_order = cls.env["sale.order"]
        cls.purchase_order = cls.env["purchase.order"]
        cls.stock_picking = cls.env["stock.picking"]

        # Currency ids
        cls.base_vef_id = cls.model_data._xmlid_to_res_id("base.VEF", raise_if_not_found=False)
        cls.base_usd_id = cls.model_data._xmlid_to_res_id("base.USD", raise_if_not_found=False)
        # Needed Groups
        cls.group_analytic_account = cls.model_data._xmlid_to_res_id(
            "analytic.group_analytic_accounting", raise_if_not_found=False
        )
        # Needed company
        cls.company = cls.env.ref("base.main_company")
        cls.warehouse = cls.env.ref("stock.warehouse0")
        # Needed transfer types
        cls.out_type_id = cls.env.ref("stock.picking_type_out")
        cls.in_type_id = cls.env.ref("stock.picking_type_in")

        cls.fake_currency = cls.res_currency.create(
            {
                "name": "Fake Currency",
                "symbol": "FC",
                "rounding": 0.02,
                "decimal_places": 2,
            }
        )
        cls.client_partner = cls.res_partner.create(
            {
                "name": "Pelo Client",
                "prefix_vat": "V",
                "vat": "27830208",
            }
        )
        cls.supplier_partner = cls.res_partner.create(
            {
                "name": "Ale Supplier",
                "prefix_vat": "V",
                "vat": "27436422",
            }
        )

    def tearDown(self):
        super().tearDown()
        base_usd = self.res_currency.browse(self.base_usd_id)
        base_vef = self.res_currency.browse(self.base_vef_id)
        company = self.env.ref("base.main_company")
        base_usd.write({"rate_ids": [Command.delete(rate.id) for rate in base_usd.rate_ids]})
        base_vef.write({"rate_ids": [Command.delete(rate.id) for rate in base_usd.rate_ids]})
        company.write({"currency_id": self.fake_currency.id, "currency_foreign_id": False})
        self.env.user.write({"groups_id": [Command.unlink(self.group_analytic_account)]})

    def create_picking(self, picking_type, partner, products, **kwargs):
        res = False
        with Form(self.stock_picking) as out:
            out.picking_type_id = picking_type
            out.partner_id = partner
            out.scheduled_date = kwargs.get("scheduled_date", fields.Date.today())
            for product in products:
                with out.move_ids_without_package.new() as move:
                    move.product_id = product
                    move.location_id = picking_type.default_location_src_id
                    move.quantity_done = randint(1, 10)
            res = out.save()

        return res

    def associate_rate_to_company(self, currency_id, foreign_currency_id, rate):
        foreign_currency = self.res_currency.browse(foreign_currency_id)
        foreign_currency.write(
            {
                "rate_ids": [
                    Command.create(
                        {
                            "name": fields.Date.today(),
                            "inverse_company_rate": rate,
                        }
                    )
                ]
            }
        )

        self.company.write(
            {
                "currency_id": currency_id,
                "currency_foreign_id": foreign_currency_id,
            }
        )

    def test_foreign_currency_taken_from_company(self):
        """
        Test case where the foreign currency must be taken
        from the company.
        """

        self.associate_rate_to_company(self.base_vef_id, self.base_usd_id, 1.0)
        picking = self.create_picking(self.out_type_id, self.client_partner, self.product_1)
        self.assertEqual(picking.foreign_currency_id, self.company.currency_foreign_id)

    def test_correlative_assignment_when_scheduled_date_is_not_in_currency_rates(self):
        """
        Test case when the scheduled date is in the future, so it must take the current rate.
        """
        rate = uniform(1.0, 30.0)
        self.associate_rate_to_company(self.base_vef_id, self.base_usd_id, rate)

        # Create a picking that the the current day rate
        picking = self.create_picking(
            self.out_type_id,
            self.client_partner,
            self.product_1,
            scheduled_date=fields.Date.today() + timedelta(days=1),
        )
        picking.action_confirm()
        foreign_rate_usd = self.currency_rate.compute_rate(self.base_usd_id, fields.Date.today())

        self.assertEqual(
            float_compare(
                picking.foreign_rate,
                foreign_rate_usd["foreign_rate"],
                precision_digits=picking.foreign_currency_id.decimal_places,
            ),
            0,
        )

    def test_correlative_assignment_when_scheduled_date_is_old(self):
        """
        Test case when the picking was created a few days ago, so it must take a rate that
        match with a date from that day.
        """

        older_rate = uniform(1.0, 30.0)
        self.associate_rate_to_company(self.base_vef_id, self.base_usd_id, uniform(1.0, 30.0))
        self.company.currency_foreign_id.write(
            {
                "rate_ids": [
                    Command.create(
                        {
                            "name": fields.Date.today() - timedelta(days=3),
                            "inverse_company_rate": older_rate,
                        }
                    ),
                ]
            }
        )

        # Create a picking that the the current day rate
        picking = self.create_picking(
            self.out_type_id,
            self.client_partner,
            self.product_1,
            scheduled_date=fields.Date.today() - timedelta(days=3),
        )
        picking.action_confirm()
        foreign_rate_usd = self.currency_rate.compute_rate(
            self.base_usd_id, fields.Date.today() - timedelta(days=3)
        )

        self.assertEqual(picking.foreign_currency_id.id, self.base_usd_id)
        self.assertEqual(
            float_compare(
                picking.foreign_rate,
                foreign_rate_usd["foreign_rate"],
                precision_digits=picking.foreign_currency_id.decimal_places,
            ),
            0,
        )

    def test_correlative_taken_from_origin_document(self):
        """
        Test case when the picking is created after a sale order is confirmed, so the picking
        must take the rate from the sale order.
        """

        self.associate_rate_to_company(self.base_vef_id, self.base_usd_id, uniform(1.0, 30.0))
        self.env["ir.config_parameter"].set_param("", True)
        product_test = self.product_product.create(
            {
                "name": "Test Product",
                "type": "product",
                "categ_id": self.env.ref("product.product_category_all").id,
                "default_code": "TEST-P-01",
                "barcode": "1234567890123",
            }
        )

        self.stock_quant._update_available_quantity(
            product_test, self.out_type_id.default_location_src_id, 100
        )

        # Create a sale order
        sale = self.sale_order
        with Form(self.sale_order) as so:
            so.partner_id = self.client_partner
            so.picking_policy = "direct"
            so.pricelist_id = self.env.ref("product.list0")
            with so.order_line.new() as line:
                line.product_id = product_test
                line.product_uom_qty = randint(3, 15)
            sale = so.save()
        sale.action_confirm()

        purchase = self.purchase_order
        with Form(self.purchase_order) as po:
            po.partner_id = self.supplier_partner
            with po.order_line.new() as line:
                line.product_id = product_test
                line.product_qty = randint(3, 15)
                line.price_unit = 10.0
            purchase = po.save()
        purchase.button_confirm()

        # Get the pickings generated from the purchase or
        # sale order
        sale_pickings = sale.picking_ids
        purchase_pickings = purchase.picking_ids

        # check if the rate is the same as the sale order
        self.assertEqual(
            float_compare(
                sale_pickings.foreign_rate,
                sale.foreign_rate,
                precision_digits=sale_pickings.foreign_currency_id.decimal_places,
            ),
            0,
        )

        # check if the rate is the same as the purchase order
        self.assertEqual(
            float_compare(
                purchase_pickings.foreign_rate,
                purchase.foreign_rate,
                precision_digits=purchase_pickings.foreign_currency_id.decimal_places,
            ),
            0,
        )

        # Generate a return from the sale order
        sale_pickings.move_line_ids.qty_done = sale_pickings.move_line_ids.reserved_uom_qty
        sale_pickings.button_validate()
        stock_return_picking = self.env["stock.return.picking"].with_context(
            active_ids=sale_pickings.ids,
            active_id=sale_pickings.ids[0],
            active_model="stock.picking",
        )
        return_wiz = Form(stock_return_picking)
        stock_return_picking = return_wiz.save()
        stock_return_picking.product_return_moves.quantity = sale_pickings.move_ids.quantity_done - 2
        res_return = stock_return_picking.create_returns()
        return_picking = self.env["stock.picking"].browse(res_return["res_id"])

        # check if the rate is the same as the picking that was returned
        self.assertEqual(
            float_compare(
                return_picking.foreign_rate,
                sale_pickings.foreign_rate,
                precision_digits=return_picking.foreign_currency_id.decimal_places,
            ),
            0,
        )

    def test_analytic_account_assignment_in_picking(self):
        """
        Test case to verify analytic account assignment in picking
        """

        # Create a picking
        # Create an analytic account
        plan_id = self.env["account.analytic.plan"].create({"name": "Test Plan"})
        analytic_account = self.env["account.analytic.account"].create(
            {
                "name": "Test Analytic Account",
                "plan_id": plan_id.id,
                "code": "TAA",
                "currency_id": self.base_usd_id,
            }
        )

        # Test case when the picking is created from the
        # form view if the analytic account does not exist
        # in the view context
        with self.assertRaises(AssertionError):
            picking = Form(self.env["stock.picking"])
            picking.picking_type_id = self.out_type_id
            picking.partner_id = self.client_partner
            picking.analytic_account_id = analytic_account

        # Add the analytic account group to the user
        self.env.user.write({"groups_id": [Command.link(self.group_analytic_account)]})
        picking2 = self.env["stock.picking"]
        with Form(self.env["stock.picking"]) as out:
            out.picking_type_id = self.out_type_id
            out.partner_id = self.client_partner
            out.analytic_account_id = analytic_account
            with out.move_ids_without_package.new() as move:
                move.product_id = self.product_1
                move.location_id = self.out_type_id.default_location_src_id
                move.quantity_done = randint(1, 10)
            picking2 = out.save()

        # Check if the analytic account is assigned to the picking
        self.assertTrue(picking2.analytic_account_id)
