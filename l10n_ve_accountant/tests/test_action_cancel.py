import logging
from odoo.tests import TransactionCase, tagged
from odoo import fields, Command
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_accountant_action_cancel")
class TestAccountPaymentActionCancel(TransactionCase):

    def setUp(self):
        super().setUp()

        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")
        self.country_ve = self.env.ref("base.ve")

        self.company.write({
            "currency_id": self.currency_vef.id,
            "foreign_currency_id": self.currency_usd.id,
            "account_fiscal_country_id": self.country_ve.id,
            "country_id": self.country_ve.id,
        })

        today = fields.Date.today()
        self.env["res.currency.rate"].create({
            "name": today, "currency_id": self.currency_vef.id,
            "inverse_company_rate": 1.0, "company_id": self.company.id,
        })
        self.env["res.currency.rate"].create({
            "name": today, "currency_id": self.currency_usd.id,
            "inverse_company_rate": 40.0, "company_id": self.company.id,
        })

        self.acc_rec = self._get_or_create('120000', 'Receivable', 'asset_receivable', reconcile=True)
        self.acc_inc = self._get_or_create('400000', 'Income', 'income')
        self.acc_bank = self._get_or_create('100100', 'Bank', 'asset_cash', reconcile=True)
        self.acc_tax = self._get_or_create('200000', 'Tax Payable', 'liability_current', reconcile=True)

        self.tax_group = self.env['account.tax.group'].create({
            'name': 'IVA', 'company_id': self.company.id,
            'country_id': self.country_ve.id,
        })
        self.tax_16 = self.env["account.tax"].with_company(self.company).create({
            "name": "IVA 16%", "amount": 16.0, "amount_type": "percent",
            "type_tax_use": "sale", "company_id": self.company.id,
            "tax_group_id": self.tax_group.id,
            "invoice_repartition_line_ids": [
                (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0,
                        'account_id': self.acc_tax.id}),
            ],
            "refund_repartition_line_ids": [
                (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0,
                        'account_id': self.acc_tax.id}),
            ],
        })

        self.partner = self.env["res.partner"].with_company(self.company).create({
            "name": "Test Partner",
            "property_account_receivable_id": self.acc_rec.id,
        })

        self.product = self.env["product.product"].with_company(self.company).create({
            "name": "Test Product",
            "type": "consu",
            "list_price": 100.0,
            "property_account_income_id": self.acc_inc.id,
            "taxes_id": [(5, 0, 0)],
            "supplier_taxes_id": [(5, 0, 0)],
        })

        self.manual_out = self.env.ref("account.account_payment_method_manual_out")

        self.bank_journal = self.env["account.journal"].with_company(self.company).create({
            "name": "Bank Test",
            "type": "bank",
            "code": "BNKT",
            "default_account_id": self.acc_bank.id,
            "inbound_payment_method_line_ids": [(0, 0, {
                "name": "Manual Out",
                "payment_method_id": self.manual_out.id,
                "payment_type": "inbound",
                "payment_account_id": self.acc_bank.id,
            })],
            "outbound_payment_method_line_ids": [(0, 0, {
                "name": "Manual Out",
                "payment_method_id": self.manual_out.id,
                "payment_type": "outbound",
                "payment_account_id": self.acc_bank.id,
            })],
        })

        self.payment_method_line = self.bank_journal.inbound_payment_method_line_ids[:1]

    def _get_or_create(self, code, name, account_type, reconcile=False):
        account = self.env["account.account"].with_company(self.company).search([
            ("code", "=", code), ("company_ids", "in", [self.company.id]),
        ], limit=1)
        if not account:
            account = self.env["account.account"].with_company(self.company).create({
                "name": name, "code": code,
                "account_type": account_type,
                "reconcile": reconcile,
                "company_ids": [(6, 0, [self.company.id])],
            })
        return account

    def _create_invoice(self, currency, lines_data):
        """Create a posted customer invoice."""
        invoice_lines = []
        for qty, price in lines_data:
            invoice_lines.append(Command.create({
                "product_id": self.product.id,
                "quantity": qty,
                "price_unit": price,
                "tax_ids": [(6, 0, [self.tax_16.id])],
            }))
        invoice = self.env["account.move"].with_company(self.company).with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "currency_id": currency.id,
            "invoice_date": fields.Date.today(),
            "date": fields.Date.today(),
            "invoice_line_ids": invoice_lines,
        })
        invoice.action_post()
        return invoice

    def _create_payment(self, invoice, currency, amount):
        """Create and post a payment for an invoice."""
        pay = self.env['account.payment'].with_company(self.company).create({
            'amount': amount,
            'date': fields.Date.today(),
            'currency_id': currency.id,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': invoice.partner_id.id,
            'journal_id': self.bank_journal.id,
            'payment_method_id': self.manual_out.id,
            'payment_method_line_id': self.payment_method_line.id,
            'company_id': self.company.id,
        })
        pay.action_post()
        return pay

    # ═══════════════════════════════════════════════════════════════
    # action_cancel
    # ═══════════════════════════════════════════════════════════════

    def test_01_cancel_payment_posted_move(self):
        """Cancel a posted payment: payment and move must both be cancelled."""
        invoice = self._create_invoice(self.currency_vef, [(1, 1000.0)])
        pay = self._create_payment(invoice, self.currency_vef, 1000.0)

        self.assertEqual(pay.state, 'posted')
        self.assertEqual(pay.move_id.state, 'posted')

        pay.action_cancel()

        self.assertEqual(pay.state, 'canceled',
                         "Payment state must be 'canceled'")
        self.assertEqual(pay.move_id.state, 'cancel',
                         "Move state must be 'cancel' after cancelling a posted payment")

    def test_02_cancel_payment_draft_move_posted_before(self):
        """Cancel a payment whose move was reset to draft after posting:
        posted_before move must be cancelled, not unlinked."""
        invoice = self._create_invoice(self.currency_vef, [(1, 1000.0)])
        pay = self._create_payment(invoice, self.currency_vef, 1000.0)

        self.assertEqual(pay.state, 'posted')
        move = pay.move_id
        self.assertTrue(move.posted_before,
                        "Move must have posted_before=True after posting")

        # Reset to draft (simulates user returning payment to draft)
        pay.action_draft()
        self.assertEqual(pay.state, 'draft')
        self.assertEqual(move.state, 'draft')

        # Now cancel from draft → posted_before move must be cancelled, not deleted
        move_id = move.id
        pay.action_cancel()

        self.assertEqual(pay.state, 'canceled',
                         "Payment state must be 'canceled'")
        # Move still exists (not unlinked) and is cancelled
        move_exists = self.env["account.move"].search([("id", "=", move_id)], limit=1)
        self.assertTrue(move_exists,
                        "posted_before move must NOT be unlinked")
        self.assertEqual(move_exists.state, 'cancel',
                         "posted_before move must be 'cancel'")

    def test_03_cancel_payment_draft_move_never_posted(self):
        """Cancel a draft payment that was NEVER posted:
        the (empty) move must be cleaned up by native Odoo."""
        invoice = self._create_invoice(self.currency_vef, [(1, 1000.0)])

        pay = self.env['account.payment'].with_company(self.company).create({
            'amount': 1000.0,
            'date': fields.Date.today(),
            'currency_id': self.currency_vef.id,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': invoice.partner_id.id,
            'journal_id': self.bank_journal.id,
            'payment_method_id': self.manual_out.id,
            'payment_method_line_id': self.payment_method_line.id,
            'company_id': self.company.id,
        })
        # Payment is draft, move exists as draft but was NEVER posted
        self.assertEqual(pay.state, 'draft')
        self.assertTrue(pay.move_id, "Draft payment must have a move")
        self.assertFalse(pay.move_id.posted_before,
                         "Move never posted must have posted_before=False")
        move_id = pay.move_id.id

        pay.action_cancel()

        self.assertEqual(pay.state, 'canceled')
        move_exists = self.env["account.move"].search([("id", "=", move_id)], limit=1)
        self.assertFalse(move_exists,
                         "Move never posted must be unlinked by native Odoo")

    def test_04_cancel_payment_consistency_posted_before(self):
        """After post → draft → cancel, both states must be consistent."""
        invoice = self._create_invoice(self.currency_vef, [(1, 500.0)])
        pay = self._create_payment(invoice, self.currency_vef, 500.0)

        # posted state
        self.assertEqual(pay.state, 'posted')
        self.assertEqual(pay.move_id.state, 'posted')
        self.assertTrue(pay.move_id.posted_before)

        # Return to draft
        pay.action_draft()
        self.assertEqual(pay.state, 'draft')
        self.assertEqual(pay.move_id.state, 'draft')

        # Cancel
        pay.action_cancel()
        self.assertEqual(pay.state, 'canceled',
                         "After cancel: payment must be canceled")
        self.assertEqual(pay.move_id.state, 'cancel',
                         "After cancel: move must be canceled")
        self.assertTrue(pay.move_id.exists(),
                        "posted_before move must still exist (fiscal trace)")

    def test_05_cancel_payment_twice_posted_before(self):
        """Post → draft → cancel → draft → cancel:
        each cycle must keep states consistent."""
        invoice = self._create_invoice(self.currency_vef, [(1, 300.0)])
        pay = self._create_payment(invoice, self.currency_vef, 300.0)

        # First cycle
        pay.action_draft()
        pay.action_cancel()
        self.assertEqual(pay.state, 'canceled')
        self.assertEqual(pay.move_id.state, 'cancel')

        # Second cycle
        pay.action_draft()
        self.assertEqual(pay.state, 'draft')
        self.assertEqual(pay.move_id.state, 'draft')

        pay.action_cancel()
        self.assertEqual(pay.state, 'canceled')
        self.assertEqual(pay.move_id.state, 'cancel')
