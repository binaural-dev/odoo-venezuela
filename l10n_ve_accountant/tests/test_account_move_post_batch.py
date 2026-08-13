from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'l10n_ve_accountant')
class TestAccountMovePostBatch(TransactionCase):
    """Regression test for a confirmed bug in
    ``l10n_ve_accountant/models/account_move.py::action_post()``:

        for move in self:
            if move.move_type in ("out_invoice", "out_refund"):
                return {..., 'context': {'default_move_id': move.id}}

    ``.id`` used to be read on ``self`` (the whole recordset passed to
    ``action_post()``) instead of on ``move`` (the current loop item).
    Odoo's ``id`` raises ``ValueError: Expected singleton`` when read on a
    recordset with more than one record, so any attempt to post 2+
    customer invoices/refunds together (e.g. multi-select "Post" from the
    list view) used to crash with an unhandled server error instead of
    showing the credit-limit alert wizard for the first one found.

    TEMPORARY, test-only fix applied directly in this checkout
    (``src/custom/test-countryclub17/odoo-venezuela``) to validate the
    hypothesis while the main reported production error (staging DB
    ``contryclub-stg-2``, "cannot edit the journal of a posted move") is
    still being confirmed -- not yet authorized for commit.
    """

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        currency_usd = self.env['res.currency'].with_context(
            active_test=False,
        ).search([('name', '=', 'USD')], limit=1)
        if currency_usd and self.company.currency_foreign_id != currency_usd:
            self.company.currency_foreign_id = currency_usd.id
        self.partner = self.env['res.partner'].create({
            'name': 'Test Partner Batch Post',
        })
        self.journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.company.id),
        ], limit=1)
        self.income_account = self.env['account.account'].search([
            ('account_type', '=', 'income'),
            ('company_id', '=', self.company.id),
        ], limit=1)
        self.product = self.env['product.product'].create({
            'name': 'Batch Post Test Product',
            'type': 'service',
        })

    def _create_invoice(self, price_unit):
        return self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'journal_id': self.journal.id,
            'invoice_line_ids': [Command.create({
                'product_id': self.product.id,
                'name': 'line',
                'quantity': 1,
                'price_unit': price_unit,
                'account_id': self.income_account.id,
            })],
        })

    def test_action_post_single_invoice_returns_wizard_with_its_own_id(self):
        """Sanity check: a single-record recordset works fine -- ``self.id``
        and ``move.id`` are the same record, so this path is not where the
        bug shows up.
        """
        invoice = self._create_invoice(10.0)

        res = invoice.action_post()

        self.assertEqual(res['res_model'], 'move.action.post.alert.wizard')
        self.assertEqual(res['context']['default_move_id'], invoice.id)
        self.assertEqual(invoice.state, 'draft')

    def test_action_post_batch_of_two_invoices_returns_wizard_for_first_move(self):
        """FIXED: calling action_post() on a 2+ record batch of customer
        invoices no longer crashes -- it returns the alert wizard for the
        first move in the batch that matches out_invoice/out_refund,
        instead of raising ValueError: Expected singleton on ``self.id``.
        """
        invoice_1 = self._create_invoice(10.0)
        invoice_2 = self._create_invoice(20.0)
        batch = invoice_1 + invoice_2

        res = batch.action_post()

        self.assertEqual(res['res_model'], 'move.action.post.alert.wizard')
        self.assertEqual(res['context']['default_move_id'], invoice_1.id)
        # Neither invoice is posted yet -- the wizard still needs to be
        # confirmed by the user (action_confirm()) to actually post.
        self.assertEqual(invoice_1.state, 'draft')
        self.assertEqual(invoice_2.state, 'draft')
