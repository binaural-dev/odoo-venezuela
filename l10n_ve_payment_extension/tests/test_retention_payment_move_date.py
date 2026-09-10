import logging

from odoo.tests import tagged, Form
from odoo import Command, fields

from .test_withholding_common_VEF import RetentionTestCommon

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "retention_payment_move_date")
class TestRetentionPaymentMoveDate(RetentionTestCommon):
    """A retention payment's journal entry must be dated (and rated) with
    the retention's own date_accounting, like any other payment -- there is
    no special-casing to pin it to the invoice's own date instead. An
    earlier version of this module added such an override based on
    outdated documentation; it was reverted, and this test now asserts the
    actual expected behavior instead."""

    def setUp(self):
        super().setUp()
        self.invoice_date = fields.Date.today().replace(day=1)
        self.date_accounting = fields.Date.today()

        self._set_rate(self.currency_usd, self.invoice_date, 40.0)
        self._set_rate(self.currency_usd, self.date_accounting, 60.0)

        # purchase_journal (RetentionTestCommon) forces VEF
        # (_check_constrains_account_id_journal_id, l10n_ve_accountant); this
        # invoice needs a journal without a forced currency so it can be
        # booked in USD.
        self.purchase_journal_usd = self.env["account.journal"].create({
            "name": "Diario Compra USD",
            "type": "purchase",
            "code": "PURUS",
            "company_id": self.company.id,
        })

    def _set_rate(self, currency, date, inverse_company_rate):
        currency_rate = self.env["res.currency.rate"].search(
            [
                ("name", "=", date),
                ("currency_id", "=", currency.id),
                ("company_id", "=", self.company.id),
            ],
            limit=1,
        )
        if currency_rate:
            currency_rate.write({"inverse_company_rate": inverse_company_rate})
            return currency_rate
        return self.env["res.currency.rate"].create(
            {
                "name": date,
                "currency_id": currency.id,
                "inverse_company_rate": inverse_company_rate,
                "company_id": self.company.id,
            }
        )

    def _create_foreign_invoice(self, amount=200.0):
        """Purchase invoice booked in USD (foreign currency), while the
        retention payment is always created in company currency (VEF, see
        AccountRetention._prepare_retention_payment_vals).

        Built through Form (like RetentionTestCommon._create_invoice_reten_iva)
        instead of a raw .create(vals): the fiscal-position/tax onchange chain
        needs to run for product_iva's taxes to resolve correctly on this
        partner/company, exactly like the rest of this test suite already
        does."""
        with Form(self.env["account.move"].with_context(
            default_move_type="in_invoice", default_journal_id=self.purchase_journal_usd.id,
        )) as inv_form:
            inv_form.partner_id = self.partner_pnr_75
            inv_form.invoice_date = self.invoice_date
            inv_form.currency_id = self.currency_usd
            inv_form.correlative = "12345678901234"
        invoice = inv_form.save()

        with Form(invoice) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product_iva
                line.quantity = 1
                line.price_unit = amount
        invoice = inv_form_edit.save()

        invoice.write({"date": self.invoice_date, "invoice_date_display": self.invoice_date})
        invoice.action_post()
        return invoice

    def _exchange_diff_moves(self, invoice):
        ap_lines = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == "liability_payable"
        )
        partials = ap_lines.matched_credit_ids | ap_lines.matched_debit_ids
        return partials.mapped("exchange_move_id").filtered(lambda m: m)

    def test_retention_payment_move_uses_date_accounting(self):
        invoice = self._create_foreign_invoice(amount=200.0)
        invoice_total_vef = abs(invoice.amount_residual_signed)
        retention_amount_vef = invoice_total_vef * 0.10

        retention = self.env["account.retention"].create({
            "type_retention": "iva",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": self.date_accounting,
            "date_accounting": self.date_accounting,
            "number": "01234567891234",
            "retention_line_ids": [Command.create({
                "move_id": invoice.id,
                "name": "IVA Line",
                "invoice_total": invoice_total_vef,
                "invoice_amount": 200.0,
                "retention_amount": retention_amount_vef,
                "foreign_invoice_amount": 200.0,
                "foreign_retention_amount": 20.0,
                "foreign_currency_rate": 1.0,
            })],
        })

        retention.action_post()

        payment = retention.payment_ids
        self.assertEqual(len(payment), 1, "Exactly one payment must be created for the single invoice retained.")

        self.assertEqual(
            payment.date, self.date_accounting,
            "payment.date must reflect the retention's own date_accounting.",
        )

        # The move behind that payment must share the same date -- no
        # special-casing to pin it to the invoice's own date.
        self.assertEqual(
            payment.move_id.date, self.date_accounting,
            "The retention payment's journal entry must be dated like "
            "date_accounting, same as any other payment.",
        )

        # Independent of the date the move is booked at: reconciling a
        # retention payment against the invoice it retains from must never
        # produce a fictitious exchange difference (see the
        # no_exchange_difference guarantee added in 22a9444b8).
        self.assertFalse(
            self._exchange_diff_moves(invoice),
            "A retention payment must never generate an exchange difference "
            "against the invoice it retains from.",
        )
