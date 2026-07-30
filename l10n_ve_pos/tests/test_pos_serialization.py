"""Slice B: Order/Payment Serialization TDD tests.

Verifies that ``l10n_ve_pos`` exposes the Venezuelan foreign-currency
serialization contract documented in
``openspec/changes/l10n-ve-pos-migration-plan/specs/pos-odoo19-serialization/spec.md``
through the Odoo 19 read-back flow (``_load_pos_data_fields`` +
``_load_pos_data_read``), without relying on the Odoo 17 ``_order_fields`` /
``_payment_fields`` / ``_export_for_ui`` hooks (removed upstream).
"""

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_pos", "slice_b")
class TestPosSerialization(TransactionCase):
    """Spec: ``pos-odoo19-serialization/spec.md``.

    Fail-fast rule (user preference): if any legacy serialization hook is
    still present and would crash on super call against Odoo 19, the test
    raises an explicit ``AttributeError`` so the failure is not masked.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # --- Reuse the same isolated VES-as-foreign environment as Slice A ---
        usd = cls.env.ref("base.USD")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test VE Slice B Co",
                "currency_id": usd.id,
                "country_id": cls.env.ref("base.ve").id,
            }
        )
        vef = cls.env["res.currency"].with_context(active_test=False).search(
            [("name", "=", "VEF")], limit=1
        )
        if vef and not vef.active:
            vef.active = True
        cls.foreign_currency = vef
        cls.company.write({"foreign_currency_id": cls.foreign_currency.id})

        # --- Minimal chart of accounts so the session can open ---
        # (Odoo 19 blocks open_ui on a company without a chart.)
        Account = cls.env["account.account"]
        company_id = cls.company.id
        cls.account_receivable = Account.create(
            {
                "name": "Slice B Receivable",
                "code": "120000SB",
                "account_type": "asset_receivable",
                "company_ids": [(6, 0, [company_id])],
                "reconcile": True,
            }
        )
        cls.account_income = Account.create(
            {
                "name": "Slice B Income",
                "code": "400000SB",
                "account_type": "income",
                "company_ids": [(6, 0, [company_id])],
            }
        )
        cls.account_cash = Account.create(
            {
                "name": "Slice B Cash",
                "code": "100000SB",
                "account_type": "asset_cash",
                "company_ids": [(6, 0, [company_id])],
            }
        )

        # --- Payment method (must be cash so the Odoo 19 paid-state path works) ---
        cls.cash_journal = cls.env["account.journal"].create(
            {
                "name": "Slice B Cash Journal",
                "type": "cash",
                "code": "CSBB",
                "company_id": cls.company.id,
                "currency_id": cls.foreign_currency.id,
                "default_account_id": cls.account_cash.id,
            }
        )
        cls.payment_method = cls.env["pos.payment.method"].create(
            {
                "name": "Slice B Cash",
                "is_cash_count": True,
                "company_id": cls.company.id,
                "journal_id": cls.cash_journal.id,
            }
        )
        cls.payment_method.write({"is_foreign_currency": True})

        # --- Product + tax ---
        cls.tax = cls.env["account.tax"].create(
            {
                "name": "Slice B Tax",
                "amount": 16.0,
                "type_tax_use": "sale",
                "tax_group_id": cls.env["account.tax.group"]
                .create(
                    {"name": "Slice B Tax Group", "company_id": cls.company.id}
                )
                .id,
                "company_id": cls.company.id,
            }
        )
        cls.product_category = cls.env["product.category"].create(
            {
                "name": "Slice B Category",
                "property_account_income_categ_id": cls.account_income.id,
                "property_account_expense_categ_id": cls.account_income.id,
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Slice B Product",
                "lst_price": 100.0,
                "standard_price": 50.0,
                "available_in_pos": True,
                "company_id": cls.company.id,
                "categ_id": cls.product_category.id,
                "taxes_id": [(6, 0, cls.tax.ids)],
            }
        )
        # `property_account_income_id` is company_dependent. Set it FOR the
        # test company so the order's tax computation can resolve the
        # income account.
        cls.product.with_company(cls.company).write(
            {"property_account_income_id": cls.account_income.id}
        )

        # --- POS config (in foreign currency so the order is multi-currency) ---
        cls.sale_journal = cls.env["account.journal"].create(
            {
                "name": "Slice B Sale Journal",
                "type": "sale",
                "code": "SBB",
                "company_id": cls.company.id,
                "currency_id": cls.foreign_currency.id,
            }
        )
        cls.invoice_journal = cls.env["account.journal"].create(
            {
                "name": "Slice B Invoice Journal",
                "type": "sale",
                "code": "IBB",
                "company_id": cls.company.id,
                "currency_id": cls.foreign_currency.id,
            }
        )
        cls.config = cls.env["pos.config"].create(
            {
                "name": "Slice B Config",
                "company_id": cls.company.id,
                "currency_id": cls.foreign_currency.id,
                "journal_id": cls.sale_journal.id,
                "invoice_journal_id": cls.invoice_journal.id,
                "payment_method_ids": [(6, 0, cls.payment_method.ids)],
            }
        )

    # ------------------------------------------------------------------
    # B.1 — pos.order._load_pos_data_read injects the Venezuelan
    #       foreign-currency values (foreign_amount_total,
    #       foreign_currency_rate) on top of whatever core returns.
    # ------------------------------------------------------------------
    def test_pos_order_load_pos_data_read_injects_foreign_total_and_rate(self):
        """B.1 / Spec: ``pos.order._load_pos_data_read`` MUST inject
        ``foreign_amount_total`` and ``foreign_currency_rate`` into every
        returned record.

        We override ``_load_pos_data_read`` instead of
        ``_load_pos_data_fields`` on purpose: the field contract belongs
        to core Odoo 19 and we do not want to enumerate its fields here.
        Our only job is to add the Venezuelan values to the payload the
        frontend gets back.
        """
        session = self.env["pos.session"].create(
            {
                "config_id": self.config.id,
                "user_id": self.env.ref("base.user_admin").id,
            }
        )
        order = self.env["pos.order"].create(
            {
                "company_id": self.company.id,
                "session_id": session.id,
                "partner_id": False,
                "pricelist_id": (
                    self.company.partner_id.property_product_pricelist.id
                ),
                "foreign_amount_total": 4234.0,
                "foreign_currency_rate": 36.5,
                "amount_total": 116.0,
                "amount_tax": 16.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "last_order_preparation_change": "{}",
            }
        )
        read_records = self.env["pos.order"]._load_pos_data_read(order, self.config)
        self.assertEqual(len(read_records), 1)
        payload = read_records[0]
        self.assertIn("foreign_amount_total", payload)
        self.assertEqual(payload["foreign_amount_total"], 4234.0)
        self.assertIn("foreign_currency_rate", payload)
        self.assertEqual(payload["foreign_currency_rate"], 36.5)

    # ------------------------------------------------------------------
    # End-to-end sync contract — exercises the real Odoo 19 flow instead
    # of guessing which fields need to be exposed. If a core change ever
    # requires a new field in the ``_load_pos_data_fields`` contract,
    # this test fails loudly instead of the frontend crashing in
    # production. See OpenSpec HB.8 for the rationale (implement only the
    # Venezuelan extension, delegate everything else to core Odoo 19 +
    # keep this regression test as the safety net).
    # ------------------------------------------------------------------
    def test_pos_order_sync_round_trip_survives_second_sync(self):
        """Simulate the real Odoo 19 POS sync: first ``sync_from_ui`` creates
        the draft order, the frontend reads it back, and a second
        ``sync_from_ui`` (as if the cashier added a payment) must NOT
        crash inside ``_process_order`` (which does
        ``del order['uuid']`` and ``del order['access_token']``).

        Rationale: our override does not need to enumerate every field
        Odoo 19 expects. Instead this test drives the actual flow so any
        missing field surfaces here.
        """
        session = self.env["pos.session"].create(
            {
                "config_id": self.config.id,
                "user_id": self.env.ref("base.user_admin").id,
            }
        )

        order_uuid = "e2e-sync-uuid-0001"
        access_token = "e2e-sync-access-token-0001"

        def _order_payload(payment_ids):
            return {
                "id": False,
                "name": "Order/E2E/0001",
                "uuid": order_uuid,
                "access_token": access_token,
                "session_id": session.id,
                "company_id": self.company.id,
                "config_id": self.config.id,
                "currency_id": self.foreign_currency.id,
                "pricelist_id": (
                    self.company.partner_id.property_product_pricelist.id
                ),
                "partner_id": False,
                "date_order": False,
                "state": "draft",
                "amount_total": 116.0,
                "amount_tax": 16.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "foreign_amount_total": 4234.0,
                "foreign_currency_rate": 36.5,
                "lines": [
                    [0, 0, {
                        "name": "OL/E2E/0001",
                        "uuid": "e2e-sync-line-0001",
                        "product_id": self.product.id,
                        "price_unit": 100.0,
                        "discount": 0.0,
                        "qty": 1.0,
                        "price_subtotal": 100.0,
                        "price_subtotal_incl": 116.0,
                        "tax_ids": [(6, 0, self.tax.ids)],
                        "foreign_price": 3650.0,
                        "foreign_subtotal": 3650.0,
                        "foreign_total": 4234.0,
                    }],
                ],
                "payment_ids": payment_ids,
                "last_order_preparation_change": "{}",
            }

        # First sync: create the draft order.
        first_payload = _order_payload(payment_ids=[])
        first_result = self.env["pos.order"].sync_from_ui([first_payload])
        self.assertIn("pos.order", first_result)
        self.assertEqual(
            len(first_result["pos.order"]),
            1,
            "first sync must return exactly one pos.order",
        )

        # Simulate what the frontend does when it wants to add a payment:
        # it takes the reloaded payload, appends a payment, and calls
        # ``sync_from_ui`` again with the same uuid/access_token.
        second_payload = _order_payload(
            payment_ids=[
                [0, 0, {
                    "name": "Payment 1",
                    "uuid": "e2e-sync-payment-0001",
                    "amount": 116.0,
                    "payment_method_id": self.payment_method.id,
                    "payment_date": fields.Datetime.now(),
                    "foreign_rate": 36.5,
                    "foreign_amount": 4234.0,
                }],
            ],
        )
        # Regression: previously this crashed with
        # ``KeyError: 'access_token'`` because our load contract did not
        # expose it. Now we delegate to super() and drive the whole flow
        # to detect any similar core-required field.
        second_result = self.env["pos.order"].sync_from_ui([second_payload])
        self.assertIn("pos.order", second_result)
        self.assertEqual(
            len(second_result["pos.order"]),
            1,
            "second sync must return the same order updated in place",
        )
        stored_order = self.env["pos.order"].search(
            [("uuid", "=", order_uuid)], limit=1
        )
        self.assertTrue(stored_order, "the order must exist after the second sync")
        self.assertEqual(
            len(stored_order.payment_ids),
            1,
            "second sync must have attached the payment to the existing order",
        )
        self.assertEqual(stored_order.foreign_amount_total, 4234.0)
        self.assertEqual(stored_order.foreign_currency_rate, 36.5)

    def test_load_data_does_not_crash_with_draft_order(self):
        """Regression: opening the POS frontend calls
        ``pos.session.load_data``, which in turn calls every model's
        ``_load_pos_data_search_read``. ``res.partner._load_pos_data_domain``
        iterates over ``data['pos.order']`` to read ``partner_id`` on each
        one (``point_of_sale/models/res_partner.py:59``). If our
        ``pos.order._load_pos_data_fields`` override does not expose
        ``partner_id``, ``load_data`` crashes with ``KeyError: 'partner_id'``
        and the frontend crashes downstream with
        ``Cannot read properties of undefined (reading 'map')``.

        This test drives ``pos.session.load_data`` with at least one draft
        order in the session so any missing core-required field surfaces
        here instead of in the browser.
        """
        session = self.env["pos.session"].create(
            {
                "config_id": self.config.id,
                "user_id": self.env.ref("base.user_admin").id,
            }
        )

        # A draft order MUST exist for res.partner's domain to iterate.
        self.env["pos.order"].create(
            {
                "company_id": self.company.id,
                "session_id": session.id,
                "partner_id": False,
                "pricelist_id": (
                    self.company.partner_id.property_product_pricelist.id
                ),
                "foreign_amount_total": 0.0,
                "foreign_currency_rate": 36.5,
                "amount_total": 0.0,
                "amount_tax": 0.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "last_order_preparation_change": "{}",
            }
        )

        # Should not raise. Under the previous VE-only override this
        # crashed inside res.partner._load_pos_data_domain because
        # pos.order did not expose partner_id.
        response = session.load_data(models_to_load=[])
        self.assertIn("pos.order", response)
        self.assertIn("res.partner", response)
        for order_payload in response["pos.order"]:
            self.assertIn(
                "partner_id",
                order_payload,
                "pos.order payload must expose partner_id so "
                "res.partner._load_pos_data_domain can build its domain.",
            )

    # ------------------------------------------------------------------
    # B.2 / B.4 — pos.payment._load_pos_data_fields exposes
    #       foreign_amount and foreign_rate.
    # ------------------------------------------------------------------
    def test_pos_payment_load_pos_data_fields_includes_foreign_amount_and_rate(self):
        """B.2 / B.4 / Spec: payment read-back payload MUST include
        ``foreign_amount`` and ``foreign_rate``."""
        fields = self.env["pos.payment"]._load_pos_data_fields(self.config)
        self.assertIn(
            "foreign_amount",
            fields,
            "pos.payment._load_pos_data_fields must expose foreign_amount",
        )
        self.assertIn(
            "foreign_rate",
            fields,
            "pos.payment._load_pos_data_fields must expose foreign_rate",
        )

    # ------------------------------------------------------------------
    # B.5 — pos.order.line._load_pos_data_fields exposes
    #       foreign_price AND foreign_currency_rate.
    # ------------------------------------------------------------------
    def test_pos_order_line_load_pos_data_fields_includes_foreign_price_and_rate(self):
        """B.5 / Spec: order-line read-back payload MUST include
        ``foreign_price`` AND ``foreign_currency_rate``.

        ``foreign_currency_rate`` is a related field on
        ``pos.order.line`` (points to ``order_id.foreign_currency_rate``).
        Native Odoo 19 base does NOT include it; we must add it.
        """
        fields = self.env["pos.order.line"]._load_pos_data_fields(self.config)
        self.assertIn(
            "foreign_price",
            fields,
            "pos.order.line._load_pos_data_fields must expose foreign_price",
        )
        self.assertIn(
            "foreign_currency_rate",
            fields,
            "pos.order.line._load_pos_data_fields must expose foreign_currency_rate",
        )

    # ------------------------------------------------------------------
    # B.6 — End-to-end round trip: create order, read back via
    #       Odoo 19 ``pos.order.read_pos_data``, assert all foreign
    #       fields survive.
    # ------------------------------------------------------------------
    def test_pos_order_serialization_round_trip_preserves_foreign_fields(self):
        """B.6 / Spec: order create -> reload -> all Venezuelan
        foreign-currency fields survive.

        Triangulation: 1 foreign field per model (order, payment, line).
        All three must round-trip together.

        We deliberately create the pos.session in the ``opening_control``
        state (default) and the pos.order in ``draft`` state so we can
        exercise the Odoo 19 read-back flow without depending on
        ``open_ui`` (which requires a full chart of accounts).
        """
        session = self.env["pos.session"].create(
            {
                "config_id": self.config.id,
                "user_id": self.env.ref("base.user_admin").id,
            }
        )
        self.assertEqual(session.state, "opening_control")

        order = self.env["pos.order"].create(
            {
                "company_id": self.company.id,
                "session_id": session.id,
                "partner_id": False,
                "pricelist_id": self.company.partner_id.property_product_pricelist.id,
                "foreign_amount_total": 116.0,
                "foreign_currency_rate": 36.5,
                "lines": [
                    Command.create(
                        {
                            "name": "OL/SLICEB/0001",
                            "product_id": self.product.id,
                            "price_unit": 100.0,
                            "discount": 0.0,
                            "qty": 1.0,
                            "price_subtotal": 100.0,
                            "price_subtotal_incl": 116.0,
                            "tax_ids": [(6, 0, self.tax.ids)],
                            "foreign_price": 3650.0,
                            "foreign_subtotal": 3650.0,
                            "foreign_total": 4234.0,
                        }
                    ),
                    Command.create(
                        {
                            "name": "OL/SLICEB/0002",
                            "product_id": self.product.id,
                            "price_unit": 50.0,
                            "discount": 0.0,
                            "qty": 1.0,
                            "price_subtotal": 50.0,
                            "price_subtotal_incl": 58.0,
                            "tax_ids": [(6, 0, self.tax.ids)],
                            "foreign_price": 1825.0,
                            "foreign_subtotal": 1825.0,
                            "foreign_total": 2117.0,
                        }
                    ),
                ],
                "amount_total": 174.0,
                "amount_tax": 24.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "last_order_preparation_change": "{}",
            }
        )
        # Manually create the payment so we can attach foreign fields
        # without driving the full paid-state flow (which depends on
        # account moves that require a chart of accounts).
        order.add_payment(
            {
                "name": "Payment 1",
                "pos_order_id": order.id,
                "amount": 174.0,
                "payment_method_id": self.payment_method.id,
                "payment_date": order.date_order,
                "foreign_rate": 36.5,
                "foreign_amount": 6351.0,
            }
        )

        # ---- Odoo 19 read-back (replaces _export_for_ui) ----
        payload = order.read_pos_data([], self.config)
        self.assertIn("pos.order", payload)
        self.assertIn("pos.payment", payload)
        self.assertIn("pos.order.line", payload)

        order_payloads = payload["pos.order"]
        self.assertEqual(len(order_payloads), 1, "exactly one order expected in payload")
        order_data = order_payloads[0]
        # Must include Venezuelan fields. ``load=False`` on read returns
        # many2one as a bare int (per Odoo 19 mixin contract).
        self.assertIn("foreign_amount_total", order_data)
        self.assertEqual(order_data["foreign_amount_total"], 116.0)
        self.assertIn("foreign_currency_rate", order_data)
        self.assertEqual(order_data["foreign_currency_rate"], 36.5)

        # Payment payload must include the Venezuelan fields.
        payment_payloads = payload["pos.payment"]
        self.assertEqual(len(payment_payloads), 1)
        payment_data = payment_payloads[0]
        self.assertIn("foreign_amount", payment_data)
        self.assertEqual(payment_data["foreign_amount"], 6351.0)
        self.assertIn("foreign_rate", payment_data)
        self.assertEqual(payment_data["foreign_rate"], 36.5)

        # Order line payload must include the Venezuelan fields. We
        # created two lines to triangulate the read-back across multiple
        # records (not just the first one).
        line_payloads = payload["pos.order.line"]
        self.assertEqual(len(line_payloads), 2)
        for line_data, expected_foreign_price in zip(
            sorted(line_payloads, key=lambda d: d["foreign_price"]),
            [1825.0, 3650.0],
        ):
            self.assertIn("foreign_price", line_data)
            self.assertEqual(line_data["foreign_price"], expected_foreign_price)
            self.assertIn("foreign_currency_rate", line_data)
            self.assertEqual(
                line_data["foreign_currency_rate"],
                36.5,
                "line.foreign_currency_rate must match the order's foreign rate",
            )

    # ------------------------------------------------------------------
    # B.5 (refund scenario) — Refund must copy ``foreign_price`` to the
    #       refund line so the Venezuelan tax/total reconstruction
    #       downstream can keep working.
    # ------------------------------------------------------------------
    def test_pos_order_refund_copies_foreign_price_to_refund_line(self):
        """B.5 / Spec: refund preparation must propagate ``foreign_price``
        to the refund line.

        Triangulation: a separate order with a single line. The refund
        must keep the foreign-currency value, otherwise the downstream
        accounting flow would lose the contract.
        """
        session = self.env["pos.session"].create(
            {
                "config_id": self.config.id,
                "user_id": self.env.ref("base.user_admin").id,
            }
        )

        order = self.env["pos.order"].create(
            {
                "company_id": self.company.id,
                "session_id": session.id,
                "pricelist_id": self.company.partner_id.property_product_pricelist.id,
                "foreign_amount_total": 116.0,
                "foreign_currency_rate": 36.5,
                "lines": [
                    Command.create(
                        {
                            "name": "OL/SLICEB/REFUND",
                            "product_id": self.product.id,
                            "price_unit": 100.0,
                            "discount": 0.0,
                            "qty": 1.0,
                            "price_subtotal": 100.0,
                            "price_subtotal_incl": 116.0,
                            "tax_ids": [(6, 0, self.tax.ids)],
                            "foreign_price": 3650.0,
                        }
                    )
                ],
                "amount_total": 116.0,
                "amount_tax": 16.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "last_order_preparation_change": "{}",
            }
        )
        original_line = order.lines[0]
        self.assertEqual(original_line.foreign_price, 3650.0)

        # Drive the refund via the official entrypoint that calls
        # _prepare_refund_data on every line of the source order.
        refund_orders = order._refund()
        self.assertEqual(len(refund_orders), 1)
        refund_line = refund_orders.lines[0]
        self.assertEqual(
            refund_line.foreign_price,
            original_line.foreign_price,
            "refund line must inherit foreign_price from the source line",
        )

    # ------------------------------------------------------------------
    # B.1 / B.3 / B.4 — Defensive check: the Odoo 17 serialization
    #       hooks must NOT be present on the l10n_ve_pos models
    #       (they would crash on super call against Odoo 19 and we
    #       explicitly prefer fail-fast over silent fallback).
    # ------------------------------------------------------------------
    def test_legacy_serialization_hooks_are_removed(self):
        """Fail-fast: ensure the Odoo 17 hooks were stripped. If any of
        them is still present, the next Odoo 19 call to super()._order_fields
        (or similar) will raise ``AttributeError`` instead of silently
        producing wrong data."""
        self.assertFalse(
            hasattr(self.env["pos.order"], "_order_fields"),
            "pos.order._order_fields was removed in Odoo 19; the l10n_ve_pos "
            "override must be deleted, not left as dead code.",
        )
        self.assertFalse(
            hasattr(self.env["pos.order"], "_payment_fields"),
            "pos.order._payment_fields was removed in Odoo 19; the l10n_ve_pos "
            "override must be deleted, not left as dead code.",
        )
        self.assertFalse(
            hasattr(self.env["pos.order"], "_export_for_ui"),
            "pos.order._export_for_ui was removed in Odoo 19; the l10n_ve_pos "
            "override must be deleted, not left as dead code.",
        )
        self.assertFalse(
            hasattr(self.env["pos.payment"], "_export_for_ui"),
            "pos.payment._export_for_ui was removed in Odoo 19; the l10n_ve_pos "
            "override must be deleted, not left as dead code.",
        )

    # ------------------------------------------------------------------
    # Regression — write_date MUST survive in every dynamicModel's field
    #       contract, or the POS frontend crashes on open.
    # ------------------------------------------------------------------
    def test_dynamic_models_expose_write_date(self):
        """Odoo 19's ``DevicesSynchronisation.constructOrdersDomain``
        (``point_of_sale/static/src/app/utils/devices_synchronisation.js``)
        calls ``record.write_date.plus(...)`` on every record of every
        "dynamic model" (``pos.order``, ``pos.order.line``, ``pos.payment``,
        ``pos.pack.operation.lot``, ``product.attribute.custom.value``)
        every time the POS opens or syncs. If any of these models'
        ``_load_pos_data_fields`` returns an explicit list that forgets
        ``write_date``, the frontend crashes with
        ``TypeError: Cannot read properties of undefined (reading 'plus')``
        — it does NOT fail server-side, so nothing short of a test like
        this one catches it before a cashier hits it in production.

        Convention: an EMPTY list means "load every stored field" (see
        ``pos.load.mixin._load_pos_data_read``, which calls
        ``records.read(fields, load=False)`` and Odoo's ORM treats an
        empty field list as "all fields") — that case is safe too, since
        ``write_date`` is always present. Only a NON-empty list that
        omits ``write_date`` is the bug.

        Real incident: ``pos.payment._load_pos_data_fields`` replaced the
        core empty-list contract with an explicit
        ``_POS_PAYMENT_CORE_FIELDS`` tuple that did not include
        ``write_date`` (db ``2doce``, 2026-07-29). ``l10n_ve_pos_mf`` has
        a defensive JS patch for the symptom, but it is not installed on
        every database, so this Python-level test is the only guard that
        applies everywhere ``l10n_ve_pos`` is installed.
        """
        dynamic_models = (
            "pos.order",
            "pos.order.line",
            "pos.payment",
            "pos.pack.operation.lot",
            "product.attribute.custom.value",
        )
        for model_name in dynamic_models:
            model_fields = self.env[model_name]._load_pos_data_fields(self.config)
            self.assertTrue(
                not model_fields or "write_date" in model_fields,
                f"{model_name}._load_pos_data_fields must either return an "
                "empty list (= load all fields) or explicitly include "
                "'write_date', otherwise constructOrdersDomain crashes the "
                "POS frontend with \"Cannot read properties of undefined "
                "(reading 'plus')\" on open.",
            )
