from pathlib import Path
from xml.etree import ElementTree

from odoo.modules.module import get_module_path
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

    def test_06_default_fees_use_canonical_tax_unit(self):
        canonical_xmlid = (
            "l10n_ve_accountant.tax_unit_data_l10n_ve_payment_extension"
        )
        data_path = Path(
            get_module_path("l10n_ve_payment_extension"),
            "data",
            "fees_retention_data.xml",
        )
        # Source-controlled module data, not user-supplied XML.
        tax_unit_fields = ElementTree.parse(data_path).findall(
            ".//field[@name='tax_unit_ids']"
        )
        self.assertEqual(len(tax_unit_fields), 7)
        self.assertTrue(
            all(field.get("ref") == canonical_xmlid for field in tax_unit_fields)
        )

        tax_unit = self.env.ref(canonical_xmlid)
        fee_xmlids = (
            "fees_retention_data_substrat_l10n_ve_payment_extension",
            "fees_retention_data_percentage_one_l10n_ve_payment_extension",
            "fees_retention_data_percentage_two_l10n_ve_payment_extension",
            "fees_retention_data_substrat_second_l10n_ve_payment_extension",
            "fees_retention_data_l10n_ve_percentage_three_payment_extension",
            "fees_retention_data_percentage_four_l10n_ve_payment_extension",
            "fees_retention_data_percentage_five_l10n_ve_payment_extension",
        )
        for xmlid in fee_xmlids:
            fee = self.env.ref(f"l10n_ve_payment_extension.{xmlid}")
            self.assertEqual(fee.tax_unit_ids, tax_unit)
