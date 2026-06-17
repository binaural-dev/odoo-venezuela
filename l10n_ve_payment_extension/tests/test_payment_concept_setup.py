from odoo.tests import tagged
from odoo import fields, Command
from odoo.exceptions import UserError, ValidationError
from datetime import date, timedelta
from .test_withholding_common_VEF import RetentionTestCommon
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "payment_concept_setup")
class TestPaymentConceptSetup(RetentionTestCommon):

    def test_01_validate_concept_lines_filters_existing(self):
        PayConcept = self.env["payment.concept"]
        existing = self.env["payment.concept.line"].search([]).mapped("code")
        lines = [{"code": 9991, "pay_from": 0.13, "percentage_tax_base": 100,
                   "tariff_id": False, "type_person_id": self.env["type.person"].search([], limit=1).id}]
        result = PayConcept.validate_concept_lines(lines)
        self.assertEqual(len(result), 1)
        self.env["payment.concept.line"].create({
            "code": "9991",
            "type_person_id": self.env["type.person"].search([], limit=1).id,
            "payment_concept_id": self.env["payment.concept"].search([], limit=1).id,
        })
        result = PayConcept.validate_concept_lines(lines)
        self.assertEqual(len(result), 0)

    def test_02_create_concept_line_creates_new(self):
        PayConcept = self.env["payment.concept"]
        tp = self.env["type.person"].search([], limit=1)
        PayConcept.create_concept_line(
            "test_fake_id", "Test Concept",
            [{"code": 7777, "pay_from": 0.13, "percentage_tax_base": 100,
              "tariff_id": False, "type_person_id": tp.id}],
        )
        concept = self.env["payment.concept"].search([("name", "=", "Test Concept")])
        self.assertTrue(concept)
        self.assertEqual(len(concept.line_payment_concept_ids), 1)

    def test_03_handle_concept_one(self):
        self.env["payment.concept"]._handle_payment_concept_one()

    def test_04_handle_concept_two(self):
        self.env["payment.concept"]._handle_payment_concept_two()

    def test_05_handle_concept_three(self):
        self.env["payment.concept"]._handle_payment_concept_three()

    def test_06_handle_concept_four(self):
        self.env["payment.concept"]._handle_payment_concept_four()

    def test_07_handle_concept_five(self):
        self.env["payment.concept"]._handle_payment_concept_five()

    def test_08_handle_concept_six(self):
        self.env["payment.concept"]._handle_payment_concept_six()

    def test_09_handle_concept_seven(self):
        self.env["payment.concept"]._handle_payment_concept_seven()


@tagged("post_install", "-at_install", "retention_iva_wizard")
class TestRetentionIvaWizard(RetentionTestCommon):

    def setUp(self):
        super().setUp()
        self.IvaWizard = self.env["wizard.retention.iva"]

    def _create_iva_retention(self, partner=None, amount=1000.0, foreign=False):
        partner = partner or self.partner_pnr_75
        date_val = fields.Date.today()
        invoice = self._create_invoice_reten_iva(
            amount=amount, partner=partner,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        invoice.action_post()
        ret = self.env["account.retention"].create({
            "type_retention": "iva",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": partner.id,
            "date": date_val,
            "date_accounting": date_val,
            "base_currency_is_vef": not foreign,
            "state": "emitted",
            "retention_line_ids": [Command.create({
                "move_id": invoice.id,
                "name": "IVA Test Line",
                "invoice_total": amount * 1.16,
                "invoice_amount": amount,
                "iva_amount": amount * 0.16,
                "retention_amount": amount * 0.16 * 0.75,
                "foreign_invoice_amount": amount / 390.0 if foreign else amount,
                "foreign_iva_amount": amount * 0.16 / 390.0 if foreign else amount * 0.16,
                "foreign_retention_amount": amount * 0.16 * 0.75 / 390.0 if foreign else amount * 0.16 * 0.75,
                "foreign_currency_rate": 390.0 if foreign else 1.0,
                "aliquot": 16.0,
                "payment_concept_id": self.concept_one.id,
            })],
        })
        return ret

    def test_01_retention_iva_in_invoice_vef(self):
        ret = self._create_iva_retention(amount=1000.0)
        data = self.IvaWizard._retention_iva(ret)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["Tipo de documento"], "01")
        self.assertGreater(data[0]["Monto del Iva Retenido"], 0)
        self.assertIn("Monto exento del IVA", data[0])

    def test_02_retention_iva_foreign_currency(self):
        ret = self._create_iva_retention(amount=1000.0, foreign=True)
        data = self.IvaWizard._retention_iva(ret)
        self.assertEqual(len(data), 1)
        self.assertGreater(data[0]["Monto del Iva Retenido"], 0)
        self.assertIn("Monto exento del IVA", data[0])

    def test_03_generate_txt_no_dates(self):
        wiz = self.IvaWizard.create({
            "date_start": False,
            "date_end": False,
        })
        with self.assertRaises(UserError):
            wiz.generate_txt()

    def test_04_generate_txt_no_vat(self):
        self.company.write({"vat": False})
        wiz = self.IvaWizard.create({
            "date_start": date.today().replace(day=1),
            "date_end": date.today(),
        })
        with self.assertRaises(UserError):
            wiz.generate_txt()

    def test_05_generate_txt_no_retentions(self):
        wiz = self.IvaWizard.create({
            "date_start": fields.Date.from_string("2020-01-01"),
            "date_end": fields.Date.from_string("2020-01-31"),
        })
        with self.assertRaises(UserError):
            wiz.generate_txt()


@tagged("post_install", "-at_install", "arcv_report_full")
class TestArcReportFull(RetentionTestCommon):

    def setUp(self):
        super().setUp()
        self.ArcvWizard = self.env["arcv.report"]

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
                "name": "ISLR Arcv Line",
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

    def test_01_get_islr_retention_lines_grouped(self):
        ret = self._create_islr_retention(amount=500.0)
        wiz = self.ArcvWizard.create({
            "partner_id": self.partner_pnr_75.id,
            "date_start": date.today().replace(day=1),
            "date_end": date.today(),
        })
        grouped = wiz._get_islr_retention_lines_grouped_by_year_month_and_percentage_fees()
        self.assertTrue(len(grouped) > 0)
        for (year, month, pct), lines in grouped.items():
            self.assertEqual(year, date.today().year)
            self.assertEqual(month, date.today().month)

    def test_02_construct_report_data(self):
        ret = self._create_islr_retention(amount=750.0)
        wiz = self.ArcvWizard.create({
            "partner_id": self.partner_pnr_75.id,
            "date_start": date.today().replace(day=1),
            "date_end": date.today(),
        })
        grouped = wiz._get_islr_retention_lines_grouped_by_year_month_and_percentage_fees()
        data = wiz._construct_report_data(grouped)
        self.assertIn("period", data)
        self.assertIn("partner", data)
        self.assertIn("retentions", data)
        self.assertEqual(data["partner"]["name"], self.partner_pnr_75.name)


@tagged("post_install", "-at_install", "accounting_reports_extra")
class TestAccountingReportsExtraBranches(RetentionTestCommon):

    def _make_wizard(self, report_type="purchase"):
        return self.env["wizard.accounting.reports"].create({
            "report": report_type,
            "date_from": fields.Date.subtract(fields.Date.today(), days=30),
            "date_to": fields.Date.today(),
            "company_id": self.company.id,
        })

    def _make_iva_invoice_with_retention(self, foreign=False):
        inv = self._create_invoice_reten_iva(
            200, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 390.0 if foreign else 1.0,
                   "foreign_inverse_rate": 1/390.0 if foreign else 1.0})
        inv.generate_iva_retention = True
        inv.action_post()
        retention = self.env["account.retention"].search([
            ("type_retention", "=", "iva"),
            ("partner_id", "=", self.partner_pnr_75.id),
        ], limit=1)
        if retention and retention.state != "emitted":
            retention.write({"base_currency_is_vef": not foreign})
            retention.action_post()
        return inv

    def test_01_get_sale_book_field_groups(self):
        wizard = self._make_wizard("sale")
        groups = wizard._get_sale_book_field_groups()
        self.assertTrue(any(g.get("header") == "RETENCIONES" for g in groups))

    def test_02_get_purchase_book_field_groups(self):
        wizard = self._make_wizard("purchase")
        groups = wizard._get_purchase_book_field_groups()
        self.assertTrue(any(g.get("header") == "RETENCIONES" for g in groups))

    def test_03_fields_purchase_book_line(self):
        inv = self._make_iva_invoice_with_retention()
        wizard = self._make_wizard("purchase")
        fields_line = wizard._fields_purchase_book_line(inv, {})
        self.assertIn("retention_date", fields_line)
        self.assertIn("retention_number", fields_line)
        self.assertIn("iva_withheld", fields_line)

    def test_04_fields_sale_book_line(self):
        inv = self._make_iva_invoice_with_retention()
        wizard = self._make_wizard("sale")
        fields_line = wizard._fields_sale_book_line(inv, {})
        self.assertIn("retention_date", fields_line)
        self.assertIn("retention_number", fields_line)
        self.assertIn("iva_withheld", fields_line)

    def test_05_sum_retention_total_foreign(self):
        inv = self._make_iva_invoice_with_retention(foreign=True)
        wizard = self._make_wizard("purchase")
        wizard.write({"currency_system": False})
        lines = inv.retention_iva_line_ids
        total = wizard._sum_retention_total(lines)
        self.assertGreaterEqual(total, 0)

    def test_06_get_retention_iva_values_no_retention_lines(self):
        inv = self._create_invoice_reten_iva(
            200, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        wizard = self._make_wizard("purchase")
        values = wizard.get_retention_iva_values(inv.id)
        self.assertEqual(values["iva_retained"], 0)

    def test_07_get_retention_iva_values_future_date(self):
        inv = self._make_iva_invoice_with_retention()
        wizard = self._make_wizard("purchase")
        retention = inv.retention_iva_line_ids.retention_id
        retention.write({"date_accounting": fields.Date.subtract(fields.Date.today(), days=60)})
        values = wizard.get_retention_iva_values(inv.id)
        self.assertEqual(values["iva_retained"], 0)


@tagged("post_install", "-at_install", "account_move_third_party")
class TestAccountMoveThirdParty(RetentionTestCommon):

    def test_01_third_party_retention_counts(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0,
                       "is_third_party_retention": True})
        invoice.action_post()
        retention = self.env["account.retention"].create([{
            "type_retention": "iva",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "is_third_party_retention": True,
            "date": fields.Date.today(),
            "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": invoice.id,
                "name": "Third Party IVA",
                "invoice_total": 232.0,
                "invoice_amount": 200.0,
                "iva_amount": 32.0,
                "retention_amount": 24.0,
                "foreign_currency_rate": 1.0,
            })],
        }])
        retention.action_post()
        invoice._compute_third_party_retention_counts()
        self.assertEqual(invoice.third_party_iva_retention_count, 1)
        self.assertEqual(invoice.third_party_islr_retention_count, 0)

    def test_02_action_view_third_party_iva_draft_error(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        invoice.write({"is_third_party_retention": True})
        with self.assertRaises(UserError):
            invoice.action_view_third_party_iva_retentions()

    def test_03_action_view_third_party_iva_posted_no_retentions(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0,
                       "is_third_party_retention": True})
        invoice.action_post()
        action = invoice.action_view_third_party_iva_retentions()
        self.assertEqual(len(action["views"]), 1)

    def test_04_action_view_third_party_iva_with_retentions(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0,
                       "is_third_party_retention": True})
        invoice.action_post()
        retention = self.env["account.retention"].create([{
            "type_retention": "iva",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "is_third_party_retention": True,
            "date": fields.Date.today(),
            "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": invoice.id,
                "name": "Third Party IVA",
                "invoice_total": 232.0,
                "invoice_amount": 200.0,
                "iva_amount": 32.0,
                "retention_amount": 24.0,
                "foreign_currency_rate": 1.0,
            })],
        }])
        retention.action_post()
        action = invoice.action_view_third_party_iva_retentions()
        self.assertIn("domain", action)

    def test_05_action_view_third_party_islr_posted_no_retentions(self):
        invoice = self._create_invoice_islr(
            200, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        invoice.write({"is_third_party_retention": True})
        invoice.action_post()
        action = invoice.action_view_third_party_islr_retentions()
        self.assertEqual(len(action["views"]), 1)


@tagged("post_install", "-at_install", "retention_line_extras")
class TestAccountRetentionLineExtras(RetentionTestCommon):

    def test_01_onchange_move_id_non_iva_returns_none(self):
        invoice = self._create_invoice_islr(
            200, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        invoice.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "islr",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(),
            "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": invoice.id,
            })],
        })
        line = retention.retention_line_ids[0]
        result = line._onchange_move_id()
        self.assertIsNone(result)

    def test_02_onchange_move_id_out_invoice_retention_zero(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75,
            "out_invoice", self.sale_journal,
        )
        invoice.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "iva",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(),
            "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": invoice.id,
            })],
        })
        line = retention.retention_line_ids[0]
        line._onchange_move_id()
        self.assertEqual(line.retention_amount, 0.0)

    def test_03_compute_name_empty(self):
        line = self.env["account.retention.line"].new({})
        line._compute_name()
        self.assertTrue(line.name)

    def test_04_compute_economic_activity_municipal(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        invoice.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "municipal",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(),
            "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": invoice.id,
            })],
        })
        line = retention.retention_line_ids[0]
        line.economic_activity_id = False
        line._compute_economic_activity_id()
        self.assertFalse(line.economic_activity_id)

    def test_05_unlink_with_payment(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75,
            "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "iva",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(),
            "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": invoice.id,
                "name": "IVA Line",
                "invoice_total": 232.0,
                "invoice_amount": 200.0,
                "iva_amount": 32.0,
                "retention_amount": 24.0,
                "foreign_currency_rate": 1.0,
            })],
        })
        retention.number = "01234567891234"
        retention.action_post()
        line = retention.retention_line_ids[0]
        if line.payment_id:
            with self.assertRaises(UserError):
                line.unlink()


@tagged("post_install", "-at_install", "islr_wizard_branches")
class TestWizardIslrBranches(RetentionTestCommon):

    def setUp(self):
        super().setUp()
        self.IslrWizard = self.env["wizard.retention.islr"]

    def test_01_get_retention_ids_no_results(self):
        wiz = self.IslrWizard.create({
            "report": "islr",
            "date_start": fields.Date.from_string("2020-01-01"),
            "date_end": fields.Date.from_string("2020-01-31"),
        })
        ids = wiz._get_retention_ids()
        self.assertEqual(len(ids), 0)

    def test_02_get_retention_islr_excel_rows_raises_no_retentions(self):
        wiz = self.IslrWizard.create({
            "report": "islr",
            "date_start": fields.Date.from_string("2020-01-01"),
            "date_end": fields.Date.from_string("2020-01-31"),
        })
        with self.assertRaises(ValidationError):
            wiz._get_retention_islr_excel_rows([], 0)

    def test_03_get_retention_islr_excel_row_no_concept_match(self):
        partner_no_match = self.env["res.partner"].create({
            "name": "No Match Partner",
            "vat": "J999",
            "property_account_receivable_id": self.acc_receivable.id,
            "property_account_payable_id": self.acc_payable.id,
            "taxpayer_type": "formal",
            "type_person_id": self.env.ref(
                "l10n_ve_payment_extension.type_person_five_l10n_ve_payment_extension"
            ).id,
        })
        invoice = self._create_invoice_islr(
            500, partner_no_match,
            "in_invoice", self.purchase_journal,
        )
        invoice.action_post()
        ret = self.env["account.retention"].create({
            "type_retention": "islr",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": partner_no_match.id,
            "date": fields.Date.today(),
            "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": invoice.id,
                "name": "ISLR No Match",
                "invoice_total": 500.0,
                "invoice_amount": 500.0,
                "retention_amount": 15.0,
                "foreign_invoice_amount": 500.0,
                "foreign_retention_amount": 15.0,
                "payment_concept_id": self.concept_one.id,
            })],
        })
        ret.number = "01234567891234"
        ret.action_post()
        wiz = self.IslrWizard.create({
            "report": "islr",
            "date_start": date.today().replace(day=1),
            "date_end": date.today(),
        })
        row = wiz._get_retention_islr_excel_row(1, ret.retention_line_ids[0], True)
        self.assertEqual(row["Código Concepto"], "")
