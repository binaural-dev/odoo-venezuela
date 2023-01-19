from odoo.tests import Form
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestResPartner(TransactionCase):
    def setUp(self):
        super(TestResPartner, self).setUp()
        self.partner = self.env["res.partner"].create(
            {
                "name": "",
                "prefix_vat": "V",
                "vat": "27436422",
                "country_id": self.env.ref("base.ve").id,
            }
        )

    def test_get_default_name_by_vat(self):
        self.assertEqual(self.partner.vat, "27436422")
        self.partner.get_default_name_by_vat()
        self.assertEqual(self.partner.name, "BRYAN ALEJANDRO GARCIA ESCALANTE")

    # def test_get_default_name_by_vat_2(self):
    #     self.AssertionError(self.partner.name, 'BRYAN ALEJANDRO GARCIA')
    #     self.partner.get_default_name_by_vat()
    #     self.AssertionError(self.partner.name, 'BRYAN ALEJANDRO GARCIA')
