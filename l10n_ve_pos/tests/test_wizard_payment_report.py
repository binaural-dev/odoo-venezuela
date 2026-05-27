from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged("post_install", "-at_install", "payment_report")
class PaymentReportWizardTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.wizard = cls.env["pos.payment.report"].create({})

    def test_01_default_dates(self):
        self.assertIsNotNone(self.wizard.start_date)
        self.assertIsNotNone(self.wizard.end_date)

    def test_02_default_categories(self):
        self.assertTrue(len(self.wizard.category_ids) > 0)

    def test_03_default_pos_configs(self):
        self.assertTrue(len(self.wizard.pos_config_ids) > 0)

    def test_04_default_type_report(self):
        self.assertEqual(self.wizard.type_report, "by_cash_register")

    def test_05_default_show_categories(self):
        self.assertEqual(self.wizard.show_categories, "both")

    def test_06_generate_report(self):
        with self.assertRaises(Exception):
            self.wizard.generate_report()
