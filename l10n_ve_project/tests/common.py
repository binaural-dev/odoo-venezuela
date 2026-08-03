# -*- coding: utf-8 -*-

from odoo import fields
from odoo.tests.common import TransactionCase


class L10nVeProjectTestCommon(TransactionCase):
    """Common fixtures for the l10n_ve_project profitability tests.

    A dedicated company is created with VEF as base currency and USD as the
    foreign currency. The exchange rate is fixed to 1 USD = 20 VEF (the USD
    rate is 0.05). All the accounting/analytic/partner/product records needed
    by the profitability flows are created deterministically so the tests can
    run on a fresh database without a chart of accounts.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usd = cls.env.ref("base.USD")
        cls.vef = cls.env.ref("base.VEF")
        cls.country_ve = cls.env.ref("base.ve")

        cls.company = cls.env["res.company"].create({
            "name": "L10n Ve Project Test Company",
            "currency_id": cls.vef.id,
            "foreign_currency_id": cls.usd.id,
        })

        # 1 USD = 20 VEF  ->  the USD rate is 0.05.
        cls.env["res.currency.rate"].create({
            "currency_id": cls.vef.id,
            "rate": 1.0,
            "name": fields.Date.today(),
            "company_id": cls.company.id,
        })
        cls.env["res.currency.rate"].create({
            "currency_id": cls.usd.id,
            "rate": 0.05,
            "name": fields.Date.today(),
            "company_id": cls.company.id,
        })

        cls.pricelist = cls.env["product.pricelist"].create({
            "name": "Test Pricelist",
            "company_id": cls.company.id,
            "currency_id": cls.vef.id,
        })

        cls.account_revenue = cls._create_account("Income", "400000", "income")
        cls.account_expense = cls._create_account("Expense", "600000", "expense")
        cls.account_receivable = cls._create_account("Receivable", "120000", "asset_receivable", reconcile=True)
        cls.account_payable = cls._create_account("Payable", "220000", "liability_payable", reconcile=True)
        cls.account_tax_payable = cls._create_account("Tax Payable", "210000", "liability_current")
        cls.account_tax_receivable = cls._create_account("Tax Receivable", "100900", "asset_current")

        cls.journal_sale = cls.env["account.journal"].create({
            "name": "Test Sale Journal",
            "code": "TSALE",
            "type": "sale",
            "company_id": cls.company.id,
        })
        cls.journal_purchase = cls.env["account.journal"].create({
            "name": "Test Purchase Journal",
            "code": "TPURC",
            "type": "purchase",
            "company_id": cls.company.id,
        })

        # 0% taxes so the invoice amounts stay untaxed while satisfying the
        # l10n_ve_invoice constraint that requires a tax on every product line.
        cls.tax_group = cls.env["account.tax.group"].create({
            "name": "Test Tax Group",
            "country_id": cls.country_ve.id,
        })
        cls.sale_tax = cls.env["account.tax"].create({
            "name": "Sale Tax 0%",
            "amount": 0.0,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "company_id": cls.company.id,
            "country_id": cls.country_ve.id,
            "tax_group_id": cls.tax_group.id,
            "invoice_repartition_line_ids": [
                (0, 0, {"account_id": cls.account_revenue.id, "factor_percent": 100, "repartition_type": "base"}),
                (0, 0, {"account_id": cls.account_tax_payable.id, "factor_percent": 100, "repartition_type": "tax"}),
            ],
            "refund_repartition_line_ids": [
                (0, 0, {"account_id": cls.account_revenue.id, "factor_percent": 100, "repartition_type": "base"}),
                (0, 0, {"account_id": cls.account_tax_payable.id, "factor_percent": 100, "repartition_type": "tax"}),
            ],
        })
        cls.purchase_tax = cls.env["account.tax"].create({
            "name": "Purchase Tax 0%",
            "amount": 0.0,
            "amount_type": "percent",
            "type_tax_use": "purchase",
            "company_id": cls.company.id,
            "country_id": cls.country_ve.id,
            "tax_group_id": cls.tax_group.id,
            "invoice_repartition_line_ids": [
                (0, 0, {"account_id": cls.account_expense.id, "factor_percent": 100, "repartition_type": "base"}),
                (0, 0, {"account_id": cls.account_tax_receivable.id, "factor_percent": 100, "repartition_type": "tax"}),
            ],
            "refund_repartition_line_ids": [
                (0, 0, {"account_id": cls.account_expense.id, "factor_percent": 100, "repartition_type": "base"}),
                (0, 0, {"account_id": cls.account_tax_receivable.id, "factor_percent": 100, "repartition_type": "tax"}),
            ],
        })

        cls.partner = cls.env["res.partner"].create({
            "name": "Test Partner",
            "company_id": False,
        })
        cls.partner.with_company(cls.company).write({
            "property_account_receivable_id": cls.account_receivable.id,
            "property_account_payable_id": cls.account_payable.id,
        })

        cls.product = cls.env["product.product"].create({
            "name": "Test Service",
            "type": "service",
            "list_price": 100.0,
            "taxes_id": [(6, 0, [cls.sale_tax.id])],
            "supplier_taxes_id": [(6, 0, [cls.purchase_tax.id])],
        })
        cls.product.with_company(cls.company).write({
            "property_account_income_id": cls.account_revenue.id,
            "property_account_expense_id": cls.account_expense.id,
        })
        cls.product_consu = cls.env["product.product"].create({
            "name": "Test Consumable",
            "type": "consu",
            "list_price": 100.0,
            "taxes_id": [(6, 0, [cls.sale_tax.id])],
        })
        cls.product_consu.with_company(cls.company).write({
            "property_account_income_id": cls.account_revenue.id,
        })

        cls.analytic_plan = cls.env["account.analytic.plan"].create({"name": "Plan A"})
        cls.analytic_account = cls.env["account.analytic.account"].create({
            "name": "Project AA",
            "code": "AA-1234",
            "plan_id": cls.analytic_plan.id,
            "company_id": cls.company.id,
        })
        cls.project = cls.env["project.project"].with_context(
            tracking_disable=True, mail_create_nolog=True
        ).create({
            "name": "Test Project",
            "partner_id": cls.partner.id,
            "account_id": cls.analytic_account.id,
            "company_id": cls.company.id,
            "allow_billable": True,
        })

        cls.env.user.group_ids |= cls.env.ref("project.group_project_manager")
        cls.env.user.group_ids |= cls.env.ref("sales_team.group_sale_salesman")
        cls.env.user.group_ids |= cls.env.ref("purchase.group_purchase_user")
        cls.env.user.group_ids |= cls.env.ref("account.group_account_invoice")
        cls.env.user.group_ids |= cls.env.ref("account.group_account_readonly")
        cls.env.user.company_id = cls.company.id

    @classmethod
    def _create_account(cls, name, code, account_type, reconcile=False):
        return cls.env["account.account"].create({
            "name": name,
            "code": code,
            "account_type": account_type,
            "reconcile": reconcile,
            "company_ids": [(6, 0, [cls.company.id])],
        })

    def _create_sale_order(self, quantity=2.0, price_unit=100.0, analytic=True, product=None):
        """Create and confirm a sale order with a single service line.

        :return: (sale_order, sale_order_line)
        """
        product = product or self.product
        so = self.env["sale.order"].with_context(tracking_disable=True).create({
            "partner_id": self.partner.id,
            "company_id": self.company.id,
            "pricelist_id": self.pricelist.id,
        })
        line_vals = {
            "product_id": product.id,
            "product_uom_qty": quantity,
            "price_unit": price_unit,
        }
        if analytic:
            line_vals["analytic_distribution"] = {str(self.analytic_account.id): 100}
        sol = self.env["sale.order.line"].with_context(tracking_disable=True).create({
            "order_id": so.id,
            **line_vals,
        })
        so.action_confirm()
        return so, sol

    def _create_purchase_order(self, quantity=2.0, price_unit=100.0, analytic=True):
        """Create and confirm a purchase order with a single service line.

        :return: (purchase_order, purchase_order_line)
        """
        line_vals = {
            "product_id": self.product.id,
            "product_qty": quantity,
            "price_unit": price_unit,
        }
        if analytic:
            line_vals["analytic_distribution"] = {str(self.analytic_account.id): 100}
        po = self.env["purchase.order"].create({
            "partner_id": self.partner.id,
            "company_id": self.company.id,
            "journal_invoice_id": self.journal_purchase.id,
            "date_order": fields.Date.today(),
            "order_line": [(0, 0, line_vals)],
        })
        po.button_confirm()
        return po, po.order_line

    def _create_bill(self, quantity=1.0, price_unit=100.0, purchase_line=None, invoice_origin=False, move_type="in_invoice"):
        """Create (draft) a vendor bill. If ``purchase_line`` is given the bill
        line is linked to the purchase order line (which bypasses the tax check
        of the purchase journal since ``invoice_origin`` is not provided).

        :return: the created ``account.move`` (draft)
        """
        line_vals = {
            "product_id": self.product.id,
            "quantity": quantity,
            "price_unit": price_unit,
            "account_id": self.account_expense.id,
            "analytic_distribution": {str(self.analytic_account.id): 100},
        }
        if purchase_line:
            line_vals["purchase_line_id"] = purchase_line.id
        vals = {
            "move_type": move_type,
            "partner_id": self.partner.id,
            "journal_id": self.journal_purchase.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [(0, 0, line_vals)],
        }
        if invoice_origin:
            vals["invoice_origin"] = invoice_origin
        return self.env["account.move"].create(vals)

    def _create_customer_invoice(self, quantity=1.0, price_unit=100.0, sale_lines=None, analytic=True):
        """Create (draft) a customer invoice. If ``sale_lines`` is given the
        invoice line is linked to those sale order lines.

        :return: the created ``account.move`` (draft)
        """
        line_vals = {
            "product_id": self.product.id,
            "quantity": quantity,
            "price_unit": price_unit,
            "account_id": self.account_revenue.id,
        }
        if analytic:
            line_vals["analytic_distribution"] = {str(self.analytic_account.id): 100}
        if sale_lines:
            line_vals["sale_line_ids"] = [(6, 0, sale_lines.ids)]
        return self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.journal_sale.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [(0, 0, line_vals)],
        })

    def _post(self, move):
        move.with_context(move_action_post_alert=True).action_post()
        return move
