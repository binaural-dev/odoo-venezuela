import random
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import Form
from odoo import fields
from odoo.tools import float_compare


class AccountRetentionTestCommon(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(
        cls,
        chart_template_ref="l10n_ve.ve_chart_template_amd",
        base_currency_ref="base.VEF",
        foreign_currency_ref="base.USD",
    ):
        super().setUpClass(chart_template_ref=chart_template_ref)

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
                "type_person_id": cls.env.ref(
                    "l10n_ve_payment_extension.type_person_three_binaural_payment_extension"
                ).id,
            }
        )

        cls.partner_b = cls.env["res.partner"].create(
            {
                "name": "partner_b",
                "prefix_vat": "J",
                "vat": "22233344",
                "taxpayer_type": "formal",
                "type_person_id": cls.env.ref(
                    "l10n_ve_payment_extension.type_person_three_binaural_payment_extension"
                ).id,
            }
        )

        cls.journal_purchase = cls.env["account.journal"].create(
            {
                "name": "Journal Sale",
                "code": "JPUR",
                "refund_sequence": True,
                "type": "purchase",
                "company_id": cls.company_data["company"].id,
            }
        )
        cls.journal_retentions = cls.env["account.journal"].create(
            {
                "name": "Journal Retentions",
                "code": "JRET",
                "refund_sequence": True,
                "type": "bank",
                "company_id": cls.company_data["company"].id,
            }
        )

        cls.Retention = cls.env["account.retention"]
        cls.partner_a.write(
            {
                "withholding_type_id": cls.env.ref(
                    "l10n_ve_payment_extension.account_withholding_type_75"
                ).id,
            }
        )
        cls.partner_b.write(
            {
                "withholding_type_id": cls.env.ref(
                    "l10n_ve_payment_extension.account_withholding_type_100"
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

    @classmethod
    def init_invoice_for_retentions(
        cls,
        move_type,
        foreign_rate,
        partner=None,
        invoice_date=None,
        products=None,
        post=False,
        amounts=None,
        taxes=None,
        company=False,
    ):
        """
        Helper to create an invoice with different taxes per line for testing retentions.
        """
        move_form = Form(
            cls.env["account.move"]
            .with_company(company or cls.env.company)
            .with_context(
                default_move_type=move_type,
                default_foreign_currency_id=cls.company_data["company"].currency_foreign_id.id,
            )
        )
        move_form.correlative = str(random.randint(0, 10000))
        move_form.journal_id = cls.journal_purchase
        move_form.foreign_rate = foreign_rate
        move_form.invoice_date = invoice_date or fields.Date.today()
        move_form.generate_iva_retention = True
        # According to the state or type of the invoice, the date field is sometimes visible or not
        # Besides, the date field can be put multiple times in the view
        if not move_form._get_modifier("date", "invisible"):
            move_form.date = move_form.invoice_date
        move_form.partner_id = partner or cls.partner_a

        for product, amount, tax in zip(products or [], amounts or [], taxes or []):
            with move_form.invoice_line_ids.new() as line_form:
                line_form.product_id = product
                # line_form.name = "Test Line"
                line_form.price_unit = amount
                if taxes is not None:
                    line_form.tax_ids.clear()
                    line_form.tax_ids.add(tax)

        rslt = move_form.save()

        if post:
            rslt.action_post()

        return rslt

    def assertIvaRetentionLinesValues(self, lines, expected_lines):
        """
        Helper to compare the values of the iva retention lines with some expected results.

        Parameters
        ----------
        lines : list of dict
            The lines to compare.
        expected_lines : list of dict
            The lines with the expected values.
        """
        self.assertEqual(len(lines), len(expected_lines))
        errors = []
        for line, expected_line in zip(lines, expected_lines):
            self.assertEqual(line["aliquot"], expected_line["aliquot"])
            retention_amount_compare = float_compare(
                line["retention_amount"], expected_line["retention_amount"], 4
            )
            if retention_amount_compare != 0:
                errors += [
                    "\n==== Differences with the retention amount ====",
                    f"Current Value: {line['retention_amount']}",
                    f"Expected Value: {expected_line['retention_amount']}",
                ]

            foreign_retention_amount_compare = float_compare(
                line["foreign_retention_amount"], expected_line["foreign_retention_amount"], 4
            )

            if foreign_retention_amount_compare != 0:
                errors += [
                    "\n==== Differences with the foreign retention amount ====",
                    f"Current Value: {line['foreign_retention_amount']}",
                    f"Expected Value: {expected_line['foreign_retention_amount']}",
                ]
        if errors:
            self.fail("\n".join(errors))
