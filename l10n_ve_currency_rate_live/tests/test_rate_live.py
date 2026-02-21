import logging
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged
from odoo import fields, Command

_logger = logging.getLogger(__name__)
@tagged("l10n_ve_currency_rate_live", "post_install", "-at_install")
class TestRateLive(TransactionCase):
    def setUp(self):
        super().setUp()
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.currency_eur = self.env.ref("base.EUR")
        self.currency_cny = self.env.ref("base.CNY")
        self.company = self.env.ref("base.main_company")
        self.company.currency_id = self.currency_vef
        self.company.foreign_currency_id = self.currency_usd

    def test_01_update_rate_live(self):
        self.company.can_update_habil_days = True
        self.currency_usd.active = True
        self.currency_eur.active = True
        self.currency_vef.active = True
        self.currency_cny.active = True
        with patch(
            "odoo.addons.l10n_ve_currency_rate_live.models.res_company.ResCompany._get_bcv_currency_rates"
        ) as mock_bcv:
            mock_bcv.return_value = {
                "USD": (30, fields.Date.today()),
                "EUR": (35, fields.Date.today()),
                "CNY": (1, fields.Date.today()),
            }
            parse_data = self.company._parse_bcv_data(available_currencies=None)
            _logger.warning(parse_data)
            expected_data = {
                "VEF": (1.0, fields.Date.today()),
                "USD": (1 / 30, fields.Date.today()),
                "EUR": (1 / 35, fields.Date.today()),
                "CNY": (1.0, fields.Date.today()),
            }
            self.assertEqual(parse_data, expected_data)
