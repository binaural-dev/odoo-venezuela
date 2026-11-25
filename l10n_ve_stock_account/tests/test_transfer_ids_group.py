# -*- coding: utf-8 -*-
from odoo import Command
from odoo.tests import tagged

from .common import StockAccountTestCommon


@tagged("post_install", "-at_install", "test_transfer_ids_group")
class TestTransferIdsGroup(StockAccountTestCommon):
    """`transfer_ids` is only exposed to users of the Inventory group."""

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

        cls.income_account = cls.env["account.account"].create({
            "name": "Transfer Group Income Account",
            "code": "TTGA001",
            "account_type": "income",
            "company_ids": [Command.set([cls.company.id])],
        })
        cls.partner = cls.env["res.partner"].create({"name": "Transfer Group Partner"})
        cls.product = cls.env["product.product"].create({
            "name": "Transfer Group Product",
            "type": "consu",
            "lst_price": 100.0,
            "list_price": 100.0,
            "property_account_income_id": cls.income_account.id,
            "taxes_id": [Command.set([cls.sale_tax.id])],
            "supplier_taxes_id": [Command.clear()],
        })

        cls.billing_user = cls.env["res.users"].create({
            "name": "Transfer Group Billing",
            "login": "transfer_group_billing",
            "group_ids": [Command.set([cls.env.ref("account.group_account_invoice").id])],
        })
        cls.stock_user = cls.env["res.users"].create({
            "name": "Transfer Group Stock",
            "login": "transfer_group_stock",
            "group_ids": [Command.set([
                cls.env.ref("account.group_account_invoice").id,
                cls.env.ref("stock.group_stock_user").id,
            ])],
        })

    def _create_invoice(self, user):
        invoice = self.env["account.move"].with_user(user).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "invoice_line_ids": [Command.create({
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 100.0,
                "tax_ids": [Command.set([self.sale_tax.id])],
            })],
        })
        return invoice

    def test_billing_user_without_stock_group_does_not_see_transfer_ids(self):
        invoice = self._create_invoice(self.billing_user)
        # Reading the invoice must not raise despite the gated field.
        invoice.with_user(self.billing_user).read(["name", "move_type"])
        fields = invoice.with_user(self.billing_user).fields_get(["transfer_ids"])
        self.assertNotIn("transfer_ids", fields)

    def test_stock_user_sees_transfer_ids(self):
        invoice = self._create_invoice(self.stock_user)
        fields = invoice.with_user(self.stock_user).fields_get(["transfer_ids"])
        self.assertIn("transfer_ids", fields)
