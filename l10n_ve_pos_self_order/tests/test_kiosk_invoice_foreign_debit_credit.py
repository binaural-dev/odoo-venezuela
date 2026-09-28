"""Tests for the precision of ``foreign_debit``/``foreign_credit`` on the
invoice generated from a Kiosk order.

Spec: ``l10n_ve_pos/openspec/changes/l10n-ve-pos-self-order-foreign-amount-fix/
specs/pos-self-order-foreign-amount/spec.md`` and ``l10n_ve_pos_self_order/
models/pos_order.py::recompute_prices`` (see its docstring for the full
chain this file exercises).

Why this file exists, and why it lives here (not in ``l10n_ve_pos`` or
``l10n_ve_accountant``): the ORIGINAL Kiosk bug was that
``pos.order.line.foreign_price`` stayed ``0.0`` (the Kiosk bundle never
loads the JS patch that sets it, unlike the cashier bundle), so every
Kiosk invoice was posted with ``foreign_debit``/``foreign_credit`` at
``0.0`` on its product lines. ``recompute_prices()`` (this module) is the
ONLY place that fills ``line.foreign_price`` for the Kiosk. Everything
downstream — ``l10n_ve_pos._get_invoice_lines_values`` copying
``foreign_price`` onto the invoice line, and ``l10n_ve_accountant``
deriving ``foreign_subtotal``/``foreign_debit``/``foreign_credit`` from
it — already exists and is exercised elsewhere for the regular cashier
flow, but nothing runs that chain end to end starting from a Kiosk order
that arrives WITHOUT ``foreign_price`` on its lines (the exact shape of
the original bug). These tests build that scenario directly and invoice
it through ``action_pos_order_invoice()``, asserting the real
``account.move.line`` values it produces.

Formulas asserted here (verified directly against the source, not
guessed):

* ``pos.config._convert``/``_get_pos_conversion_rate``
  (``l10n_ve_pos/models/pos_config.py``) multiply by the RAW rate and
  round only the final result with ``to_currency.round()`` — i.e.
  ``float_round(..., rounding_method='HALF-UP')``
  (``odoo/tools/float_utils.py``).
* ``account_move_line._get_foreign_value`` (``l10n_ve_accountant/models/
  account_move_line.py``): for a ``product``/``cogs`` line,
  ``sign = move.direction_sign * -1`` and
  ``value = -(foreign_subtotal * sign)``. ``account.move.get_outbound_types``
  (core, ``account/models/account_move.py``) is
  ``['in_invoice', 'out_refund', 'in_receipt']`` — ``out_invoice`` is NOT in
  it (it's an INBOUND type: money comes IN from the customer), so
  ``direction_sign == -1`` for a normal Kiosk sale, not ``+1`` as the name
  "direction_sign" might suggest. That makes
  ``sign = -1 * -1 = 1`` and ``value = -foreign_subtotal`` (negative) →
  ``foreign_credit = foreign_subtotal``, ``foreign_debit = 0.0`` — the
  product/income line is CREDITED in the foreign column too, mirroring the
  local entry (income lines are credited in double-entry bookkeeping).
  Verified empirically against a real posted invoice, not just read off
  the source — a first pass at this file had the sign backwards.
* ``pos.order.line.foreign_price`` is a PER-UNIT price; ``foreign_subtotal``
  on the invoice line applies quantity/discount/tax on top of it
  (``_compute_foreign_subtotal``), so a line with quantity > 1 exercises a
  second, independently-rounded arithmetic path — asserted with a small
  tolerance rather than bit-for-bit equality, matching the tolerance style
  already used in ``l10n_ve_accountant/tests/test_foreign_balance.py``.
"""

from datetime import date, timedelta

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_pos_self_order")
class TestKioskInvoiceForeignDebitCredit(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        usd = cls.env.ref("base.USD")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test VE Kiosk Invoice Foreign Co",
                "currency_id": usd.id,
                "country_id": cls.env.ref("base.ve").id,
            }
        )
        vef = (
            cls.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", "VEF")], limit=1)
        )
        if vef and not vef.active:
            vef.active = True
        cls.foreign_currency = vef
        cls.company.write({"foreign_currency_id": cls.foreign_currency.id})

        # l10n_ve_rate's compute_rate (models/res_currency_rate.py) looks up
        # res.currency.rate filtered by ``self.env.company.id`` — the
        # CALLING env's active company — not by the record's own
        # ``company_id`` being assigned throughout this file. Without
        # rebinding ``cls.env`` here, every later read of
        # ``pos.config.foreign_rate``/``foreign_inverse_rate`` (including
        # indirectly, e.g. ``order.config_id.foreign_inverse_rate`` inside
        # ``recompute_prices()``) would resolve against the test runner's
        # ambient/admin company instead of ``cls.company``, find no rate,
        # and silently settle on 0.0.
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company.id]))

        # Deliberately non-round rate (1 USD = 36.5 VEF): a real BCV rate is
        # never a clean number, and this stresses the HALF-UP rounding
        # instead of hiding it behind convenient integers.
        #
        # Sets the PLAIN ``rate`` field (not ``inverse_company_rate``):
        # ``company_rate``/``inverse_company_rate`` both have an
        # ``inverse=`` that writes back to OTHER fields on the same
        # record, so setting either directly re-triggers a compute/inverse
        # cascade. Setting ``rate`` instead leaves ``company_rate``/
        # ``inverse_company_rate`` as purely computed reads
        # (``company_rate = rate / last_rate[company]``, and
        # ``last_rate[company] == 1`` for a company with no rate history
        # of its own) — see ``l10n_ve_pos/tests/
        # test_pos_config_convert_precision.py::_set_bs_per_usd_rate`` for
        # the same reasoning, applied there across many rates.
        cls.bs_per_usd_rate = 36.5
        cls.env["res.currency.rate"].create(
            {
                "name": "2026-01-01",
                "currency_id": cls.foreign_currency.id,
                "rate": cls.bs_per_usd_rate,
                "company_id": cls.company.id,
            }
        )

        Account = cls.env["account.account"]
        cls.account_receivable = Account.create(
            {
                "name": "Kiosk FX Receivable",
                "code": "120000KFX",
                "account_type": "asset_receivable",
                "company_ids": [(6, 0, [cls.company.id])],
                "reconcile": True,
            }
        )
        # point_of_sale/models/pos_payment.py::_create_payment_moves reads
        # ``company_id.account_default_pos_receivable_account_id`` for the
        # payment move's counterpart line when the payment isn't a split/
        # reverse transaction — left unset, that line's ``account_id`` is
        # NULL and account.move.line's own DB check constraint
        # (``_check_accountable_required_fields``) rejects the row.
        cls.company.write(
            {"account_default_pos_receivable_account_id": cls.account_receivable.id}
        )
        cls.account_income = Account.create(
            {
                "name": "Kiosk FX Income",
                "code": "400000KFX",
                "account_type": "income",
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )
        cls.account_bank = Account.create(
            {
                "name": "Kiosk FX Bank",
                "code": "100000KFX",
                "account_type": "asset_cash",
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )
        cls.company.partner_id.with_company(cls.company).write(
            {
                "property_account_receivable_id": cls.account_receivable.id,
                "property_account_payable_id": cls.account_receivable.id,
            }
        )

        cls.tax_group = cls.env["account.tax.group"].create(
            {"name": "Kiosk FX Tax Group", "company_id": cls.company.id}
        )
        cls.tax = cls.env["account.tax"].create(
            {
                "name": "Kiosk FX Tax 16%",
                "amount": 16.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "tax_group_id": cls.tax_group.id,
                "company_id": cls.company.id,
            }
        )
        cls.product_category = cls.env["product.category"].create(
            {
                "name": "Kiosk FX Category",
                "property_account_income_categ_id": cls.account_income.id,
                "property_account_expense_categ_id": cls.account_income.id,
            }
        )
        # l10n_ve_accountant enforces a company-scoped PURCHASE tax too
        # (product_template.py::_enforce_single_tax_vals), not just sale —
        # cls.product below only sets taxes_id (sale); this company default
        # satisfies the purchase side without touching the product vals.
        cls.company.write({"account_purchase_tax_id": cls.tax.id})
        # ``type="service"``: sidesteps stock/picking generation entirely so
        # these tests stay focused on the accounting (foreign) side.
        cls.product = cls.env["product.product"].create(
            {
                "name": "Kiosk FX Product",
                "type": "service",
                "lst_price": 100.0,
                "available_in_pos": True,
                "company_id": cls.company.id,
                "categ_id": cls.product_category.id,
                "taxes_id": [(6, 0, cls.tax.ids)],
            }
        )
        # `property_account_income_id` is company_dependent — the category
        # default set above is NOT enough for
        # point_of_sale/models/pos_order.py::_prepare_base_line_for_taxes_computation
        # ("Please define income account for this product"), it must be
        # written FOR this company explicitly.
        cls.product.with_company(cls.company).write(
            {"property_account_income_id": cls.account_income.id}
        )

        # A Kiosk config cannot carry a cash payment method
        # (pos_self_order/models/pos_config.py::_onchange_payment_method_ids
        # — "You cannot add cash payment methods in kiosk mode"), matching
        # reality: a Kiosk pays by card/terminal (Megasoft/SITEF), never
        # cash. A bank journal in Odoo 19 must have BOTH inbound and
        # outbound payment method lines with payment_account_id set
        # (l10n_ve_accountant's ``_check_payment_method_line_accounts``).
        manual_in = cls.env.ref("account.account_payment_method_manual_in")
        manual_out = cls.env.ref("account.account_payment_method_manual_out")
        cls.bank_journal = cls.env["account.journal"].create(
            {
                "name": "Kiosk FX Bank Journal",
                "type": "bank",
                "code": "KFXC",
                "company_id": cls.company.id,
                "default_account_id": cls.account_bank.id,
                "inbound_payment_method_line_ids": [
                    (0, 0, {"payment_method_id": manual_in.id, "payment_account_id": cls.account_bank.id})
                ],
                "outbound_payment_method_line_ids": [
                    (0, 0, {"payment_method_id": manual_out.id, "payment_account_id": cls.account_bank.id})
                ],
            }
        )
        cls.payment_method = cls.env["pos.payment.method"].create(
            {
                "name": "Kiosk FX Card",
                "is_cash_count": False,
                "company_id": cls.company.id,
                "journal_id": cls.bank_journal.id,
                "outstanding_account_id": cls.account_bank.id,
            }
        )
        cls.sale_journal = cls.env["account.journal"].create(
            {
                "name": "Kiosk FX Sale Journal",
                "type": "sale",
                "code": "KFXSJ",
                "company_id": cls.company.id,
            }
        )
        cls.invoice_journal = cls.env["account.journal"].create(
            {
                "name": "Kiosk FX Invoice Journal",
                "type": "sale",
                "code": "KFXIJ",
                "company_id": cls.company.id,
            }
        )
        cls.config = cls.env["pos.config"].create(
            {
                "name": "Kiosk FX Config",
                "company_id": cls.company.id,
                "self_ordering_mode": "kiosk",
                "journal_id": cls.sale_journal.id,
                "invoice_journal_id": cls.invoice_journal.id,
                "payment_method_ids": [(6, 0, [cls.payment_method.id])],
                # self_ordering_default_user_id's default
                # (pos_self_order/models/pos_config.py::_self_order_default_user)
                # searches res.users by ``company_ids in self.env.company``
                # — the admin user isn't a member of this freshly created
                # test company, so with allowed_company_ids restricted to
                # it above the default silently resolves to no user, and
                # ``_check_default_user`` then rejects the empty value for
                # a non-"nothing" self_ordering_mode.
                "self_ordering_default_user_id": cls.env.ref("base.user_admin").id,
            }
        )
        cls.session = cls.env["pos.session"].create(
            {
                "config_id": cls.config.id,
                "user_id": cls.env.ref("base.user_admin").id,
            }
        )
        # order.currency_id (related to config.currency_id) must resolve to
        # the COMPANY currency (USD), not the foreign one — otherwise
        # ``config._convert`` would take the same-currency shortcut and
        # never exercise a real cross-currency conversion.
        assert cls.config.currency_id == usd, (
            "test setup must keep the POS operating in the company currency"
        )

    def _set_bs_per_usd_rate(self, bs_per_usd):
        """Add a new, later-dated VEF rate row so a single test can sweep
        several rates, meaning "1 USD = bs_per_usd VEF".

        Sets the PLAIN ``rate`` field (not ``inverse_company_rate``) — see
        ``l10n_ve_pos/tests/test_pos_config_convert_precision.py::
        _set_bs_per_usd_rate`` for why. Creates a FRESH row (never
        overwrites the ``setUpClass`` one in place): ``compute_rate``
        always picks the LATEST row with ``name <= today``, so a strictly
        later date makes each new row the one in effect without ever
        touching the previous one.

        Also invalidates ``self.config``'s cache: ``pos.config.
        _compute_rate``'s ``@api.depends`` does NOT include
        ``res.currency.rate``, so ``foreign_rate``/``foreign_inverse_rate``
        would otherwise keep returning the FIRST rate ever read for the
        rest of the test method regardless of any new row created
        afterwards (verified empirically — see the sibling file's
        docstring for the full story)."""
        self._rate_seq = getattr(self, "_rate_seq", 0) + 1
        self.env["res.currency.rate"].create(
            {
                "name": date(2026, 1, 1) + timedelta(days=self._rate_seq),
                "currency_id": self.foreign_currency.id,
                "company_id": self.company.id,
                "rate": bs_per_usd,
            }
        )
        self.config.invalidate_recordset(["foreign_rate", "foreign_inverse_rate"])

    def _create_kiosk_order(self, *, qty=1.0, price_unit=1.0):
        """Build a Kiosk order the way the (broken, pre-fix) client would:
        no ``foreign_price`` on the line at all (defaults to ``0.0``), and a
        placeholder ``price_unit``/``amount_total`` that ``recompute_prices()``
        is expected to correct from the real catalog price
        (``self.product.lst_price``), same as ``test_recompute_prices_foreign_amount``.
        """
        return self.env["pos.order"].create(
            {
                "company_id": self.company.id,
                "session_id": self.session.id,
                "partner_id": self.company.partner_id.id,
                "pricelist_id": (
                    self.company.partner_id.property_product_pricelist.id
                ),
                "amount_total": price_unit * qty,
                "amount_tax": 0.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "last_order_preparation_change": "{}",
                "lines": [
                    Command.create(
                        {
                            "name": "OL/KFX/0001",
                            "product_id": self.product.id,
                            "price_unit": price_unit,
                            "discount": 0.0,
                            "qty": qty,
                            "price_subtotal": price_unit * qty,
                            "price_subtotal_incl": price_unit * qty,
                            "tax_ids": [(6, 0, self.tax.ids)],
                        }
                    )
                ],
            }
        )

    def _pay_and_invoice(self, order):
        """Recompute (as the Kiosk controller does after creating the
        order), pay in full, and invoice — mirrors
        ``_process_saved_order``/``action_pos_order_invoice`` without going
        through HTTP."""
        order.recompute_prices()
        order.add_payment(
            {
                "name": "OL/KFX/0001/P",
                "pos_order_id": order.id,
                "amount": order.amount_total,
                "payment_method_id": self.payment_method.id,
                "payment_date": order.date_order,
            }
        )
        order.write({"state": "paid"})
        order.action_pos_order_invoice()
        return order.account_move

    def _product_line(self, invoice):
        lines = invoice.line_ids.filtered(lambda l: l.display_type == "product")
        self.assertEqual(len(lines), 1, "expected exactly one product line")
        return lines

    # ------------------------------------------------------------------
    def test_kiosk_order_line_foreign_price_filled_by_recompute(self):
        """Regression guard for the original bug: a Kiosk order line created
        WITHOUT ``foreign_price`` (simulating the missing JS patch) must not
        stay at the field's ``0.0`` default after ``recompute_prices()`` —
        it must match ``config._convert(price_unit, ...)`` exactly, the
        formula this module's ``recompute_prices()`` override uses."""
        order = self._create_kiosk_order(qty=1.0, price_unit=1.0)
        self.assertEqual(
            order.lines.foreign_price,
            0.0,
            "test setup must start from the pre-fix bug shape (no foreign_price)",
        )

        order.recompute_prices()

        self.assertEqual(
            order.lines.price_unit,
            self.product.lst_price,
            "recompute_prices() must correct price_unit from the real catalog price",
        )
        expected_foreign_price = self.config._convert(
            order.lines.price_unit, order.currency_id, self.foreign_currency
        )
        self.assertNotEqual(
            expected_foreign_price,
            0.0,
            "test setup must exercise a real, non-zero conversion",
        )
        self.assertEqual(order.lines.foreign_price, expected_foreign_price)

    def test_kiosk_invoice_product_line_foreign_credit_matches_conversion(self):
        """The invoice generated from a Kiosk order must carry the product
        line's ``foreign_credit`` precisely equal to ``foreign_subtotal``
        (an ``out_invoice`` has ``direction_sign == -1`` — it's an INBOUND
        type, not outbound, see the module docstring — so
        ``account_move_line._get_foreign_value`` reduces to
        ``value == -foreign_subtotal``, i.e. a CREDIT), and that value must
        match the catalog-price conversion — not the ``0.0`` the Kiosk bug
        produced."""
        order = self._create_kiosk_order(qty=1.0, price_unit=1.0)
        invoice = self._pay_and_invoice(order)

        self.assertEqual(invoice.move_type, "out_invoice")
        line = self._product_line(invoice)

        expected_foreign_subtotal = self.config._convert(
            self.product.lst_price, order.currency_id, self.foreign_currency
        )
        self.assertGreater(
            line.foreign_credit,
            0.0,
            "foreign_credit must not be 0.0 (the original Kiosk bug)",
        )
        self.assertAlmostEqual(
            line.foreign_subtotal, expected_foreign_subtotal, delta=0.01
        )
        self.assertAlmostEqual(
            line.foreign_credit, line.foreign_subtotal, delta=0.0001,
            msg="for an out_invoice, foreign_credit must equal foreign_subtotal",
        )
        self.assertEqual(
            line.foreign_debit,
            0.0,
            "a product line on an out_invoice must not carry foreign_debit",
        )

    def test_kiosk_invoice_foreign_credit_precise_with_quantity(self):
        """Same contract with quantity > 1: ``foreign_price`` is a PER-UNIT
        price (``recompute_prices()`` never multiplies it by quantity), so
        the invoice's ``foreign_subtotal``/``foreign_credit`` must scale by
        quantity through the tax engine's OWN (independently rounded)
        arithmetic — checked with a small tolerance rather than bit-for-bit
        equality, since two independently-rounded paths are involved."""
        order = self._create_kiosk_order(qty=3.0, price_unit=1.0)
        self.product.lst_price = 16.67
        invoice = self._pay_and_invoice(order)

        line = self._product_line(invoice)
        expected_unit_foreign_price = self.config._convert(
            16.67, order.currency_id, self.foreign_currency
        )
        expected_foreign_subtotal = expected_unit_foreign_price * 3.0
        self.assertAlmostEqual(
            line.foreign_subtotal, expected_foreign_subtotal, delta=0.02
        )
        self.assertAlmostEqual(
            line.foreign_credit, expected_foreign_subtotal, delta=0.02
        )
        self.assertEqual(line.foreign_debit, 0.0)

    def test_kiosk_invoice_foreign_rate_pinned_from_order_not_recomputed(self):
        """``l10n_ve_pos._prepare_invoice_vals`` pins ``foreign_rate`` AND
        ``foreign_inverse_rate`` on the invoice to the SAME single
        ``pos.order.foreign_currency_rate`` value, with
        ``manually_set_rate=True`` — this must survive posting untouched
        (``account.move._compute_rate_for_documents`` skips manually-set
        rates), otherwise the invoice could silently use a different rate
        than what the Kiosk customer was charged against."""
        order = self._create_kiosk_order(qty=1.0, price_unit=1.0)
        invoice = self._pay_and_invoice(order)

        self.assertTrue(invoice.manually_set_rate)
        self.assertNotEqual(
            order.foreign_currency_rate,
            0.0,
            "test setup must exercise a real conversion rate",
        )
        self.assertAlmostEqual(
            invoice.foreign_rate, order.foreign_currency_rate, places=6
        )
        self.assertAlmostEqual(
            invoice.foreign_inverse_rate, order.foreign_currency_rate, places=6
        )

    def test_kiosk_invoice_foreign_balance_squares(self):
        """Invariant across the WHOLE invoice (product + tax + payment_term
        lines): total foreign debit must equal total foreign credit — same
        check used in ``l10n_ve_accountant/tests/test_foreign_balance.py``.
        Combined with the non-zero assertions above (this check alone would
        also pass on an all-``0.0`` invoice, which is exactly the original
        bug)."""
        order = self._create_kiosk_order(qty=1.0, price_unit=1.0)
        invoice = self._pay_and_invoice(order)

        sum_foreign_debit = sum(invoice.line_ids.mapped("foreign_debit"))
        sum_foreign_credit = sum(invoice.line_ids.mapped("foreign_credit"))
        self.assertGreater(sum_foreign_debit, 0.0)
        self.assertAlmostEqual(sum_foreign_debit, sum_foreign_credit, places=2)

    # ------------------------------------------------------------------
    # Decimal precision across many rates/quantities — THIS module's own
    # code (recompute_prices()/invoice generation), not the engine itself
    # (that generic contract is covered separately in ``l10n_ve_pos/tests/
    # test_pos_config_convert_precision.py``, since ``_convert``/
    # ``_get_pos_conversion_rate`` are defined there, not here).
    # ------------------------------------------------------------------
    #
    # "Distintas tasas y configuraciones, ejecutando _convert debe darme
    # lo mismo": for every (rate, quantity) combination below, the SAME
    # ``config._convert`` call is used both as (a) what
    # ``recompute_prices()`` calls internally to fill
    # ``pos.order.line.foreign_price``, and (b) the oracle this test
    # recomputes independently to check the invoice's ``foreign_credit``
    # against — proving the whole Kiosk chain (recompute → invoice line
    # copy → l10n_ve_accountant's tax-engine-driven ``foreign_subtotal``)
    # never drifts from what ``_convert`` says, at ANY of these rates.
    BS_PER_USD_RATES = [
        0.99999949,  # near 1:1
        36.567891234,  # realistic BCV-shaped rate, many decimals
        189.34567891234,  # realistic, bigger
        7654321.123456,  # hyperinflation-scale
    ]
    QUANTITIES = [1.0, 3.0, 7.0]

    def test_kiosk_invoice_foreign_credit_precise_across_many_rates_and_quantities(self):
        """Sweep several decimal-heavy rates × quantities. For each
        combination: ``pos.order.line.foreign_price`` (set by THIS
        module's ``recompute_prices()``) must equal
        ``config._convert(price_unit, ...)`` exactly, and the resulting
        invoice's product-line ``foreign_credit`` must match
        ``config._convert(price_unit, ...) * qty`` within a small
        tolerance (the tax engine rounds ``foreign_subtotal``
        independently — see the module docstring)."""
        for bs_per_usd in self.BS_PER_USD_RATES:
            self._set_bs_per_usd_rate(bs_per_usd)
            for qty in self.QUANTITIES:
                with self.subTest(bs_per_usd=bs_per_usd, qty=qty):
                    order = self._create_kiosk_order(qty=qty, price_unit=1.0)
                    order.recompute_prices()

                    expected_unit_foreign_price = self.config._convert(
                        order.lines.price_unit,
                        order.currency_id,
                        self.foreign_currency,
                    )
                    self.assertNotEqual(expected_unit_foreign_price, 0.0)
                    self.assertEqual(
                        order.lines.foreign_price, expected_unit_foreign_price
                    )

                    order.add_payment(
                        {
                            "name": "OL/KFX/0001/P",
                            "pos_order_id": order.id,
                            "amount": order.amount_total,
                            "payment_method_id": self.payment_method.id,
                            "payment_date": order.date_order,
                        }
                    )
                    order.write({"state": "paid"})
                    order.action_pos_order_invoice()
                    line = self._product_line(order.account_move)

                    expected_foreign_subtotal = expected_unit_foreign_price * qty
                    self.assertAlmostEqual(
                        line.foreign_credit, expected_foreign_subtotal, delta=0.02
                    )
                    self.assertEqual(line.foreign_debit, 0.0)
