from odoo import Command, fields
from odoo.tests import tagged, Form
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("bin", "account_move", "-at_install", "post_install")
class TestAccountMove(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls, chart_template_ref="l10n_ve.ve_chart_template_amd"):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.out_move = cls.env["account.move"].with_context(default_move_type="out_invoice")
        cls.in_move = cls.env["account.move"].with_context(default_move_type="in_invoice")
    
    def setUp(self):
        super().setUp()
        out_invoice = self.out_move.create(
            {
                "partner_id": self.partner_a.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product_a.id,
                            "quantity": 2,
                        }
                    )
                ],
            }
        )
        self.out_invoice = Form(out_invoice)

        in_invoice = self.in_move.create(
            {
                "partner_id": self.partner_b.id,
                "correlative": "any-seq",
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product_a.id,
                            "quantity": 5,
                        }
                    )
                ],
            }
        )
        self.in_invoice = Form(in_invoice)

    def test_check_sequence_existance(self):
        """Test if the generic invoice sequence is created
        when the module is installed.
        """

        generic_sequence = self.env.ref("l10n_ve_invoice.invoice_correlative")
        self.assertTrue(generic_sequence, "The generic invoice sequence was not created")
    
    def test_check_move_type_correlative_field_state(self):
        """Test to check correlative field state when the move type is
        client related or supplier related.
        """

        self.assertTrue(self.out_invoice._get_modifier("correlative", "readonly"))
        self.assertTrue(self.in_invoice._get_modifier("correlative", "required"))

    def test_correlative_assignment(self):
        """Test case when a invoice is still in draft,
        so the correlative must not be assigned. and when
        the invoice is posted, the correlative must be assigned
        only in the client related invoices.
        """

        out_invoice = self.out_invoice.save()
        in_invoice = self.in_invoice.save()

        self.assertFalse(out_invoice.correlative)
        self.assertTrue(in_invoice.correlative)
        in_correlative = in_invoice.correlative
        
        out_invoice.action_post()
        self.assertTrue(out_invoice.correlative)

        in_invoice.action_post()
        self.assertEqual(in_invoice.correlative, in_correlative)

    def test_correlative_draft_assignment(self):
        """ Test case when a in a posted invoice, the user
        sent back to draft the invoice, so the correlative
        must be still there and if posted again, it should
        not be assigned again.
        """

        out_invoice = self.out_invoice.save()

        out_invoice.action_post()
        out_correlative = out_invoice.correlative
        out_invoice.button_draft()

        self.assertTrue(out_invoice.correlative)
        self.assertEqual(out_invoice.correlative, out_correlative)

        out_invoice.action_post()
        self.assertEqual(out_invoice.correlative, out_correlative)
