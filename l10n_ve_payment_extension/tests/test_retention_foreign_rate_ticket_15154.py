# -*- coding: utf-8 -*-
"""
Tests for helpdesk ticket #15154: a retention payment's journal entry line
must convert its VEF amount to USD using the ORIGINAL invoice's exchange
rate (frozen at the invoice's own invoice_date), not the exchange rate in
effect on the day the retention itself gets confirmed/posted.
"""
from odoo import Command, fields
from odoo.tests import Form, tagged

from .test_withholding_common_VEF import RetentionTestCommon


@tagged("post_install", "-at_install", "retention_foreign_rate_ticket_15154")
class TestRetentionForeignRateTicket15154(RetentionTestCommon):

    def test_iva_customer_retention_payment_uses_invoice_rate_not_post_date_rate(self):
        """
        Invoice issued 3 days ago at rate R1 (390.2944 VEF/USD, from the
        common fixture's "yesterday" rate is not used here - we set our own
        explicit historical rate). The retention is confirmed TODAY, after
        the BCV rate has moved to a different value R2 (400.0 VEF/USD) for
        today's date. The retention payment's own journal entry line must
        still report its alternate (USD) amount using R1, not R2.
        """
        invoice_date = fields.Date.subtract(fields.Date.today(), days=3)
        rate_invoice = 390.2944  # R1: rate in effect on the invoice's own date
        rate_today = 400.0       # R2: rate in effect today (retention post date)

        # Pin an explicit historical rate for the invoice's date and a
        # different one for today, on the foreign currency (USD).
        self.currency_usd.rate_ids.filtered(
            lambda r: r.name == invoice_date and r.company_id == self.company
        ).unlink()
        self.currency_usd.rate_ids.filtered(
            lambda r: r.name == fields.Date.today() and r.company_id == self.company
        ).write({
            "rate": 1 / rate_today,
            "company_rate": 1 / rate_today,
            "inverse_company_rate": rate_today,
        })
        self.env["res.currency.rate"].create({
            "currency_id": self.currency_usd.id,
            "company_id": self.company.id,
            "name": invoice_date,
            "rate": 1 / rate_invoice,
            "company_rate": 1 / rate_invoice,
            "inverse_company_rate": rate_invoice,
        })

        # 1000.0 VEF untaxed, taxed at 16% -> 160.0 VEF IVA; customer
        # withholding_type_id on partner_pnr_75 is 75%.
        with Form(
            self.env["account.move"].with_context(
                default_move_type="out_invoice", default_journal_id=self.sale_journal.id
            )
        ) as inv_form:
            inv_form.partner_id = self.partner_pnr_75
            inv_form.invoice_date = invoice_date
            inv_form.currency_id = self.currency_vef
        invoice = inv_form.save()
        with Form(invoice) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product_iva
                line.quantity = 1
                line.price_unit = 1000.0
        invoice = inv_form_edit.save()
        invoice.action_post()

        # The invoice's own frozen rate must match R1 (sanity check that our
        # fixture actually pinned the historical rate as intended).
        self.assertAlmostEqual(invoice.foreign_rate, rate_invoice, places=4)

        invoice_amount = 1000.0
        iva_amount = 160.0
        retention_amount = 120.0  # 160.0 * 0.75
        # Hand-computed: 120.0 VEF / 390.2944 VEF-per-USD = 0.307460...
        foreign_retention_amount_expected = 0.31

        retention = self.env["account.retention"].create({
            "type_retention": "iva",
            "type": "out_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(),
            "date_accounting": fields.Date.today(),
            "number": "01234567891234",
            "retention_line_ids": [Command.create({
                "move_id": invoice.id,
                "name": "Iva Retention",
                "invoice_type": "out_invoice",
                "aliquot": 16.0,
                "iva_amount": iva_amount,
                "invoice_total": invoice.amount_total,
                "invoice_amount": invoice_amount,
                "retention_amount": retention_amount,
                "foreign_currency_rate": rate_invoice,
                "foreign_invoice_amount": invoice_amount / rate_invoice,
                "foreign_retention_amount": foreign_retention_amount_expected,
            })],
        })

        retention.action_post()
        self.assertEqual(retention.state, "emitted")

        payment = retention.payment_ids
        self.assertEqual(len(payment), 1)
        self.assertAlmostEqual(
            payment.retention_foreign_amount, foreign_retention_amount_expected, places=2
        )

        retention_account_lines = payment.move_id.line_ids.filtered(
            lambda l: l.account_id.code == "1151003"
            or "RETENIDO" in (l.account_id.name or "").upper()
            or l.account_id == self.acc_receivable
            or l.debit == retention_amount
            or l.credit == retention_amount
        )
        # At least the two regular lines of the payment's own move (the
        # retained-tax account and the receivable account) must exist.
        self.assertTrue(payment.move_id.line_ids)

        for line in payment.move_id.line_ids.filtered(
            lambda l: not l.display_type and (l.debit or l.credit)
        ):
            foreign_value = line.foreign_debit if line.debit else line.foreign_credit
            # Fixed with ticket #15154's rule: must equal the amount
            # converted at R1 (the invoice's own rate), NOT at R2 (today's
            # rate, which would give retention_amount / rate_today).
            expected_with_invoice_rate = round(retention_amount / rate_invoice, 2)
            wrong_with_post_date_rate = round(retention_amount / rate_today, 2)
            self.assertNotEqual(
                wrong_with_post_date_rate,
                expected_with_invoice_rate,
                "Test fixture error: R1 and R2 must yield distinguishable amounts.",
            )
            self.assertAlmostEqual(
                foreign_value, expected_with_invoice_rate, places=2,
                msg=(
                    "Retention payment move line's alternate amount must use the "
                    "invoice's own rate (%s), not the retention post date's rate (%s)."
                ) % (rate_invoice, rate_today),
            )
