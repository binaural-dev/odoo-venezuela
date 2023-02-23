from odoo.tests import Form
from odoo.tests import tagged
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@tagged("account_asset", "bin", "-at_install")
class TestAccountMove(TestAccountReportsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account_asset_model_fixedassets = cls.env["account.asset"].create(
            {
                "account_depreciation_id": cls.company_data["default_account_assets"].copy().id,
                "account_depreciation_expense_id": cls.company_data["default_account_expense"].id,
                "account_asset_id": cls.company_data["default_account_assets"].id,
                "journal_id": cls.company_data["default_journal_purchase"].id,
                "name": "Hardware - 3 Years",
                "method_number": 3,
                "method_period": "12",
                "state": "model",
            }
        )

        cls.closing_invoice = cls.env["account.move"].create(
            {"move_type": "out_invoice", "invoice_line_ids": [(0, 0, {"price_unit": 100})]}
        )

        cls.env.company.loss_account_id = cls.company_data["default_account_expense"].copy()
        cls.env.company.gain_account_id = cls.company_data["default_account_revenue"].copy()
        cls.assert_counterpart_account_id = cls.company_data["default_account_expense"].copy().id

        cls.move_ids = cls.env["account.move"].create(
            [
                {
                    "ref": "line1",
                    "foreign_rate": 20.0,
                    "foreign_inverse_rate": 0.05,
                    "line_ids": [
                        (
                            0,
                            0,
                            {
                                "account_id": cls.company_data["default_account_expense"].id,
                                "debit": 300,
                                "name": "Furniture",
                            },
                        ),
                        (
                            0,
                            0,
                            {
                                "account_id": cls.company_data["default_account_assets"].id,
                                "credit": 300,
                            },
                        ),
                    ],
                },
                {
                    "ref": "line2",
                    "foreign_rate": 20.0,
                    "foreign_inverse_rate": 0.05,
                    "line_ids": [
                        (
                            0,
                            0,
                            {
                                "account_id": cls.company_data["default_account_expense"].id,
                                "debit": 600,
                                "name": "Furniture too",
                            },
                        ),
                        (
                            0,
                            0,
                            {
                                "account_id": cls.company_data["default_account_assets"].id,
                                "credit": 600,
                            },
                        ),
                    ],
                },
            ]
        )
        cls.move_ids.action_post()
        cls.Asset = cls.env["account.asset"]

    def test_that_the_asset_has_the_rates_from_the_original_move_line_ids(self):
        """
        Test that the asset has the rate and inverse rate from the original move line ids.
        """
        move_line_ids = self.move_ids.mapped("line_ids").filtered(lambda x: x.debit)

        asset_form = Form(
            self.env["account.asset"].with_context(
                default_original_move_line_ids=move_line_ids.ids, asset_type="purchase"
            )
        )
        asset_form._values["original_move_line_ids"] = [(6, 0, move_line_ids.ids)]
        asset_form._perform_onchange(["original_move_line_ids"])
        asset_form.account_depreciation_expense_id = self.company_data["default_account_expense"]
        asset_form.save()

        asset = self.Asset.browse(asset_form.id)
        self.assertEqual(asset.foreign_rate, 20.0)
        self.assertEqual(asset.foreign_inverse_rate, 0.05)

    def test_that_the_moves_created_by_the_asset_have_its_rates(self):
        """
        Test that the moves created by the asset have the rate and inverse rate from the asset.
        """
        move_line_ids = self.move_ids.mapped("line_ids").filtered(lambda x: x.debit)

        asset_form = Form(
            self.env["account.asset"].with_context(
                default_original_move_line_ids=move_line_ids.ids, asset_type="purchase"
            )
        )
        asset_form._values["original_move_line_ids"] = [(6, 0, move_line_ids.ids)]
        asset_form._perform_onchange(["original_move_line_ids"])
        asset_form.account_depreciation_expense_id = self.company_data["default_account_expense"]
        asset_form.save()

        asset = self.Asset.browse(asset_form.id)
        asset.compute_depreciation_board()

        depreciation_move_ids = asset.depreciation_move_ids.mapped("line_ids")
        all(
            self.assertEqual(move.foreign_rate, 20.0)
            and self.assertEqual(move.foreign_inverse_rate, 0.05)
            for move in depreciation_move_ids
        )
