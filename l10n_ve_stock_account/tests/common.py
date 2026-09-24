# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase
from odoo import fields


class StockAccountTestCommon(TransactionCase):
    """Shared fiscal/currency fixtures for l10n_ve_stock_account and
    l10n_ve_donation tests.

    A minimal test database has none of these by default, which several
    unrelated pieces of code implicitly require:
    - `l10n_ve_sale.action_confirm()` needs a `res.currency.rate` for the
      confirmation date (`res.currency.rate.compute_rate(...,
      raise_if_not_found=True)`).
    - `l10n_ve_accountant` requires every product to resolve exactly one
      sale/purchase tax, either explicitly or via the company's default
      fiscal configuration.
    - `account.tax`/`account.tax.group` both require a `country_id` (no
      usable default without real fiscal localization data loaded), and
      `account.move`'s own tax/fiscal-position check requires the
      company's `account_fiscal_country_id` to match.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company
        cls.currency_usd = cls.env.ref("base.USD")
        cls.currency_usd.active = True
        cls.currency_vef = cls.env.ref("base.VEF")
        cls.currency_vef.active = True
        cls.company.write({
            "currency_id": cls.currency_vef.id,
            "foreign_currency_id": cls.currency_usd.id,
        })

        cls.env["res.currency.rate"].create({
            "currency_id": cls.currency_usd.id,
            "company_id": cls.company.id,
            "name": fields.Date.today(),
            "rate": 1.0 / 380.0,
        })

        cls.country_ve = cls.env.ref("base.ve")
        cls.company.account_fiscal_country_id = cls.country_ve.id
        cls.tax_group = cls.env["account.tax.group"].create({
            "name": "Test Tax Group",
            "country_id": cls.country_ve.id,
        })
        cls.sale_tax = cls.env["account.tax"].create({
            "name": "Test Sale Tax 16%",
            "amount": 16,
            "type_tax_use": "sale",
            "company_id": cls.company.id,
            "tax_group_id": cls.tax_group.id,
            "country_id": cls.country_ve.id,
        })
        cls.company.account_sale_tax_id = cls.sale_tax.id
        cls.purchase_tax = cls.env["account.tax"].create({
            "name": "Test Purchase Tax 16%",
            "amount": 16,
            "type_tax_use": "purchase",
            "company_id": cls.company.id,
            "tax_group_id": cls.tax_group.id,
            "country_id": cls.country_ve.id,
        })
        cls.company.account_purchase_tax_id = cls.purchase_tax.id
