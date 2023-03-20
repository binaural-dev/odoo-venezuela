from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo import Command


class AccountRetentionTestCommon(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(
        cls,
        # chart_template_ref="l10n_ve.ve_chart_template_amd",
        base_currency_ref="base.VEF",
        foreign_currency_ref="base.USD",
    ):
        # super().setUpClass(chart_template_ref=chart_template_ref)
        super().setUpClass()


        base_currency = cls.env.ref(base_currency_ref)
        foreign_currency = cls.env.ref(foreign_currency_ref)
        cls.company_data["company"].write(
            {
                "currency_id": base_currency.id,
                "currency_foreign_id": foreign_currency.id,
            }
        )

        cls.partner_a = cls.env["res.partner"].create(
            {
                "name": "partner_a",
                "prefix_vat": "J",
                "vat": "123456789",
                "taxpayer_type": "formal",
                "type_person_id": cls.env.ref("binaural_payment_extension.type_person_three_binaural_payment_extension").id,

            }
        )

        cls.partner_b = cls.env["res.partner"].create(
            {
                "name": "partner_b",
                "prefix_vat": "J",
                "vat": "22233344",
                "taxpayer_type": "formal",
                "type_person_id": cls.env.ref("binaural_payment_extension.type_person_three_binaural_payment_extension").id,

            }
        )

        cls.journal_sale = cls.env["account.journal"].create(
            {
                "name": "Journal Sale",
                "code": "JPUR",
                "refund_sequence": True,
                "type": "purchase",
                "company_id": cls.company_data["company"].id,
                "fiscal": True,
            }
        )

        cls.journal_nofiscal = cls.env["account.journal"].create(
            {
                "name": "Journal No Fiscal",
                "code": "JNOFISCAL",
                "refund_sequence": True,
                "type": "purchase",
                "company_id": cls.company_data["company"].id,
                "fiscal": False,
            }
        )

        cls.Retention = cls.env["account.retention"]
        cls.partner_a.write(
            {
                "withholding_type_id": cls.env.ref(
                    "binaural_payment_extension.account_withholding_type_75"
                ).id,
            }
        )
        cls.product_c = cls.env["product.product"].create(
            {
                "name": "product_c",
                "uom_id": cls.env.ref("uom.product_uom_unit").id,
                "lst_price": 1000.0,
                "standard_price": 800.0,
                "property_account_income_id": cls.company_data["default_account_revenue"].id,
                "property_account_expense_id": cls.company_data["default_account_expense"].id,
                "taxes_id": [(6, 0, cls.tax_sale_a.ids)],
                "supplier_taxes_id": [(6, 0, cls.tax_purchase_a.ids)],
            }
        )
        cls.product_d = cls.env["product.product"].create(
            {
                "name": "product_d",
                "uom_id": cls.env.ref("uom.product_uom_unit").id,
                "lst_price": 1000.0,
                "standard_price": 800.0,
                "property_account_income_id": cls.company_data["default_account_revenue"].id,
                "property_account_expense_id": cls.company_data["default_account_expense"].id,
                "taxes_id": [(6, 0, cls.tax_sale_a.ids)],
                "supplier_taxes_id": [(6, 0, cls.tax_purchase_a.ids)],
            }
        )
        cls.product_e = cls.env["product.product"].create(
            {
                "name": "product_e",
                "uom_id": cls.env.ref("uom.product_uom_unit").id,
                "lst_price": 1000.0,
                "standard_price": 800.0,
                "property_account_income_id": cls.company_data["default_account_revenue"].id,
                "property_account_expense_id": cls.company_data["default_account_expense"].id,
                "taxes_id": [(6, 0, cls.tax_sale_a.ids)],
                "supplier_taxes_id": [(6, 0, cls.tax_purchase_a.ids)],
            }
        )

        cls.tax_group_a = cls.env["account.tax.group"].create({"name": "IVA 16%"})
        cls.tax_group_b = cls.env["account.tax.group"].create({"name": "IVA 0%"})
        cls.tax_group_c = cls.env["account.tax.group"].create({"name": "IVA 8%"})
        cls.tax_group_d = cls.env["account.tax.group"].create({"name": "IVA 31%"})

        cls.tax_purchase_c = cls.safe_copy(cls.company_data["default_tax_purchase"])
        cls.tax_purchase_d = cls.safe_copy(cls.company_data["default_tax_purchase"])

        cls.tax_purchase_a.write(
            {"amount": 16, "tax_group_id": cls.tax_group_a.id, "name": "IVA 16%"}
        )
        cls.tax_purchase_b.write(
            {"amount": 0, "tax_group_id": cls.tax_group_b.id, "name": "IVA 0%"}
        )
        cls.tax_purchase_c.write(
            {"amount": 8, "tax_group_id": cls.tax_group_c.id, "name": "IVA 8%"}
        )
        cls.tax_purchase_d.write(
            {"amount": 31, "tax_group_id": cls.tax_group_d.id, "name": "IVA 31%"}
        )


        cls.account_move = cls.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "journal_id": cls.journal_sale.id,
                "partner_id": cls.partner_b.id,
                "foreign_currency_id": cls.company_data["company"].currency_foreign_id.id,
                "foreign_rate": 20,
                "foreign_inverse_rate": 0.05,
                "invoice_line_ids": [
                     Command.create(
                        {
                            "product_id": cls.product_a.id,
                            "quantity": 1,
                            "price_unit": 100,
                            "tax_ids": [Command.link(cls.tax_purchase_a.id)],
                        }
                    ),
                ],
            }
        )
        cls.account_move.action_post()
                
