from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_pos")
class TestPosProductAvailableQty(TransactionCase):
    """TI-16064: the PoS loader sends ``qty_available`` / ``free_qty`` of the
    PoS warehouse, the quantity "Mostrar solamente los productos disponibles"
    hides products by."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test VE Loader Co",
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
        # PoS operation type exists.
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        ) or cls.env["stock.warehouse"].create(
            {"name": "VE WH", "code": "VEWH", "company_id": cls.company.id}
        )
        cls.other_warehouse = cls.env["stock.warehouse"].create(
            {"name": "Other WH", "code": "OWH", "company_id": cls.company.id}
        )
        # l10n_ve_accountant requires exactly one sale and one purchase tax.
        cls.product = cls.env["product.product"].create(
            {
                "name": "Lampara",
                "type": "consu",
                "is_storable": True,
                "company_id": cls.company.id,
                "taxes_id": [(6, 0, tax.ids)],
                "supplier_taxes_id": [(6, 0, tax.ids)],
            }
        )

    def _load_product(self):
        # A virtual record is enough (no journals/payment methods needed). It
        # is built right before the call: its values only live in the cache,
        # which creating other records may invalidate.
        config = self.env["pos.config"].new(
            {
                "company_id": self.company.id,
                "picking_type_id": self.warehouse.pos_type_id.id,
            }
        )
        self.assertEqual(config.picking_type_id.warehouse_id, self.warehouse)
        [data] = self.env["product.product"]._load_pos_data_read(self.product, config)
        return data

    def _set_on_hand(self, qty, warehouse):
        self.env["stock.quant"]._update_available_quantity(
            self.product, warehouse.lot_stock_id, qty
        )

    def test_quantity_of_the_pos_warehouse(self):
        self._set_on_hand(2, self.warehouse)
        self._set_on_hand(5, self.other_warehouse)
        data = self._load_product()
        self.assertEqual(data["qty_available"], 2)
        self.assertEqual(data["free_qty"], 2)

    def test_stock_of_other_warehouse_does_not_count(self):
        self._set_on_hand(10, self.other_warehouse)
        data = self._load_product()
        self.assertEqual(data["qty_available"], 0)
        self.assertEqual(data["free_qty"], 0)
