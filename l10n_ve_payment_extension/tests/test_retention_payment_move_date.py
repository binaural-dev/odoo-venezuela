import logging

from odoo.addons.account.models.account_payment import AccountPayment as CoreAccountPayment
from odoo.tests import tagged, Form
from odoo import Command, fields

from .test_withholding_common_VEF import RetentionTestCommon

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "retention_payment_move_date")
class TestRetentionPaymentMoveDate(RetentionTestCommon):
    """Covers the fix in AccountPayment._generate_move_vals /
    AccountRetention._reconcile_all_payments: a retention payment's journal
    entry must be dated (and rated) like the invoice it retains from, not
    like the retention's own date_accounting, even though payment.date keeps
    showing date_accounting in the UI."""

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
        AccountRetention._prepare_retention_payment_vals) -- the combination
        that exposes a rate mismatch on reconciliation if the payment's move
        isn't pinned to the invoice's own date/rate.

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

    def test_retention_payment_move_uses_invoice_date_and_rate(self):
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

        # payment.date (shown in the UI) keeps the user-chosen retention date.
        self.assertEqual(
            payment.date, self.date_accounting,
            "payment.date must still reflect the retention's own date_accounting.",
        )

        # The move behind that payment must instead be dated like the invoice.
        self.assertEqual(
            payment.move_id.date, invoice.date,
            "The retention payment's journal entry must be dated like the "
            "invoice it retains from, not like date_accounting.",
        )

        # Since the move now shares the invoice's date, it must also share its
        # rate: reconciling them must NOT produce an exchange difference.
        self.assertFalse(
            self._exchange_diff_moves(invoice),
            "A retention payment must never generate an exchange difference "
            "against the invoice it retains from.",
        )

    def test_retention_payment_generate_move_vals_pins_invoice_date(self):
        """Direct unit check on the overridden hook itself: _generate_move_vals
        must inject the invoice's own date as 'date' in the vals used to build
        the payment's move, precisely because payment.date (date_accounting)
        is not it."""
        invoice = self._create_foreign_invoice(amount=200.0)
        invoice_total_vef = abs(invoice.amount_residual_signed)

        retention = self.env["account.retention"].create({
            "type_retention": "iva",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": self.date_accounting,
            "date_accounting": self.date_accounting,
            "number": "01234567891235",
            "retention_line_ids": [Command.create({
                "move_id": invoice.id,
                "name": "IVA Line",
                "invoice_total": invoice_total_vef,
                "invoice_amount": 200.0,
                "retention_amount": invoice_total_vef * 0.10,
                "foreign_invoice_amount": 200.0,
                "foreign_retention_amount": 20.0,
                "foreign_currency_rate": 1.0,
            })],
        })
        payment_vals = retention._prepare_retention_payment_vals(
            invoice, retention.retention_line_ids
        )
        self.assertEqual(
            payment_vals["date"], self.date_accounting,
            "The payment itself must still be dated with date_accounting.",
        )

        payment = self.env["account.payment"].create(payment_vals)
        payment.retention_line_ids = retention.retention_line_ids

        move_vals = payment._generate_move_vals()
        self.assertEqual(
            move_vals.get("date"), invoice.date,
            "_generate_move_vals must override 'date' to the invoice's own "
            "accounting date once the payment is linked to its retention_line_ids, "
            "instead of leaving payment.date (date_accounting) as the move's date.",
        )

    def test_regression_without_conversion_date_context_move_uses_date_accounting(self):
        """Regression test: reproduces exactly what happened before this fix.

        AccountPayment._generate_move_vals only pins the move to the
        invoice's date because IT injects l10n_ve_conversion_date into the
        context itself before calling super(). If that injection never
        happened -- i.e. the context never reached the payment, which is
        exactly the state of the code before the fix -- core Odoo's own
        _generate_move_vals falls back to 'date': self.date (payment.date,
        which for a retention payment is date_accounting). We reproduce that
        exact pre-fix code path by calling the core implementation directly,
        bypassing AccountPayment._generate_move_vals's override entirely."""
        invoice = self._create_foreign_invoice(amount=200.0)
        invoice_total_vef = abs(invoice.amount_residual_signed)

        retention = self.env["account.retention"].create({
            "type_retention": "iva",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": self.date_accounting,
            "date_accounting": self.date_accounting,
            "number": "01234567891236",
            "retention_line_ids": [Command.create({
                "move_id": invoice.id,
                "name": "IVA Line",
                "invoice_total": invoice_total_vef,
                "invoice_amount": 200.0,
                "retention_amount": invoice_total_vef * 0.10,
                "foreign_invoice_amount": 200.0,
                "foreign_retention_amount": 20.0,
                "foreign_currency_rate": 1.0,
            })],
        })
        payment_vals = retention._prepare_retention_payment_vals(
            invoice, retention.retention_line_ids
        )
        payment = self.env["account.payment"].create(payment_vals)
        payment.retention_line_ids = retention.retention_line_ids

        # Sanity check: this scenario must actually have distinct dates,
        # otherwise the assertions below would pass even without the bug.
        self.assertNotEqual(
            self.date_accounting, invoice.date,
            "date_accounting and the invoice's date must differ in this "
            "scenario for the regression check below to mean anything.",
        )
        # Bypass the fix: call core Odoo's _generate_move_vals directly, as
        # if AccountPayment._generate_move_vals (and its
        # l10n_ve_conversion_date injection) did not exist -- the exact
        # situation before this module carried the fix.
        move_vals_without_context = CoreAccountPayment._generate_move_vals(payment)

        self.assertEqual(
            move_vals_without_context["date"], self.date_accounting,
            "Without the l10n_ve_conversion_date injection reaching the "
            "payment, the move falls back to payment.date (date_accounting) "
            "instead of the invoice's own date -- this is the exact "
            "regression this fix prevents.",
        )
        self.assertNotEqual(
            move_vals_without_context["date"], invoice.date,
            "Confirms the pre-fix 'date' does NOT match the invoice, unlike "
            "the fixed _generate_move_vals covered by "
            "test_retention_payment_generate_move_vals_pins_invoice_date.",
        )
