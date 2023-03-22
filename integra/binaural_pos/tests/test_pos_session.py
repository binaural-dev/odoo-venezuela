# from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.addons.point_of_sale.tests.common import TestPoSCommon
from odoo import Command, fields

import logging

_logger = logging.getLogger(__name__)


@tagged("pos_session", "post_install", "-at_install")
class TestPosSession(TestPoSCommon):
    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        """
        l10n_ve is required to run this test
        """
        super().setUpClass(chart_template_ref="l10n_ve.ve_chart_template_amd")
        cls.company_data["company"].write(
            {
                "currency_foreign_id": cls.env.ref("base.USD"),
            }
        )
        cls.config = cls.basic_config
        cls.product0 = cls.create_product("Product 0", cls.categ_basic, 0.0, 0.0)
        cls.product1 = cls.create_product("Product 1", cls.categ_basic, 10.0, 5)
        cls.product2 = cls.create_product("Product 2", cls.categ_basic, 20.0, 10)
        cls.product3 = cls.create_product("Product 3", cls.categ_basic, 30.0, 15)
        cls.product4 = cls.create_product("Product_4", cls.categ_basic, 9.96, 4.98)
        cls.product99 = cls.create_product("Product_99", cls.categ_basic, 99, 50)
        cls.product100 = cls.create_product("Product_100", cls.categ_basic, 100, 50)
        cls.adjust_inventory([cls.product1, cls.product2, cls.product3], [100, 50, 50])

