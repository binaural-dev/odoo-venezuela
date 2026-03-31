import logging
from dateutil.relativedelta import relativedelta
from odoo.tests.common import Form
from odoo.tests import tagged
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError
from odoo import Command, fields

from .test_common_sale_international import TestCommonSaleInternational

_logger = logging.getLogger(__name__)


@tagged("igtf_providers_usd", "igtf_run", "-at_install", "post_install")
class TestsAccountMoveLine(TestCommonSaleInternational):

    def test01_payment_from_invoice(self,product_id=None,create_reversal=False):
        
        invoice_amount = float(2681.20)
        invoice = self._create_invoice_usd(invoice_amount,product_id)

        for line in invoice.invoice_line_ids:

            if line.move_id.journal_id.is_sale_international:

                tax_zero = line._get_computed_taxes()

                self.assertEqual(tax_zero,self.company.zero_aliquot_sale_international)
                
                self.assertEqual(line.tax_ids,self.company.zero_aliquot_sale_international)