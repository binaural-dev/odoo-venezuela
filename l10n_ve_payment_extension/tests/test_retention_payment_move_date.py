import logging

from odoo.tests import tagged, Form
from odoo import Command, fields

from .test_withholding_common_VEF import RetentionTestCommon

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "retention_payment_move_date")
class TestRetentionPaymentMoveDate(RetentionTestCommon):
    """Covers how a retention payment's journal entry gets dated today:
    with the retention's own date_accounting, the same date shown on
    payment.date -- there is no override pinning it to the date (or rate)
    of the invoice being retained from, even when that invoice is booked
    in a foreign currency at a different rate."""

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
        AccountRetention._prepare_retention_payment_vals)."""
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

    def _create_retention(self, invoice, number="01234567891234"):
        invoice_total_vef = abs(invoice.amount_residual_signed)
        return self.env["account.retention"].create({
            "type_retention": "iva",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": self.date_accounting,
            "date_accounting": self.date_accounting,
            "number": number,
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

    def test_retention_payment_move_uses_date_accounting(self):
        """The payment (and the move behind it) are dated with the
        retention's own date_accounting, regardless of the date -- and
        rate -- of the invoice being retained from. There is no pinning to
        the invoice's own accounting date anywhere in this module."""
        invoice = self._create_foreign_invoice(amount=200.0)
        retention = self._create_retention(invoice)

        retention.action_post()

        payment = retention.payment_ids
        self.assertEqual(len(payment), 1, "Exactly one payment must be created for the single invoice retained.")

        self.assertEqual(
            payment.date, self.date_accounting,
            "payment.date must reflect the retention's own date_accounting.",
        )
        self.assertEqual(
            payment.move_id.date, self.date_accounting,
            "The retention payment's journal entry is dated like "
            "date_accounting -- nothing in this module pins it to the "
            "invoice's own date.",
        )

    def test_retention_payment_generate_move_vals_uses_date_accounting(self):
        """Direct unit check: _generate_move_vals is core Odoo's own
        implementation here (no override in this module), so it falls back
        to 'date': self.date, which for a retention payment is
        date_accounting -- not the date of the invoice being retained
        from."""
        invoice = self._create_foreign_invoice(amount=200.0)
        retention = self._create_retention(invoice, number="01234567891235")

        payment_vals = retention._prepare_retention_payment_vals(
            invoice, retention.retention_line_ids
        )
        self.assertEqual(
            payment_vals["date"], self.date_accounting,
            "The payment itself is dated with date_accounting.",
        )

        payment = self.env["account.payment"].create(payment_vals)
        payment.retention_line_ids = retention.retention_line_ids

        move_vals = payment._generate_move_vals()
        self.assertEqual(
            move_vals.get("date"), self.date_accounting,
            "_generate_move_vals has no override in this module, so it "
            "keeps core Odoo's default: 'date' falls back to payment.date "
            "(date_accounting), not the invoice's own accounting date.",
        )
