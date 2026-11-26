# -*- coding: utf-8 -*-
import logging
from odoo.tests import tagged
from odoo import Command

from .common import StockAccountTestCommon

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "test_create_invoice_cancel")
class TestCancelInvoiceFromPicking(StockAccountTestCommon):
    """
    Regression tests for ticket #15521: cancelling an invoice created from a
    dispatch-guide picking must revert the guide's invoicing state and the
    sale order line's qty_invoiced, the same way they were set when the
    invoice was created.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.sale_journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.company.id)], limit=1
        )
        if not cls.sale_journal:
            cls.sale_journal = cls.env["account.journal"].create({
                "name": "Customer Invoices Test",
                "type": "sale",
                "code": "TSINV",
                "company_id": cls.company.id,
            })
        cls.company.customer_journal_id = cls.sale_journal.id

        cls.income_account = cls.env["account.account"].create({
            "name": "Test Income Account",
            "code": "TINC002",
            "account_type": "income",
            "company_ids": [Command.set([cls.company.id])],
        })

        cls.partner = cls.env["res.partner"].create({"name": "Test Partner Cancel"})
        cls.product = cls.env["product.product"].create({
            "name": "Test Product Cancel",
            "type": "consu",
            "lst_price": 100.0,
            "list_price": 100.0,
            "property_account_income_id": cls.income_account.id,
            "taxes_id": [Command.set([cls.sale_tax.id])],
            "supplier_taxes_id": [Command.clear()],
        })

    def _create_sale_order(self, qty=22.0, price_unit=100.0):
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "document": "dispatch_guide",
            "order_line": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": qty,
                "price_unit": price_unit,
            })],
        })
        so.action_confirm()

        picking = so.picking_ids
        picking.move_ids.write({"quantity": qty, "picked": True})
        picking.button_validate()
        return picking

    def _post(self, invoice):
        # l10n_ve_accountant wraps action_post behind a confirmation wizard
        # unless this context flag is set (same bypass create_invoice()
        # callers use elsewhere in this module).
        invoice.with_context(move_action_post_alert=True).action_post()

    def test_cancel_reverts_guide_dispatch_state(self):
        """Cancelling the invoice must put the guide back to 'to_invoice'."""
        picking = self._create_sale_order()
        invoice = picking.create_invoice()
        self._post(invoice)
        self.assertEqual(picking.state_guide_dispatch, "invoiced")

        invoice.button_cancel()

        self.assertEqual(picking.state_guide_dispatch, "to_invoice")
        self.assertTrue(picking.show_create_invoice)

    def test_cancel_reverts_qty_invoiced(self):
        """Cancelling the invoice must bring qty_invoiced and invoice_status back down,
        without creating stock moves, and allow re-invoicing the delivery."""
        picking = self._create_sale_order(qty=22.0)
        line = picking.sale_id.order_line
        move_count_before = len(picking.move_ids)
        invoice = picking.create_invoice()
        self._post(invoice)
        self.assertEqual(line.qty_invoiced, 22.0)

        invoice.button_cancel()

        self.assertEqual(line.qty_invoiced, 0.0)
        self.assertEqual(picking.sale_id.invoice_status, "to invoice")
        self.assertEqual(len(picking.move_ids), move_count_before)
        self.assertEqual(picking.state, "done")

        new_invoice = picking.create_invoice()
        self.assertTrue(new_invoice)
        self.assertEqual(picking.state_guide_dispatch, "invoiced")
        self.assertEqual(line.qty_invoiced, 22.0)

    def test_cancel_draft_invoice_also_reverts(self):
        """The invoice doesn't need to be posted for the revert to apply."""
        picking = self._create_sale_order()
        line = picking.sale_id.order_line
        invoice = picking.create_invoice()

        invoice.button_cancel()

        self.assertEqual(picking.state_guide_dispatch, "to_invoice")
        self.assertEqual(line.qty_invoiced, 0.0)
        self.assertEqual(picking.sale_id.invoice_status, "to invoice")

    def test_unlink_draft_invoice_reverts_guide_and_order(self):
        """Deleting (unlink) a draft invoice created from a picking must revert
        state_guide_dispatch, qty_invoiced, and invoice_status without touching stock moves."""
        picking = self._create_sale_order(qty=22.0)
        line = picking.sale_id.order_line
        move_count_before = len(picking.move_ids)
        invoice = picking.create_invoice()
        self.assertEqual(picking.state_guide_dispatch, "invoiced")
        self.assertFalse(picking.show_create_invoice)
        self.assertEqual(line.qty_invoiced, 22.0)

        invoice.unlink()

        self.assertEqual(picking.state_guide_dispatch, "to_invoice")
        self.assertTrue(picking.show_create_invoice)
        self.assertEqual(line.qty_invoiced, 0.0)
        self.assertEqual(picking.sale_id.invoice_status, "to invoice")
        self.assertEqual(len(picking.move_ids), move_count_before)
        self.assertEqual(picking.state, "done")

        new_invoice = picking.create_invoice()
        self.assertTrue(new_invoice)
        self.assertEqual(picking.state_guide_dispatch, "invoiced")

    def test_cancel_keeps_partial_state_with_other_valid_invoice(self):
        """If another non-cancelled invoice still links to the guide, it
        should land on 'invoiced_partial' and keep qty_invoiced covered by it."""
        picking = self._create_sale_order(qty=22.0)
        line = picking.sale_id.order_line
        invoice = picking.create_invoice()
        self._post(invoice)

        other_invoice = invoice.copy({"transfer_ids": [Command.set(picking.ids)]})
        self._post(other_invoice)

        invoice.button_cancel()

        self.assertEqual(picking.state_guide_dispatch, "invoiced_partial")
        self.assertEqual(line.qty_invoiced, 22.0)
        self.assertEqual(picking.sale_id.invoice_status, "invoiced")

    def test_cancel_one_of_two_created_invoices_keeps_remaining_qty(self):
        """When two invoices are created from the same picking, cancelling one
        reverts only its share and leaves qty_invoiced covering the remaining one;
        cancelling the last one drops qty_invoiced back to 0."""
        picking = self._create_sale_order(qty=22.0)
        line = picking.sale_id.order_line
        invoice_1 = picking.create_invoice()
        invoice_2 = picking.create_invoice()
        self._post(invoice_2)
        self.assertEqual(line.qty_invoiced, 44.0)

        invoice_1.button_cancel()

        self.assertEqual(picking.state_guide_dispatch, "invoiced_partial")
        self.assertEqual(line.qty_invoiced, 22.0)
        self.assertEqual(picking.sale_id.invoice_status, "invoiced")

        invoice_2.button_cancel()

        self.assertEqual(picking.state_guide_dispatch, "to_invoice")
        self.assertTrue(picking.show_create_invoice)
        self.assertEqual(line.qty_invoiced, 0.0)
        self.assertEqual(picking.sale_id.invoice_status, "to invoice")

    def test_unlink_cancelled_invoice_does_not_double_revert(self):
        """Unlinking an already-cancelled invoice must not subtract qty_invoiced again."""
        picking = self._create_sale_order(qty=22.0)
        line = picking.sale_id.order_line
        invoice_1 = picking.create_invoice()
        invoice_2 = picking.create_invoice()
        self._post(invoice_2)

        invoice_1.button_cancel()
        self.assertEqual(line.qty_invoiced, 22.0)
        self.assertEqual(picking.state_guide_dispatch, "invoiced_partial")

        invoice_1.unlink()

        self.assertEqual(line.qty_invoiced, 22.0)
        self.assertEqual(picking.state_guide_dispatch, "invoiced_partial")

    def test_cancel_then_button_draft_and_post_restores_invoiced_state(self):
        """Resetting a cancelled picking invoice to draft and posting it again
        must restore the guide and sale order to invoiced so it cannot be billed twice."""
        picking = self._create_sale_order(qty=22.0)
        line = picking.sale_id.order_line
        move_count_before = len(picking.move_ids)
        invoice = picking.create_invoice()
        self._post(invoice)

        invoice.button_cancel()
        self.assertEqual(picking.state_guide_dispatch, "to_invoice")
        self.assertEqual(line.qty_invoiced, 0.0)
        self.assertEqual(picking.sale_id.invoice_status, "to invoice")
        self.assertTrue(picking.show_create_invoice)

        invoice.button_draft()

        self.assertEqual(invoice.state, "draft")
        self.assertEqual(picking.state_guide_dispatch, "invoiced")
        self.assertEqual(line.qty_invoiced, 22.0)
        self.assertEqual(picking.sale_id.invoice_status, "invoiced")
        self.assertFalse(picking.show_create_invoice)

        self._post(invoice)

        self.assertEqual(invoice.state, "posted")
        self.assertEqual(picking.state_guide_dispatch, "invoiced")
        self.assertEqual(line.qty_invoiced, 22.0)
        self.assertEqual(picking.sale_id.invoice_status, "invoiced")
        self.assertFalse(picking.show_create_invoice)
        self.assertEqual(len(picking.move_ids), move_count_before)

    def test_button_draft_from_posted_does_not_double_count_qty_invoiced(self):
        """Resetting a posted (non-cancelled) invoice to draft must not add qty_delivered again."""
        picking = self._create_sale_order(qty=22.0)
        line = picking.sale_id.order_line
        invoice = picking.create_invoice()
        self._post(invoice)
        self.assertEqual(line.qty_invoiced, 22.0)

        invoice.button_draft()

        self.assertEqual(invoice.state, "draft")
        self.assertEqual(picking.state_guide_dispatch, "invoiced")
        self.assertEqual(line.qty_invoiced, 22.0)
        self.assertEqual(picking.sale_id.invoice_status, "invoiced")
