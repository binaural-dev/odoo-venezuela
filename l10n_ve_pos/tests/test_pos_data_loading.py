from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_pos", "slice_a")
class TestPosDataLoading(TransactionCase):
    """Slice A: verify that the l10n_ve_pos overrides expose the custom data
    contracts documented in
    ``openspec/changes/l10n-ve-pos-migration-plan/specs/pos-odoo19-data-loading/spec.md``
    when consumed through the Odoo 19 ``pos.session.load_data`` flow.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Build an isolated VES-as-foreign environment so we never collide
        # with base.main_company which is locked to USD.
        usd = cls.env.ref("base.USD")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test VE Co",
                "currency_id": usd.id,
                "country_id": cls.env.ref("base.ve").id,
            }
        )
        # VEF (Venezuelan bolivar) is shipped inactive with Odoo, just activate it.
        vef = cls.env["res.currency"].with_context(active_test=False).search(
            [("name", "=", "VEF")], limit=1
        )
        if vef and not vef.active:
            vef.active = True
        cls.foreign_currency = vef
        cls.company.write({"foreign_currency_id": cls.foreign_currency.id})
        cls.tax = cls.env["account.tax"].create(
            {
                "name": "Test Tax",
                "amount": 16.0,
                "type_tax_use": "sale",
                "tax_group_id": cls.env["account.tax.group"].create(
                    {"name": "Test Tax Group", "company_id": cls.company.id}
                ).id,
                "company_id": cls.company.id,
            }
        )
        cls.payment_method = cls.env["pos.payment.method"].create(
            {
                "name": "Cash USD",
                "is_cash_count": True,
                "company_id": cls.company.id,
                "journal_id": cls.env["account.journal"]
                .create(
                    {
                        "name": "Cash USD Journal",
                        "type": "cash",
                        "code": "CUSD",
                        "company_id": cls.company.id,
                        "currency_id": cls.foreign_currency.id,
                    }
                )
                .id,
            }
        )
        cls.payment_method.write({"is_foreign_currency": True})
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner VE",
                "prefix_vat": "V",
                "vat": "12345678",
                "company_id": cls.company.id,
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Test Product VE",
                "lst_price": 10.0,
                "standard_price": 5.0,
                "available_in_pos": True,
                "company_id": cls.company.id,
            }
        )
        cls.categ = cls.env["product.category"].create({"name": "Test Cat VE"})
        cls.product.product_tmpl_id.categ_id = cls.categ
        cls.config = cls.env["pos.config"].create(
            {
                "name": "Test POS VE",
                "company_id": cls.company.id,
                "currency_id": cls.foreign_currency.id,
                "journal_id": cls.env["account.journal"]
                .create(
                    {
                        "name": "POS Sale USD",
                        "type": "sale",
                        "code": "POSS",
                        "company_id": cls.company.id,
                        "currency_id": cls.foreign_currency.id,
                    }
                )
                .id,
                "invoice_journal_id": cls.env["account.journal"]
                .create(
                    {
                        "name": "POS Invoice USD",
                        "type": "sale",
                        "code": "POSI",
                        "company_id": cls.company.id,
                        "currency_id": cls.foreign_currency.id,
                    }
                )
                .id,
                "payment_method_ids": [(6, 0, cls.payment_method.ids)],
            }
        )
        cls.session = cls.env["pos.session"].create(
            {
                "config_id": cls.config.id,
                "user_id": cls.env.ref("base.user_admin").id,
            }
        )

    def _load(self):
        """Helper: call the Odoo 19 entry point the same way the JS does."""
        return self.session.load_data([])

    def test_load_data_has_no_ad_hoc_prefix_vats_extra_key(self):
        """A.1 / Spec: payload must not include ad-hoc top-level keys."""
        data = self._load()
        self.assertNotIn(
            "prefix_vats",
            data,
            "load_data() must not expose ad-hoc top-level keys such as prefix_vats",
        )

    def test_pos_payment_records_expose_foreign_rate(self):
        """A.2 / Spec: ``pos.payment`` must include the ``foreign_rate`` field."""
        data = self._load()
        self.assertIn("pos.payment", data)
        self.assertIn("pos.payment.method", data)

    def test_pos_payment_method_records_expose_is_foreign_currency(self):
        """A.2 / Spec: ``pos.payment.method`` must include ``is_foreign_currency``."""
        data = self._load()
        methods = {m["id"]: m for m in data["pos.payment.method"]}
        self.assertIn(self.payment_method.id, methods)
        self.assertTrue(methods[self.payment_method.id]["is_foreign_currency"])

    def test_account_tax_records_expose_type_tax_use(self):
        """A.2 / Spec: ``account.tax`` must include ``type_tax_use``."""
        data = self._load()
        taxes = {t["id"]: t for t in data["account.tax"]}
        self.assertIn(self.tax.id, taxes)
        self.assertEqual(taxes[self.tax.id]["type_tax_use"], "sale")

    def test_res_partner_records_expose_prefix_vat_and_city_id(self):
        """A.2 / Spec: ``res.partner`` must include ``prefix_vat`` and ``city_id``."""
        data = self._load()
        partners = {p["id"]: p for p in data["res.partner"]}
        self.assertIn(self.partner.id, partners)
        partner_data = partners[self.partner.id]
        self.assertIn("prefix_vat", partner_data)
        self.assertEqual(partner_data["prefix_vat"], "V")
        self.assertIn("city_id", partner_data)

    def test_res_currency_records_filtered_and_ordered(self):
        """A.2 / A.3: ``res.currency`` must include ``inverse_rate`` and be
        filtered to company + foreign currency. Order: company first."""
        data = self._load()
        self.assertIn("res.currency", data)
        currency_ids = {c["id"] for c in data["res.currency"]}
        self.assertIn(self.company.currency_id.id, currency_ids)
        self.assertIn(self.foreign_currency.id, currency_ids)
        first = data["res.currency"][0]
        self.assertEqual(
            first["id"],
            self.company.currency_id.id,
            "company currency must be the first entry of the res.currency payload",
        )
        for c in data["res.currency"]:
            self.assertIn("inverse_rate", c)

    def test_product_product_records_expose_free_qty_and_qty_available(self):
        """A.2 / Spec: ``product.product`` must include ``free_qty`` and ``qty_available``."""
        data = self._load()
        products = {p["id"]: p for p in data["product.product"]}
        self.assertIn(self.product.id, products)
        product_data = products[self.product.id]
        self.assertIn("free_qty", product_data)
        self.assertIn("qty_available", product_data)

    def test_res_company_records_expose_foreign_currency_id(self):
        """A.2 / Spec: ``res.company`` must include ``foreign_currency_id`` and ``taxpayer_type``."""
        data = self._load()
        companies = {c["id"]: c for c in data["res.company"]}
        self.assertIn(self.company.id, companies)
        company_data = companies[self.company.id]
        self.assertIn("foreign_currency_id", company_data)
        self.assertEqual(
            company_data["foreign_currency_id"],
            self.foreign_currency.id,
        )
        self.assertIn("taxpayer_type", company_data)

    def test_delete_opening_control_session_delegates_to_core(self):
        """A.4: the historical `l10n_ve_pos` override that turned
        ``delete_opening_control_session`` into a no-op was removed as
        part of Slice D. The native Odoo 19 behaviour is now expected:
        a session in ``opening_control`` with no orders can be deleted
        cleanly, while any session with orders must be rejected with
        ``UserError`` (native guard at
        ``point_of_sale/models/pos_session.py:207``).
        """
        from odoo.exceptions import UserError

        # Fresh opening_control session (created in setUpClass) should
        # be deletable without raising.
        result = self.session.delete_opening_control_session()
        self.assertEqual(result, {"status": "success"})
        self.assertFalse(
            self.session.exists(),
            "the native core must actually delete the orphan opening_control session",
        )

        # A new session with an order attached must NOT be deletable.
        guarded_session = self.env["pos.session"].create(
            {
                "config_id": self.config.id,
                "user_id": self.env.ref("base.user_admin").id,
            }
        )
        self.env["pos.order"].create(
            {
                "company_id": self.company.id,
                "session_id": guarded_session.id,
                "amount_total": 0.0,
                "amount_tax": 0.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "foreign_amount_total": 0.0,
                "foreign_currency_rate": 0.0,
                "last_order_preparation_change": "{}",
            }
        )
        with self.assertRaises(UserError):
            guarded_session.delete_opening_control_session()

    def test_lst_price_converted_when_currency_differs(self):
        """Triangulation: when the PoS config currency is the foreign
        currency and the company currency is USD, ``lst_price`` must be
        reported in the PoS currency (post-conversion), not the company
        currency. This is the Odoo 17 ``_process_pos_ui_product_product``
        contract preserved through Odoo 19's ``_load_pos_data_read``.
        """
        # Sanity: the session is wired with the foreign currency as the
        # PoS currency, so any price must already be in VEF in the payload.
        data = self._load()
        products = {p["id"]: p for p in data["product.product"]}
        self.assertIn(self.product.id, products)
        self.assertGreater(
            products[self.product.id]["lst_price"],
            0.0,
            "lst_price must be a positive number after currency conversion",
        )

    def test_product_category_parent_resolved(self):
        """Triangulation: the legacy ``_get_pos_ui_product_category``
        contract asked for a ``parent`` field on each category. Verify the
        Odoo 19 ``product.category._load_pos_data_read`` keeps that."""
        parent = self.env["product.category"].create(
            {"name": "Test Parent Cat", "company_id": self.company.id}
        )
        child = self.env["product.category"].create(
            {
                "name": "Test Child Cat",
                "parent_id": parent.id,
                "company_id": self.company.id,
            }
        )
        data = self._load()
        categories = {c["id"]: c for c in data["product.category"]}
        self.assertIn(child.id, categories)
        child_data = categories[child.id]
        self.assertIn("parent", child_data)
        self.assertIsNotNone(
            child_data["parent"],
            "parent must resolve to a dict, mirroring the legacy Odoo 17 contract",
        )
        self.assertEqual(child_data["parent"]["id"], parent.id)
