"""TI-16064: "Mostrar solamente los productos disponibles"
(``pos_show_just_products_with_available_qty``) en el Kiosko.

El Kiosko no carga los productos almacenables sin stock a mano en la ubicación
de origen de la caja; sin esos productos no salen en la cuadrícula, el
buscador ni el escaneo. Los que llegan como opción de un combo vienen con
``self_order_available = False``.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_pos_self_order")
class TestKioskProductAvailableQty(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create(
            {
                "name": "Kiosk Available Qty Co",
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
            {"name": "Kiosk Tax Group", "company_id": cls.company.id}
        )
        cls.tax = cls.env["account.tax"].create(
            {
                "name": "Kiosk Tax",
                "amount": 16.0,
                "type_tax_use": "sale",
                "tax_group_id": tax_group.id,
                "company_id": cls.company.id,
            }
        )
        # Una compañía nueva no siempre trae almacén aquí: se crea para que
        # exista el tipo de operación del PdV.
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        ) or cls.env["stock.warehouse"].create(
            {"name": "Kiosk WH", "code": "KWH", "company_id": cls.company.id}
        )
        cls.stock_location = cls.warehouse.pos_type_id.default_location_src_id
        cls.other_warehouse = cls.env["stock.warehouse"].create(
            {"name": "Other Kiosk WH", "code": "OKWH", "company_id": cls.company.id}
        )
        cls.storable = cls._new_template("Lampara", is_storable=True)
        cls.service = cls._new_template("Instalación", type="service")
        cls.consumable = cls._new_template("Bolsa", is_storable=False)
        cls.templates = cls.storable | cls.service | cls.consumable

    @classmethod
    def _new_template(cls, name, **values):
        # l10n_ve_accountant exige un impuesto de venta y uno de compra.
        return cls.env["product.template"].create(
            {
                "name": name,
                "type": "consu",
                "available_in_pos": True,
                "company_id": cls.company.id,
                "taxes_id": [(6, 0, cls.tax.ids)],
                "supplier_taxes_id": [(6, 0, cls.tax.ids)],
                **values,
            }
        )

    def _new_combo_with(self, option):
        """Combo disponible en el PdV con ``option`` como única opción. Sin
        stock, la opción queda fuera del dominio de carga y el core la agrega
        por id como opción del combo."""
        combo = self.env["product.combo"].create(
            {
                "name": "Menu",
                "company_id": self.company.id,
                "combo_item_ids": [(0, 0, {"product_id": option.product_variant_id.id})],
            }
        )
        menu = self._new_template("Menu", type="combo", combo_ids=[(6, 0, combo.ids)])
        self.templates |= menu
        return menu

    def _set_setting(self, show_only_available):
        self.company.pos_show_just_products_with_available_qty = show_only_available

    def _load(self, show_only_available=True):
        """Plantillas (por id) y variantes de este test que carga el Kiosko."""
        # La caja virtual guarda el ajuste relacionado al crearse: va antes.
        self._set_setting(show_only_available)
        config = self.env["pos.config"].new(
            {
                "company_id": self.company.id,
                "picking_type_id": self.warehouse.pos_type_id.id,
                "self_ordering_mode": "kiosk",
            }
        )
        data = {}
        for model in ("product.template", "product.product"):
            data[model] = self.env[model]._load_pos_self_data_search_read(data, config)
        variants = self.templates.product_variant_ids
        return (
            {t["id"]: t for t in data["product.template"] if t["id"] in self.templates.ids},
            variants.browse(p["id"] for p in data["product.product"]) & variants,
        )

    def _set_on_hand(self, template, qty, location=None):
        self.env["stock.quant"]._update_available_quantity(
            template.product_variant_ids[:1], location or self.stock_location, qty
        )

    def test_storable_without_stock_is_not_loaded(self):
        templates, variants = self._load()
        self.assertNotIn(self.storable.id, templates)
        self.assertNotIn(self.storable.product_variant_id, variants)

    def test_non_storable_products_are_loaded_without_stock(self):
        templates, variants = self._load()
        self.assertEqual(set(templates), set((self.service | self.consumable).ids))
        self.assertEqual(variants, (self.service | self.consumable).product_variant_ids)

    def test_stock_in_the_source_location_loads_it(self):
        shelf = self.env["stock.location"].create(
            {"name": "Shelf", "location_id": self.stock_location.id, "usage": "internal"}
        )
        self._set_on_hand(self.storable, 0.5, shelf)
        templates, variants = self._load()
        self.assertTrue(templates[self.storable.id]["self_order_available"])
        self.assertIn(self.storable.product_variant_id, variants)

    def test_stock_of_other_warehouse_does_not_count(self):
        self._set_on_hand(self.storable, 10, self.other_warehouse.lot_stock_id)
        templates, _variants = self._load()
        self.assertNotIn(self.storable.id, templates)

    def test_negative_stock_is_not_loaded(self):
        self._set_on_hand(self.storable, -3)
        templates, _variants = self._load()
        self.assertNotIn(self.storable.id, templates)

    def test_one_variant_with_stock_loads_every_variant(self):
        attribute = self.env["product.attribute"].create(
            {"name": "Color", "value_ids": [(0, 0, {"name": "Rojo"}), (0, 0, {"name": "Azul"})]}
        )
        self.storable.attribute_line_ids = [
            (0, 0, {"attribute_id": attribute.id, "value_ids": [(6, 0, attribute.value_ids.ids)]})
        ]
        self.assertEqual(len(self.storable.product_variant_ids), 2)
        self._set_on_hand(self.storable, 1)
        templates, variants = self._load()
        self.assertIn(self.storable.id, templates)
        self.assertEqual(variants & self.storable.product_variant_ids, self.storable.product_variant_ids)

    def test_setting_off_loads_storable_without_stock(self):
        templates, _variants = self._load(show_only_available=False)
        self.assertEqual(set(templates), set(self.templates.ids))
        self.assertTrue(templates[self.storable.id]["self_order_available"])

    def test_combo_option_without_stock_is_not_available(self):
        """El core carga las opciones de combo por id: la almacenable sin stock
        llega, pero el Kiosko no la ofrece."""
        menu = self._new_combo_with(self.storable)
        templates, variants = self._load()
        self.assertFalse(templates[self.storable.id]["self_order_available"])
        self.assertIn(self.storable.product_variant_id, variants)
        self.assertTrue(templates[menu.id]["self_order_available"])
        self.assertTrue(templates[self.service.id]["self_order_available"])

    def test_combo_option_with_stock_stays_available(self):
        self._new_combo_with(self.storable)
        self._set_on_hand(self.storable, 2)
        templates, _variants = self._load()
        self.assertTrue(templates[self.storable.id]["self_order_available"])

    def test_combo_option_without_stock_with_the_setting_off(self):
        self._new_combo_with(self.storable)
        templates, _variants = self._load(show_only_available=False)
        self.assertTrue(templates[self.storable.id]["self_order_available"])

    def test_public_route_load(self):
        """La carga real (``load_self_data``) con el privilegio reducido de la
        ruta pública (``_verify_pos_config`` del core). ``load_self_data``
        devuelve ``[]`` en silencio ante un AccessError: el Kiosko no queda
        vacío, saca el almacenable sin stock y recibe el ajuste."""
        self._set_setting(True)
        # El usuario por defecto del Kiosko pertenece a la compañía de la caja.
        admin = self.env.ref("base.user_admin")
        admin.company_ids |= self.company
        journal = self.env["account.journal"].create(
            {
                "name": "Kiosk Available Qty Sales",
                "type": "sale",
                "code": "KAQS",
                "company_id": self.company.id,
            }
        )
        config = self.env["pos.config"].create(
            {
                "name": "Kiosk Available Qty",
                "company_id": self.company.id,
                "journal_id": journal.id,
                "invoice_journal_id": journal.id,
                "picking_type_id": self.warehouse.pos_type_id.id,
                "self_ordering_mode": "kiosk",
                "self_ordering_default_user_id": admin.id,
                "payment_method_ids": [(6, 0, [])],
            }
        )
        data = (
            config.sudo(False)
            .with_company(self.company)
            .with_user(admin)
            .with_context(allowed_company_ids=self.company.ids)
            .load_self_data()
        )
        loaded = {t["id"] for t in data["product.template"]}
        self.assertTrue(data["pos.config"][0]["pos_show_just_products_with_available_qty"])
        self.assertTrue({self.service.id, self.consumable.id} <= loaded)
        self.assertNotIn(self.storable.id, loaded)
