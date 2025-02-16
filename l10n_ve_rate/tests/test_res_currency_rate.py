from datetime import timedelta
from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo import Command, fields
from odoo.tools import float_compare


@tagged("res_currency_rate", "bin", "-at_install", "post_install")
class TestResCurrencyRate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        base_usd = cls.env.ref("base.USD")
        base_vef = cls.env.ref("base.VEF")

        base_usd.write(
            {
                "rate_ids": [
                    Command.create({"name": fields.Date.today(), "inverse_company_rate": 22}),
                    Command.create(
                        {
                            "name": fields.Date.today() - timedelta(days=1),
                            "inverse_company_rate": 25,
                        }
                    ),
                ]
            }
        )

        base_vef.write(
            {
                "rate_ids": [
                    Command.create({"name": fields.Date.today(), "company_rate": 22}),
                    Command.create(
                        {
                            "name": fields.Date.today() - timedelta(days=1),
                            "company_rate": 25,
                        }
                    ),
                ]
            }
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        base_usd = cls.env.ref("base.USD")
        base_vef = cls.env.ref("base.VEF")

        base_usd.write({"rate_ids": [Command.delete(rate.id) for rate in base_usd.rate_ids]})
        base_vef.write({"rate_ids": [Command.delete(rate.id) for rate in base_usd.rate_ids]})

    def test_compute_rate_with_different_dates(self):
        """
        Test that the compute_rate method returns the correct rate and inverse rate for the given
        currency and date.
        """
        base_usd_id = self.env["ir.model.data"]._xmlid_to_res_id(
            "base.USD", raise_if_not_found=False
        )
        base_vef_id = self.env["ir.model.data"]._xmlid_to_res_id(
            "base.VEF", raise_if_not_found=False
        )

        # Test with today's date and USD as foreign currency
        compute_rate_usd_result_today = self.env["res.currency.rate"].compute_rate(
            base_usd_id, fields.Date.today()
        )
        self.assertEqual(float_compare(compute_rate_usd_result_today["foreign_rate"], 22, 2), 0)
        self.assertEqual(
            float_compare(
                compute_rate_usd_result_today["foreign_inverse_rate"], 0.045454545454545456, 18
            ),
            0,
        )

        # Test with yesterday's date and USD as foreign currency
        compute_rate_usd_result_yesterday = self.env["res.currency.rate"].compute_rate(
            base_usd_id, fields.Date.today() - timedelta(days=1)
        )
        self.assertEqual(float_compare(compute_rate_usd_result_yesterday["foreign_rate"], 25, 2), 0)
        self.assertEqual(
            float_compare(compute_rate_usd_result_yesterday["foreign_inverse_rate"], 0.04, 2), 0
        )

        # Test with today's date and VEF as foreign currency
        compute_rate_vef_result_today = self.env["res.currency.rate"].compute_rate(
            base_vef_id, fields.Date.today()
        )
        self.assertEqual(float_compare(compute_rate_vef_result_today["foreign_rate"], 22, 2), 0)
        self.assertEqual(
            float_compare(compute_rate_vef_result_today["foreign_inverse_rate"], 22, 2), 0
        )

        # Test with yesterday's date and VEF as foreign currency
        compute_rate_vef_result_yesterday = self.env["res.currency.rate"].compute_rate(
            base_vef_id, fields.Date.today() - timedelta(days=1)
        )
        self.assertEqual(float_compare(compute_rate_vef_result_yesterday["foreign_rate"], 25, 2), 0)
        self.assertEqual(
            float_compare(compute_rate_vef_result_yesterday["foreign_inverse_rate"], 25, 2), 0
        )

    def test_compute_rate_with_a_date_without_rate(self):
        """
        Test that the compute_rate method returns the last rate when the given date does not
        have a rate.
        """
        base_usd_id = self.env["ir.model.data"]._xmlid_to_res_id(
            "base.USD", raise_if_not_found=False
        )
        base_vef_id = self.env["ir.model.data"]._xmlid_to_res_id(
            "base.VEF", raise_if_not_found=False
        )

        # Test with USD as foreign currency
        compute_rate_usd_result = self.env["res.currency.rate"].compute_rate(
            base_usd_id, fields.Date.today() + timedelta(days=2)
        )
        self.assertEqual(float_compare(compute_rate_usd_result["foreign_rate"], 22, 2), 0)
        self.assertEqual(
            float_compare(
                compute_rate_usd_result["foreign_inverse_rate"], 0.045454545454545456, 18
            ),
            0,
        )

        # Test with VEF as foreign currency
        compute_rate_vef_result = self.env["res.currency.rate"].compute_rate(
            base_vef_id, fields.Date.today() + timedelta(days=2)
        )
        self.assertEqual(float_compare(compute_rate_vef_result["foreign_rate"], 22, 2), 0)
        self.assertEqual(
            float_compare(compute_rate_vef_result["foreign_inverse_rate"], 22, 2), 0
        )
