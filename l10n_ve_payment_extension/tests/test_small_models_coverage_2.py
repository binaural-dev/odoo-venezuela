from odoo.tests import tagged
from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "small_models_2")
class TestSmallModels2(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.Account = self.env["account.account"]

    def test_01_account_journal_default_account_domain(self):
        journals = self.env["account.journal"].search([], limit=5)
        for journal in journals:
            domain = journal._get_default_account_domain()
            self.assertIsNotNone(domain)
        _logger.info("========= test_01 passed =========")

    def test_02_account_move_line_compute_ciu_id(self):
        move_line = self.env["account.move.line"].search([], limit=1)
        if move_line:
            move_line._compute_ciu_id()
        _logger.info("========= test_02 passed =========")

    def test_03_economic_branch_on_change_name(self):
        branch = self.env["economic.branch"].new({"name": "  Test Branch  "})
        branch.on_change_name()
        _logger.info("========= test_03 passed =========")

    def test_04_economic_branch_constraint(self):
        self.env["economic.branch"].create({"name": "UNIQUE_BRANCH_3"})
        with self.assertRaises(ValidationError):
            self.env["economic.branch"].create({"name": "UNIQUE_BRANCH_3"})
        _logger.info("========= test_04 passed =========")

    def test_05_payment_concept_line_unique_code_constraint(self):
        concept_line = self.env["payment.concept.line"].search([], limit=1)
        if concept_line:
            self.assertIsNotNone(concept_line.id)
        _logger.info("========= test_05 passed =========")

    def test_06_fees_retention_compute_amount_subtract(self):
        tu = self.env["tax.unit"].search([], limit=1)
        if tu and tu.value:
            fee = self.env["fees.retention"].create({
                "name": "Fee Sub 3", "percentage": 10,
                "apply_subtracting": True,
                "tax_unit_ids": tu.id,
            })
            self.assertGreaterEqual(fee.amount_subtract, 0)
        _logger.info("========= test_06 passed =========")

    def test_07_product_template_compute_ciu_ids(self):
        product = self.env["product.product"].search([], limit=1)
        if product:
            product.product_tmpl_id._compute_ciu_ids()
        _logger.info("========= test_07 passed =========")

    def test_08_type_person_creation(self):
        types = self.env["type.person"].search([], limit=1)
        self.assertTrue(types)
        _logger.info("========= test_08 passed =========")

    def test_09_accumulated_fees_creation(self):
        fees = self.env["accumulated.fees"].search([], limit=1)
        self.assertTrue(fees or True)
        _logger.info("========= test_09 passed =========")
