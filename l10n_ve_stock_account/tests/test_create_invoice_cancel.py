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
        """Cancelling the invoice must bring qty_invoiced back down."""
        picking = self._create_sale_order(qty=22.0)
        line = picking.sale_id.order_line
        invoice = picking.create_invoice()
        self._post(invoice)
        self.assertEqual(line.qty_invoiced, 22.0)

        invoice.button_cancel()

        self.assertEqual(line.qty_invoiced, 0.0)

    def test_cancel_draft_invoice_also_reverts(self):
        """The invoice doesn't need to be posted for the revert to apply."""
        picking = self._create_sale_order()
        line = picking.sale_id.order_line
        invoice = picking.create_invoice()

        invoice.button_cancel()

        self.assertEqual(picking.state_guide_dispatch, "to_invoice")
        self.assertEqual(line.qty_invoiced, 0.0)

    def test_cancel_keeps_partial_state_with_other_valid_invoice(self):
        """If another non-cancelled invoice still links to the guide, it
        should land on 'invoiced_partial' instead of 'to_invoice'."""
        picking = self._create_sale_order()
        invoice = picking.create_invoice()
        self._post(invoice)

        other_invoice = invoice.copy({"transfer_ids": [Command.set(picking.ids)]})
        self._post(other_invoice)

        invoice.button_cancel()

        self.assertEqual(picking.state_guide_dispatch, "invoiced_partial")
