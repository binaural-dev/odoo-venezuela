from odoo.tests import TransactionCase, tagged
from odoo import fields, Command
from odoo.exceptions import UserError
from unittest.mock import patch


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestReportPrintRestriction(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.user.company_id
        self.company.currency_id = self.env.ref('base.VEF')
        self.company.foreign_currency_id = self.env.ref('base.USD')

        self.account_receivable = self.env['account.account'].create({
            'name': 'Receivable', 'code': '1111111',
            'account_type': 'asset_receivable', 'reconcile': True,
        })
        self.account_revenue = self.env['account.account'].create({
            'name': 'Revenue', 'code': '4444444',
            'account_type': 'income',
        })
        self.account_expense = self.env['account.account'].create({
            'name': 'Expense', 'code': '5555555',
            'account_type': 'expense',
        })

        self.partner = self.env['res.partner'].create({
            'name': 'Test Partner',
            'property_account_receivable_id': self.account_receivable.id,
        })
        self.product = self.env['product.product'].create({
            'name': 'Product Test', 'type': 'service',
            'property_account_income_id': self.account_revenue.id,
            'property_account_expense_id': self.account_expense.id,
        })
        self.journal_sale = self.env['account.journal'].create({
            'name': 'Sale Journal', 'type': 'sale',
            'code': 'SALE1',
            'default_account_id': self.account_revenue.id,
        })

        self.report_invoice = 'account.account_invoices'

    def _create_invoice(self, move_type='out_invoice', state='draft'):
        inv = self.env['account.move'].with_context(check_move_validity=False).create({
            'move_type': move_type,
            'partner_id': self.partner.id,
            'journal_id': self.journal_sale.id,
            'invoice_date': fields.Date.today(),
            'date': fields.Date.today(),
            'invoice_line_ids': [Command.create({
                'product_id': self.product.id,
                'quantity': 1,
                'price_unit': 100.0,
            })],
        })
        if state == 'posted':
            inv.with_context(move_action_post_alert=True).action_post()
        elif state == 'cancel':
            inv.with_context(move_action_post_alert=True).action_post()
            inv.button_cancel()
        return inv

    def _test_pdf_raises(self, res_ids):
        with self.assertRaises(UserError):
            self.env['ir.actions.report']._render_qweb_pdf_prepare_streams(
                self.report_invoice, {}, res_ids=res_ids
            )

    def _test_pdf_ok(self, res_ids):
        with patch.object(type(self.env['ir.actions.report']), '_render_qweb_pdf_prepare_streams') as mock:
            mock.return_value = {}
            result = self.env['ir.actions.report']._render_qweb_pdf_prepare_streams(
                self.report_invoice, {}, res_ids=res_ids
            )
        self.assertEqual(result, {})

    def _test_html_raises(self, docids, data=None):
        with self.assertRaises(UserError):
            self.env['ir.actions.report']._render_qweb_html(
                self.report_invoice, docids, data=data
            )

    def _test_html_ok(self, docids, data=None):
        with patch.object(type(self.env['ir.actions.report']), '_render_qweb_html') as mock:
            mock.return_value = [b'%PDF']
            result = self.env['ir.actions.report']._render_qweb_html(
                self.report_invoice, docids, data=data
            )
        self.assertEqual(result, [b'%PDF'])

    # ═══════════════════════════════════════════════════════════════
    # account.move PDF
    # ═══════════════════════════════════════════════════════════════

    def test_01_print_posted_invoice_pdf(self):
        inv = self._create_invoice(state='posted')
        self._test_pdf_ok(inv.ids)

    def test_02_print_draft_invoice_pdf(self):
        inv = self._create_invoice(state='draft')
        self._test_pdf_raises(inv.ids)

    def test_03_print_cancel_invoice_pdf(self):
        inv = self._create_invoice(state='cancel')
        self._test_pdf_raises(inv.ids)

    def test_04_print_mixed_invoices_pdf(self):
        inv_posted = self._create_invoice(state='posted')
        inv_draft = self._create_invoice(state='draft')
        self._test_pdf_ok(inv_posted.ids + inv_draft.ids)

    def test_05_print_posted_refund_pdf(self):
        inv = self._create_invoice(state='posted')
        refund = self._create_invoice(move_type='out_refund', state='draft')
        self._test_pdf_raises(refund.ids)

    # ═══════════════════════════════════════════════════════════════
    # _render_qweb_html (incluye fix del bypass)
    # ═══════════════════════════════════════════════════════════════

    def test_06_print_posted_invoice_html_no_data(self):
        inv = self._create_invoice(state='posted')
        self._test_html_ok(inv.ids)

    def test_07_print_draft_invoice_html_no_data(self):
        inv = self._create_invoice(state='draft')
        self._test_html_raises(inv.ids)

    def test_08_print_draft_invoice_html_with_context(self):
        inv = self._create_invoice(state='draft')
        data = {'context': {'active_ids': inv.ids, 'active_model': 'account.move'}}
        self._test_html_raises(inv.ids, data=data)

    def test_09_print_cancel_invoice_html_no_data(self):
        inv = self._create_invoice(state='cancel')
        self._test_html_raises(inv.ids)

    def test_10_print_mixed_invoices_html(self):
        inv_posted = self._create_invoice(state='posted')
        inv_draft = self._create_invoice(state='draft')
        self._test_html_ok(inv_posted.ids + inv_draft.ids)
