"""Slice C1: Session Accounting Accumulators TDD tests.

Verifies that ``l10n_ve_pos`` ``_accumulate_amounts`` and ``_update_amounts``
preserves the Odoo 19 dict contract (per-bucket ``amount`` /
``amount_converted`` keys) AND adds the Venezuelan ``foreign_amount`` key
without dropping or renaming Odoo 19 keys.

Spec: ``openspec/changes/l10n-ve-pos-migration-plan/specs/pos-odoo19-session-accounting/spec.md``
Doc: ``.../specs/pos-odoo19-session-accounting/key-map.md``
Native Odoo 19 reference: ``/home/binaural19/odoo/addons/point_of_sale/models/pos_session.py:840-1011``
and ``:1486-1545``.
"""

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_pos", "slice_c1")
class TestPosSessionAccountingAccumulators(TransactionCase):
    """Spec: ``pos-odoo19-session-accounting/spec.md`` (C1.2 + C1.3 + C1.4).

    The accumulators produce the data dict consumed by C2
    (``_create_split_account_payment``, ``_create_bank_payment_moves``,
    ``_create_cash_statement_lines_and_cash_move_lines``,
    ``_create_invoice_receivable_lines``). Any silent loss of an Odoo 19
    key here breaks C2 accounting without an obvious error message.

    The test layer is **Unit** (Odoo ORM in-process) because we are
    verifying the contract of two methods against the real Odoo 19 super;
    no chart of accounts or move creation is required.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # --- Isolated VES-as-foreign environment (same pattern as Slice A/B) ---
        usd = cls.env.ref("base.USD")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test VE Slice C1 Co",
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

        # --- Minimal chart of accounts so a session can be opened ---
        Account = cls.env["account.account"]
        cls.account_receivable = Account.create(
            {
                "name": "C1 Receivable",
                "code": "120000C1",
                "account_type": "asset_receivable",
                "company_ids": [(6, 0, [cls.company.id])],
                "reconcile": True,
            }
        )
        cls.account_income = Account.create(
            {
                "name": "C1 Income",
                "code": "400000C1",
                "account_type": "income",
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )
        cls.account_cash = Account.create(
            {
                "name": "C1 Cash",
                "code": "100000C1",
                "account_type": "asset_cash",
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )

        # --- Two payment methods: combined cash and split cash.
        # Both use cash journals to keep the test setup simple (l10n_ve_accountant
        # requires bank journals to have payment method lines with accounts;
        # the C1 accumulator contract does not depend on journal type).
        cls.cash_journal = cls.env["account.journal"].create(
            {
                "name": "C1 Cash Journal",
                "type": "cash",
                "code": "CSC1",
                "company_id": cls.company.id,
                "currency_id": cls.foreign_currency.id,
                "default_account_id": cls.account_cash.id,
            }
        )
        cls.split_cash_journal = cls.env["account.journal"].create(
            {
                "name": "C1 Split Cash Journal",
                "type": "cash",
                "code": "SCC1",
                "company_id": cls.company.id,
                "currency_id": cls.foreign_currency.id,
                "default_account_id": cls.account_cash.id,
            }
        )
        # Combined cash method (no split_transactions) → combine_receivables_cash
        cls.combined_cash_method = cls.env["pos.payment.method"].create(
            {
                "name": "C1 Combined Cash",
                "is_cash_count": True,
                "split_transactions": False,
                "company_id": cls.company.id,
                "journal_id": cls.cash_journal.id,
            }
        )
        cls.combined_cash_method.write({"is_foreign_currency": True})
        # Split cash method (split_transactions=True) → split_receivables_cash
        cls.split_cash_method = cls.env["pos.payment.method"].create(
            {
                "name": "C1 Split Cash",
                "is_cash_count": True,
                "split_transactions": True,
                "company_id": cls.company.id,
                "journal_id": cls.split_cash_journal.id,
            }
        )
        cls.split_cash_method.write({"is_foreign_currency": True})

        # --- Product + tax (needed for the order to compute totals) ---
        cls.tax_group = cls.env["account.tax.group"].create(
            {"name": "C1 Tax Group", "company_id": cls.company.id}
        )
        cls.tax = cls.env["account.tax"].create(
            {
                "name": "C1 Tax",
                "amount": 16.0,
                "type_tax_use": "sale",
                "tax_group_id": cls.tax_group.id,
                "company_id": cls.company.id,
            }
        )
        cls.product_category = cls.env["product.category"].create(
            {
                "name": "C1 Category",
                "property_account_income_categ_id": cls.account_income.id,
                "property_account_expense_categ_id": cls.account_income.id,
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "C1 Product",
                "lst_price": 100.0,
                "standard_price": 50.0,
                "available_in_pos": True,
                "company_id": cls.company.id,
                "categ_id": cls.product_category.id,
                "taxes_id": [(6, 0, cls.tax.ids)],
            }
        )
        cls.product.with_company(cls.company).write(
            {"property_account_income_id": cls.account_income.id}
        )

        # --- POS config in foreign currency ---
        cls.sale_journal = cls.env["account.journal"].create(
            {
                "name": "C1 Sale Journal",
                "type": "sale",
                "code": "SJC1",
                "company_id": cls.company.id,
                "currency_id": cls.foreign_currency.id,
            }
        )
        cls.invoice_journal = cls.env["account.journal"].create(
            {
                "name": "C1 Invoice Journal",
                "type": "sale",
                "code": "IJC1",
                "company_id": cls.company.id,
                "currency_id": cls.foreign_currency.id,
            }
        )
        cls.config = cls.env["pos.config"].create(
            {
                "name": "C1 Config",
                "company_id": cls.company.id,
                "currency_id": cls.foreign_currency.id,
                "journal_id": cls.sale_journal.id,
                "invoice_journal_id": cls.invoice_journal.id,
                "payment_method_ids": [
                    (6, 0, [cls.combined_cash_method.id, cls.split_cash_method.id])
                ],
            }
        )

    # ----------------------------------------------------------------------
    # Helper: build a closed session with two paid orders.
    # ----------------------------------------------------------------------
    @classmethod
    def _build_session_with_paid_orders(cls):
        """Create one session with three paid orders in foreign currency.

        - Order 1: 1 line × 100 VEF, paid with combined cash, non-invoiced
          → ``combine_receivables_cash`` accumulates both orders 1 + 3.
        - Order 2: 1 line × 50 VEF, paid with split cash, non-invoiced
          → ``split_receivables_cash`` (keyed by the payment record).
        - Order 3: 1 line × 50 VEF, paid with combined cash, INVOICED
          → ``combine_invoice_receivables`` (keyed by the payment method).

        All orders are flipped to ``paid`` so ``_get_closed_orders()`` (the
        Odoo 19 super iteration source) returns them.
        """
        session = cls.env["pos.session"].create(
            {
                "config_id": cls.config.id,
                "user_id": cls.env.ref("base.user_admin").id,
            }
        )

        # ---- Order 1: combined cash, non-invoiced ----
        order1 = cls.env["pos.order"].create(
            {
                "company_id": cls.company.id,
                "session_id": session.id,
                "pricelist_id": cls.company.partner_id.property_product_pricelist.id,
                "foreign_amount_total": 116.0,
                "foreign_currency_rate": 36.5,
                "lines": [
                    Command.create(
                        {
                            "name": "OL/C1/0001",
                            "product_id": cls.product.id,
                            "price_unit": 100.0,
                            "discount": 0.0,
                            "qty": 1.0,
                            "price_subtotal": 100.0,
                            "price_subtotal_incl": 116.0,
                            "tax_ids": [(6, 0, cls.tax.ids)],
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
        order1.add_payment(
            {
                "name": "P1",
                "pos_order_id": order1.id,
                "amount": 116.0,
                "payment_method_id": cls.combined_cash_method.id,
                "payment_date": order1.date_order,
                "foreign_rate": 36.5,
                "foreign_amount": 4234.0,
            }
        )

        # ---- Order 2: split cash, non-invoiced ----
        order2 = cls.env["pos.order"].create(
            {
                "company_id": cls.company.id,
                "session_id": session.id,
                "pricelist_id": cls.company.partner_id.property_product_pricelist.id,
                "foreign_amount_total": 58.0,
                "foreign_currency_rate": 36.5,
                "lines": [
                    Command.create(
                        {
                            "name": "OL/C1/0002",
                            "product_id": cls.product.id,
                            "price_unit": 50.0,
                            "discount": 0.0,
                            "qty": 1.0,
                            "price_subtotal": 50.0,
                            "price_subtotal_incl": 58.0,
                            "tax_ids": [(6, 0, cls.tax.ids)],
                            "foreign_price": 1825.0,
                        }
                    )
                ],
                "amount_total": 58.0,
                "amount_tax": 8.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "last_order_preparation_change": "{}",
            }
        )
        order2.add_payment(
            {
                "name": "P2",
                "pos_order_id": order2.id,
                "amount": 58.0,
                "payment_method_id": cls.split_cash_method.id,
                "payment_date": order2.date_order,
                "foreign_rate": 36.5,
                "foreign_amount": 2117.0,
            }
        )

        # ---- Order 3: combined cash, INVOICED ----
        # To exercise the ``combine_invoice_receivables`` bucket we need
        # ``order.is_invoiced = True``. The cleanest way without running
        # the full invoicing flow is to set a real (but DRAFT — we must
        # NOT post it because ``pos.payment`` blocks creation on a posted
        # order) ``account.move`` on the order — this triggers the
        # ``_compute_is_invoiced`` Boolean and is enough for the
        # accumulator path.
        #
        # CRITICAL: ``pos.payment._check_amount`` raises
        # ``You cannot edit a payment for a posted order.`` if the order
        # has an ``account_move`` at payment-creation time. We must
        # therefore: (1) create the order WITHOUT the invoice, (2) add
        # the payment, (3) attach the invoice afterwards.
        order3 = cls.env["pos.order"].create(
            {
                "company_id": cls.company.id,
                "session_id": session.id,
                "pricelist_id": cls.company.partner_id.property_product_pricelist.id,
                "foreign_amount_total": 50.0,
                "foreign_currency_rate": 36.5,
                "lines": [
                    Command.create(
                        {
                            "name": "OL/C1/0003",
                            "product_id": cls.product.id,
                            "price_unit": 50.0,
                            "discount": 0.0,
                            "qty": 1.0,
                            "price_subtotal": 50.0,
                            "price_subtotal_incl": 58.0,
                            "tax_ids": [(6, 0, cls.tax.ids)],
                            "foreign_price": 1825.0,
                        }
                    )
                ],
                "amount_total": 58.0,
                "amount_tax": 8.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "last_order_preparation_change": "{}",
            }
        )
        order3.add_payment(
            {
                "name": "P3",
                "pos_order_id": order3.id,
                "amount": 58.0,
                "payment_method_id": cls.combined_cash_method.id,
                "payment_date": order3.date_order,
                "foreign_rate": 36.5,
                "foreign_amount": 2117.0,
            }
        )
        # Now attach the invoice (draft, so pos_payment blocks nothing).
        invoice = cls.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "journal_id": cls.invoice_journal.id,
                "partner_id": cls.company.partner_id.id,
            }
        )
        order3.write({"account_move": invoice.id})
        # Force ``paid`` so ``_get_closed_orders()`` picks them up. The
        # accumulator contract is consumed from there.
        order1.write({"state": "paid"})
        order2.write({"state": "paid"})
        order3.write({"state": "paid"})
        return session

    # ----------------------------------------------------------------------
    # C1.4 / Spec: combine_receivables_cash MUST keep Odoo 19 keys
    #       (``amount`` + ``amount_converted``) AND add the Venezuelan
    #       ``foreign_amount`` for every entry keyed by payment_method.
    # ----------------------------------------------------------------------
    def test_combine_receivables_cash_preserves_odoo19_keys_and_adds_foreign_amount(self):
        """C1.4 — Combined cash bucket shape.

        Both order 1 (non-invoiced, 116) and order 3 (invoiced, 58) pay
        with ``combined_cash_method`` → one bucket entry keyed by the
        method, with ``amount`` = 116 + 58 = 174 and ``foreign_amount`` =
        4234 + 2117 = 6351.
        """
        session = self._build_session_with_paid_orders()
        data = session._accumulate_amounts({})

        self.assertIn("combine_receivables_cash", data)
        bucket = data["combine_receivables_cash"]
        # Both orders 1 + 3 share the combined_cash_method → one entry.
        self.assertEqual(len(bucket), 1, "expected one combine_receivables_cash entry")

        entry = bucket[self.combined_cash_method]
        # Odoo 19 native keys (must remain present)
        self.assertIn("amount", entry)
        self.assertIn("amount_converted", entry)
        self.assertEqual(entry["amount"], 174.0)  # 116 + 58
        # amount_converted depends on currency conversion; just check it's
        # a finite number — the exact value is the Odoo 19 base's job.
        self.assertIsInstance(entry["amount_converted"], (int, float))
        # Venezuelan additive key — sum across both payments.
        self.assertIn("foreign_amount", entry)
        self.assertEqual(entry["foreign_amount"], 6351.0)  # 4234 + 2117

    # ----------------------------------------------------------------------
    # C1.4 / Spec: split_receivables_cash MUST keep Odoo 19 keys
    #       AND add ``foreign_amount`` for every entry keyed by payment.
    # ----------------------------------------------------------------------
    def test_split_receivables_cash_preserves_odoo19_keys_and_adds_foreign_amount(self):
        """C1.4 — Split cash bucket shape (order 2, non-invoiced)."""
        session = self._build_session_with_paid_orders()
        data = session._accumulate_amounts({})

        self.assertIn("split_receivables_cash", data)
        bucket = data["split_receivables_cash"]
        # Order 2 paid with the split cash method → one entry per payment.
        self.assertEqual(len(bucket), 1, "expected one split_receivables_cash entry")

        # The key is the payment record, not the method. Find it.
        order2 = session.order_ids.filtered(lambda o: o.foreign_amount_total == 58.0 and not o.is_invoiced)
        payment = order2.payment_ids[0]
        entry = bucket[payment]
        self.assertIn("amount", entry)
        self.assertIn("amount_converted", entry)
        self.assertEqual(entry["amount"], 58.0)
        self.assertIn("foreign_amount", entry)
        self.assertEqual(entry["foreign_amount"], 2117.0)

    # ----------------------------------------------------------------------
    # C1.4 / Spec: combine_invoice_receivables carries ``foreign_amount``
    #       for the invoiced-order combined cash payment.
    # ----------------------------------------------------------------------
    def test_combine_invoice_receivables_keeps_foreign_amount_for_invoiced_orders(self):
        """C1.4 — Invoiced order bucket shape (order 3, combined cash).

        Order 3 is invoiced AND paid with the combined cash method, so its
        invoiced receivables bucket is ``combine_invoice_receivables`` keyed
        by payment_method.
        """
        session = self._build_session_with_paid_orders()
        data = session._accumulate_amounts({})

        self.assertIn("combine_invoice_receivables", data)
        bucket = data["combine_invoice_receivables"]
        self.assertEqual(len(bucket), 1)
        # Note: the bucket key for invoiced receivables is the
        # payment_method, regardless of split_transactions on the payment
        # itself (per the Odoo 19 super contract).
        entry = bucket[self.combined_cash_method]
        self.assertIn("amount", entry)
        self.assertIn("amount_converted", entry)
        self.assertIn("foreign_amount", entry)
        self.assertEqual(entry["foreign_amount"], 2117.0)

    # ----------------------------------------------------------------------
    # C1.3 / Spec: _update_amounts returns a dict that has BOTH the
    #       Odoo 19 keys (``amount``, ``amount_converted``) AND the
    #       Venezuelan ``foreign_amount`` after l10n_ve_pos extension.
    # ----------------------------------------------------------------------
    def test_update_amounts_returns_odoo19_keys_plus_foreign_amount(self):
        """C1.3 — ``_update_amounts`` additive contract."""
        session = self._build_session_with_paid_orders()

        # First call: seed with native + foreign
        seed = session._update_amounts(
            {"amount": 0.0, "amount_converted": 0.0},
            {"amount": 100.0, "foreign_amount": 3650.0},
            session.start_at,
        )
        self.assertIn("amount", seed)
        self.assertIn("amount_converted", seed)
        self.assertIn("foreign_amount", seed)
        self.assertEqual(seed["amount"], 100.0)
        self.assertEqual(seed["foreign_amount"], 3650.0)

        # Second call: accumulate
        grown = session._update_amounts(
            seed,
            {"amount": 50.0, "foreign_amount": 1825.0},
            session.start_at,
        )
        self.assertEqual(grown["amount"], 150.0)
        self.assertEqual(grown["foreign_amount"], 5475.0)
        # Odoo 19 keys must still be present (not renamed / dropped)
        self.assertIn("amount_converted", grown)

    # ----------------------------------------------------------------------
    # C1.4 / Spec: ``foreign_amount`` accumulation matches the
    #       per-payment source (split vs combine).
    # ----------------------------------------------------------------------
    def test_foreign_amount_aggregates_across_payments_for_same_method(self):
        """C1.4 triangulation: two cash payments on the same method →
        ``foreign_amount`` is the sum of the two (combine bucket).
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
                "foreign_amount_total": 200.0,
                "foreign_currency_rate": 36.5,
                "lines": [
                    Command.create(
                        {
                            "name": "OL/C1/AGG",
                            "product_id": self.product.id,
                            "price_unit": 100.0,
                            "discount": 0.0,
                            "qty": 2.0,
                            "price_subtotal": 200.0,
                            "price_subtotal_incl": 232.0,
                            "tax_ids": [(6, 0, self.tax.ids)],
                            "foreign_price": 3650.0,
                        }
                    )
                ],
                "amount_total": 232.0,
                "amount_tax": 32.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "last_order_preparation_change": "{}",
            }
        )
        # Two combined-cash payments on the same method
        order.add_payment(
            {
                "name": "AGG1",
                "pos_order_id": order.id,
                "amount": 116.0,
                "payment_method_id": self.combined_cash_method.id,
                "payment_date": order.date_order,
                "foreign_rate": 36.5,
                "foreign_amount": 4234.0,
            }
        )
        order.add_payment(
            {
                "name": "AGG2",
                "pos_order_id": order.id,
                "amount": 116.0,
                "payment_method_id": self.combined_cash_method.id,
                "payment_date": order.date_order,
                "foreign_rate": 36.5,
                "foreign_amount": 4234.0,
            }
        )
        order.write({"state": "paid"})  # one-at-a-time, see _compute_order_name

        data = session._accumulate_amounts({})
        bucket = data["combine_receivables_cash"]
        self.assertEqual(len(bucket), 1)
        entry = bucket[self.combined_cash_method]
        # Odoo 19: amount is 116 + 116 = 232 (sum of both payments)
        self.assertEqual(entry["amount"], 232.0)
        # l10n_ve_pos: foreign_amount is 4234 + 4234 = 8468
        self.assertEqual(entry["foreign_amount"], 8468.0)

    # ----------------------------------------------------------------------
    # C1.4 / Spec regression guard: NO receivable bucket loses the
    #       Odoo 19 ``amount`` or ``amount_converted`` keys.
    # ----------------------------------------------------------------------
    def test_no_receivable_bucket_loses_odoo19_keys(self):
        """C1.4 regression — populated buckets must keep all Odoo 19 keys.

        Defends against a future refactor that accidentally only writes
        ``foreign_amount`` to the dict (e.g. by calling
        ``dict.update({'foreign_amount': ...})`` on a freshly-allocated
        empty dict, which would clobber the Odoo 19 super's contribution).

        Only checks the buckets that this scenario populates (orders 1, 2,
        3 above).
        """
        session = self._build_session_with_paid_orders()
        data = session._accumulate_amounts({})
        # Buckets that MUST be populated by the test scenario above.
        populated_buckets = (
            "split_receivables_cash",
            "combine_receivables_cash",
            "combine_invoice_receivables",
        )
        for bucket_name in populated_buckets:
            bucket = data[bucket_name]
            self.assertGreater(
                len(bucket),
                0,
                f"{bucket_name} should have at least one entry (sanity)",
            )
            for key, entry in bucket.items():
                self.assertIn(
                    "amount",
                    entry,
                    f"{bucket_name}[{key}] lost the Odoo 19 'amount' key",
                )
                self.assertIn(
                    "amount_converted",
                    entry,
                    f"{bucket_name}[{key}] lost the Odoo 19 'amount_converted' key",
                )
                self.assertIn(
                    "foreign_amount",
                    entry,
                    f"{bucket_name}[{key}] missing the Venezuelan 'foreign_amount' key",
                )

    # ----------------------------------------------------------------------
    # C1.2 / Spec: l10n_ve_pos MUST NOT pollute the Odoo 19 dict with
    #       ghost entries from draft / cancelled orders.
    #
    # Odoo 19 super iterates ``self._get_closed_orders()`` (filters out
    # ``draft`` and ``cancel``). The pre-C1 l10n_ve_pos override iterated
    # ``self.order_ids`` (no filter), so a draft order with a payment
    # would CREATE a ghost entry in the Odoo 19 defaultdict — entries
    # with ``amount=0`` and ``foreign_amount=Z``. C2's move creation
    # would then call ``_get_split_receivable_vals(payment, 0, 0)`` and
    # try to create zero-amount moves (or fail loudly).
    # ----------------------------------------------------------------------
    def test_draft_order_with_payment_does_not_create_ghost_accumulator_entry(self):
        """C1.2 regression — no ghost entries from non-closed orders.

        Triangulation: a draft order with a payment in the same session
        as a paid order. The l10n_ve_pos override must follow the Odoo
        19 super and only iterate closed orders; otherwise the draft
        payment would pollute ``split_receivables_cash`` with a
        ``{amount: 0, amount_converted: 0, foreign_amount: Z}`` entry.
        """
        session = self.env["pos.session"].create(
            {
                "config_id": self.config.id,
                "user_id": self.env.ref("base.user_admin").id,
            }
        )

        # Order A: paid (closed) — should appear in accumulators.
        order_paid = self.env["pos.order"].create(
            {
                "company_id": self.company.id,
                "session_id": session.id,
                "pricelist_id": self.company.partner_id.property_product_pricelist.id,
                "foreign_amount_total": 58.0,
                "foreign_currency_rate": 36.5,
                "lines": [
                    Command.create(
                        {
                            "name": "OL/C1/GHOST/PAID",
                            "product_id": self.product.id,
                            "price_unit": 50.0,
                            "discount": 0.0,
                            "qty": 1.0,
                            "price_subtotal": 50.0,
                            "price_subtotal_incl": 58.0,
                            "tax_ids": [(6, 0, self.tax.ids)],
                            "foreign_price": 1825.0,
                        }
                    )
                ],
                "amount_total": 58.0,
                "amount_tax": 8.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "last_order_preparation_change": "{}",
            }
        )
        order_paid.add_payment(
            {
                "name": "GHOST-P",
                "pos_order_id": order_paid.id,
                "amount": 58.0,
                "payment_method_id": self.split_cash_method.id,
                "payment_date": order_paid.date_order,
                "foreign_rate": 36.5,
                "foreign_amount": 2117.0,
            }
        )
        order_paid.write({"state": "paid"})

        # Order B: DRAFT (not closed) — must NOT appear in accumulators.
        order_draft = self.env["pos.order"].create(
            {
                "company_id": self.company.id,
                "session_id": session.id,
                "pricelist_id": self.company.partner_id.property_product_pricelist.id,
                "foreign_amount_total": 58.0,
                "foreign_currency_rate": 36.5,
                "lines": [
                    Command.create(
                        {
                            "name": "OL/C1/GHOST/DRAFT",
                            "product_id": self.product.id,
                            "price_unit": 50.0,
                            "discount": 0.0,
                            "qty": 1.0,
                            "price_subtotal": 50.0,
                            "price_subtotal_incl": 58.0,
                            "tax_ids": [(6, 0, self.tax.ids)],
                            "foreign_price": 1825.0,
                        }
                    )
                ],
                "amount_total": 58.0,
                "amount_tax": 8.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "last_order_preparation_change": "{}",
            }
        )
        order_draft.add_payment(
            {
                "name": "GHOST-D",
                "pos_order_id": order_draft.id,
                "amount": 58.0,
                "payment_method_id": self.split_cash_method.id,
                "payment_date": order_draft.date_order,
                "foreign_rate": 36.5,
                "foreign_amount": 2117.0,
            }
        )
        # ``order_draft`` stays in ``draft`` state.

        data = session._accumulate_amounts({})
        bucket = data["split_receivables_cash"]
        # Only the paid order's payment should be in the bucket. The
        # draft order's payment must NOT create a ghost entry.
        self.assertEqual(
            len(bucket),
            1,
            f"split_receivables_cash should have 1 entry (paid only); got {len(bucket)}: "
            f"{[(p.pos_order_id.name, p.pos_order_id.state) for p in bucket.keys()]}",
        )
        only_payment = list(bucket.keys())[0]
        self.assertEqual(only_payment.pos_order_id, order_paid)
