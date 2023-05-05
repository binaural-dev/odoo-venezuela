from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


class TestAccountReportsCommonBinaural(TestAccountReportsCommon):
    @classmethod
    def setUpClass(
        cls, base_currency_ref="base.VEF", foreign_currency_ref="base.USD", chart_template_ref=None
    ):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.base_currency = cls.env.ref(base_currency_ref)
        cls.foreign_currency = cls.env.ref(foreign_currency_ref)
        cls.base_currency.active = True
        cls.foreign_currency.active = True
        cls.foreign_currency.rate_ids.unlink()
        cls.env.company.currency_id = cls.base_currency.id
        cls.env.company.currency_foreign_id = cls.foreign_currency.id
