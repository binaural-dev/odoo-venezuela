from odoo.tests import tagged
from odoo import fields, Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase
from ..utils.utils_retention import search_invoices_with_taxes, load_retention_lines, get_current_date_format
from datetime import date, timedelta
from .test_withholding_common_VEF import RetentionTestCommon
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "small_models")
class TestSmallModels(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.type_person = self.env["type.person"].search([], limit=1)

    # --- payment.concept.line ---
    def test_01_payment_concept_line_check_percentage(self):
        line = self.env["payment.concept.line"].new({"percentage_tax_base": 150})
        res = line.check_value_percentage()
        self.assertIn("warning", res)
        _logger.info("========= test_01 passed =========")

    # --- account.withholding.type ---
    def test_02_withholding_type_upper_name(self):
        wt = self.env["account.withholding.type"].new({"name": " test "})
        res = wt.upper_name()
        self.assertIn("value", res)
        self.assertEqual(res["value"]["name"], "TEST")
        _logger.info("========= test_02 passed =========")

    def test_03_withholding_type_onchange_value(self):
        wt = self.env["account.withholding.type"].new({"value": 5.5})
        res = wt.onchange_template_id()
        self.assertIn("warning", res)
        _logger.info("========= test_03 passed =========")

    # --- economic.activity ---
    def test_04_economic_activity_create(self):
        branch = self.env["economic.branch"].create({"name": "TEST BRANCH"})
        muni = self.env["res.country.municipality"].search([], limit=1)
        if not muni:
            state = self.env["res.country.state"].search([], limit=1)
            country = self.env.ref("base.ve") or self.env["res.country"].search([], limit=1)
            muni = self.env["res.country.municipality"].create({
                "name": "Test Muni", "state_id": state.id if state else False,
            })
        act = self.env["economic.activity"].create({
            "name": "TEST", "aliquot": 5.0,
            "municipality_id": muni.id, "branch_id": branch.id,
            "description": "Test", "minimum_monthly": 0, "minimum_annual": 0,
        })
        self.assertTrue(act)
        _logger.info("========= test_04 passed =========")

    # --- economic.branch ---
    def test_05_economic_branch_constraint(self):
        self.env["economic.branch"].create({"name": "UNIQUE BRANCH"})
        with self.assertRaises(ValidationError):
            self.env["economic.branch"].create({"name": "UNIQUE BRANCH"})
        _logger.info("========= test_05 passed =========")

    # --- fees.retention ---
    def test_06_fees_retention_constraint_negative(self):
        tu = self.env["tax.unit"].search([], limit=1)
        with self.assertRaises(ValidationError):
            self.env["fees.retention"].create({
                "name": "Test", "percentage": -5,
                "tax_unit_ids": tu.id,
            })
        _logger.info("========= test_06 passed =========")

    def test_07_fees_retention_compute_amount_subtract(self):
        tu = self.env["tax.unit"].search([], limit=1)
        if tu and tu.value:
            fee = self.env["fees.retention"].create({
                "name": "Fee Sub", "percentage": 10,
                "apply_subtracting": True,
                "tax_unit_ids": tu.id,
            })
            self.assertGreater(fee.amount_subtract, 0)
        _logger.info("========= test_07 passed =========")

    def test_08_fees_retention_onchange_percentage(self):
        fee = self.env["fees.retention"].new({"percentage": 101})
        res = fee.onchange_percentage()
        self.assertIn("warning", res)
        _logger.info("========= test_08 passed =========")

    # --- ir.actions.report ---
    def test_09_report_render_draft_raises(self):
        report = self.env["ir.actions.report"]
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "partner_id": self.env["res.partner"].search([], limit=1).id,
        })
        retention.write({"state": "draft"})
        with self.assertRaises(ValidationError):
            report._render_qweb_pdf(
                "l10n_ve_payment_extension.retention_voucher_template",
                res_ids=retention.ids,
            )
        _logger.info("========= test_09 passed =========")

    # --- utils_retention ---
    def test_10_utils_get_current_date_format(self):
        d = date(2026, 5, 30)
        result = get_current_date_format(d)
        self.assertIn("May", result)
        self.assertIn("2026", result)
        _logger.info("========= test_10 passed =========")

    def test_11_utils_search_invoices_with_taxes(self):
        domain = [("company_id", "=", self.company.id)]
        result = search_invoices_with_taxes(self.env["account.move"], domain)
        self.assertIsNotNone(result)
        _logger.info("========= test_11 passed =========")

    def test_12_utils_load_retention_lines_no_invoices(self):
        invoices = self.env["account.move"]
        result = load_retention_lines(invoices, self.env["account.retention"])
        self.assertEqual(result, [])


@tagged("post_install", "-at_install", "retention_islr_wizard")
class TestRetentionIslrWizard(RetentionTestCommon):

    def setUp(self):
        super().setUp()
        self.IslrWizard = self.env["wizard.retention.islr"]

    def _create_islr_retention(self, partner=None, amount=1000.0, date_val=None):
        partner = partner or self.partner_pnr_75
        date_val = date_val or fields.Date.today()
        invoice = self._create_invoice_islr(
            amount=amount, partner=partner,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        invoice.action_post()
        ret = self.env["account.retention"].create({
            "type_retention": "islr",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": partner.id,
            "date": date_val,
            "date_accounting": date_val,
            "retention_line_ids": [Command.create({
                "move_id": invoice.id,
                "name": "ISLR Test Line",
                "invoice_total": amount,
                "invoice_amount": amount,
                "retention_amount": amount * 0.03,
                "foreign_invoice_amount": amount,
                "foreign_retention_amount": amount * 0.03,
                "payment_concept_id": self.concept_one.id,
            })],
        })
        ret.number = "01234567891234"
        ret.action_post()
        return ret

    def test_01_download_format(self):
        wiz = self.IslrWizard.create({
            "report": "islr",
            "date_start": date.today().replace(day=1),
            "date_end": date.today(),
        })
        ext = wiz.download_format()
        self.assertEqual(ext, ".xlsm")

    def test_02_get_domain(self):
        wiz = self.IslrWizard.create({
            "report": "islr",
            "date_start": date.today().replace(day=1),
            "date_end": date.today(),
        })
        domain = wiz._get_domain()
        self.assertIn(("date_accounting", ">=", wiz.date_start), domain)
        self.assertIn(("date_accounting", "<=", wiz.date_end), domain)

    def test_03_get_domain_with_company(self):
        wiz = self.IslrWizard.create({
            "report": "islr",
            "date_start": date.today().replace(day=1),
            "date_end": date.today(),
        })
        domain = wiz._get_domain(current_company_id=self.company)
        self.assertIn(("company_id", "=", self.company.id), domain)

    def test_04_get_retention_ids(self):
        ret = self._create_islr_retention()
        wiz = self.IslrWizard.create({
            "report": "islr",
            "date_start": date.today().replace(day=1),
            "date_end": date.today(),
        })
        ids = wiz._get_retention_ids()
        self.assertIn(ret.id, ids.ids)

    def test_05_get_retention_islr_excel_model_row(self):
        wiz = self.IslrWizard.create({
            "report": "islr",
            "date_start": date.today().replace(day=1),
            "date_end": date.today(),
        })
        row = wiz._get_retention_islr_excel_model_row()
        self.assertIn("ID Sec", row)
        self.assertIn("RIF Retenido", row)
        self.assertIn("Monto Operación", row)
        self.assertIn("Porcentaje de retención", row)

    def test_06_get_retention_islr_excel_row(self):
        ret = self._create_islr_retention(amount=500.0)
        wiz = self.IslrWizard.create({
            "report": "islr",
            "date_start": date.today().replace(day=1),
            "date_end": date.today(),
        })
        row = wiz._get_retention_islr_excel_row(1, ret.retention_line_ids[0], True)
        self.assertEqual(row["ID Sec"], 1)
        self.assertEqual(row["Monto Operación"], 500.0)

    def test_07_get_retention_islr_excel_row_non_vef(self):
        ret = self._create_islr_retention(amount=300.0)
        wiz = self.IslrWizard.create({
            "report": "islr",
            "date_start": date.today().replace(day=1),
            "date_end": date.today(),
        })
        row = wiz._get_retention_islr_excel_row(2, ret.retention_line_ids[0], False)
        self.assertEqual(row["ID Sec"], 2)
        self.assertEqual(row["Monto Operación"], 300.0)

    def test_08_get_retention_islr_excel_rows(self):
        self._create_islr_retention(amount=200.0)
        self._create_islr_retention(amount=300.0)
        wiz = self.IslrWizard.create({
            "report": "islr",
            "date_start": date.today().replace(day=1),
            "date_end": date.today(),
        })
        rows, count = wiz._get_retention_islr_excel_rows([], 0)
        self.assertGreaterEqual(count, 2)
        self.assertEqual(len(rows), count)

    def test_09_get_table_rows_sorted(self):
        wiz = self.IslrWizard.create({
            "report": "islr",
            "date_start": date.today().replace(day=1),
            "date_end": date.today(),
        })
        unordered = [
            {"Fecha Operación": "15/05/2026", "ID Sec": 2},
            {"Fecha Operación": "01/05/2026", "ID Sec": 1},
            {"Fecha Operación": "20/05/2026", "ID Sec": 3},
        ]
        ordered = wiz._get_table_rows_sorted(unordered)
        self.assertEqual(ordered[0]["ID Sec"], 1)
        self.assertEqual(ordered[1]["ID Sec"], 2)
        self.assertEqual(ordered[2]["ID Sec"], 3)

    def test_10_retention_islr_excel(self):
        self._create_islr_retention(amount=400.0)
        wiz = self.IslrWizard.create({
            "report": "islr",
            "date_start": date.today().replace(day=1),
            "date_end": date.today(),
        })
        table = wiz._retention_islr_excel()
        self.assertFalse(table.empty)

    def test_11_table_retention_islr(self):
        self._create_islr_retention(amount=500.0)
        wiz = self.IslrWizard.create({
            "report": "islr",
            "date_start": date.today().replace(day=1),
            "date_end": date.today(),
        })
        table = wiz._table_retention_islr()
        self.assertFalse(table.empty)
