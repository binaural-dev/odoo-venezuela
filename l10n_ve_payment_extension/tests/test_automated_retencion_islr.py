from odoo.tests import tagged , Form ,TransactionCase
from odoo.exceptions import UserError, ValidationError
from odoo import Command, fields
from .test_common_islr_retention import ISLRCommon 
import logging
from odoo import Command, fields



@tagged('post_install', '-at_install', 'retencion_islr')
class TestTaxUnit(ISLRCommon):

    def test_01_islr_cliente_retention_invoice_vef(self):

        self._create_invoice_vef(amount, journal):
            pass