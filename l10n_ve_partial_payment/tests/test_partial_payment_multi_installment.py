from odoo import Command, fields
from odoo.tests import Form, tagged

from .test_partial_payment_common import PartialPaymentTestCommon


@tagged("post_install", "-at_install", "l10n_ve_partial_payment")
class TestPartialPaymentMultiInstallment(PartialPaymentTestCommon):
    """Coverage of the shared-budget cap in
    ``account_move_line._prepare_reconciliation_amls`` when the invoice's
    payment term has more than one installment line.

    Before the fix, each installment line was capped INDEPENDENTLY to
    ``min(paid_amount, residual)``, so a 2x50 payment term applying a
    requested 60 would let each installment independently claim up to 50,
    over-applying 100 instead of 60. These tests reconcile a plain
    payment's outstanding line against such a multi-installment invoice and
    assert the TOTAL applied never exceeds the requested amount, and that
    it is distributed oldest-due-date first.
    """

    def _create_invoice_vef_with_term(self, amount, term):
        """Like ``IGTFTestCommon._create_invoice_vef`` but assigning a
        custom ``invoice_payment_term_id`` instead of the default one, so
        the resulting invoice has more than one open receivable line."""
        sale_journal = self.Journal.search(
            [
                ("type", "=", "sale"),
                ("company_id", "=", self.company.id),
                ("is_debit", "=", False),
            ],
            limit=1,
        )
        if not sale_journal:
            sale_journal = self.Journal.create(
                {
                    "name": "Diario Venta",
                    "type": "sale",
                    "code": "SALE",
                    "company_id": self.company.id,
                    "currency_id": self.currency_vef.id,
                }
            )

        with Form(
            self.env["account.move"].with_context(
                default_move_type="out_invoice", default_journal_id=sale_journal
            )
        ) as inv_form:
            inv_form.partner_id = self.partner
            inv_form.invoice_date = fields.Date.today()
            inv_form.currency_id = self.currency_vef
            inv_form.invoice_payment_term_id = term
            inv_form.save()

        inv = inv_form.save()
        with Form(inv) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product
                line.quantity = 1
                line.price_unit = amount

        return inv_form_edit.save()

    def _receivable_lines(self, invoice):
        """Return the invoice's open receivable lines, ordered by
        ``date_maturity`` then ``id`` (oldest due date first)."""
        return invoice.line_ids.filtered(
            lambda l: l.account_id == self.acc_receivable
        ).sorted(key=lambda l: (l.date_maturity or l.date, l.id))

    # -- 1. 2x50 term, apply 60: cuota 1 full, cuota 2 partial ---------------

    def test_two_installments_50_50_apply_60_caps_shared_budget(self):
        term = self.env["account.payment.term"].create(
            {
                "name": "term_50_50",
                "line_ids": [
                    Command.create(
                        {"value": "percent", "value_amount": 50.0, "nb_days": 0}
                    ),
                    Command.create(
                        {"value": "percent", "value_amount": 50.0, "nb_days": 30}
                    ),
                ],
            }
        )
        invoice = self._create_invoice_vef_with_term(100.00, term)
        invoice.with_context(move_action_post_alert=True).action_post()

        payment = self._create_plain_payment(self.bank_journal_bs, 100.00)
        line = self._outstanding_line_for_payment(payment, self.acc_receivable)

        partials_before = self.env["account.partial.reconcile"].search_count([])

        self._apply_partial(invoice, line, 60.00)
        invoice = self.env["account.move"].browse(invoice.id)

        installment_1, installment_2 = self._receivable_lines(invoice)

        self.assertAlmostEqual(installment_1.amount_residual, 0.0, places=2)
        self.assertAlmostEqual(abs(installment_2.amount_residual), 40.00, places=2)
        self.assertAlmostEqual(invoice.amount_residual, 40.00, places=2)

        partials_created = (
            self.env["account.partial.reconcile"].search_count([]) - partials_before
        )
        self.assertEqual(partials_created, 2)

    # -- 2. Apply exactly 50: only cuota 1 touched, cuota 2 intact -----------

    def test_two_installments_50_50_apply_exactly_50_leaves_second_untouched(self):
        term = self.env["account.payment.term"].create(
            {
                "name": "term_50_50_exact",
                "line_ids": [
                    Command.create(
                        {"value": "percent", "value_amount": 50.0, "nb_days": 0}
                    ),
                    Command.create(
                        {"value": "percent", "value_amount": 50.0, "nb_days": 30}
                    ),
                ],
            }
        )
        invoice = self._create_invoice_vef_with_term(100.00, term)
        invoice.with_context(move_action_post_alert=True).action_post()

        payment = self._create_plain_payment(self.bank_journal_bs, 100.00)
        line = self._outstanding_line_for_payment(payment, self.acc_receivable)

        partials_before = self.env["account.partial.reconcile"].search_count([])

        self._apply_partial(invoice, line, 50.00)
        invoice = self.env["account.move"].browse(invoice.id)

        installment_1, installment_2 = self._receivable_lines(invoice)

        self.assertAlmostEqual(installment_1.amount_residual, 0.0, places=2)
        self.assertAlmostEqual(abs(installment_2.amount_residual), 50.00, places=2)
        self.assertFalse(installment_2.reconciled)

        partials_created = (
            self.env["account.partial.reconcile"].search_count([]) - partials_before
        )
        self.assertEqual(partials_created, 1)

    # -- 3. Apply 30: only cuota 1 partially touched, cuota 2 intact ---------

    def test_two_installments_50_50_apply_30_only_touches_first(self):
        term = self.env["account.payment.term"].create(
            {
                "name": "term_50_50_partial",
                "line_ids": [
                    Command.create(
                        {"value": "percent", "value_amount": 50.0, "nb_days": 0}
                    ),
                    Command.create(
                        {"value": "percent", "value_amount": 50.0, "nb_days": 30}
                    ),
                ],
            }
        )
        invoice = self._create_invoice_vef_with_term(100.00, term)
        invoice.with_context(move_action_post_alert=True).action_post()

        payment = self._create_plain_payment(self.bank_journal_bs, 100.00)
        line = self._outstanding_line_for_payment(payment, self.acc_receivable)

        self._apply_partial(invoice, line, 30.00)
        invoice = self.env["account.move"].browse(invoice.id)

        installment_1, installment_2 = self._receivable_lines(invoice)

        self.assertAlmostEqual(abs(installment_1.amount_residual), 20.00, places=2)
        self.assertAlmostEqual(abs(installment_2.amount_residual), 50.00, places=2)

    # -- 4. Due dates inverted vs. line creation order/id --------------------

    def test_budget_follows_due_date_not_creation_order(self):
        """The second payment-term line has FEWER days than the first, so
        its installment is actually due BEFORE the first one created (and
        therefore has a lower ``id``... but an earlier maturity date on the
        LATER-created term line). The shared budget must still consume the
        installment with the earliest ``date_maturity`` first, regardless
        of creation order/id."""
        term = self.env["account.payment.term"].create(
            {
                "name": "term_inverted_due_dates",
                "line_ids": [
                    Command.create(
                        {"value": "percent", "value_amount": 50.0, "nb_days": 30}
                    ),
                    Command.create(
                        {"value": "percent", "value_amount": 50.0, "nb_days": 0}
                    ),
                ],
            }
        )
        invoice = self._create_invoice_vef_with_term(100.00, term)
        invoice.with_context(move_action_post_alert=True).action_post()

        payment = self._create_plain_payment(self.bank_journal_bs, 100.00)
        line = self._outstanding_line_for_payment(payment, self.acc_receivable)

        receivables_by_creation = invoice.line_ids.filtered(
            lambda l: l.account_id == self.acc_receivable
        ).sorted("id")
        # The line created FIRST (lower id) has nb_days=30 -> later due
        # date; the line created SECOND (higher id) has nb_days=0 -> the
        # earliest due date.
        earliest_due_line = receivables_by_creation[1]
        latest_due_line = receivables_by_creation[0]
        self.assertLess(
            earliest_due_line.date_maturity, latest_due_line.date_maturity
        )

        self._apply_partial(invoice, line, 60.00)

        earliest_due_line = self.env["account.move.line"].browse(
            earliest_due_line.id
        )
        latest_due_line = self.env["account.move.line"].browse(latest_due_line.id)

        # The earliest-due installment (created SECOND, lower nb_days) must
        # be the one fully consumed first by the shared budget.
        self.assertAlmostEqual(abs(earliest_due_line.amount_residual), 0.0, places=2)
        self.assertAlmostEqual(abs(latest_due_line.amount_residual), 40.00, places=2)
