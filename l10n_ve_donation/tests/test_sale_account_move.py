from unittest.mock import patch
from odoo import fields, Command
from odoo.tests import tagged
from odoo.exceptions import ValidationError, UserError
from .common import TestDonationCommon


@tagged('l10n_ve_donation', 'sale_account', '-at_install', 'post_install')
class TestSaleAccountMove(TestDonationCommon):

    def test_01_sale_order_donation_onchange(self):
        """Creating a donation SO sets partner to company and warehouse to donation."""
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "document": "invoice",
            "manually_set_rate": True,
            "foreign_rate": 1.0,
            "foreign_inverse_rate": 1.0,
        })
        order.is_donation = True
        order._onchange_is_donation()
        self.assertEqual(order.partner_id, self.company.partner_id)
        self.assertEqual(order.document, "invoice")
        self.assertEqual(order.warehouse_id, self.warehouse_donation)

    def test_02_sale_order_donation_no_warehouse(self):
        """ValidationError if no donation warehouse exists."""
        self.warehouse_donation.write({"is_donation_warehouse": False})
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "document": "invoice",
            "manually_set_rate": True,
            "foreign_rate": 1.0,
            "foreign_inverse_rate": 1.0,
        })
        order.is_donation = True
        with self.assertRaises(ValidationError):
            order._onchange_is_donation()
        self.warehouse_donation.write({"is_donation_warehouse": True})

    def test_03_sale_order_partner_change_donation(self):
        """Cannot change partner on a donation SO."""
        order = self.env["sale.order"].create({
            "partner_id": self.company.partner_id.id,
            "is_donation": True,
            "document": "invoice",
            "manually_set_rate": True,
            "foreign_rate": 1.0,
            "foreign_inverse_rate": 1.0,
        })
        with self.assertRaises(ValidationError):
            order.partner_id = self.partner.id
            order._onchange_partner_id_donation()

    def test_04_sale_order_donation_constrain(self):
        """Cannot change is_donation on confirmed order."""
        order = self.env["sale.order"].create({
            "partner_id": self.company.partner_id.id,
            "is_donation": False,
            "document": "invoice",
            "manually_set_rate": True,
            "foreign_rate": 1.0,
            "foreign_inverse_rate": 1.0,
            "order_line": [Command.create({
                "product_id": self.product_donation.id,
                "product_uom_qty": 1,
                "price_unit": 100,
            })]
        })
        order.action_confirm()
        with self.assertRaises(ValidationError):
            order.write({"is_donation": True})

    def test_05_sale_order_prepare_invoice(self):
        """Invoice prepared from donation SO has is_donation=True."""
        order = self.env["sale.order"].create({
            "partner_id": self.company.partner_id.id,
            "is_donation": True,
            "document": "invoice",
            "manually_set_rate": True,
            "foreign_rate": 1.0,
            "foreign_inverse_rate": 1.0,
            "order_line": [Command.create({
                "product_id": self.product_storable.id,
                "product_uom_qty": 1,
                "price_unit": 100,
            })]
        })
        invoice_vals = order._prepare_invoice()
        self.assertTrue(invoice_vals.get("is_donation"))

    def test_06_account_move_check_partner_donation(self):
        """Partner on donation move must be company partner."""
        move = self.env["account.move"].create({
            "move_type": "entry",
            "is_donation": True,
            "journal_id": self.journal_general.id,
            "line_ids": [
                Command.create({
                    "account_id": self.account_expense.id,
                    "debit": 100,
                    "credit": 0,
                    "partner_id": self.company.partner_id.id,
                }),
                Command.create({
                    "account_id": self.account_receivable.id,
                    "debit": 0,
                    "credit": 100,
                    "partner_id": self.company.partner_id.id,
                }),
            ],
        })
        # Should not raise
        move._check_partner_donation()
        # Now change partner on move
        with self.assertRaises(ValidationError):
            move.partner_id = self.partner.id
            move._check_partner_donation()

    def test_07_account_move_check_line_partner_donation(self):
        """Line partner on donation move must be company partner."""
        move = self.env["account.move"].create({
            "move_type": "entry",
            "is_donation": True,
            "journal_id": self.journal_general.id,
            "line_ids": [
                Command.create({
                    "account_id": self.account_expense.id,
                    "debit": 100,
                    "credit": 0,
                    "partner_id": self.company.partner_id.id,
                }),
                Command.create({
                    "account_id": self.account_receivable.id,
                    "debit": 0,
                    "credit": 100,
                    "partner_id": self.company.partner_id.id,
                }),
            ],
        })
        # Change line partner
        line = move.line_ids.filtered(lambda l: l.credit > 0)
        with self.assertRaises(ValidationError):
            line.partner_id = self.partner.id
            move._check_partner_donation()

    def test_08_account_move_post_donation_invoice(self):
        """Posting a donation out_invoice creates a credit note automatically."""
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.company.partner_id.id,
            "journal_id": self.journal_sale.id,
            "is_donation": True,
            "correlative": "99991",
            "invoice_date": fields.Date.today(),
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product_donation.id,
                    "quantity": 1,
                    "price_unit": 100,
                    "tax_ids": [Command.set([self.tax_iva16.id])],
                }),
            ],
        })
        move.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(move.state, "posted")
        # A credit note should exist
        credit_notes = self.env["account.move"].search([
            ("reversed_entry_id", "=", move.id),
        ])
        self.assertTrue(credit_notes)
        self.assertEqual(credit_notes[0].move_type, "out_refund")

    def test_09_account_move_post_donation_entry(self):
        """Posting a donation entry updates line partners and names."""
        move = self.env["account.move"].create({
            "move_type": "entry",
            "is_donation": True,
            "journal_id": self.journal_general.id,
            "ref": "Donation Ref",
            "line_ids": [
                Command.create({
                    "account_id": self.account_expense.id,
                    "debit": 100,
                    "credit": 0,
                    "name": "Line 1",
                    "partner_id": self.company.partner_id.id,
                }),
                Command.create({
                    "account_id": self.account_receivable.id,
                    "debit": 0,
                    "credit": 100,
                    "partner_id": self.company.partner_id.id,
                }),
            ],
        })
        move.with_context(move_action_post_alert=True).action_post()
        for line in move.line_ids:
            self.assertEqual(line.partner_id, self.company.partner_id)
        debit_line = move.line_ids.filtered(lambda l: l.debit > 0)
        self.assertIn("Donation Ref", debit_line.name)

    def test_10_account_move_reverse_donation(self):
        """Reverse a donation invoice creates refund with donation lines."""
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.company.partner_id.id,
            "journal_id": self.journal_sale.id,
            "is_donation": True,
            "correlative": "99992",
            "invoice_date": fields.Date.today(),
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product_donation.id,
                    "quantity": 1,
                    "price_unit": 100,
                    "tax_ids": [Command.set([self.tax_iva16.id])],
                }),
            ],
        })
        move.with_context(move_action_post_alert=True).action_post()
        # Reverse via wizard
        wizard = self.env["account.move.reversal"].with_context(
            active_ids=move.ids,
            active_model="account.move",
        ).create({
            "date": fields.Date.today(),
            "journal_id": move.journal_id.id,
        })
        wizard.reverse_moves()
        refund = wizard.new_move_ids
        self.assertTrue(refund)
        self.assertTrue(refund.is_donation)
        self.assertEqual(refund.move_type, "out_refund")

    def test_11_product_line_donation_no_product(self):
        """Error if no donation product configured."""
        self.product_donation.product_tmpl_id.write({"is_donation_product": False})
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.company.partner_id.id,
            "journal_id": self.journal_sale.id,
            "is_donation": True,
            "invoice_date": fields.Date.today(),
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product_donation.id,
                    "quantity": 1,
                    "price_unit": 100,
                    "tax_ids": [Command.set([self.tax_iva16.id])],
                }),
            ],
        })
        with self.assertRaises(UserError):
            move.product_line_donation()
        self.product_donation.product_tmpl_id.write({"is_donation_product": True})

    def test_12_product_line_donation_no_account(self):
        """Error if no donation account configured."""
        self.company.write({"donation_account_id": False})
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.company.partner_id.id,
            "journal_id": self.journal_sale.id,
            "is_donation": True,
            "invoice_date": fields.Date.today(),
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product_donation.id,
                    "quantity": 1,
                    "price_unit": 100,
                    "tax_ids": [Command.set([self.tax_iva16.id])],
                }),
            ],
        })
        with self.assertRaises(UserError):
            move.product_line_donation()
        self.company.write({"donation_account_id": self.account_expense.id})

    def test_13_get_tax_grouped_lines(self):
        """Tax grouping returns correct base amounts."""
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.company.partner_id.id,
            "journal_id": self.journal_sale.id,
            "is_donation": True,
            "invoice_date": fields.Date.today(),
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product_donation.id,
                    "quantity": 1,
                    "price_unit": 100,
                    "tax_ids": [Command.set([self.tax_iva16.id])],
                }),
                Command.create({
                    "product_id": self.product_donation.id,
                    "quantity": 2,
                    "price_unit": 50,
                    "tax_ids": [Command.set([self.tax_iva16.id])],
                }),
            ],
        })
        groups = move._get_tax_grouped_lines()
        self.assertEqual(len(groups), 1)
        self.assertAlmostEqual(
            groups[tuple(sorted([self.tax_iva16.id]))]["base_amount"],
            200.0,
            places=2,
        )

    def test_14_can_reverse_donation_move(self):
        """Field computed based on group."""
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.company.partner_id.id,
            "journal_id": self.journal_sale.id,
            "is_donation": True,
        })
        move._compute_can_reverse_donation_move()
        self.assertTrue(move.can_reverse_donation_move)

    def test_15_account_move_line_check_payable_receivable_donation(self):
        """Override allows expense account as payment_term for donation."""
        # Create a donation sale move manually with payment term line on expense account
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.company.partner_id.id,
            "journal_id": self.journal_sale.id,
            "is_donation": True,
            "correlative": "99993",
            "invoice_date": fields.Date.today(),
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product_donation.id,
                    "quantity": 1,
                    "price_unit": 100,
                    "tax_ids": [Command.set([self.tax_iva16.id])],
                }),
            ],
        })
        # After creation, find the payment term line and switch its account to expense (donation)
        pt_line = move.line_ids.filtered(lambda l: l.display_type == 'payment_term')
        self.assertTrue(pt_line)
        pt_line.account_id = self.account_expense
        # Trigger the constrains manually to exercise the override
        pt_line._check_payable_receivable()
        # Posting should also succeed
        move.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(move.state, "posted")

    def test_16_print_donation_certificate(self):
        """Print action returns an action dict."""
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.company.partner_id.id,
            "journal_id": self.journal_sale.id,
            "is_donation": True,
            "invoice_date": fields.Date.today(),
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product_donation.id,
                    "quantity": 1,
                    "price_unit": 100,
                }),
            ],
        })
        action = move.print_donation_certificate()
        self.assertTrue(isinstance(action, dict))
        self.assertIn("type", action)

    @patch('odoo.addons.account_asset.models.account_asset.AccountAsset._get_disposal_moves')
    def test_17_asset_disposal_donation(self, mock_get_disposal_moves):
        """Asset disposal as donation sets move ref."""
        # Create a dummy move to receive the ref update
        dummy_move = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": self.asset_journal.id,
            "line_ids": [
                Command.create({"account_id": self.account_expense.id, "debit": 100, "credit": 0}),
                Command.create({"account_id": self.account_income.id, "debit": 0, "credit": 100}),
            ],
        })
        mock_get_disposal_moves.return_value = [dummy_move.id]
        asset = self.env["account.asset"].create({
            "name": "Test Asset",
            "account_asset_id": self.asset_account.id,
            "account_depreciation_id": self.asset_account.copy().id,
            "account_depreciation_expense_id": self.account_expense.id,
            "journal_id": self.asset_journal.id,
            "original_value": 1000,
            "acquisition_date": fields.Date.today(),
            "method_number": 1,
            "method_period": "12",
        })
        asset.validate()
        # Dispose as donation
        asset.set_to_close(
            invoice_line_ids=[],
            date=fields.Date.today(),
            message="Donation Disposal",
        )
        self.assertEqual(dummy_move.ref, "Donation Disposal")

    def test_18_company_settings(self):
        """Company and settings fields are linked correctly."""
        self.assertEqual(self.company.donation_account_id, self.account_expense)
        self.assertEqual(self.company.account_stock_journal_id, self.journal_general)
        settings = self.env["res.config.settings"].create({})
        self.assertEqual(settings.donation_account_id, self.account_expense)
        self.assertEqual(settings.account_stock_journal_id, self.journal_general)

    def test_19_multi_company_warehouse_selection(self):
        """Sale Order MUST pick donation warehouse of the current company."""
        company_b = self.env["res.company"].create({"name": "Company B"})
        warehouse_b = self.env["stock.warehouse"].create({
            "name": "Donation WH B",
            "code": "DWHB",
            "company_id": company_b.id,
            "is_donation_warehouse": True,
        })

        order_a = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "company_id": self.company.id,
        })
        order_a.is_donation = True
        order_a._onchange_is_donation()
        
        self.assertEqual(order_a.warehouse_id, self.warehouse_donation)
        self.assertNotEqual(order_a.warehouse_id, warehouse_b)

        order_b = self.env["sale.order"].with_company(company_b).create({
            "partner_id": self.partner.id,
            "company_id": company_b.id,
        })
        order_b.is_donation = True
        order_b._onchange_is_donation()

        self.assertEqual(order_b.warehouse_id, warehouse_b)
        self.assertNotEqual(order_b.warehouse_id, self.warehouse_donation)
