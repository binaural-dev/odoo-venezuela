from odoo import Command
from odoo.addons.l10n_ve_exchange_difference.models.account_move_line import CLOSING_NOTE_LINE_KEY
from odoo.tests import Form, tagged

from .test_exchange_note_reversal import TestExchangeNoteReversal


@tagged("l10n_ve_exchange_difference", "-at_install", "post_install")
class TestExchangeNoteBsOnly(TestExchangeNoteReversal):
    """The exchange difference note (a company-currency document) must be
    closed in company currency ONLY: its crossing never consumes foreign
    balance of the line it is closed against, even when that line still
    holds foreign balance (partial settlement). Also covers how the notes
    show up in the invoice "Paid/Reversed" widget.

    Subclasses `TestExchangeNoteReversal` to reuse its fixture (same known
    re-execution cost as `TestExchangeNoteMixedFlow`)."""

    GAIN_DATE = "2026-05-01"   # rate 44 > invoice rate 40 -> gain -> debit note
    LOSS_DATE = "2026-08-01"   # rate 36 < invoice rate 40 -> loss -> credit note

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usd.write({
            "rate_ids": [Command.create({"name": cls.GAIN_DATE, "company_rate": 1 / 44.0})],
        })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _receivable(self, move):
        return move.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

    def _make_invoice(self, usd_amount, invoice_date="2026-01-01"):
        with Form(self.env["account.move"].with_context(default_move_type="out_invoice")) as form:
            form.partner_id = self.partner
            form.invoice_date = invoice_date
            form.journal_id = self.sale_journal
            form.currency_id = self.usd
        invoice = form.save()
        with Form(invoice) as form_edit:
            with form_edit.invoice_line_ids.new() as line:
                line.product_id = self.sale_product
                line.quantity = 1
                line.price_unit = usd_amount
        invoice = form_edit.save()
        invoice.with_context(move_action_post_alert=True).action_post()
        return invoice

    def _make_payment(self, usd_amount, date):
        payment = self.env["account.payment"].create({
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner.id,
            "amount": usd_amount,
            "currency_id": self.usd.id,
            "journal_id": self.usd_bank_journal.id,
            "date": date,
        })
        payment.action_post()
        return payment

    def _settle(self, invoice, payment):
        """Reconciles invoice and payment through `reconcile()` (the entry
        point this module hooks), like the payments widget does."""
        (self._receivable(invoice) + self._receivable(payment.move_id)).reconcile()
        self.env.cr.flush()
        self.env.invalidate_all()

    def _notes(self, invoice):
        return self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("l10n_ve_exchange_invoice_id", "=", invoice.id),
        ])

    def _note_partials(self, note):
        note_line = self._receivable(note)
        return note_line.matched_debit_ids | note_line.matched_credit_ids

    def _foreign_amount_of_partial(self, partial, foreign_line):
        """Foreign-currency amount the partial carries on `foreign_line`."""
        if partial.debit_move_id == foreign_line:
            return partial.debit_amount_currency
        self.assertEqual(partial.credit_move_id, foreign_line)
        return partial.credit_amount_currency

    def _pair_partial(self, line_a, line_b):
        partials = (line_a.matched_debit_ids | line_a.matched_credit_ids).filtered(
            lambda p: line_b in (p.debit_move_id | p.credit_move_id)
        )
        self.assertEqual(len(partials), 1)
        return partials

    # ------------------------------------------------------------------
    # A. Totals
    # ------------------------------------------------------------------

    def test_full_application_loss_credit_note_is_bs_only(self):
        invoice = self._make_invoice(100.0)
        payment = self._make_payment(100.0, self.LOSS_DATE)
        self._settle(invoice, payment)
        notes = self._notes(invoice)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes.move_type, "out_refund")
        partials = self._note_partials(notes)
        self.assertEqual(len(partials), 1)
        inv_line = self._receivable(invoice)
        self.assertAlmostEqual(self._foreign_amount_of_partial(partials, inv_line), 0.0, places=2)
        self.assertAlmostEqual(inv_line.amount_residual, 0.0, places=2)
        self.assertAlmostEqual(inv_line.amount_residual_currency, 0.0, places=2)
        self.assertEqual(invoice.payment_state, "paid")

    def test_full_application_gain_debit_note_is_bs_only(self):
        invoice = self._make_invoice(100.0)
        payment = self._make_payment(100.0, self.GAIN_DATE)
        self._settle(invoice, payment)
        notes = self._notes(invoice)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes.move_type, "out_invoice")
        partials = self._note_partials(notes)
        self.assertEqual(len(partials), 1)
        pay_line = self._receivable(payment.move_id)
        self.assertAlmostEqual(self._foreign_amount_of_partial(partials, pay_line), 0.0, places=2)
        self.assertAlmostEqual(pay_line.amount_residual, 0.0, places=2)
        self.assertAlmostEqual(pay_line.amount_residual_currency, 0.0, places=2)
        self.assertAlmostEqual(self._receivable(invoice).amount_residual_currency, 0.0, places=2)

    def test_partial_application_loss_credit_note_keeps_foreign_balance(self):
        """Invoice 100 USD, payment 40 USD: the credit note closes against
        the invoice line, which still holds 60 USD."""
        invoice = self._make_invoice(100.0)
        payment = self._make_payment(40.0, self.LOSS_DATE)
        inv_line = self._receivable(invoice)
        original_balance = inv_line.balance
        self._settle(invoice, payment)

        notes = self._notes(invoice)
        self.assertEqual(len(notes), 1)
        note = notes
        self.assertEqual(note.move_type, "out_refund")
        partials = self._note_partials(note)
        self.assertEqual(len(partials), 1, "The note must be reconciled with exactly one partial.")
        self.assertAlmostEqual(self._foreign_amount_of_partial(partials, inv_line), 0.0, places=2)

        self.assertAlmostEqual(inv_line.amount_residual_currency, 60.0, places=2)
        self.assertAlmostEqual(invoice.amount_residual, 60.0, places=2)
        pay_line = self._receivable(payment.move_id)
        self.assertAlmostEqual(pay_line.amount_residual_currency, 0.0, places=2)
        pair = self._pair_partial(inv_line, pay_line)
        # Company-currency balance dropped by the payment crossing plus
        # EXACTLY the note amount.
        self.assertAlmostEqual(
            inv_line.amount_residual,
            original_balance - pair.amount - abs(note.amount_total_signed),
            places=2,
        )
        self.assertAlmostEqual(inv_line.amount_residual, 60.0 * self.rate_invoice_date, places=1)

    def test_partial_application_gain_debit_note_keeps_foreign_balance(self):
        """Invoice 40 USD, payment 100 USD: the debit note closes against
        the payment line, which still holds 60 USD."""
        invoice = self._make_invoice(40.0)
        payment = self._make_payment(100.0, self.GAIN_DATE)
        pay_line = self._receivable(payment.move_id)
        original_balance = pay_line.balance
        self._settle(invoice, payment)

        note = self._notes(invoice)
        self.assertEqual(len(note), 1)
        self.assertEqual(note.move_type, "out_invoice")
        partials = self._note_partials(note)
        self.assertEqual(len(partials), 1, "The note must be reconciled with exactly one partial.")
        self.assertAlmostEqual(self._foreign_amount_of_partial(partials, pay_line), 0.0, places=2)

        self.assertAlmostEqual(pay_line.amount_residual_currency, -60.0, places=2)
        self.assertEqual(invoice.payment_state, "paid")
        pair = self._pair_partial(self._receivable(invoice), pay_line)
        self.assertAlmostEqual(
            pay_line.amount_residual,
            original_balance + pair.amount + abs(note.amount_total_signed),
            places=2,
        )

    def test_two_partial_payments_then_full_payment_closes_invoice(self):
        """The guard is per (invoice, payment) pair, so every payment gets
        its own note; the invoice ends fully paid in both currencies."""
        invoice = self._make_invoice(100.0)
        inv_line = self._receivable(invoice)
        for usd_amount in (40.0, 30.0, 30.0):
            self._settle(invoice, self._make_payment(usd_amount, self.LOSS_DATE))
        self.assertEqual(len(self._notes(invoice)), 3)
        for note in self._notes(invoice):
            self.assertEqual(len(self._note_partials(note)), 1)
        self.assertAlmostEqual(inv_line.amount_residual, 0.0, places=2)
        self.assertAlmostEqual(inv_line.amount_residual_currency, 0.0, places=2)
        self.assertAlmostEqual(invoice.amount_residual, 0.0, places=2)
        self.assertEqual(invoice.payment_state, "paid")

    # ------------------------------------------------------------------
    # Detector and override contract
    # ------------------------------------------------------------------

    def _loss_fixture(self):
        invoice = self._make_invoice(100.0)
        payment = self._make_payment(40.0, self.LOSS_DATE)
        self._settle(invoice, payment)
        note = self._notes(invoice)
        return invoice, payment, note

    def _values(self, aml, residual, residual_currency):
        return {
            "aml": aml,
            "amount_residual": residual,
            "amount_residual_currency": residual_currency,
        }

    def _detect(self, debit_values, credit_values, closing_line=None):
        model = self.env["account.move.line"]
        if closing_line is not None:
            model = model.with_context(**{CLOSING_NOTE_LINE_KEY: closing_line.id})
        return model._l10n_ve_note_foreign_values(debit_values, credit_values)

    def test_detector_cases(self):
        invoice, payment, note = self._loss_fixture()
        note_line = self._receivable(note)
        inv_line = self._receivable(invoice)
        pay_line = self._receivable(payment.move_id)
        note_values = self._values(note_line, -160.0, -160.0)
        foreign_values = self._values(inv_line, 2560.0, 60.0)

        self.assertIsNone(self._detect(foreign_values, note_values), "No closing key in context.")
        self.assertIs(self._detect(foreign_values, note_values, note_line), foreign_values)
        # Debit note flavour: note on the debit side, foreign line on the credit side.
        debit_note_values = self._values(note_line, 160.0, 160.0)
        credit_foreign_values = self._values(pay_line, -2560.0, -60.0)
        self.assertIs(
            self._detect(debit_note_values, credit_foreign_values, note_line), credit_foreign_values,
        )
        # Closing key pointing to another line.
        self.assertIsNone(self._detect(foreign_values, note_values, inv_line))
        # Note against note (reversal-like pair).
        self.assertIsNone(self._detect(
            self._values(note_line, 160.0, 160.0), self._values(note_line, -160.0, -160.0), note_line,
        ))
        # No note involved.
        self.assertIsNone(self._detect(
            self._values(inv_line, 2560.0, 60.0), self._values(pay_line, -2560.0, -60.0), inv_line,
        ))
        # Counterpart in company currency.
        ves_invoice = self._create_invoice_company_currency("2026-01-01")
        ves_invoice.with_context(move_action_post_alert=True).action_post()
        ves_values = self._values(self._receivable(ves_invoice), 4000.0, 4000.0)
        self.assertIsNone(self._detect(ves_values, note_values, note_line))
        # Counterpart without foreign balance.
        self.assertIsNone(self._detect(self._values(inv_line, 2560.0, 0.0), note_values, note_line))
        # Counterpart company-currency balance <= note amount.
        self.assertIsNone(self._detect(self._values(inv_line, 160.0, 60.0), note_values, note_line))
        self.assertIsNone(self._detect(self._values(inv_line, 100.0, 60.0), note_values, note_line))

    def test_override_does_not_mutate_foreign_residual_of_original_dict(self):
        """Pins the core contract this relies on: residuals are read from
        the dicts it receives and written back to them, and the returned
        `debit_values`/`credit_values` are those same dicts (or None)."""
        invoice, _payment, note = self._loss_fixture()
        note_line = self._receivable(note)
        inv_line = self._receivable(invoice)
        model = self.env["account.move.line"]

        def run(context):
            foreign_values = self._values(inv_line, 2560.0, 60.0)
            note_values = self._values(note_line, -160.0, -160.0)
            res = model.with_context(no_exchange_difference=True, **context)._prepare_reconciliation_single_partial(
                foreign_values, note_values,
            )
            return foreign_values, note_values, res

        foreign_values, note_values, res = run({CLOSING_NOTE_LINE_KEY: note_line.id})
        self.assertAlmostEqual(foreign_values["amount_residual_currency"], 60.0, places=2)
        self.assertAlmostEqual(foreign_values["amount_residual"], 2400.0, places=2)
        self.assertIs(res["debit_values"], foreign_values)
        self.assertIsNone(res["credit_values"], "The note is fully matched.")
        self.assertAlmostEqual(res["partial_values"]["debit_amount_currency"], 0.0, places=2)
        self.assertAlmostEqual(res["partial_values"]["amount"], 160.0, places=2)

        # Control: without the key the core invents a foreign equivalent.
        _foreign, _note, res_core = run({})
        self.assertGreater(res_core["partial_values"]["debit_amount_currency"], 0.0)

    def test_override_inactive_with_shadowed_aml_values(self):
        invoice, _payment, note = self._loss_fixture()
        note_line = self._receivable(note)
        inv_line = self._receivable(invoice)
        model = self.env["account.move.line"].with_context(
            no_exchange_difference=True, **{CLOSING_NOTE_LINE_KEY: note_line.id},
        )
        res = model._prepare_reconciliation_single_partial(
            self._values(inv_line, 2560.0, 60.0), self._values(note_line, -160.0, -160.0),
            shadowed_aml_values={inv_line: {}},
        )
        self.assertGreater(res["partial_values"]["debit_amount_currency"], 0.0)

    # ------------------------------------------------------------------
    # Reversal and unchanged flows
    # ------------------------------------------------------------------

    def test_breaking_reconciliation_after_bs_only_note_reverses_it(self):
        invoice, payment, note = self._loss_fixture()
        inv_line = self._receivable(invoice)
        partial = self._pair_partial(inv_line, self._receivable(payment.move_id))
        invoice.js_remove_outstanding_partial(partial.id)
        self.env.cr.flush()
        self.env.invalidate_all()
        self.assertEqual(note.state, "posted")
        self.assertEqual(len(note.reversal_move_ids), 1)

    def test_company_currency_invoice_paid_in_usd_still_has_no_note(self):
        invoice = self._create_invoice_company_currency("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        payment = self._make_payment(100.0, self.LOSS_DATE)
        self._settle(invoice, payment)
        self.assertFalse(self._notes(invoice))

    def test_toggle_off_uses_native_exchange_entry(self):
        self.company.l10n_ve_exchange_use_nd_nc = False
        invoice = self._make_invoice(100.0)
        payment = self._make_payment(100.0, self.LOSS_DATE)
        self._settle(invoice, payment)
        self.assertFalse(self._notes(invoice))
        rows = invoice.sudo()._get_all_reconciled_invoice_partials()
        exchange_rows = [r for r in rows if r["is_exchange"]]
        self.assertEqual(len(exchange_rows), 1, "The native exchange entry shows up as before.")
        self.assertFalse(exchange_rows[0]["aml"].move_id.l10n_ve_exchange_diff_entry)
        widget_rows = invoice.invoice_payments_widget["content"]
        self.assertFalse(any(r.get("is_exchange_note") for r in widget_rows))
        self.assertEqual(len([r for r in widget_rows if not r["is_exchange"]]), 1)

    # ------------------------------------------------------------------
    # C. "Paid/Reversed" widget
    # ------------------------------------------------------------------

    def _assert_one_note_row(self, invoice, note):
        rows = [r for r in invoice.sudo()._get_all_reconciled_invoice_partials() if r["is_exchange"]]
        self.assertEqual(len(rows), 1, "One row per live note.")
        row = rows[0]
        self.assertEqual(row["currency"], self.company.currency_id)
        self.assertAlmostEqual(row["amount"], abs(note.amount_total_signed), places=2)
        self.assertEqual(row["aml"], self._receivable(note))
        self.assertIn(row["partial_id"], self._note_partials(note).ids, "A real partial id is kept.")

        invoice.invalidate_recordset()
        content = invoice.invoice_payments_widget["content"]
        note_rows = [r for r in content if r.get("is_exchange_note")]
        self.assertEqual(len(note_rows), 1)
        self.assertEqual(note_rows[0]["exchange_note_name"], note.name)
        self.assertEqual(note_rows[0]["move_id"], note.id)
        self.assertTrue(note_rows[0]["is_exchange"])
        self.assertEqual(note_rows[0]["currency_id"], self.company.currency_id.id)
        # The payment row is a normal one.
        payment_rows = [r for r in content if not r["is_exchange"]]
        self.assertEqual(len(payment_rows), 1)
        self.assertFalse(payment_rows[0].get("is_exchange_note"))

    def test_widget_row_for_credit_note_closed_against_invoice(self):
        invoice, _payment, note = self._loss_fixture()
        self.assertEqual(note.move_type, "out_refund")
        self._assert_one_note_row(invoice, note)

    def test_widget_row_for_debit_note_closed_against_payment(self):
        invoice = self._make_invoice(40.0)
        payment = self._make_payment(100.0, self.GAIN_DATE)
        self._settle(invoice, payment)
        note = self._notes(invoice)
        self.assertEqual(note.move_type, "out_invoice")
        self._assert_one_note_row(invoice, note)

    def test_widget_does_not_list_reversed_note(self):
        invoice, payment, note = self._loss_fixture()
        partial = self._pair_partial(self._receivable(invoice), self._receivable(payment.move_id))
        invoice.js_remove_outstanding_partial(partial.id)
        self.env.cr.flush()
        self.env.invalidate_all()
        self.assertTrue(note.reversal_move_ids)
        rows = invoice.sudo()._get_all_reconciled_invoice_partials()
        self.assertFalse([r for r in rows if r["aml"].move_id.l10n_ve_exchange_diff_entry])
        content = (invoice.invoice_payments_widget or {}).get("content", [])
        self.assertFalse([r for r in content if r.get("is_exchange_note")])
