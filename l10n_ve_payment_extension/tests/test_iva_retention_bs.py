from odoo.tests import tagged, Form
from odoo.exceptions import UserError
from .common import AccountRetentionTestCommon
from odoo.tools.float_utils import float_round


@tagged("post_install", "-at_install", "iva_retention", "base_vef_retention")
class TestIvaRetentionBs(AccountRetentionTestCommon):
    def setUp(self):
        super().setUp()
        # Data for the both invoices that are gonna be used for testing the IVA retentions as the
        # one thing that we change between them is the partner which has a different withholding
        # type.
        rate = 23.57
        products = [self.product_a, self.product_b, self.product_c, self.product_d]
        amounts = [2615.69, 4594.3, 9873.72, 2422754.42]
        taxes = [
            self.tax_purchase_a,
            self.tax_purchase_b,
            self.tax_purchase_c,
            self.tax_purchase_d,
        ]

        self.invoice_a = self.init_invoice_for_retentions(
            "in_invoice",
            rate,
            self.partner_a,
            products=products,
            amounts=amounts,
            taxes=taxes,
        )
        self.invoice_b = self.init_invoice_for_retentions(
            "in_invoice",
            rate,
            self.partner_b,
            products=products,
            amounts=amounts,
            taxes=taxes,
        )

        self.expected_retention_lines_data_75 = [
            {
                "aliquot": 16,
                "retention_amount": 313.8825,
                "foreign_retention_amount": 13.32,
            },
            {
                "aliquot": 8,
                "retention_amount": 592.425,
                "foreign_retention_amount": 25.1325,
            },
            {
                "aliquot": 31,
                "retention_amount": 563290.4025,
                "foreign_retention_amount": 23898.615,
            },
        ]
        self.expected_retention_lines_data_100 = [
            {
                "aliquot": 16,
                "retention_amount": 418.51,
                "foreign_retention_amount": 17.76,
            },
            {
                "aliquot": 8,
                "retention_amount": 789.90,
                "foreign_retention_amount": 33.51,
            },
            {
                "aliquot": 31,
                "retention_amount": 751053.87,
                "foreign_retention_amount": 31864.82,
            },
        ]

    def test_account_retention_line_compute_vef_base(self):
        """
        Test that the retention line data is computed correctly for a given invoice with base.VEF
        as the company currency and base.USD as the foreign currency.
        """
        # Testing with a partner that has 75% as withholding amount
        retention_lines_data_75 = self.Retention.compute_retention_lines_data(self.invoice_a)

        # Testing with a partner that has 100% as withholding amount
        retention_lines_data_100 = self.Retention.compute_retention_lines_data(self.invoice_b)

        self.assertIvaRetentionLinesValues(
            retention_lines_data_100, self.expected_retention_lines_data_100
        )
        self.assertIvaRetentionLinesValues(
            retention_lines_data_75, self.expected_retention_lines_data_75
        )

    def test_iva_supplier_retention_validations(self):
        """
        Test the corresponding validations are shown when the user is trying to create an IVA
        supplier retention. These validations are:

            * The company must have a journal for supplier IVA retentions configurated.
            * The invoice must have taxes with values different than 0.
        """
        rate = 23.57
        products = [self.product_a, self.product_b, self.product_c, self.product_d]
        amounts = [2615.69, 4594.3, 9873.72, 2422754.42]
        taxes = [self.tax_purchase_b] * 4

        invoice = self.init_invoice_for_retentions(
            "in_invoice",
            rate,
            self.partner_a,
            products=products,
            amounts=amounts,
            taxes=taxes,
        )

        invoice.generate_iva_retention = True

        # An error should be raised if the company does not have a journal for creating supplier
        # IVA retentions.
        with self.assertRaises(UserError):
            invoice.action_post()

        # An error should be raised if the generate_iva_retention field is True and the invoice does
        # not have lines with taxes.
        self.env.company.iva_supplier_retention_journal_id = self.journal_retentions.id
        with self.assertRaises(UserError):
            invoice.action_post()

        with Form(invoice) as invoice_form:
            self.assertTrue(invoice_form._get_modifier("generate_iva_retention", "invisible"))

    def test_iva_supplier_retention(self):
        """
        Test the iva supplier retention is created succesfully with the corresponding data.
        """
        self.env.company.iva_supplier_retention_journal_id = self.journal_retentions.id
        rounding = self.env.ref("base.VEF").rounding

        # Testing with a partner that has 75% as withholding amount
        self.invoice_a.action_post()
        retention_75 = self.env["account.retention"].search(
            [("number", "=", self.invoice_a.iva_voucher_number)]
        )
        retention_lines_75 = retention_75.retention_line_ids
        self.assertIvaRetentionLinesValues(
            retention_lines_75.read([]),
            [
                {
                    **line,
                    "retention_amount": float_round(
                        line["retention_amount"], precision_rounding=rounding
                    ),
                }
                for line in self.expected_retention_lines_data_75
            ],
        )
        self.assertEqual(
            retention_75.total_invoice_amount,
            sum(retention_lines_75.mapped("invoice_amount")),
        )
        self.assertEqual(
            retention_75.total_iva_amount, sum(retention_lines_75.mapped("iva_amount"))
        )
        self.assertEqual(
            retention_75.total_retention_amount, sum(retention_lines_75.mapped("retention_amount"))
        )

        # Testing with a partner that has 100% as withholding amount
        self.invoice_b.action_post()
        retention = self.env["account.retention"].search(
            [("number", "=", self.invoice_b.iva_voucher_number)]
        )
        retention_lines = retention.retention_line_ids
        rounding = self.env.ref("base.VEF").rounding
        self.assertIvaRetentionLinesValues(
            retention_lines.read([]),
            [
                {
                    **line,
                    "retention_amount": float_round(
                        line["retention_amount"], precision_rounding=rounding
                    ),
                }
                for line in self.expected_retention_lines_data_100
            ],
        )
        self.assertEqual(
            retention.total_invoice_amount,
            sum(retention_lines.mapped("invoice_amount")),
        )
        self.assertEqual(retention.total_iva_amount, sum(retention_lines.mapped("iva_amount")))
        self.assertEqual(
            retention.total_retention_amount, sum(retention_lines.mapped("retention_amount"))
        )
