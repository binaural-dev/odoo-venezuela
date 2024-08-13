from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import ValidationError
from odoo import Command, fields
from datetime import timedelta


import logging

_logger = logging.getLogger(__name__)


class BinauralAccountTestInvoicingCommon(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref="ve")
        tax_group_obj = cls.env["account.tax.group"]
        tax_obj = cls.env["account.tax"]

        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
                "email": "",
                "vat": "27436422",
            }
        )

        cls.tax_group_0 = tax_group_obj.create({"name": "EXENTO", "sequence": 1})
        cls.tax_group_1 = tax_group_obj.create({"name": "IVA 16%", "sequence": 1})
        cls.tax_group_2 = tax_group_obj.create({"name": "IVA 8%", "sequence": 1})
        cls.tax_group_3 = tax_group_obj.create({"name": "IVA 31%", "sequence": 1})

        cls.tax0 = tax_obj.create(
            {
                "name": "EXENTO",
                "type_tax_use": "sale",
                "amount_type": "percent",
                "amount": "0.00",
                "description": "EXENTO",
                "tax_group_id": cls.tax_group_0.id,
            }
        )

        cls.tax1 = tax_obj.create(
            {
                "name": "IVA 16",
                "type_tax_use": "sale",
                "amount_type": "percent",
                "amount": "16.00",
                "description": "IVA 16",
                "tax_group_id": cls.tax_group_1.id,
            }
        )

        cls.tax2 = tax_obj.create(
            {
                "name": "IVA 8",
                "type_tax_use": "sale",
                "amount_type": "percent",
                "amount": "8.00",
                "description": "IVA 8",
                "tax_group_id": cls.tax_group_2.id,
            }
        )

        cls.tax3 = tax_obj.create(
            {
                "name": "IVA 31",
                "type_tax_use": "sale",
                "amount_type": "percent",
                "amount": "31.00",
                "description": "IVA 31",
                "tax_group_id": cls.tax_group_3.id,
            }
        )

    @classmethod
    def setup_multi_currency_data(cls, default_values=None, rate2016=3.0, rate2017=2.0):
        default_values = default_values or {}
        foreign_currency = cls.env.ref("base.VEF")
        rate2016 = 35
        rate2017 = 37.5
        rate1 = cls.env["res.currency.rate"].create(
            {
                "name": "2016-01-01",
                "rate": rate2016,
                "currency_id": foreign_currency.id,
                "company_id": cls.env.company.id,
            }
        )
        rate2 = cls.env["res.currency.rate"].create(
            {
                "name": "2017-01-01",
                "rate": rate2017,
                "currency_id": foreign_currency.id,
                "company_id": cls.env.company.id,
            }
        )
        rate_now = cls.env["res.currency.rate"].create(
            {
                "name": fields.Date.today() - timedelta(days=1),
                "rate": 40,
                "currency_id": foreign_currency.id,
                "company_id": cls.env.company.id,
            }
        )

        return {
            "currency": foreign_currency,
            "rates": rate1 + rate2 + rate_now,
        }

    @classmethod
    def setup_company_data(cls, company_name, chart_template=None, **kwargs):
        res = super().setup_company_data(company_name, chart_template=chart_template, **kwargs)
        res["company"].write(
            {
                "currency_id": cls.env.ref("base.USD").id,
                "currency_foreign_id": cls.env.ref("base.VEF").id,
            }
        )
        return res

    @classmethod
    def change_tax_included(cls):
        tax_ids = cls.tax0 + cls.tax1 + cls.tax2 + cls.tax3

        if all(tax_ids.mapped("price_include")):
            tax_ids.write({"price_include": False ,"include_base_amount": False})
        else:
            tax_ids.write({"price_include": True ,"include_base_amount": True})

