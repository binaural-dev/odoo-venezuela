from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_pos")
class TestPosConfigStockAvailability(TransactionCase):
    """TI-15722: ``pos.config.check_stock_availability`` ("Cantidad en 0")
    compares the order against the stock on hand of the PoS source location;
    what other confirmed orders reserved does not block."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test VE Stock Co",
                "currency_id": cls.env.ref("base.USD").id,
                "country_id": cls.env.ref("base.ve").id,
            }
        )
        vef = cls.env["res.currency"].with_context(active_test=False).search(
            [("name", "=", "VEF")], limit=1
        )
        vef.active = True
        cls.company.foreign_currency_id = vef
        cls.env = cls.env(
            context=dict(cls.env.context, allowed_company_ids=cls.company.ids)
        )
        tax_group = cls.env["account.tax.group"].create(
            {"name": "Test Tax Group", "company_id": cls.company.id}
        )
        tax = cls.env["account.tax"].create(
            {
                "name": "Test Tax",
                "amount": 16.0,
                "type_tax_use": "sale",
                "tax_group_id": tax_group.id,
                "company_id": cls.company.id,
            }
        )
        # A new company does not always get a warehouse here: create it so the
        # PoS operation type (and its source location) exists.
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        ) or cls.env["stock.warehouse"].create(
            {"name": "VE WH", "code": "VEWH", "company_id": cls.company.id}
        )
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.partner = cls.env["res.partner"].create({"name": "Test Partner"})

        def create_product(name, **vals):
            # l10n_ve_accountant requires exactly one sale and one purchase tax.
            return cls.env["product.product"].create(
                {
                    "name": name,
                    "company_id": cls.company.id,
                    "taxes_id": [(6, 0, tax.ids)],
                    "supplier_taxes_id": [(6, 0, tax.ids)],
                    **vals,
                }
            )

        cls.product = create_product("Lampara", type="consu", is_storable=True)
        cls.consumable = create_product("Bolsa", type="consu", is_storable=False)
        cls.service = create_product("Servicio", type="service")

    def _check(self, qty_by_product, amount_to_zero=True):
        # A virtual record is enough (no journals/payment methods needed). It
        # is built right before the call: its values only live in the cache,
        # which creating other records may invalidate.
        config = self.env["pos.config"].new(
            {
                "amount_to_zero": amount_to_zero,
                "company_id": self.company.id,
                "picking_type_id": self.warehouse.pos_type_id.id,
            }
        )
        self.assertTrue(config.picking_type_id.default_location_src_id)
        return config.check_stock_availability(qty_by_product)

    def _set_on_hand(self, product, qty, location=None):
        self.env["stock.quant"]._update_available_quantity(
            product, location or self.stock_location, qty
        )

    def _reserve_in_other_order(self, product, qty):
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.warehouse.out_type_id.id,
                "location_id": self.stock_location.id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
                "partner_id": self.partner.id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": qty,
                            "location_id": self.stock_location.id,
                            "location_dest_id": self.env.ref(
                                "stock.stock_location_customers"
                            ).id,
                        },
                    )
                ],
            }
        )
        picking.action_confirm()
        picking.action_assign()
        return picking

    def test_enough_on_hand(self):
        self._set_on_hand(self.product, 8)
        self.assertEqual(self._check({self.product.id: 7}), [])

    def test_not_enough_on_hand(self):
        self._set_on_hand(self.product, 1)
        shortages = self._check({str(self.product.id): 7})
        self.assertEqual(len(shortages), 1)
        self.assertEqual(shortages[0]["name"], self.product.display_name)
        self.assertEqual(shortages[0]["requested"], 7)
        self.assertEqual(shortages[0]["available"], 1)

    def test_reserved_by_other_order_does_not_block(self):
        """8 on hand, 7 reserved by a confirmed delivery: the PoS order being
        sold has priority, so selling 7 is allowed."""
        self._set_on_hand(self.product, 8)
        picking = self._reserve_in_other_order(self.product, 7)
        self.assertEqual(picking.state, "assigned")
        self.assertEqual(self._check({self.product.id: 7}), [])

    def test_stock_of_other_warehouse_does_not_count(self):
        other_warehouse = self.env["stock.warehouse"].create(
            {"name": "Other WH", "code": "OWH", "company_id": self.company.id}
        )
        self._set_on_hand(self.product, 10, other_warehouse.lot_stock_id)
        shortages = self._check({self.product.id: 1})
        self.assertEqual([s["available"] for s in shortages], [0])

    def test_non_storable_products_are_ignored(self):
        self.assertEqual(
            self._check(
                {self.consumable.id: 5, self.service.id: 5}
            ),
            [],
        )

    def test_without_source_location(self):
        self._set_on_hand(self.product, 1)
        config = self.env["pos.config"].new(
            {"amount_to_zero": True, "company_id": self.company.id, "picking_type_id": False}
        )
        self.assertFalse(config.picking_type_id.default_location_src_id)
        self.assertEqual(config.check_stock_availability({self.product.id: 7}), [])

    def test_disabled(self):
        self.assertEqual(self._check({self.product.id: 7}, amount_to_zero=False), [])
