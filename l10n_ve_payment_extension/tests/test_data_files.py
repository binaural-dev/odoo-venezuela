from odoo.tests import tagged
from odoo.tests.common import TransactionCase
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "test_data_files")
class TestDataFiles(TransactionCase):

    def test_01_payment_concepts_loaded(self):
        concepts = self.env["payment.concept"].search([])
        self.assertTrue(len(concepts) > 0)
        _logger.info("========= test_01 passed =========")

    def test_02_type_person_loaded(self):
        types = self.env["type.person"].search([])
        self.assertTrue(len(types) > 0)
        _logger.info("========= test_02 passed =========")

    def test_03_withholding_types_loaded(self):
        types = self.env["account.withholding.type"].search([])
        self.assertTrue(len(types) > 0)
        _logger.info("========= test_03 passed =========")

    def test_04_withholding_type_75_exists(self):
        wt = self.env.ref("l10n_ve_payment_extension.account_withholding_type_75", raise_if_not_found=False)
        self.assertTrue(wt)
        _logger.info("========= test_04 passed =========")

    def test_05_withholding_type_100_exists(self):
        wt = self.env.ref("l10n_ve_payment_extension.account_withholding_type_100", raise_if_not_found=False)
        self.assertTrue(wt)
        _logger.info("========= test_05 passed =========")
