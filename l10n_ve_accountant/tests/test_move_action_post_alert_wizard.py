from unittest.mock import patch

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'l10n_ve_accountant')
class TestMoveActionPostAlertWizard(TransactionCase):
    """Regression test for the confirmed root cause of the recurring
    production error "You cannot edit the journal of an account move if
    it has been posted once." (staging DB contryclub-stg-2).

    Root cause (confirmed via a full production traceback, not guessed):
    ``account_move.py::action_post()`` opens this wizard with
    ``context={'default_move_id': move.id}``. The wizard's
    ``action_confirm()`` used to call
    ``self.move_id.with_context(move_action_post_alert=True).action_post()``
    -- ``with_context()`` only ADDS keys, it never clears the wizard's own
    inherited context, which still carries that ``default_move_id``.

    Any ``account.payment.create()`` triggered downstream (via
    ``_reconcile_after_done()`` reconciling a real payment against the
    invoice) that does not explicitly set ``move_id`` in its vals then
    picks up the LEAKED ``default_move_id`` as an implicit default --
    Odoo's ``_inherits`` machinery (``odoo/models.py:4632-4645``) then
    treats that as "the payment's parent record already exists" and
    writes the payment's own field values (e.g. its ``journal_id``, the
    bank journal of the payment provider) onto the INVOICE's move instead
    of creating the payment's own new journal entry. If the invoice was
    already posted (``posted_before=True``), that write raises the
    journal-editing guard.

    Fix: ``action_confirm()`` now calls
    ``self.move_id.with_context(clean_context(self.env.context),
    move_action_post_alert=True).action_post()`` -- stripping any leaked
    ``default_*`` context keys before triggering the real posting/
    reconciliation chain.
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
            'name': 'Test Partner Wizard Confirm',
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
            'name': 'Wizard Confirm Test Product',
            'type': 'service',
        })

    def _create_invoice(self):
        return self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'journal_id': self.journal.id,
            'invoice_line_ids': [Command.create({
                'product_id': self.product.id,
                'name': 'line',
                'quantity': 1,
                'price_unit': 10.0,
                'account_id': self.income_account.id,
            })],
        })

    def _open_wizard_like_action_post_does(self, invoice):
        """Mirrors exactly how account_move.py::action_post() opens this
        wizard: context={'default_move_id': move.id} on the window action.
        """
        return self.env['move.action.post.alert.wizard'].with_context(
            default_move_id=invoice.id,
        ).create({})

    def test_wizard_context_carries_the_leaked_default_move_id(self):
        """Sanity check: confirms the scenario is realistic -- creating the
        wizard the way the real action does leaves default_move_id in its
        own env context, available to leak into anything called from it.
        """
        invoice = self._create_invoice()
        wizard = self._open_wizard_like_action_post_does(invoice)

        self.assertEqual(wizard.move_id, invoice)
        self.assertEqual(wizard.env.context.get('default_move_id'), invoice.id)

    def test_action_confirm_does_not_leak_default_move_id_downstream(self):
        """FIXED: action_confirm() must call action_post() with a context
        that no longer carries the wizard's own default_move_id, while
        still setting move_action_post_alert=True.
        """
        invoice = self._create_invoice()
        wizard = self._open_wizard_like_action_post_does(invoice)

        captured_contexts = []
        AccountMove = type(self.env['account.move'])
        original_action_post = AccountMove.action_post

        def spy_action_post(move_self):
            captured_contexts.append(dict(move_self.env.context))
            return original_action_post(move_self)

        with patch.object(AccountMove, 'action_post', spy_action_post):
            wizard.action_confirm()

        self.assertTrue(captured_contexts, "action_post() was never called")
        self.assertNotIn(
            'default_move_id', captured_contexts[0],
            "default_move_id leaked from the wizard's own context into "
            "action_post()'s context -- this is exactly what corrupts any "
            "account.payment.create() triggered downstream.",
        )
        self.assertTrue(captured_contexts[0].get('move_action_post_alert'))
        self.assertEqual(invoice.state, 'posted')

    def test_downstream_account_payment_create_does_not_target_the_invoice_move(self):
        """Direct reproduction of the actual corruption mechanism: an
        account.payment created (without an explicit move_id, exactly like
        account_payment/models/payment_transaction.py::_create_payment()
        does) while running under the wizard's leaked (uncleaned) context
        gets parented to the invoice's own account.move, and crashes with
        the exact production error when that invoice was already posted.
        Cleaning the context (as action_confirm() now does) avoids this
        entirely -- the payment gets its own, independent journal entry.
        """
        invoice = self._create_invoice()
        invoice.with_context(move_action_post_alert=True).action_post()
        wizard = self._open_wizard_like_action_post_does(invoice)

        bank_journal = self.env['account.journal'].search([
            ('type', '=', 'bank'),
            ('company_id', '=', self.company.id),
        ], limit=1)
        payment_method_line = bank_journal.inbound_payment_method_line_ids[:1]
        payment_vals = {
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'amount': 10.0,
            'journal_id': bank_journal.id,
            'payment_method_line_id': payment_method_line.id,
            'partner_id': self.partner.id,
        }

        # Reproduces the bug: creating a payment under the wizard's own
        # (leaked, uncleaned) context crashes with the exact production
        # error, because the payment's delegate-parent write lands on the
        # already-posted invoice instead of a brand new journal entry.
        with self.assertRaises(UserError):
            self.env['account.payment'].with_context(
                wizard.env.context,
            ).create(dict(payment_vals))

        # The guard raises before any persistence happens -- the invoice's
        # own journal is untouched.
        self.assertEqual(invoice.journal_id, self.journal)

        # Fixed path: same leaked context, but cleaned as action_confirm()
        # now does before calling action_post() -- no crash, independent
        # journal entry for the payment.
        from odoo.tools import clean_context
        payment_clean_ctx = self.env['account.payment'].with_context(
            clean_context(wizard.env.context),
        ).create(dict(payment_vals))
        self.assertNotEqual(payment_clean_ctx.move_id, invoice)
        self.assertEqual(invoice.journal_id, self.journal)
