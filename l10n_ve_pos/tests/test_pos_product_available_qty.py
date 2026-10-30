from unittest.mock import patch

from odoo.addons.point_of_sale.models.pos_session import PosSession
from odoo.tests import TransactionCase, tagged

# What the PoS sends when it opens with a browser cache: only the records
# modified after the cache date (here, none).
INCREMENTAL_CONTEXT = {
    "pos_last_server_date": "2999-01-01 00:00:00",
    "pos_limited_loading": True,
}


@tagged("post_install", "-at_install", "l10n_ve_pos")
class TestPosProductAvailableQty(TransactionCase):
    """TI-16064: the PoS loader sends ``qty_available`` / ``free_qty`` of the
    source location of the PoS (the stock "Cantidad en 0" checks), the
    quantity "Mostrar solamente los productos disponibles" hides products by,
    and with that setting every load brings the current stock, not only the
    products modified since the browser cache."""

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
        cls.stock_location = cls.warehouse.pos_type_id.default_location_src_id
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

    def _new_config(self):
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
        return config

    def _load_product(self):
        [data] = self.env["product.product"]._load_pos_data_read(self.product, self._new_config())
        return data

    def _load_variants_incrementally(self, **context):
        products = self.env["product.product"].with_context(**INCREMENTAL_CONTEXT, **context)
        return products._load_pos_data_search_read(
            {"product.template": [{"id": self.product.product_tmpl_id.id}]},
            self._new_config(),
        )

    def _set_on_hand(self, qty, location=None):
        self.env["stock.quant"]._update_available_quantity(
            self.product, location or self.stock_location, qty
        )

    def _new_internal_location(self, name, parent):
        return self.env["stock.location"].create(
            {"name": name, "location_id": parent.id, "usage": "internal"}
        )

    def test_quantity_of_the_pos_source_location(self):
        """The source location and its children count."""
        self._set_on_hand(2)
        self._set_on_hand(1, self._new_internal_location("Shelf", self.stock_location))
        self._set_on_hand(5, self.other_warehouse.lot_stock_id)
        data = self._load_product()
        self.assertEqual(data["qty_available"], 3)
        self.assertEqual(data["free_qty"], 3)

    def test_stock_of_other_warehouse_does_not_count(self):
        self._set_on_hand(10, self.other_warehouse.lot_stock_id)
        data = self._load_product()
        self.assertEqual(data["qty_available"], 0)
        self.assertEqual(data["free_qty"], 0)

    def test_stock_outside_the_source_location_does_not_count(self):
        """Same warehouse, but a location the PoS does not sell from: it would
        show a product "Cantidad en 0" then blocks."""
        outside = self._new_internal_location("Outside", self.warehouse.view_location_id)
        self._set_on_hand(4, outside)
        data = self._load_product()
        self.assertEqual(data["qty_available"], 0)

    def test_incremental_load_skips_products_not_modified(self):
        """Without the setting the core filter stays: a stock move does not
        change the product ``write_date``, so the PoS keeps its cache."""
        self._set_on_hand(3)
        self.assertEqual(self._load_variants_incrementally(), [])

    def test_setting_reloads_the_current_stock(self):
        self._set_on_hand(3)
        [data] = self._load_variants_incrementally(pos_reload_stock_dependent_data=True)
        self.assertEqual(data["id"], self.product.id)
        self.assertEqual(data["qty_available"], 3)

    def test_setting_only_reloads_the_product_models(self):
        context = {**INCREMENTAL_CONTEXT, "pos_reload_stock_dependent_data": True}
        for model in ("product.template", "product.product"):
            self.assertFalse(self.env[model].with_context(**context)._last_server_date_to_load())
        self.assertEqual(
            self.env["product.category"].with_context(**context)._last_server_date_to_load(),
            INCREMENTAL_CONTEXT["pos_last_server_date"],
        )

    def test_load_data_flags_the_context_by_the_setting(self):
        contexts = []

        def core_load_data(session, models_to_load):
            contexts.append(session.env.context.get("pos_reload_stock_dependent_data"))
            return {}

        with patch.object(PosSession, "load_data", core_load_data):
            for show_only_available in (False, True):
                # The virtual config caches the related setting: set it first.
                self.company.pos_show_just_products_with_available_qty = show_only_available
                session = self.env["pos.session"].new({"config_id": self._new_config()})
                session.load_data([])
        self.assertEqual(contexts, [None, True])
