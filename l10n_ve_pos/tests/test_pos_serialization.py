"""Slice B: Order/Payment Serialization TDD tests.

Verifies that ``l10n_ve_pos`` exposes the Venezuelan foreign-currency
serialization contract documented in
``openspec/changes/l10n-ve-pos-migration-plan/specs/pos-odoo19-serialization/spec.md``
through the Odoo 19 read-back flow (``_load_pos_data_fields`` +
``_load_pos_data_read``), without relying on the Odoo 17 ``_order_fields`` /
``_payment_fields`` / ``_export_for_ui`` hooks (removed upstream).
"""

from odoo import Command
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
    # B.1 — pos.order._load_pos_data_fields exposes the Venezuelan
    #       foreign-currency contract (foreign_amount_total,
    #       foreign_currency_rate).
    # ------------------------------------------------------------------
    def test_pos_order_load_pos_data_fields_includes_foreign_total_and_rate(self):
        """B.1 / Spec: ``pos.order._load_pos_data_fields`` MUST include
        ``foreign_amount_total`` and ``foreign_currency_rate``.

        The Odoo 19 base returns an empty list (the model relies on
        ``read_pos_data`` consumers to call our override). Without these
        fields in the override, ``read_pos_data`` would return an order
        payload with no Venezuelan foreign-currency fields.
        """
        fields = self.env["pos.order"]._load_pos_data_fields(self.config)
        self.assertIn(
            "foreign_amount_total",
            fields,
            "pos.order._load_pos_data_fields must expose foreign_amount_total",
        )
        self.assertIn(
            "foreign_currency_rate",
            fields,
            "pos.order._load_pos_data_fields must expose foreign_currency_rate",
        )

    # ------------------------------------------------------------------
    # Odoo 19 sync contract — write_date must be part of the pos.order
    # payload, otherwise ``devices_synchronisation.constructOrdersDomain``
    # crashes with "Cannot read properties of undefined (reading 'plus')"
    # on the frontend the moment a synced open order is refreshed.
    # ------------------------------------------------------------------
    def test_pos_order_load_pos_data_fields_includes_write_date(self):
        """The Odoo 19 POS device sync calls ``record.write_date.plus(...)``
        on synced open orders (see
        ``point_of_sale/static/src/app/utils/devices_synchronisation.js``
        -> ``constructOrdersDomain``). If our override drops ``write_date``,
        the whole POS UI crashes when the sync loop kicks in.
        """
        fields = self.env["pos.order"]._load_pos_data_fields(self.config)
        self.assertIn(
            "write_date",
            fields,
            "pos.order._load_pos_data_fields must expose write_date so the "
            "Odoo 19 POS device sync can compute the reload domain.",
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
