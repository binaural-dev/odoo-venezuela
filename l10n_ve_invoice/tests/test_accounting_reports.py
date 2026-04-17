import logging
from dateutil.relativedelta import relativedelta
from odoo.tests.common import Form
from odoo.tests import tagged
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError
from odoo import Command, fields

from .test_common_purchase_international import TestCommonPurchaseInternational

_logger = logging.getLogger(__name__)


@tagged("igtf_providers_usd", "igtf_run", "-at_install", "post_install")
class TestsAccountingReports(TransactionCase):

    def get_sales_book_wizard(self):

        with Form(self.env['wizard.accounting.reports']) as wiz_form:
            wiz_form.report = 'sale'
            wiz_form.date_from = fields.Date.today()
            wiz_form.date_to = fields.Date.today()
            wizard = wiz_form.save()

        return wizard
    
    def test_default_date_to(self):
        wizard = self.env['wizard.accounting.reports'].create({
            'report': 'sale'
        })

        date_to = wizard._default_date_to()

        self.assertEqual(
            date_to,
            fields.Date.today(),
            "date_to debería ser la fecha actual"
        )

    def test_default_date_from(self):
        wizard = self.env['wizard.accounting.reports'].create({
            'report': 'sale'
        })

        expected_date = fields.Date.today() + relativedelta(months=-1)

        date_from = wizard._default_date_from()

        self.assertEqual(
            date_from,
            expected_date,
            "date_from debería ser un mes antes de hoy"
        )

    def test_default_company(self):
        wizard = self.env['wizard.accounting.reports'].create({
            'report': 'sale'
        })

        company_id = self.env['res.company'].browse(wizard._default_company_id())

        self.assertEqual(
            company_id,
            self.env.company,
            "La compañía por defecto debería ser la actual"
        )

    def test_default_check_currency_system(self):

        wizard = self.env['wizard.accounting.reports'].create({
            'report': 'sale'
        })

        is_vef = wizard._default_check_currency_system()

        self.assertEqual(
            is_vef,
            False,
            "check currency system no coincide con la lógica esperada"
        )

    def test_default_currency_system(self):

        wizard = self.env['wizard.accounting.reports'].create({
            'report': 'sale'
        })

        is_vef = wizard._default_currency_system()

        self.assertEqual(
            is_vef,
            False,
            "currency system no coincide con la lógica esperada"
        )

    def test_default_check_currency_system_vef(self):

        self.env.company.currency_id = self.env.ref("base.VEF").id

        self.env.company.currency_foreign_id = self.env.ref("base.USD").id

        wizard = self.env['wizard.accounting.reports'].create({
            'report': 'sale'
        })

        is_vef = wizard._default_check_currency_system()

        self.assertEqual(
            is_vef,
            True,
            "check currency system no coincide con la lógica esperada"
        )

    def test_default_currency_system_vef(self):

        self.env.company.currency_id = self.env.ref("base.VEF").id

        self.env.company.currency_foreign_id = self.env.ref("base.USD").id

        wizard = self.env['wizard.accounting.reports'].create({
            'report': 'sale'
        })

        is_vef = wizard._default_currency_system()

        self.assertEqual(
            is_vef,
            True,
            "currency system no coincide con la lógica esperada"
        )