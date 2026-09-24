from datetime import timedelta
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged
from odoo import fields
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_foreign_exchange_diff")
class TestForeignExchangeDiff(TransactionCase):
    """Alternate-currency amounts injected into Odoo's native exchange
    difference entry, and the standalone entry when only the alternate
    currency differs. Covers amounts, signs, posted state, and the
    reconciliation-break/reversal flow for both cases.
    """

    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.env.user.write({'company_ids': [(4, self.company.id)], 'company_id': self.company.id})
        self.currency_vef = self.env.ref("base.VEF")
        self.currency_usd = self.env.ref("base.USD")
        self.Rate = self.env["res.currency.rate"]
        self.today = fields.Date.today()
        # Distinct dates for booking vs. settlement -- `res.currency.rate`
        # has a real unique constraint of one rate per (currency, day).
        self.booking_date = self.today - timedelta(days=5)
        self.settlement_date = self.today

        self.company.write({
            "currency_id": self.currency_vef.id,
            "foreign_currency_id": self.currency_usd.id,
        })

        # Native exchange-difference config, required by core regardless
        # of this feature -- our standalone entry reuses these same
        # accounts/journal via `_get_exchange_account`/`_get_exchange_journal`.
        if not self.company.income_currency_exchange_account_id:
            self.company.income_currency_exchange_account_id = self.env["account.account"].create({
                "name": "Exchange Gain", "code": "EXCHGAIN",
                "account_type": "income_other",
                "company_ids": [(6, 0, [self.company.id])],
            }).id
        if not self.company.expense_currency_exchange_account_id:
            self.company.expense_currency_exchange_account_id = self.env["account.account"].create({
                "name": "Exchange Loss", "code": "EXCHLOSS",
                "account_type": "expense",
                "company_ids": [(6, 0, [self.company.id])],
            }).id
        if not self.company.currency_exchange_journal_id:
            self.company.currency_exchange_journal_id = self.env["account.journal"].create({
                "name": "Exchange Difference", "type": "general", "code": "EXCH",
                "company_id": self.company.id,
            }).id

        self.company.l10n_ve_use_foreign_exchange_diff = True
        # "Indexed" mode re-rates the invoice to the payment date's rate,
        # erasing the rate difference this feature must detect -- use
        # "not_indexed" so the booking rate survives to settlement.
        self.company.index_payment_in_wizard = False
        self.company.indexaxion_payment_mode = "not_indexed"

        self.partner = self.env["res.partner"].create({"name": "Alt Diff Partner"})
        self.product = self.env["product.product"].create({
            "name": "Service", "type": "service", "list_price": 100.0,
        })
        self.account_bank = self.env["account.account"].create({
            "name": "BANK ALT DIFF",
            "code": "100200",
            "account_type": "asset_cash",
            "company_ids": [(6, 0, [self.company.id])],
            "reconcile": True,
        })
        manual_in = self.env.ref("account.account_payment_method_manual_in")
        manual_out = self.env.ref("account.account_payment_method_manual_out")
        pm_line_in = self.env["account.payment.method.line"].create({
            "name": "Manual Inbound Alt",
            "payment_method_id": manual_in.id,
            "payment_type": "inbound",
            "payment_account_id": self.account_bank.id,
        })
        pm_line_out = self.env["account.payment.method.line"].create({
            "name": "Manual Outbound Alt",
            "payment_method_id": manual_out.id,
            "payment_type": "outbound",
            "payment_account_id": self.account_bank.id,
        })
        self.bank_journal = self.env["account.journal"].create({
            "name": "Bank Alt Diff",
            "type": "bank",
            "code": "BALTV",
            "currency_id": self.currency_vef.id,
            "default_account_id": self.account_bank.id,
            "inbound_payment_method_line_ids": [(6, 0, pm_line_in.ids)],
            "outbound_payment_method_line_ids": [(6, 0, pm_line_out.ids)],
        })

        account_bank_usd = self.env["account.account"].create({
            "name": "BANK ALT DIFF USD",
            "code": "100201",
            "account_type": "asset_cash",
            "company_ids": [(6, 0, [self.company.id])],
            "reconcile": True,
        })
        pm_line_in_usd = self.env["account.payment.method.line"].create({
            "name": "Manual Inbound Alt USD",
            "payment_method_id": manual_in.id,
            "payment_type": "inbound",
            "payment_account_id": account_bank_usd.id,
        })
        pm_line_out_usd = self.env["account.payment.method.line"].create({
            "name": "Manual Outbound Alt USD",
            "payment_method_id": manual_out.id,
            "payment_type": "outbound",
            "payment_account_id": account_bank_usd.id,
        })
        self.bank_journal_usd = self.env["account.journal"].create({
            "name": "Bank Alt Diff USD",
            "type": "bank",
            "code": "BALTU",
            "currency_id": self.currency_usd.id,
            "default_account_id": account_bank_usd.id,
            "inbound_payment_method_line_ids": [(6, 0, pm_line_in_usd.ids)],
            "outbound_payment_method_line_ids": [(6, 0, pm_line_out_usd.ids)],
        })

    def _set_usd_rate(self, date, ves_per_usd):
        """1 USD = `ves_per_usd` VEF on `date` (native `company_rate` /
        `inverse_company_rate` convention: `company_rate` = USD per VEF,
        `inverse_company_rate` = VEF per USD).
        """
        return self.Rate.create({
            "name": date,
            "currency_id": self.currency_usd.id,
            "company_id": self.company.id,
            "company_rate": 1.0 / ves_per_usd,
            "inverse_company_rate": ves_per_usd,
        })

    def _create_invoice(self, amount=100.0, currency=None, booking_ves_per_usd=None):
        # Doesn't force `foreign_inverse_rate` manually: as long as the
        # booking-date rate exists before creation, `_compute_rate_for_documents`
        # resolves it naturally (a manual value gets overwritten anyway by
        # this module's `create()`, which re-triggers `_compute_rate()`).
        if booking_ves_per_usd is not None:
            self._set_usd_rate(self.booking_date, booking_ves_per_usd)
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "currency_id": (currency or self.currency_vef).id,
            "invoice_date": self.booking_date,
            "invoice_date_display": self.booking_date,
            "date": self.booking_date,
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "price_unit": amount,
                "tax_ids": [(6, 0, [])],
            })],
        })
        # `out_invoice`/`out_refund` `action_post()` returns a confirmation
        # wizard action instead of posting unless this context is set --
        # same pattern `l10n_ve_exchange_difference` uses for its own notes.
        move.with_context(move_action_post_alert=True).action_post()
        return move

    def _pay_invoice(self, move, amount=None, currency=None, date=None):
        currency = currency or self.currency_vef
        journal = self.bank_journal_usd if currency == self.currency_usd else self.bank_journal
        amount = move.amount_total if amount is None else amount
        payment = self.env["account.payment"].with_company(self.company).create({
            "amount": amount,
            "date": date or self.settlement_date,
            "currency_id": currency.id,
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner.id,
            "journal_id": journal.id,
            "payment_method_line_id": journal.inbound_payment_method_line_ids[:1].id,
        })
        payment.action_post()
        receivable_line = move.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        payment_line = payment.move_id.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        (receivable_line + payment_line).reconcile()
        return payment, receivable_line, payment_line

    # ── Isolated unit tests: exact sign and magnitude ──

    def test_foreign_exposure_at_residual_is_exact_at_both_extremes(self):
        """At both extremes (residual 0 or the line's own original amount),
        `_foreign_exposure_at_residual` must reproduce the stored value
        EXACTLY, not a float approximation.
        Ver openspec: design-notes.md § foreign_exposure_at_residual
        """
        move = self._create_invoice(100.0, booking_ves_per_usd=40.0)
        line = move.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        self.assertAlmostEqual(line.foreign_debit, 2.5, places=6)  # 100 / 40

        self.assertEqual(line._foreign_exposure_at_residual(100.0), line.foreign_debit)
        self.assertEqual(line._foreign_exposure_at_residual(0.0), 0.0)
        # Halfway through the residual, exactly half the fixed exposure.
        self.assertAlmostEqual(line._foreign_exposure_at_residual(50.0), 1.25, places=6)

    def test_settlement_diff_ves_devaluation_on_receivable_is_a_loss(self):
        """VES weakens between booking and settlement: the alternate value
        of a receivable's settled amount FALLS -- must be a LOSS (positive),
        matching `l10n_ve_exchange_difference`'s sign convention.
        """
        move = self._create_invoice(100.0, booking_ves_per_usd=40.0)
        self._set_usd_rate(self.settlement_date, 50.0)  # 1 USD = 50 VEF at settlement
        _payment, receivable_line, payment_line = self._pay_invoice(move)
        self.assertAlmostEqual(receivable_line.foreign_debit, 2.5, places=6)   # 100 / 40
        self.assertAlmostEqual(payment_line.foreign_credit, 2.0, places=6)    # 100 / 50

        alt_diff = receivable_line._compute_alt_exchange_diff_from_settlement(
            payment_line, 100.0, 0.0, -100.0, 0.0, receivable_line,
        )
        # invoice.foreign_debit - payment.foreign_credit = 2.5 - 2.0 = 0.5
        self.assertAlmostEqual(alt_diff, 0.5, places=6)
        self.assertGreater(alt_diff, 0.0, "A VES devaluation on a receivable must be a loss (positive)")

    def test_settlement_diff_ves_revaluation_on_receivable_is_a_gain(self):
        move = self._create_invoice(100.0, booking_ves_per_usd=50.0)
        self._set_usd_rate(self.settlement_date, 40.0)  # VES strengthens
        _payment, receivable_line, payment_line = self._pay_invoice(move)

        alt_diff = receivable_line._compute_alt_exchange_diff_from_settlement(
            payment_line, 100.0, 0.0, -100.0, 0.0, receivable_line,
        )
        # 100/50 - 100/40 = 2.0 - 2.5 = -0.5
        self.assertAlmostEqual(alt_diff, -0.5, places=6)
        self.assertLess(alt_diff, 0.0, "A VES revaluation on a receivable must be a gain (negative)")

    def test_zero_when_toggle_disabled(self):
        move = self._create_invoice(100.0, booking_ves_per_usd=40.0)
        self._set_usd_rate(self.settlement_date, 50.0)
        self.company.l10n_ve_use_foreign_exchange_diff = False
        _payment, receivable_line, payment_line = self._pay_invoice(move)
        alt_diff = receivable_line._compute_alt_exchange_diff_from_settlement(
            payment_line, 100.0, 0.0, -100.0, 0.0, receivable_line,
        )
        self.assertEqual(alt_diff, 0.0)

    def test_zero_when_no_rate_change(self):
        move = self._create_invoice(100.0, booking_ves_per_usd=40.0)
        _payment, receivable_line, payment_line = self._pay_invoice(move)
        alt_diff = receivable_line._compute_alt_exchange_diff_from_settlement(
            payment_line, 100.0, 0.0, -100.0, 0.0, receivable_line,
        )
        self.assertEqual(alt_diff, 0.0)

    def test_full_settlement_with_non_clean_rates_matches_real_reported_amounts_exactly(self):
        """Reproduces the exact bug reported in production (1-cent rounding
        drift from re-deriving the amount via a rate delta instead of the
        two real fixed per-line amounts).
        Ver openspec: design-notes.md § Bug de redondeo reportado en producción
        """
        move = self._create_invoice(133.0, booking_ves_per_usd=8.65)
        self._set_usd_rate(self.settlement_date, 8.79)
        _payment, receivable_line, payment_line = self._pay_invoice(move)

        self.assertAlmostEqual(receivable_line.foreign_debit, 15.38, places=2)
        self.assertAlmostEqual(payment_line.foreign_credit, 15.13, places=2)

        entry = self.env["account.move"].search([
            ("l10n_ve_exchange_foreign_source_move_id", "=", move.id),
        ])
        self.assertEqual(len(entry), 1)
        loss_line = entry.line_ids.filtered(lambda l: l.foreign_credit > 0.0)
        expected = self.currency_usd.round(
            receivable_line.foreign_debit - payment_line.foreign_credit
        )
        self.assertEqual(expected, 0.25, "Sanity: the real (non-buggy) expected difference is 0.25, not 0.24")
        self.assertEqual(
            loss_line.foreign_credit, expected,
            "The posted alternate exchange difference must match the invoice/payment's own fixed "
            "foreign amounts EXACTLY, not a rate-based re-derivation prone to 1-cent rounding drift",
        )

    def test_three_uneven_partials_sum_exactly_to_the_line_fixed_foreign_amount(self):
        """Property test: 3 unevenly-sliced partials must sum EXACTLY to
        the line's fixed foreign amount, zero rounding drift left over.
        Ver openspec: design-notes.md § foreign_exposure_at_residual
        """
        move = self._create_invoice(133.0, booking_ves_per_usd=8.65)
        line = move.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        self.assertAlmostEqual(line.foreign_debit, 15.38, places=2)

        # 3 uneven slices of the 133.00 original amount, none a clean
        # divisor of it: 37.33 + 41.11 + 54.56 == 133.00.
        residual_boundaries = [133.0, 95.67, 54.56, 0.0]
        consumed = [
            line._foreign_exposure_at_residual(residual_boundaries[i])
            - line._foreign_exposure_at_residual(residual_boundaries[i + 1])
            for i in range(3)
        ]
        self.assertEqual(
            sum(consumed), line.foreign_debit,
            "3 unevenly-sliced partials must sum EXACTLY to the line's fixed foreign amount",
        )

    # ── Standalone case: amounts, state, and reversal ──

    def test_alternate_only_case_amounts_and_state(self):
        """Invoice paid exactly at face value in company currency (no
        native exchange difference at all) but the alternate rate moved
        -- must post a standalone entry with the exact expected amounts.
        """
        move = self._create_invoice(100.0, booking_ves_per_usd=40.0)
        self._set_usd_rate(self.settlement_date, 50.0)

        _payment, receivable_line, _payment_line = self._pay_invoice(move)

        entry = self.env["account.move"].search([
            ("l10n_ve_exchange_foreign_source_move_id", "=", move.id),
        ])
        self.assertEqual(len(entry), 1)
        self.assertEqual(entry.state, "posted")
        self.assertEqual(entry.l10n_ve_exchange_foreign_diff_entry, True)
        self.assertTrue(entry.l10n_ve_exchange_foreign_payment_move_id)

        for line in entry.line_ids:
            self.assertEqual(line.debit, 0.0)
            self.assertEqual(line.credit, 0.0)

        loss_line = entry.line_ids.filtered(lambda l: l.foreign_credit > 0.0)
        gain_line = entry.line_ids.filtered(lambda l: l.foreign_debit > 0.0)
        self.assertEqual(len(loss_line), 1, "Devaluation must credit foreign_credit on the closing line")
        self.assertAlmostEqual(loss_line.foreign_credit, 0.5, places=6)
        self.assertEqual(len(gain_line), 1)
        self.assertAlmostEqual(gain_line.foreign_debit, 0.5, places=6)
        self.assertEqual(loss_line.account_id, receivable_line.account_id)
        self.assertEqual(gain_line.account_id, self.company.expense_currency_exchange_account_id)

    def test_no_entry_when_no_rate_change_at_all(self):
        move = self._create_invoice(100.0, booking_ves_per_usd=40.0)
        self._pay_invoice(move)
        entries = self.env["account.move"].search([
            ("l10n_ve_exchange_foreign_source_move_id", "=", move.id),
        ])
        self.assertFalse(entries, "No rate change must not post any alternate-currency entry")

    def test_standalone_entry_idempotent_via_native_exchange_move_id(self):
        """Re-processing the SAME settlement (same `account.partial.reconcile`)
        must reuse its native `exchange_move_id`, not create a duplicate --
        idempotency rides entirely on that native field, no custom key.
        """
        move = self._create_invoice(100.0, booking_ves_per_usd=40.0)
        self._set_usd_rate(self.settlement_date, 50.0)
        _payment, receivable_line, payment_line = self._pay_invoice(move)

        first = self.env["account.move"].search([
            ("l10n_ve_exchange_foreign_source_move_id", "=", move.id),
        ])
        self.assertEqual(len(first), 1)

        partial = self.env["account.partial.reconcile"].search([
            ("debit_move_id", "in", (receivable_line.id, payment_line.id)),
            ("credit_move_id", "in", (receivable_line.id, payment_line.id)),
        ])
        self.assertEqual(partial.exchange_move_id, first, "The partial must have claimed the entry via exchange_move_id")

        second = receivable_line._create_standalone_foreign_exchange_difference_entry(
            payment_line, 0.5, self.today,
        )
        self.assertEqual(first, second, "Re-processing the SAME settlement must reuse exchange_move_id, not duplicate")

    def test_standalone_entry_reversed_when_reconciliation_broken(self):
        move = self._create_invoice(100.0, booking_ves_per_usd=40.0)
        self._set_usd_rate(self.settlement_date, 50.0)

        _payment, receivable_line, payment_line = self._pay_invoice(move)
        entry = self.env["account.move"].search([
            ("l10n_ve_exchange_foreign_source_move_id", "=", move.id),
        ])
        self.assertEqual(entry.state, "posted")

        (receivable_line + payment_line).remove_move_reconcile()

        self.assertEqual(entry.state, "posted", "The entry itself is reversed, not cancelled")
        self.assertTrue(entry.reversal_move_ids, "Breaking the reconciliation must reverse the standalone entry")
        reversal = entry.reversal_move_ids
        self.assertEqual(reversal.state, "posted")
        self.assertTrue(reversal.l10n_ve_exchange_foreign_diff_entry)

    def test_two_installments_get_independent_entries_and_reversal(self):
        """Two separate settlements against the same invoice, same day --
        each must get its OWN standalone entry (not suppressed by the
        other's idempotency guard), and undoing ONE must reverse only
        its own entry, leaving the other intact.
        """
        move = self._create_invoice(100.0, booking_ves_per_usd=40.0)
        self._set_usd_rate(self.settlement_date, 50.0)

        _payment1, receivable_line, payment_line1 = self._pay_invoice(move, amount=60.0)
        _payment2, _receivable_line2, payment_line2 = self._pay_invoice(move, amount=40.0)

        entries = self.env["account.move"].search([
            ("l10n_ve_exchange_foreign_source_move_id", "=", move.id),
        ])
        self.assertEqual(len(entries), 2, "Each installment must produce its own entry")

        # Unreconcile ONLY the first installment's partial -- not
        # `remove_move_reconcile()` on `receivable_line`, which would tear
        # down BOTH installments at once (it matches on either line).
        first_partial = self.env["account.partial.reconcile"].search([
            ("debit_move_id", "in", (receivable_line.id, payment_line1.id)),
            ("credit_move_id", "in", (receivable_line.id, payment_line1.id)),
        ])
        first_partial.unlink()

        entries.invalidate_recordset()
        reversed_entries = entries.filtered(lambda e: e.reversal_move_ids)
        self.assertEqual(len(reversed_entries), 1, "Only the broken installment's entry must be reversed")
        still_intact = entries - reversed_entries
        self.assertFalse(still_intact.reversal_move_ids, "The other installment's entry must remain untouched")

    def test_multiple_partial_payments_in_different_currencies_get_independent_alt_diffs(self):
        """3 installments (VEF, USD, VEF), each its own date/rate: every
        one must get its OWN correction vs. the SAME original booking
        rate -- never lumped together, never skipped.
        """
        move = self._create_invoice(300.0, booking_ves_per_usd=40.0)

        # Installment 1: 100 VEF cash, rate has moved to 50 by then.
        settlement_1 = self.settlement_date
        self._set_usd_rate(settlement_1, 50.0)
        _p1, receivable_line, payment_line_1 = self._pay_invoice(move, amount=100.0)

        # Installment 2: 100 VEF-equivalent paid straight in USD, later
        # date, rate moved again (to 60). Rounded through each currency's
        # OWN precision, never a hardcoded decimal count.
        settlement_2 = settlement_1 + timedelta(days=3)
        self._set_usd_rate(settlement_2, 60.0)
        usd_amount_2 = self.currency_usd.round(100.0 / 60.0)
        vef_equivalent_2 = self.currency_vef.round(usd_amount_2 * 60.0)
        payment_2 = self.env["account.payment"].with_company(self.company).create({
            "amount": usd_amount_2,
            "date": settlement_2,
            "currency_id": self.currency_usd.id,
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner.id,
            "journal_id": self.bank_journal_usd.id,
            "payment_method_line_id": self.bank_journal_usd.inbound_payment_method_line_ids[:1].id,
        })
        payment_2.action_post()
        payment_line_2 = payment_2.move_id.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        (receivable_line + payment_line_2).reconcile()

        # Installment 3: the remaining 100 VEF cash, yet another date/rate.
        settlement_3 = settlement_2 + timedelta(days=3)
        self._set_usd_rate(settlement_3, 45.0)
        _p3, _rl3, payment_line_3 = self._pay_invoice(move, amount=100.0, date=settlement_3)

        # The invoice itself is fully settled in VEF, regardless of how
        # many currencies/dates it took to get there.
        self.assertTrue(receivable_line.reconciled)
        self.assertEqual(receivable_line.amount_residual, 0.0)

        entries = self.env["account.move"].search([
            ("l10n_ve_exchange_foreign_source_move_id", "=", move.id),
        ])
        self.assertEqual(len(entries), 3, "Each of the 3 installments must produce its own entry")

        def diff_of(entry):
            loss = entry.line_ids.filtered(lambda l: l.foreign_credit > 0.0)
            gain = entry.line_ids.filtered(lambda l: l.foreign_debit > 0.0)
            self.assertEqual(len(loss) + len(gain), 2)
            return loss.foreign_credit if loss else -gain.foreign_debit

        entries_by_payment = {
            entry.l10n_ve_exchange_foreign_payment_move_id: entry for entry in entries
        }
        entry_1 = entries_by_payment[payment_line_1.move_id]
        entry_2 = entries_by_payment[payment_line_2.move_id]
        entry_3 = entries_by_payment[payment_line_3.move_id]

        # Always vs. the ORIGINAL booking rate (1/40), never the previous
        # installment's rate.
        self.assertAlmostEqual(diff_of(entry_1), 100.0 * (1 / 40.0 - 1 / 50.0), places=6)   # 0.5, loss
        # `delta` absorbs Odoo's own conversion rounding chain (USD-typed
        # amount, VEF equivalent not exactly 100) while still proving it
        # used ITS OWN rate (60), not installment 1's (would read ~0.5).
        self.assertAlmostEqual(diff_of(entry_2), vef_equivalent_2 * (1 / 40.0 - 1 / 60.0), delta=0.01)
        # Rounds to USD's own 2-decimal precision -- correct, not a bug.
        self.assertAlmostEqual(diff_of(entry_3), self.currency_usd.round(100.0 * (1 / 40.0 - 1 / 45.0)), places=6)

    def test_full_flow_foreign_invoice_multiple_partials_mixed_currencies_squares_natively_and_alternately(self):
        """USD invoice, 3 mixed-currency/date partials: all fire the native
        VEF entry, but NONE may carry an injected alternate amount (the
        invoice's own USD exposure is already fixed and exact).
        Ver openspec: design-notes.md § Exclusión: factura en moneda alterna
        """
        move = self._create_invoice(300.0, currency=self.currency_usd, booking_ves_per_usd=40.0)

        # Installment 1: 100 USD paid in USD.
        date_1 = self.settlement_date
        self._set_usd_rate(date_1, 50.0)
        _p1, receivable_line, payment_line_1 = self._pay_invoice(
            move, amount=100.0, currency=self.currency_usd, date=date_1,
        )

        # Installment 2: 100 USD-worth paid in VEF CASH instead, computed
        # exactly at that day's rate -- a different currency AND a
        # different date/rate from installment 1.
        date_2 = date_1 + timedelta(days=3)
        self._set_usd_rate(date_2, 60.0)
        vef_amount_2 = self.currency_vef.round(100.0 * 60.0)
        _p2, _rl2, payment_line_2 = self._pay_invoice(
            move, amount=vef_amount_2, currency=self.currency_vef, date=date_2,
        )

        # Installment 3: the remaining 100 USD, paid in USD again, at yet
        # another rate.
        date_3 = date_2 + timedelta(days=3)
        self._set_usd_rate(date_3, 45.0)
        _p3, _rl3, payment_line_3 = self._pay_invoice(
            move, amount=100.0, currency=self.currency_usd, date=date_3,
        )

        # ── 1) Full closure -- both the company-currency ledger AND the
        # invoice's own (USD) residual must be exactly zero. ──
        self.assertTrue(receivable_line.reconciled)
        self.assertEqual(receivable_line.amount_residual, 0.0)
        self.assertEqual(receivable_line.amount_residual_currency, 0.0)

        def native_amount_of(entry):
            """Signed VEF amount actually recorded on `entry` -- read from
            core's own output, not recomputed.
            """
            loss = entry.line_ids.filtered(lambda l: l.credit > 0.0)
            gain = entry.line_ids.filtered(lambda l: l.debit > 0.0)
            self.assertEqual(len(loss) + len(gain), 2, "Exactly one credit and one debit VEF line")
            return loss.credit if loss else -gain.debit

        # ── 2) Each installment fires its OWN native entry, but with NO
        # alternate amount injected on any of them (flag False, both
        # foreign_debit/foreign_credit 0.0 on every line). ──
        native_entries = self.env["account.move"].search([
            ("journal_id", "=", self.company.currency_exchange_journal_id.id),
        ])
        entry_1 = native_entries.filtered(lambda e: (receivable_line + payment_line_1) & e.line_ids.reconciled_lines_ids)
        entry_2 = native_entries.filtered(lambda e: (receivable_line + payment_line_2) & e.line_ids.reconciled_lines_ids)
        entry_3 = native_entries.filtered(lambda e: (receivable_line + payment_line_3) & e.line_ids.reconciled_lines_ids)
        self.assertEqual(len(entry_1), 1, "Installment 1 (USD/USD) must fire the native entry")
        self.assertEqual(len(entry_2), 1, "Installment 2 (USD invoice/VEF cash) must fire the native entry too")
        self.assertEqual(len(entry_3), 1, "Installment 3 (USD/USD) must fire the native entry")
        self.assertEqual(len(entry_1 | entry_2 | entry_3), 3, "Each installment gets its OWN entry, none shared")

        for entry in (entry_1, entry_2, entry_3):
            self.assertFalse(entry.l10n_ve_exchange_foreign_diff_entry)
            self.assertFalse(entry.line_ids.filtered(lambda l: l.foreign_debit or l.foreign_credit))

        native_1 = native_amount_of(entry_1)
        native_2 = native_amount_of(entry_2)
        native_3 = native_amount_of(entry_3)
        # Every rate here moved the SAME direction (VES weakening) on a
        # receivable being collected -- all three must read as losses.
        self.assertGreater(native_1, 0.0)
        self.assertGreater(native_2, 0.0)
        self.assertGreater(native_3, 0.0)
        self.assertAlmostEqual(native_1, 1000.0, places=2)   # 100 USD: 5000 - 4000
        self.assertAlmostEqual(native_2, 2000.0, places=2)   # 100 USD: 6000 - 4000
        self.assertAlmostEqual(native_3, 500.0, places=2)    # 100 USD: 4500 - 4000

        # ── 3) No standalone entry exists for this invoice: with a
        # foreign-currency invoice, native always has something to fix,
        # in either payment currency -- confirmed, not assumed. ──
        self.assertFalse(
            self.env["account.move"].search([("l10n_ve_exchange_foreign_source_move_id", "=", move.id)]),
            "A foreign-currency invoice should never need the standalone path, in any payment currency",
        )

        # ── 4) Nothing was flagged as an alternate-currency diff entry at
        # all for this invoice -- confirmed, not assumed. ──
        self.assertFalse(
            self.env["account.move"].search([("l10n_ve_exchange_foreign_diff_entry", "=", True)]),
            "A USD invoice must never produce an alternate-currency-flagged entry",
        )

    # ── Native + alternate case: same move, both amounts, native reversal ──

    def test_native_and_alternate_case_sets_both_amounts_on_same_move(self):
        """USD invoice, native VEF diff fires -- but no alternate amount
        may be injected, since the invoice's own USD exposure is already
        fixed and exact (double-counting a VEF-only difference).
        Ver openspec: design-notes.md § Exclusión: factura en moneda alterna
        """
        move = self._create_invoice(100.0, currency=self.currency_usd, booking_ves_per_usd=40.0)

        self._set_usd_rate(self.settlement_date, 50.0)

        native_before = self.env["account.move"].search([
            ("journal_id", "=", self.company.currency_exchange_journal_id.id),
        ])
        self._pay_invoice(move, amount=100.0, currency=self.currency_usd)
        native_after = self.env["account.move"].search([
            ("journal_id", "=", self.company.currency_exchange_journal_id.id),
        ])

        new_native_entries = native_after - native_before
        self.assertEqual(len(new_native_entries), 1, "Exactly one native entry, not a separate alternate one")
        entry = new_native_entries
        self.assertEqual(entry.state, "posted")
        self.assertFalse(
            entry.l10n_ve_exchange_foreign_diff_entry,
            "No alternate amount was injected -- the flag must not be set",
        )
        self.assertFalse(entry.line_ids.filtered(lambda l: l.foreign_debit or l.foreign_credit))
        # Native VEF fix still happens exactly as core computes it: the
        # invoice recorded 4000 VEF (100 USD @ 40), the payment settled at
        # 5000 VEF (100 USD @ 50) -- a pure VEF-side artifact.
        loss_line = entry.line_ids.filtered(lambda l: l.credit > 0.0)
        gain_line = entry.line_ids.filtered(lambda l: l.debit > 0.0)
        self.assertAlmostEqual(loss_line.credit, 1000.0, places=2)
        self.assertAlmostEqual(gain_line.debit, 1000.0, places=2)
        self.assertFalse(
            self.env["account.move"].search([("l10n_ve_exchange_foreign_source_move_id", "=", move.id)]),
            "No separate standalone entry should exist either -- there is nothing to fix in the alternate currency",
        )

    def test_no_exchange_difference_context_is_honored(self):
        """This feature must never create a standalone entry while core's
        own exchange-diff logic is suppressed under this context.
        """
        move = self._create_invoice(100.0, booking_ves_per_usd=40.0)
        self._set_usd_rate(self.settlement_date, 50.0)
        payment = self.env["account.payment"].with_company(self.company).create({
            "amount": move.amount_total,
            "date": self.settlement_date,
            "currency_id": self.currency_vef.id,
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner.id,
            "journal_id": self.bank_journal.id,
            "payment_method_line_id": self.bank_journal.inbound_payment_method_line_ids[:1].id,
        })
        payment.action_post()
        receivable_line = move.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        payment_line = payment.move_id.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        (receivable_line + payment_line).with_context(no_exchange_difference=True).reconcile()

        self.assertFalse(
            self.env["account.move"].search([("l10n_ve_exchange_foreign_source_move_id", "=", move.id)]),
            "No entry should be created while core's own exchange-diff logic is suppressed",
        )

    def test_amount_residual_currency_branch_is_covered(self):
        """VES invoice paid from a USD journal: core fixes this via the
        `amount_residual_currency` branch (`debit`/`credit` both 0).
        Ver openspec: design-notes.md § inject_foreign_exchange_amounts
        """
        move = self._create_invoice(100.0, booking_ves_per_usd=40.0)
        self._set_usd_rate(self.settlement_date, 50.0)

        before = self.env["account.move"].search([
            ("journal_id", "=", self.company.currency_exchange_journal_id.id),
        ])
        self._pay_invoice(move, amount=100.0 / 50.0, currency=self.currency_usd)
        after = self.env["account.move"].search([
            ("journal_id", "=", self.company.currency_exchange_journal_id.id),
        ])
        new_entries = after - before
        self.assertTrue(new_entries, "Must produce a native entry via the amount_residual_currency branch")
        self.assertTrue(
            any((l.foreign_debit or l.foreign_credit) for e in new_entries for l in e.line_ids),
            "The alternate-currency amount must be set even via this branch",
        )

    def test_ves_invoice_paid_in_foreign_currency_natively_balances_but_alternate_still_differs(self):
        """VEF invoice paid from a USD journal for an amount that exactly
        covers the VEF total: native has nothing to fix, but the alternate
        valuation of that VEF amount still moved -- this feature must
        catch it on its own via the standalone entry.
        """
        move = self._create_invoice(100.0, booking_ves_per_usd=40.0)
        self._set_usd_rate(self.settlement_date, 50.0)

        # Pay in USD, but with the EXACT amount that covers the VEF total
        # at the settlement-date rate -- native has nothing left to fix.
        usd_paid = move.amount_total / 50.0
        _payment, receivable_line, _payment_line = self._pay_invoice(move, amount=usd_paid, currency=self.currency_usd)

        # 1) The invoice's own VEF residual is genuinely, fully closed --
        # native "balanced the VEF", exactly as the business expects.
        self.assertTrue(receivable_line.reconciled)
        self.assertEqual(receivable_line.amount_residual, 0.0)

        # 2) Native never created a generic company-currency diff entry --
        # there was nothing in VEF for it to fix.
        native_entries = self.env["account.move"].search([
            ("journal_id", "=", self.company.currency_exchange_journal_id.id),
            ("l10n_ve_exchange_foreign_diff_entry", "=", False),
        ])
        self.assertFalse(native_entries, "Native must not create a generic VEF diff entry when VEF is exact")

        # 3) This feature still catches the alternate-currency movement on
        # its own, via its standalone entry.
        alt_entry = self.env["account.move"].search([
            ("l10n_ve_exchange_foreign_source_move_id", "=", move.id),
        ])
        self.assertEqual(len(alt_entry), 1, "The alternate-only difference must still be recorded")
        self.assertEqual(alt_entry.state, "posted")
        loss_line = alt_entry.line_ids.filtered(lambda l: l.foreign_credit > 0.0)
        gain_line = alt_entry.line_ids.filtered(lambda l: l.foreign_debit > 0.0)
        self.assertEqual(len(loss_line), 1, "VES devaluation (40 -> 50) on a receivable must be a loss")
        # 100 VEF * (1/40 - 1/50) = 0.5 USD
        self.assertAlmostEqual(loss_line.foreign_credit, 0.5, places=6)
        self.assertAlmostEqual(gain_line.foreign_debit, 0.5, places=6)
        for line in alt_entry.line_ids:
            self.assertEqual(line.debit, 0.0, "The standalone entry must never touch the VEF ledger")
            self.assertEqual(line.credit, 0.0)

    def test_native_case_reversed_automatically_via_core(self):
        """The injected alternate amounts ride along with core's own
        reversal mechanism (`account.partial.reconcile.exchange_move_id`)
        -- no custom reversal code needed for this case.
        """
        move = self._create_invoice(100.0, currency=self.currency_usd, booking_ves_per_usd=40.0)
        self._set_usd_rate(self.settlement_date, 50.0)

        native_before = self.env["account.move"].search([
            ("journal_id", "=", self.company.currency_exchange_journal_id.id),
        ])
        _payment, receivable_line, payment_line = self._pay_invoice(move, amount=100.0, currency=self.currency_usd)
        native_entry = self.env["account.move"].search([
            ("journal_id", "=", self.company.currency_exchange_journal_id.id),
        ]) - native_before

        (receivable_line + payment_line).remove_move_reconcile()

        self.assertTrue(native_entry.reversal_move_ids, "Core must reverse its own exchange move automatically")

    # ── `_reverse_moves`: foreign_debit/foreign_credit must be swapped per
    # line on the reversal, not zeroed or duplicated (bug fixed this session) ──

    def test_reverse_moves_swaps_foreign_debit_and_credit_for_standalone_entry(self):
        """Without the fix, `foreign_debit`/`foreign_credit` on the reversal
        stayed at 0/0 (or duplicated the original, unswapped) instead of
        being exactly inverted per line.
        """
        move = self._create_invoice(100.0, booking_ves_per_usd=40.0)
        self._set_usd_rate(self.settlement_date, 50.0)
        _payment, receivable_line, payment_line = self._pay_invoice(move)

        entry = self.env["account.move"].search([
            ("l10n_ve_exchange_foreign_source_move_id", "=", move.id),
        ])
        self.assertEqual(entry.state, "posted")
        original_lines = list(entry.line_ids)
        original_amounts = [(line.foreign_debit, line.foreign_credit) for line in original_lines]
        self.assertTrue(
            any(debit or credit for debit, credit in original_amounts),
            "Setup sanity: the original entry must carry a nonzero alternate amount",
        )

        (receivable_line + payment_line).remove_move_reconcile()

        reversal = entry.reversal_move_ids
        self.assertEqual(len(reversal), 1)
        reversal_lines = list(reversal.line_ids)
        self.assertEqual(len(reversal_lines), len(original_lines))
        for (orig_debit, orig_credit), rev_line in zip(original_amounts, reversal_lines):
            self.assertAlmostEqual(
                rev_line.foreign_debit, orig_credit, places=6,
                msg="The reversal's foreign_debit must equal the original line's foreign_credit",
            )
            self.assertAlmostEqual(
                rev_line.foreign_credit, orig_debit, places=6,
                msg="The reversal's foreign_credit must equal the original line's foreign_debit",
            )
        # At least one line must have actually flipped a nonzero amount --
        # otherwise the assertions above would trivially pass on all-zeros.
        self.assertTrue(any(rl.foreign_debit or rl.foreign_credit for rl in reversal_lines))

    def test_reverse_moves_swaps_foreign_debit_and_credit_for_combined_entry(self):
        """Same guarantee for the COMBINED case: core's own native entry,
        with the alternate amount injected on the same two lines.
        """
        move = self._create_invoice(100.0, booking_ves_per_usd=40.0)
        self._set_usd_rate(self.settlement_date, 50.0)

        before = self.env["account.move"].search([
            ("journal_id", "=", self.company.currency_exchange_journal_id.id),
        ])
        _payment, receivable_line, payment_line = self._pay_invoice(
            move, amount=100.0 / 50.0, currency=self.currency_usd,
        )
        entry = self.env["account.move"].search([
            ("journal_id", "=", self.company.currency_exchange_journal_id.id),
        ]) - before
        self.assertEqual(len(entry), 1)
        original_lines = list(entry.line_ids)
        original_amounts = [(line.foreign_debit, line.foreign_credit) for line in original_lines]
        self.assertTrue(any(debit or credit for debit, credit in original_amounts))

        (receivable_line + payment_line).remove_move_reconcile()

        reversal = entry.reversal_move_ids
        self.assertEqual(len(reversal), 1)
        reversal_lines = list(reversal.line_ids)
        for (orig_debit, orig_credit), rev_line in zip(original_amounts, reversal_lines):
            self.assertAlmostEqual(rev_line.foreign_debit, orig_credit, places=6)
            self.assertAlmostEqual(rev_line.foreign_credit, orig_debit, places=6)

    # ── `open_reconcile_view`: the standalone entry must surface in
    # "Reconciled Items" even though it is never itself reconciled ──

    @staticmethod
    def _domain_ids(action):
        """Extract the id list from the `[('id', 'in', ids)]` leaf core's
        `open_reconcile_view` builds -- parsed the same defensive way the
        override itself does, not by assuming a fixed index/shape.
        """
        for leaf in action['domain']:
            if isinstance(leaf, (list, tuple)) and len(leaf) == 3 and leaf[0] == 'id' and leaf[1] == 'in':
                return set(leaf[2])
        return set()

    def test_open_reconcile_view_includes_standalone_entry_lines(self):
        """Only the standalone entry's CLOSING line belongs in this view --
        its P&L counterpart line must be excluded.
        Ver openspec: design-notes.md § open_reconcile_view (Reconciled Items)
        """
        move = self._create_invoice(100.0, booking_ves_per_usd=40.0)
        self._set_usd_rate(self.settlement_date, 50.0)
        self._pay_invoice(move)

        entry = self.env["account.move"].search([
            ("l10n_ve_exchange_foreign_source_move_id", "=", move.id),
        ])
        self.assertTrue(entry, "Setup sanity: the standalone entry must exist")
        closing_line = entry.line_ids.filtered(
            lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
        )
        pnl_line = entry.line_ids - closing_line
        self.assertTrue(closing_line and pnl_line, "Setup sanity: both lines must exist")

        action = move.open_reconcile_view()
        self.assertEqual(action['res_model'], 'account.move.line')
        ids = self._domain_ids(action)
        self.assertTrue(
            set(closing_line.ids) <= ids,
            "The standalone entry's CLOSING line must be reachable from the invoice's Reconciled Items",
        )
        self.assertFalse(
            set(pnl_line.ids) & ids,
            "The standalone entry's P&L line must NOT appear -- it isn't the settled document's account",
        )

    def test_open_reconcile_view_without_standalone_matches_core(self):
        """No rate change at all -- no standalone entry exists, so this
        module's override must not add anything beyond core's own
        `_all_reconciled_lines()` result.
        """
        move = self._create_invoice(100.0, booking_ves_per_usd=40.0)
        self._pay_invoice(move)

        self.assertFalse(self.env["account.move"].search([
            ("l10n_ve_exchange_foreign_source_move_id", "=", move.id),
        ]))

        action = move.open_reconcile_view()
        core_ids = set(
            move.line_ids._all_reconciled_lines()
            .filtered(lambda l: l.matched_debit_ids or l.matched_credit_ids).ids
        )
        self.assertEqual(self._domain_ids(action), core_ids)

    def test_open_reconcile_view_excludes_reversed_standalone_entry_lines(self):
        """Once the standalone entry is reversed, its closing line must
        stop appearing in "Reconciled Items" -- the settlement it tracked
        is gone (bug fixed this session: it kept showing up after undoing
        the reconciliation, even with the entry already reversed).
        """
        move = self._create_invoice(100.0, booking_ves_per_usd=40.0)
        self._set_usd_rate(self.settlement_date, 50.0)
        _payment, receivable_line, payment_line = self._pay_invoice(move)

        entry = self.env["account.move"].search([
            ("l10n_ve_exchange_foreign_source_move_id", "=", move.id),
        ])
        closing_line = entry.line_ids.filtered(
            lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
        )
        ids_before = self._domain_ids(move.open_reconcile_view())
        self.assertTrue(set(closing_line.ids) <= ids_before, "Setup sanity: must be reachable before reversal")

        (receivable_line + payment_line).remove_move_reconcile()
        self.assertTrue(entry.reversal_move_ids, "Setup sanity: the entry must be reversed")

        ids_after = self._domain_ids(move.open_reconcile_view())
        self.assertFalse(
            set(closing_line.ids) & ids_after,
            "A reversed standalone entry's line must no longer appear in Reconciled Items",
        )

    # ── `_get_all_reconciled_invoice_partials`: surfaces the standalone
    # entry in the "Pagos" widget. `is_exchange=True` hides the dead
    # "Unreconcile" button (accepted cost: hardcoded row currency).
    # Ver openspec: design-notes.md § _get_all_reconciled_invoice_partials

    def test_get_all_reconciled_invoice_partials_adds_standalone_entry(self):
        move = self._create_invoice(100.0, booking_ves_per_usd=40.0)
        self._set_usd_rate(self.settlement_date, 50.0)
        self._pay_invoice(move)

        entry = self.env["account.move"].search([
            ("l10n_ve_exchange_foreign_source_move_id", "=", move.id),
        ])
        self.assertTrue(entry, "Setup sanity: the standalone entry must exist")

        partials = move._get_all_reconciled_invoice_partials()
        synthetic = [p for p in partials if p['aml'].move_id == entry]
        self.assertEqual(len(synthetic), 1)
        partial = synthetic[0]
        self.assertFalse(partial['partial_id'], "No real partial backs this row -- must stay False")
        self.assertEqual(partial['currency'], self.currency_usd)
        self.assertAlmostEqual(partial['amount'], 0.5, places=6)
        self.assertTrue(
            partial['is_exchange'],
            "Must be True so the popover hides the dead 'Unreconcile' button -- the accepted cost "
            "is the row's currency getting hardcoded to the company currency downstream",
        )

    def test_get_all_reconciled_invoice_partials_unchanged_without_standalone_entry(self):
        """No rate change at all -- no standalone entry exists, so this
        override must return exactly what core's own method already
        returns, nothing more.
        """
        move = self._create_invoice(100.0, booking_ves_per_usd=40.0)
        self._pay_invoice(move)

        self.assertFalse(self.env["account.move"].search([
            ("l10n_ve_exchange_foreign_source_move_id", "=", move.id),
        ]))

        partials = move._get_all_reconciled_invoice_partials()
        self.assertTrue(partials, "The real payment reconciliation must still be there")
        self.assertFalse(any(p['partial_id'] is False for p in partials))

    def test_get_all_reconciled_invoice_partials_excludes_reversed_standalone_entry(self):
        """Once the standalone entry is reversed, its synthetic row must
        disappear from the "Pagos" widget data -- fixed this session
        (it kept showing up after undoing the reconciliation).
        """
        move = self._create_invoice(100.0, booking_ves_per_usd=40.0)
        self._set_usd_rate(self.settlement_date, 50.0)
        _payment, receivable_line, payment_line = self._pay_invoice(move)

        entry = self.env["account.move"].search([
            ("l10n_ve_exchange_foreign_source_move_id", "=", move.id),
        ])
        self.assertTrue(
            any(p['aml'].move_id == entry for p in move._get_all_reconciled_invoice_partials()),
            "Setup sanity: must be present before reversal",
        )

        (receivable_line + payment_line).remove_move_reconcile()
        self.assertTrue(entry.reversal_move_ids, "Setup sanity: the entry must be reversed")

        partials_after = move._get_all_reconciled_invoice_partials()
        self.assertFalse(
            any(p['aml'].move_id == entry for p in partials_after),
            "A reversed standalone entry must not produce a synthetic row anymore",
        )

    def test_payments_widget_standalone_case_shows_amount_and_hides_unreconcile(self):
        """End-to-end via the real `invoice_payments_widget`: the row shows
        the real 0.5 amount, no real partial, currency hardcoded to VEF.
        Ver openspec: design-notes.md § _get_all_reconciled_invoice_partials
        """
        move = self._create_invoice(100.0, booking_ves_per_usd=40.0)
        self._set_usd_rate(self.settlement_date, 50.0)
        self._pay_invoice(move)

        entry = self.env["account.move"].search([
            ("l10n_ve_exchange_foreign_source_move_id", "=", move.id),
        ])
        widget = move.invoice_payments_widget
        self.assertTrue(widget)
        rows = [r for r in widget['content'] if r.get('move_id') == entry.id]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['currency_id'], self.currency_vef.id)
        self.assertAlmostEqual(row['amount'], 0.5, places=6)
        self.assertFalse(row['partial_id'])

    def test_payments_widget_no_synthetic_row_when_no_standalone_entry(self):
        move = self._create_invoice(100.0, booking_ves_per_usd=40.0)
        self._pay_invoice(move)  # no rate change -> no standalone entry at all
        widget = move.invoice_payments_widget
        self.assertTrue(widget, "A plain reconciled payment must still produce core's own row")
        self.assertFalse(any(r.get('partial_id') is False for r in widget['content']))

    def test_payments_widget_hides_row_after_standalone_entry_reversed(self):
        """End-to-end: after undoing the reconciliation, the widget must no
        longer show the "Diferencial de cambio" row for the reversed entry.
        """
        move = self._create_invoice(100.0, booking_ves_per_usd=40.0)
        self._set_usd_rate(self.settlement_date, 50.0)
        _payment, receivable_line, payment_line = self._pay_invoice(move)

        entry = self.env["account.move"].search([
            ("l10n_ve_exchange_foreign_source_move_id", "=", move.id),
        ])
        rows_before = [r for r in move.invoice_payments_widget['content'] if r.get('move_id') == entry.id]
        self.assertEqual(len(rows_before), 1, "Setup sanity: the row must be present before reversal")

        (receivable_line + payment_line).remove_move_reconcile()
        self.assertTrue(entry.reversal_move_ids, "Setup sanity: the entry must be reversed")
        move.invalidate_recordset(['invoice_payments_widget'])

        # Undoing the reconciliation entirely can collapse the widget to
        # `False` (core's own behavior when there is nothing left to show
        # at all) -- either way, the reversed entry's row must be gone.
        widget_after = move.invoice_payments_widget
        rows_after = [r for r in widget_after['content'] if r.get('move_id') == entry.id] if widget_after else []
        self.assertFalse(rows_after, "A reversed standalone entry must not show up in the Pagos widget")

    # ── `account.partial.reconcile.unlink()`: safety net for the reversal ──
    # Ver openspec: design-notes.md § account_partial_reconcile.unlink()

    def test_partial_reconcile_unlink_does_not_double_reverse(self):
        """Normal path: core's own `unlink()` already reverses
        `exchange_move_id` -- the safety net must stay a no-op and NOT
        produce a second reversal of the same entry.
        """
        move = self._create_invoice(100.0, booking_ves_per_usd=40.0)
        self._set_usd_rate(self.settlement_date, 50.0)
        _payment, receivable_line, payment_line = self._pay_invoice(move)

        entry = self.env["account.move"].search([
            ("l10n_ve_exchange_foreign_source_move_id", "=", move.id),
        ])
        (receivable_line + payment_line).remove_move_reconcile()

        self.assertEqual(
            len(entry.reversal_move_ids), 1,
            "The safety net must not create a second reversal on top of core's own",
        )

    def test_partial_reconcile_unlink_safety_net_reverses_when_core_did_not(self):
        """Forces the exact scenario the safety net exists for: core's own
        `unlink()` runs but (simulated here) fails to reverse
        `exchange_move_id` -- the override must still reverse it itself.

        `_reverse_moves` is patched to no-op on its FIRST call (standing in
        for core's own internal reversal call, inside `super().unlink()`)
        and to behave normally from the second call onward (this module's
        own safety-net call, made explicitly after `super().unlink()`).
        """
        move = self._create_invoice(100.0, booking_ves_per_usd=40.0)
        self._set_usd_rate(self.settlement_date, 50.0)
        _payment, receivable_line, payment_line = self._pay_invoice(move)

        entry = self.env["account.move"].search([
            ("l10n_ve_exchange_foreign_source_move_id", "=", move.id),
        ])
        self.assertEqual(entry.state, "posted")
        partial = self.env["account.partial.reconcile"].search([
            ("debit_move_id", "in", (receivable_line.id, payment_line.id)),
            ("credit_move_id", "in", (receivable_line.id, payment_line.id)),
        ])
        self.assertEqual(partial.exchange_move_id, entry)

        move_model = type(entry)
        original_reverse_moves = move_model._reverse_moves
        # Only calls involving `entry` itself matter -- an unrelated
        # `account_accountant` deferral-move `_reverse_moves()` call (on an
        # empty recordset) is also triggered by this same `unlink()` and
        # must be ignored here.
        calls_on_entry = []

        def fake_reverse_moves(self, *args, **kwargs):
            if entry.id in self.ids:
                calls_on_entry.append(self)
                if len(calls_on_entry) == 1:
                    # Simulate core's own reversal call silently doing nothing.
                    return self.browse()
            return original_reverse_moves(self, *args, **kwargs)

        with patch.object(move_model, '_reverse_moves', fake_reverse_moves):
            partial.unlink()

        self.assertEqual(
            len(calls_on_entry), 2,
            "Both core's own call and the safety net's call on `entry` must have happened",
        )
        entry.invalidate_recordset()
        self.assertTrue(
            entry.reversal_move_ids,
            "The safety net must reverse the entry itself when core's own path did not",
        )
