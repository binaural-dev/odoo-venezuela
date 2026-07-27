from odoo.tests import tagged, Form
from odoo.tests.common import TransactionCase
from odoo import fields, Command

from .test_common_purchase_book_igtf_usd_provider_formal import IGTFTestCommonPurchaseBook
from .test_common_sale_book_igtf_usd_partner_formal import IGTFTestCommonSaleBook


@tagged("igtf_payment_fields", "post_install", "-at_install")
class TestIGTFPurchasePaymentFields(IGTFTestCommonPurchaseBook):

    def _open_payment_wizard(self, invoice, journal=None):
        journal = journal or self.bank_journal_usd
        ctx = invoice.action_register_payment()['context']
        return self.env['account.payment.register'].with_context(ctx)

    # ─────────────────────────────────────────────────────────
    # Single invoice full payment (outbound)
    # ─────────────────────────────────────────────────────────
    def test_single_full_payment_outbound(self):
        invoice = self._create_invoice_usd(1000.0)
        invoice.with_context(move_action_post_alert=True).action_post()

        igtf_top_aply = round(1000.0 * 0.03, 2)

        with Form(self._open_payment_wizard(invoice)) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.foreign_currency_id = self.currency_usd
            pay_form.foreign_rate = invoice.foreign_rate
            pay_form.save()

        action = pay_form.record.action_create_payments()
        payment = self.env['account.payment'].browse(action['res_id'])

        self.assertTrue(payment.payment_from_wizard)
        self.assertAlmostEqual(payment.igtf_amount, 30.0, 2)
        self.assertTrue(payment.is_igtf_on_foreign_exchange)
        self.assertAlmostEqual(payment.igtf_percentage, 3.0, 2)
        self.assertEqual(payment.invoices_origin_ids, invoice)
        self.assertEqual(payment.payment_type, 'outbound')
        self.assertEqual(payment.partner_type, 'supplier')

        self.assertEqual(len(payment.move_id.line_ids), 3)
        td = sum(payment.move_id.line_ids.mapped('debit'))
        tc = sum(payment.move_id.line_ids.mapped('credit'))
        self.assertAlmostEqual(td, tc, 2)

        self.assertEqual(invoice.payment_state, 'paid')
        self.assertAlmostEqual(invoice.amount_residual, 0.0, 2)
        self.assertAlmostEqual(invoice.bi_igtf, 1000.0, 2)
        self.assertAlmostEqual(invoice.foreign_bi_igtf, 1000.0, 2)
        self.assertAlmostEqual(invoice.igtf_top_aply, igtf_top_aply, 2)
        self.assertAlmostEqual(invoice.alter_bi_igtf, 30.0, 2)

    # ─────────────────────────────────────────────────────────
    # Single invoice partial payment (outbound)
    # ─────────────────────────────────────────────────────────
    def test_single_partial_payment_outbound(self):
        invoice = self._create_invoice_usd(2681.20)
        invoice.with_context(move_action_post_alert=True).action_post()

        payment_amount = 2000.0
        expected_igtf = 60.0
        expected_residual = 741.20

        ctx = invoice.action_register_payment()['context']
        with Form(self.env['account.payment.register'].with_context(ctx)) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.foreign_currency_id = self.currency_usd
            pay_form.foreign_rate = invoice.foreign_rate
            pay_form.save()
            pay_form.amount = payment_amount

        action = pay_form.record.action_create_payments()
        payment = self.env['account.payment'].browse(action['res_id'])
        

        self.assertAlmostEqual(payment.igtf_amount, expected_igtf, 2)
        self.assertTrue(payment.payment_from_wizard)
        self.assertTrue(payment.is_igtf_on_foreign_exchange)
        self.assertAlmostEqual(payment.igtf_percentage, 3.0, 2)
        self.assertEqual(payment.invoices_origin_ids, invoice)

        self.assertEqual(invoice.payment_state, 'partial')
        self.assertAlmostEqual(invoice.amount_residual, expected_residual, 2)
        self.assertGreater(invoice.bi_igtf, 0)
        self.assertGreater(invoice.alter_bi_igtf, 0)

    # ─────────────────────────────────────────────────────────
    # Multiple invoices paid with one payment (outbound)
    # ─────────────────────────────────────────────────────────
    def test_multi_invoice_payment_outbound(self):
        """Two invoices, each paid separately with IGTF via the wizard."""
        inv1 = self._create_invoice_usd(500.0)
        inv1.correlative = "98765432100001"
        inv2 = self._create_invoice_usd(700.0)
        inv2.correlative = "98765432100002"
        inv1.with_context(move_action_post_alert=True).action_post()
        inv2.with_context(move_action_post_alert=True).action_post()

        payments = self.env['account.payment']
        for inv in (inv1, inv2):
            with Form(self._open_payment_wizard(inv)) as pay_form:
                pay_form.journal_id = self.bank_journal_usd
                pay_form.payment_date = fields.Date.today()
                pay_form.foreign_currency_id = self.currency_usd
                pay_form.foreign_rate = inv.foreign_rate
                pay_form.save()

            action = pay_form.record.action_create_payments()
            payment = self.env['account.payment'].browse(action['res_id'])
            payments += payment

        for inv, payment in zip((inv1, inv2), payments):
            expected_igtf = round(abs(inv.amount_total_signed) * 0.03, 2)
            self.assertTrue(payment.payment_from_wizard)
            self.assertTrue(payment.is_igtf_on_foreign_exchange)
            self.assertAlmostEqual(payment.igtf_percentage, 3.0, 2)
            self.assertAlmostEqual(payment.igtf_amount, expected_igtf, 2)
            self.assertEqual(payment.invoices_origin_ids, inv)
            td = sum(payment.move_id.line_ids.mapped('debit'))
            tc = sum(payment.move_id.line_ids.mapped('credit'))
            self.assertAlmostEqual(td, tc, 2)
            self.assertEqual(inv.payment_state, 'paid')
            self.assertAlmostEqual(inv.amount_residual, 0.0, 2)

    # ─────────────────────────────────────────────────────────
    # Non-IGTF journal bypass
    # ─────────────────────────────────────────────────────────
    def test_non_igtf_journal(self):
        invoice = self._create_invoice_usd(1000.0)
        invoice.with_context(move_action_post_alert=True).action_post()

        non_igtf_journal = self.Journal.create({
            'name': 'Banco No IGTF',
            'code': 'BNKNO',
            'type': 'bank',
            'currency_id': self.currency_usd.id,
            'company_id': self.company.id,
            'is_igtf': False,
            'default_account_id': self.account_bank.id,
            'outbound_payment_method_line_ids': [(6, 0, self.pm_line_out_usd.ids)],
        })

        with Form(self._open_payment_wizard(invoice, non_igtf_journal)) as pay_form:
            pay_form.journal_id = non_igtf_journal
            pay_form.payment_date = fields.Date.today()
            pay_form.foreign_currency_id = self.currency_usd
            pay_form.foreign_rate = invoice.foreign_rate
            pay_form.save()

        wizard = pay_form.record
        self.assertFalse(wizard.is_igtf)
        self.assertFalse(wizard.is_igtf_on_foreign_exchange)
        self.assertEqual(wizard.igtf_amount, 0.0)
        self.assertEqual(wizard.igtf_to_show, 0.0)


@tagged("igtf_payment_fields", "post_install", "-at_install")
class TestIGTFSalePaymentFields(IGTFTestCommonSaleBook):

    def _open_payment_wizard(self, invoice, journal=None):
        journal = journal or self.bank_journal_usd
        ctx = invoice.action_register_payment()['context']
        return self.env['account.payment.register'].with_context(ctx)

    # ─────────────────────────────────────────────────────────
    # Single invoice full payment (inbound)
    # ─────────────────────────────────────────────────────────
    def test_single_full_payment_inbound(self):
        invoice = self._create_invoice_usd(1000.0)
        invoice.with_context(move_action_post_alert=True).action_post()

        igtf_top_aply = round(1000.0 * 0.03, 2)

        with Form(self._open_payment_wizard(invoice)) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.foreign_currency_id = self.currency_usd
            pay_form.foreign_rate = invoice.foreign_rate
            pay_form.save()

        action = pay_form.record.action_create_payments()
        payment = self.env['account.payment'].browse(action['res_id'])
        

        self.assertTrue(payment.payment_from_wizard)
        self.assertAlmostEqual(payment.igtf_amount, 30.0, 2)
        self.assertTrue(payment.is_igtf_on_foreign_exchange)
        self.assertAlmostEqual(payment.igtf_percentage, 3.0, 2)
        self.assertEqual(payment.invoices_origin_ids, invoice)
        self.assertEqual(payment.payment_type, 'inbound')
        self.assertEqual(payment.partner_type, 'customer')

        self.assertEqual(len(payment.move_id.line_ids), 3)
        td = sum(payment.move_id.line_ids.mapped('debit'))
        tc = sum(payment.move_id.line_ids.mapped('credit'))
        self.assertAlmostEqual(td, tc, 2)

        self.assertEqual(invoice.payment_state, 'paid')
        self.assertAlmostEqual(invoice.amount_residual, 0.0, 2)
        self.assertAlmostEqual(invoice.bi_igtf, 1000.0, 2)
        self.assertAlmostEqual(invoice.foreign_bi_igtf, 1000.0, 2)
        self.assertAlmostEqual(invoice.igtf_top_aply, igtf_top_aply, 2)
        self.assertGreater(invoice.alter_bi_igtf, 0)

    # ─────────────────────────────────────────────────────────
    # Single invoice partial payment (inbound)
    # ─────────────────────────────────────────────────────────
    def test_single_partial_payment_inbound(self):
        invoice = self._create_invoice_usd(2681.20)
        invoice.with_context(move_action_post_alert=True).action_post()

        payment_amount = 2000.0
        expected_igtf = 60.0

        ctx = invoice.action_register_payment()['context']
        with Form(self.env['account.payment.register'].with_context(ctx)) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.foreign_currency_id = self.currency_usd
            pay_form.foreign_rate = invoice.foreign_rate
            pay_form.save()
            pay_form.amount = payment_amount

        action = pay_form.record.action_create_payments()
        payment = self.env['account.payment'].browse(action['res_id'])
        

        self.assertAlmostEqual(payment.igtf_amount, expected_igtf, 2)
        self.assertTrue(payment.payment_from_wizard)
        self.assertEqual(invoice.payment_state, 'partial')

    # ─────────────────────────────────────────────────────────
    # Multiple invoices paid with one payment (inbound)
    # ─────────────────────────────────────────────────────────
    def test_multi_invoice_payment_inbound(self):
        """Two invoices, each paid separately with IGTF via the wizard."""
        inv1 = self._create_invoice_usd(500.0)
        inv1.correlative = "98765432100001"
        inv2 = self._create_invoice_usd(700.0)
        inv2.correlative = "98765432100002"
        inv1.with_context(move_action_post_alert=True).action_post()
        inv2.with_context(move_action_post_alert=True).action_post()

        payments = self.env['account.payment']
        for inv in (inv1, inv2):
            with Form(self._open_payment_wizard(inv)) as pay_form:
                pay_form.journal_id = self.bank_journal_usd
                pay_form.payment_date = fields.Date.today()
                pay_form.foreign_currency_id = self.currency_usd
                pay_form.foreign_rate = inv.foreign_rate
                pay_form.save()

            action = pay_form.record.action_create_payments()
            payment = self.env['account.payment'].browse(action['res_id'])
            payments += payment

        for inv, payment in zip((inv1, inv2), payments):
            expected_igtf = round(inv.amount_total_signed * 0.03, 2)
            self.assertTrue(payment.payment_from_wizard)
            self.assertTrue(payment.is_igtf_on_foreign_exchange)
            self.assertAlmostEqual(payment.igtf_percentage, 3.0, 2)
            self.assertAlmostEqual(payment.igtf_amount, expected_igtf, 2)
            self.assertEqual(payment.payment_type, 'inbound')
            self.assertEqual(payment.partner_type, 'customer')
            td = sum(payment.move_id.line_ids.mapped('debit'))
            tc = sum(payment.move_id.line_ids.mapped('credit'))
            self.assertAlmostEqual(td, tc, 2)
            self.assertEqual(inv.payment_state, 'paid')
            self.assertAlmostEqual(inv.amount_residual, 0.0, 2)
