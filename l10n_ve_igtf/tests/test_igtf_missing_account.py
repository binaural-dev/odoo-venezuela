from odoo.tests import tagged, Form
from .test_common_purchase_book_igtf_usd_provider_formal import IGTFTestCommonPurchaseBook
from odoo.exceptions import ValidationError, UserError
from psycopg2.errors import CheckViolation

@tagged("igtf_missing_account", "post_install", "-at_install")
class TestIGTFMissingAccount(IGTFTestCommonPurchaseBook):

    def setUp(self):
        super().setUp()
        # Unset IGTF accounts to simulate user configuration error
        self.company.write({
            'customer_account_igtf_id': False,
            'supplier_account_igtf_id': False,
        })

    def test_payment_missing_igtf_account(self):
        """Test that payment raises a clear error when IGTF account is missing, instead of DB constraint."""
        
        # Create invoice
        invoice = self._create_invoice_usd(100.0)
        invoice.action_post()

        # Standard Bank Journal (IGTF enabled)
        bank_journal = self.bank_journal_usd
        
        # Register payment
        # This should now raise UserError due to our fix
        with self.assertRaises(UserError):
            register_payments = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=invoice.ids).create({
                'journal_id': bank_journal.id,
                'currency_id': self.currency_usd.id,
                'amount': 100.0,
            })
            register_payments._create_payments()
