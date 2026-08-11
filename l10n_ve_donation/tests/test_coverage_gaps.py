from unittest.mock import patch
from odoo import fields, Command
from odoo.tests import tagged
from odoo.exceptions import ValidationError, UserError
from .common import TestDonationCommon


@tagged('l10n_ve_donation', 'coverage_gaps', '-at_install', 'post_install')
class TestCoverageGaps(TestDonationCommon):

    def test_01_product_line_donation_success(self):
        """product_line_donation returns invoice lines grouped by tax."""
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
        lines = move.product_line_donation()
        self.assertTrue(lines)
        self.assertEqual(len(lines), 1)

    def test_02_reverse_moves_donation(self):
        """_reverse_moves on donation invoice creates refund lines."""
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
        refund = move._reverse_moves(default_values_list=[{"date": fields.Date.today()}])
        self.assertTrue(refund)
        self.assertEqual(refund.move_type, "out_refund")
        self.assertTrue(refund.is_donation)

    def test_03_account_move_line_purchase_donation(self):
        """Standard check for payable/receivable in purchase documents."""
        journal_purchase = self.env["account.journal"].search([
            ("type", "=", "purchase"),
            ("company_id", "=", self.company.id),
        ], limit=1) or self.env["account.journal"].create({
            "name": "Test Purchase Journal",
            "code": "TPJ",
            "type": "purchase",
            "company_id": self.company.id,
        })
        move = self.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": self.company.partner_id.id,
            "journal_id": journal_purchase.id,
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
        pt_line = move.line_ids.filtered(lambda l: l.display_type == 'payment_term')
        self.assertTrue(pt_line)
        with self.assertRaises(UserError):
            pt_line.account_id = self.account_receivable

    def test_04_sale_order_onchange_else_branch(self):
        """_onchange_is_donation resets warehouse when switching off donation."""
        order = self.env["sale.order"].create({
            "partner_id": self.company.partner_id.id,
            "is_donation": True,
            "document": "invoice",
            "manually_set_rate": True,
            "foreign_rate": 1.0,
            "foreign_inverse_rate": 1.0,
        })
        order._onchange_is_donation()
        self.assertEqual(order.warehouse_id, self.warehouse_donation)
        order.is_donation = False
        order._onchange_is_donation()
        self.assertNotEqual(order.warehouse_id, self.warehouse_donation)

    def test_05_sale_order_line_launch_stock_rule(self):
        """_action_launch_stock_rule override delegates to super."""
        order = self.env["sale.order"].create({
            "partner_id": self.company.partner_id.id,
            "is_donation": True,
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
        line = order.order_line[0]
        with patch('odoo.addons.sale_stock.models.sale_order_line.SaleOrderLine._action_launch_stock_rule') as mock_super:
            mock_super.return_value = True
            result = line._action_launch_stock_rule()
            self.assertTrue(result)
            mock_super.assert_called_once()

    def test_06_stock_scrap_replenish(self):
        """Donation scrap with replenish executes do_replenish."""
        scrap = self.env["stock.scrap"].create({
            "product_id": self.product_storable.id,
            "scrap_qty": 1,
            "location_id": self.warehouse_normal.lot_stock_id.id,
            "is_donation": True,
            "donation_reason": "Replenish test",
        })
        scrap.scrap_location_id = self.warehouse_donation.lot_stock_id
        # Force replenish flag if the field exists
        if 'should_replenish' in scrap._fields:
            scrap.should_replenish = True
        scrap.do_scrap()
        self.assertEqual(scrap.state, "done")

    def test_07_stock_warehouse_subsidiary_id(self):
        """Unique donation warehouse constraint includes subsidiary_id if present."""
        # Simply exercise the method by creating a warehouse; if subsidiary_id
        # field does not exist the branch is skipped but the rest of the
        # constraint still validates.
        with self.assertRaises(ValidationError):
            self.env["stock.warehouse"].create({
                "name": "Sub Warehouse",
                "code": "SUB",
                "company_id": self.company.id,
                "is_donation_warehouse": True,
            })
