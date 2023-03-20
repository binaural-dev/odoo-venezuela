from random import randint
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
        cls.model_data = cls.env["ir.model.data"]
        cls.res_currency = cls.env["res.currency"]
        cls.res_partner = cls.env["res.partner"]
        cls.stock_quant = cls.env["stock.quant"]
        # Origin Documents
        cls.sale_order = cls.env["sale.order"]
        cls.purchase_order = cls.env["purchase.order"]
        cls.stock_picking = cls.env["stock.picking"]

        # Currency ids
        cls.base_vef_id = cls.model_data._xmlid_to_res_id("base.VEF", raise_if_not_found=False)
        cls.base_usd_id = cls.model_data._xmlid_to_res_id("base.USD", raise_if_not_found=False)
        # Needed Groups
        group_stock_multi_locations = cls.model_data._xmlid_to_res_id(
            "stock.group_stock_multi_locations", raise_if_not_found=False
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

    def create_picking(self, picking_type, partner, products):
        picking = self.env["stock.picking"].with_context(default_picking_type_id=picking_type.id)
        picking = picking.create(
            {
                "partner_id": partner.id,
                "move_ids": [
                    Command.create(
                        {
                            "location_id": picking_type.default_location_src_id.id,
                            "location_dest_id": picking_type.default_location_dest_id.id,
                            "product_id": product.id,
                            "quantity_done": randint(1, 10),
                        }
                    )
                    for product in products
                ],
            }
        )

        return picking

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

    def test_correlative_assignment_in_vef_when_scheduled_date_is_not_in_currency_rates(self):
        """
        Test case when the main currency is VES and the foreign currency is USD,
        and the scheduled date is in the future, so it must take the current rate
        and the foreign currency.
        """
        currency_rate = self.env["res.currency.rate"]
        rate = 24.38
        self.associate_rate_to_company(self.base_vef_id, self.base_usd_id, rate)

        # Create a picking that the the current day rate
        picking = False
        with Form(self.stock_picking) as out:
            out.picking_type_id = self.out_type_id
            out.partner_id = self.client_partner
            out.scheduled_date = fields.Date.today() + timedelta(days=1)
            with out.move_ids_without_package.new() as move:
                move.product_id = self.product_1
                move.location_id = self.out_type_id.default_location_src_id
                move.quantity_done = randint(1, 10)
            picking = out.save()
        picking.action_confirm()

        foreign_rate_usd = currency_rate.compute_rate(self.base_usd_id, fields.Date.today())
        self.assertEqual(picking.foreign_currency_id.id, self.base_usd_id)
        self.assertEqual(
            float_compare(
                picking.foreign_rate,
                foreign_rate_usd["foreign_rate"],
                precision_digits=picking.foreign_currency_id.decimal_places,
            ),
            0,
            "The foreign rate must take the current rate",
        )
