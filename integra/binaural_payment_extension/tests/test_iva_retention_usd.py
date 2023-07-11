from odoo.tests import tagged
from odoo import Command
from .common import AccountRetentionTestCommon
from odoo.tools.float_utils import float_round


@tagged("post_install", "-at_install", "iva_retention", "base_usd_retention")
class TestIvaRetentionUsd(AccountRetentionTestCommon):
    @classmethod
    def setUpClass(
        cls,
        chart_template_ref="l10n_ve.ve_chart_template_amd",
        base_currency_ref="base.USD",
        foreign_currency_ref="base.VEF",
    ):
        super().setUpClass(
            chart_template_ref=chart_template_ref,
            base_currency_ref=base_currency_ref,
            foreign_currency_ref=foreign_currency_ref,
        )

    def setUp(self):
        super().setUp()
        # Data for both invoices as the one thing that we change between them is the partner
        # which has a different withholding type.
        rate = 23.57
        products = [self.product_a, self.product_b, self.product_c, self.product_d]
        amounts = [110.9758, 194.92196, 418.9085, 102789.72]
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
                "retention_amount": 13.32,
                "foreign_retention_amount": 313.8975,
            },
            {
                "aliquot": 8,
                "retention_amount": 25.1325,
                "foreign_retention_amount": 592.425,
            },
            {
                "aliquot": 31,
                "retention_amount": 23898.6075,
                "foreign_retention_amount": 563290.2375,
            },
        ]
        self.expected_retention_lines_data_100 = [
            {
                "aliquot": 16,
                "retention_amount": 17.76,
                "foreign_retention_amount": 418.53,
            },
            {
                "aliquot": 8,
                "retention_amount": 33.51,
                "foreign_retention_amount": 789.9,
            },
            {
                "aliquot": 31,
                "retention_amount": 31864.81,
                "foreign_retention_amount": 751053.65,
            },
        ]

    def test_account_retention_line_compute_usd_base(self):
        """
        Test that the retention line data is computed correctly for a given invoice with base.USD
        as the company currency and base.VEF as the foreign currency.
        """
        # Testing with a partner that has 75% as withholding amount
        retention_lines_data_75 = self.Retention.compute_retention_lines_data(self.invoice_a)

        # Testing with a partner that has 100% as withholding amount
        retention_lines_data_100 = self.Retention.compute_retention_lines_data(self.invoice_b)

        self.assertIvaRetentionLinesValues(
            retention_lines_data_75, self.expected_retention_lines_data_75
        )
        self.assertIvaRetentionLinesValues(
            retention_lines_data_100, self.expected_retention_lines_data_100
        )

    def test_iva_supplier_retention(self):
        """
        Test the iva supplier retention is created succesfully with the corresponding data.
        """
        rounding = self.env.ref("base.USD").rounding
        self.env.company.iva_supplier_retention_journal_id = self.journal_retentions.id

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
