from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged("post_install", "-at_install", "igtf_pos_config")
class IgtfPosConfigTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.igtf_percentage = 3.0
        cls.pos_config = cls.env["pos.config"].create({
            "name": "Test POS Config IGTF",
            "company_id": cls.company.id,
        })

    def test_01_igtf_percentage_related(self):
        self.assertAlmostEqual(self.pos_config.igtf_percentage, 3.0)

    def test_02_igtf_percentage_default_zero(self):
        company2 = self.env["res.company"].create({
            "name": "Test Company 2",
        })
        journal2 = self.env["account.journal"].create({
            "name": "Test Journal 2",
            "code": "TJT2",
            "type": "general",
            "company_id": company2.id,
        })
        config2 = self.env["pos.config"].create({
            "name": "Test Config 2",
            "company_id": company2.id,
            "journal_id": journal2.id,
            "payment_method_ids": [(5, 0, 0)],
        })
        self.assertAlmostEqual(config2.igtf_percentage, 0.0)
