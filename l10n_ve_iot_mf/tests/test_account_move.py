from datetime import date, timedelta
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError
from odoo import fields


@tagged("post_install", "-at_install", "l10n_ve_iot_mf")
class TestAccountMoveInh(TransactionCase):

    def setUp(self):
        super().setUp()
        self.currency_vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")
        self.company.write({
            "currency_id": self.currency_vef.id,
            "invoice_print_type": "fiscal",
        })

        self.tax_iva16 = self.env["account.tax"].create({
            "name": "IVA 16%",
            "amount": 16,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "fiscal_code": 1,
        })

        self.product = self.env["product.product"].create({
            "name": "Producto Prueba",
            "type": "service",
            "list_price": 100,
            "default_code": "PRD001",
            "taxes_id": [(6, 0, [self.tax_iva16.id])],
        })

        self.partner = self.env["res.partner"].create({
            "name": "Test Partner",
            "customer_rank": 1,
            "vat": "12345678",
            "prefix_vat": "J",
            "street": "Calle Test 123",
            "phone": "04121234567",
        })

        self.journal = self.env["account.journal"].create({
            "name": "Diario Ventas Test",
            "code": "TVEN",
            "type": "sale",
            "company_id": self.company.id,
        })

        self.iot_box = self.env["iot.box"].create({
            "name": "IoT Box Test",
            "ip": "192.168.1.100",
            "has_fiscal_machine": True,
        })

        self.iot_device = self.env["iot.device"].create({
            "name": "Fiscal Printer HKA Test",
            "type": "fiscal_data_module",
            "identifier": "iot-test-001",
            "serial_machine": "SN-TEST-001",
            "iot_box": self.iot_box.id,
            "flag_21": "00",
            "flag_24": "00",
        })

    def _create_invoice(self, **kwargs):
        invoice_line_ids = kwargs.pop("invoice_line_ids", None) or [
            (0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 100,
                "tax_ids": [(6, 0, [self.tax_iva16.id])],
                "name": self.product.name,
            })
        ]
        invoice_vals = {
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "invoice_date": fields.Date.today(),
            "invoice_date_display": fields.Date.today(),
            "company_id": self.company.id,
            "currency_id": self.currency_vef.id,
            "iot_mf": self.iot_device.id,
            "invoice_line_ids": invoice_line_ids,
        }
        invoice_vals.update(kwargs)
        invoice = self.env["account.move"].create(invoice_vals)
        should_post = invoice_vals.get("state") == "posted" or kwargs.get("_post", False)
        if should_post:
            invoice.action_post()
        return invoice

    # --- default_fiscal_machine ---

    def test_default_fiscal_machine_returns_device(self):
        default_id = self.env["account.move"].default_fiscal_machine()
        self.assertEqual(default_id, self.iot_device.id)

    def test_default_fiscal_machine_no_device(self):
        self.iot_device.unlink()
        default_id = self.env["account.move"].default_fiscal_machine()
        self.assertFalse(default_id)

    # --- default values ---

    def test_is_credit_default_false(self):
        invoice = self._create_invoice()
        self.assertFalse(invoice.is_credit)

    def test_mf_invoice_number_default_false(self):
        invoice = self._create_invoice()
        self.assertFalse(invoice.mf_invoice_number)

    def test_mf_serial_default_false(self):
        invoice = self._create_invoice()
        self.assertFalse(invoice.mf_serial)

    def test_mf_reportz_default_false(self):
        invoice = self._create_invoice()
        self.assertFalse(invoice.mf_reportz)

    def test_print_type_related(self):
        invoice = self._create_invoice()
        self.assertEqual(invoice.print_type, "fiscal")

    def test_print_type_free(self):
        self.company.invoice_print_type = "free"
        invoice = self._create_invoice()
        self.assertEqual(invoice.print_type, "free")

    # --- has_printed ---

    def test_has_printed_single_invoice(self):
        invoice = self._create_invoice(mf_invoice_number="100")
        self.assertFalse(invoice.has_printed("100"))

    def test_has_printed_duplicate(self):
        inv1 = self._create_invoice(mf_invoice_number="100")
        inv2 = self._create_invoice(mf_invoice_number="100")
        self.assertTrue(inv2.has_printed("100"))

    # --- _onchange_is_credit ---

    def test_onchange_is_credit_ok(self):
        inv = self._create_invoice()
        inv.is_credit = True
        inv._onchange_is_credit()

    def test_onchange_is_credit_with_mf_invoice_number(self):
        invoice = self._create_invoice(mf_invoice_number="100")
        invoice.is_credit = True
        with self.assertRaises(ValidationError):
            invoice._onchange_is_credit()

    # --- check_report_z ---

    def test_check_report_z_returns_true(self):
        result = self.env["account.move"].check_report_z("SN-TEST-001")
        self.assertTrue(result)

    # --- report_z ---

    def test_report_z_with_valid_data(self):
        inv = self._create_invoice(mf_serial="SN-TEST-001")
        inv.action_post()
        response = {
            "valid": True,
            "data": {
                "_registeredMachineNumber": "SN-TEST-001",
                "_dailyClosureCounter": 5,
            }
        }
        result = self.env["account.move"].report_z("SN-TEST-001", response)
        self.assertEqual(inv.mf_reportz, 6)

    def test_report_z_invalid_response(self):
        response = {"valid": False, "message": "Error test"}
        with self.assertRaises(ValidationError):
            self.env["account.move"].report_z("SN-TEST-001", response)

    def test_report_z_no_data(self):
        response = {"valid": True}
        result = self.env["account.move"].report_z("SN-TEST-001", response)
        self.assertFalse(result)

    # --- _get_z_and_add_one ---

    def test_get_z_and_add_one_no_previous(self):
        result = self.env["account.move"]._get_z_and_add_one("SN-NEW-001")
        self.assertEqual(result, 0)

    def test_get_z_and_add_one_with_previous(self):
        inv = self._create_invoice(mf_serial="SN-TEST-001", mf_reportz="10")
        inv.action_post()
        result = self.env["account.move"]._get_z_and_add_one("SN-TEST-001")
        self.assertEqual(result, 10)

    # --- check_print_out_invoice ---

    def test_check_print_out_invoice_ok(self):
        inv = self._create_invoice(state="posted")
        result = inv.check_print_out_invoice()
        self.assertIn("flag_21", result)
        self.assertIn("partner_id", result)
        self.assertIn("invoice_lines", result)
        self.assertIn("payment_lines", result)
        self.assertEqual(result["partner_id"]["vat"], "J-12345678")
        self.assertEqual(len(result["invoice_lines"]), 1)
        self.assertEqual(result["invoice_lines"][0]["tax"], 1)

    def test_check_print_out_invoice_already_printed(self):
        inv = self._create_invoice(state="posted", mf_invoice_number="100")
        with self.assertRaises(ValidationError):
            inv.check_print_out_invoice()

    def test_check_print_out_invoice_no_iot_mf(self):
        inv = self._create_invoice(state="posted", iot_mf=False)
        with self.assertRaises(ValidationError):
            inv.check_print_out_invoice()

    def test_check_print_out_invoice_draft(self):
        inv = self._create_invoice(state="draft")
        with self.assertRaises(ValidationError):
            inv.check_print_out_invoice()

    def test_check_print_out_invoice_cancel(self):
        inv = self._create_invoice(state="posted")
        inv.button_cancel()
        with self.assertRaises(ValidationError):
            inv.check_print_out_invoice()

    def test_check_print_out_invoice_future_date(self):
        inv = self._create_invoice(
            state="posted",
            invoice_date_display=str(date.today() + timedelta(days=1)),
        )
        with self.assertRaises(ValidationError):
            inv.check_print_out_invoice()

    def test_check_print_out_invoice_no_lines(self):
        inv = self._create_invoice(state="posted", invoice_line_ids=[])
        result = inv.check_print_out_invoice()
        self.assertIsInstance(result, dict)
        self.assertFalse(result.get("valid", True))

    def test_check_print_out_invoice_no_payments(self):
        inv = self._create_invoice(state="posted")
        result = inv.check_print_out_invoice()
        self.assertEqual(len(result["payment_lines"]), 1)
        self.assertEqual(result["payment_lines"][0]["amount"], 0)
        self.assertEqual(result["payment_lines"][0]["payment_method"], "01")

    # --- print_out_invoice ---

    def test_print_out_invoice_ok(self):
        inv = self._create_invoice()
        values = {"sequence": "200", "serial_machine": "SN-TEST-001"}
        result = inv.print_out_invoice(values)
        self.assertEqual(inv.mf_invoice_number, "200")
        self.assertEqual(inv.mf_serial, "SN-TEST-001")
        self.assertIsNone(result)

    def test_print_out_invoice_duplicate_warning(self):
        inv1 = self._create_invoice()
        inv1.print_out_invoice({"sequence": "300", "serial_machine": "SN-001"})
        inv2 = self._create_invoice()
        result = inv2.print_out_invoice({"sequence": "300", "serial_machine": "SN-001"})
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("res_model"), "sh.message.wizard")
        self.assertEqual(result.get("type"), "ir.actions.act_window")

    # --- check_print_out_refund ---

    def test_check_print_out_refund_ok(self):
        inv = self._create_invoice(state="posted", mf_invoice_number="100", mf_serial="SN-TEST-001")
        refund = self._create_invoice(
            move_type="out_refund",
            state="posted",
            reversed_entry_id=inv.id,
        )
        result = refund.check_print_out_refund()
        self.assertIn("invoice_affected", result)
        self.assertEqual(result["invoice_affected"]["number"], "100")

    def test_check_print_out_refund_no_iot_mf(self):
        refund = self._create_invoice(move_type="out_refund", state="posted", iot_mf=False)
        with self.assertRaises(ValidationError):
            refund.check_print_out_refund()

    def test_check_print_out_refund_draft(self):
        refund = self._create_invoice(move_type="out_refund")
        with self.assertRaises(ValidationError):
            refund.check_print_out_refund()

    def test_check_print_out_refund_no_lines(self):
        refund = self._create_invoice(
            move_type="out_refund",
            state="posted",
            invoice_line_ids=[],
        )
        result = refund.check_print_out_refund()
        self.assertIsInstance(result, dict)
        self.assertFalse(result.get("valid", True))

    # --- print_out_refund ---

    def test_print_out_refund_ok(self):
        refund = self._create_invoice(move_type="out_refund")
        refund.print_out_refund({"sequence": "50", "serial_machine": "SN-TEST-001"})
        self.assertEqual(refund.mf_invoice_number, "50")
        self.assertEqual(refund.mf_serial, "SN-TEST-001")

    def test_print_out_refund_empty_values(self):
        refund = self._create_invoice(move_type="out_refund")
        refund.print_out_refund({})
        self.assertFalse(refund.mf_invoice_number)
        self.assertFalse(refund.mf_serial)

    # --- check_print_debit_note ---

    def test_check_print_debit_note_ok(self):
        origin = self._create_invoice(state="posted", mf_invoice_number="100", mf_serial="SN-TEST-001")
        debit = self._create_invoice(
            state="posted",
            debit_origin_id=origin.id,
        )
        result = debit.check_print_debit_note()
        self.assertIn("invoice_affected", result)
        self.assertEqual(result["invoice_affected"]["number"], "100")

    def test_check_print_debit_note_no_iot_mf(self):
        debit = self._create_invoice(state="posted", iot_mf=False)
        with self.assertRaises(ValidationError):
            debit.check_print_debit_note()

    def test_check_print_debit_note_draft(self):
        debit = self._create_invoice()
        with self.assertRaises(ValidationError):
            debit.check_print_debit_note()

    def test_check_print_debit_note_no_lines(self):
        debit = self._create_invoice(state="posted", invoice_line_ids=[])
        result = debit.check_print_debit_note()
        self.assertIsInstance(result, dict)
        self.assertFalse(result.get("valid", True))

    # --- print_debit_note ---

    def test_print_debit_note_ok(self):
        debit = self._create_invoice()
        debit.print_debit_note({"sequence": "400", "serial_machine": "SN-TEST-001"})
        self.assertEqual(debit.mf_invoice_number, "400")
        self.assertEqual(debit.mf_serial, "SN-TEST-001")

    # --- check_reprint ---

    def test_check_reprint_ok(self):
        inv = self._create_invoice(state="posted", mf_invoice_number="100")
        result = inv.check_reprint()
        self.assertIn("identifier", result)
        self.assertIn("iot_ip", result)
        self.assertIn("mf_number", result)
        self.assertEqual(result["mf_number"], "100")

    def test_check_reprint_not_printed(self):
        inv = self._create_invoice()
        with self.assertRaises(ValidationError):
            inv.check_reprint()

    def test_check_reprint_no_iot_mf(self):
        inv = self._create_invoice(iot_mf=False, mf_invoice_number="100")
        with self.assertRaises(ValidationError):
            inv.check_reprint()

    def test_check_reprint_no_lines(self):
        inv = self._create_invoice(
            state="posted",
            mf_invoice_number="100",
            invoice_line_ids=[],
        )
        result = inv.check_reprint()
        self.assertIsInstance(result, dict)
        self.assertFalse(result.get("valid", True))

    # --- _get_reconciled_info_JSON_values ---

    def test_get_reconciled_info_JSON_values_empty(self):
        inv = self._create_invoice(state="posted")
        result = inv._get_reconciled_info_JSON_values()
        self.assertIsInstance(result, list)
