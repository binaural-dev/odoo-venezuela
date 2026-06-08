import logging
from odoo.tests import tagged, Form
from odoo.exceptions import UserError, ValidationError
from odoo import Command, fields
from odoo.tools.safe_eval import safe_eval

from .test_withholding_common_VEF import RetentionTestCommon

_logger = logging.getLogger(__name__)


@tagged("manual_retention_flow", "-at_install", "post_install")
class TestManualRetentionFlow(RetentionTestCommon):
    """Tests for manual retention creation via Form views (real user flow)."""

    

    # ═══════════════════════════════════════════════════════════════
    #   IVA Manual supplier retention (Form)
    # ═══════════════════════════════════════════════════════════════

    def test_1_iva_manual_supplier_flow(self):
        invoice = self._create_invoice_reten_iva(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self.assertTrue(
            any(invoice.invoice_line_ids.mapped("tax_ids").filtered(lambda x: x.amount > 0))
        )
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, "posted")

        invoice.flush_recordset() 
        # 2. Limpiar la caché para que la siguiente consulta lea los valores reales
        invoice.invalidate_recordset()

        action_ref = self.env.ref('l10n_ve_payment_extension.action_retention_iva_supplier')
        action_data = action_ref.read()[0]
        ctx = safe_eval(action_data.get('context', '{}'))
        with Form(self.env[action_data['res_model']].with_context(ctx)) as ret_form:
            ret_form.partner_id = invoice.partner_id
            ret_form.date_accounting = fields.Date.today()
            
        retention = ret_form.save()

        self.assertTrue(retention.retention_line_ids)
        self.assertEqual(retention.state, "draft")
        line = retention.retention_line_ids[0]
        self.assertEqual(line.invoice_amount, 1000.0)
        self.assertEqual(line.invoice_total, 1160.0)
        self.assertEqual(line.retention_amount, 120.0,
                         "Supplier IVA: 160 × 75/100 = 120")
        self.assertEqual(retention.total_invoice_amount, 1000.0)
        self.assertEqual(retention.total_retention_amount, 120.0)

        retention.action_post()
        self.assertEqual(retention.state, "emitted")
        self.assertTrue(retention.payment_ids)
        pay = retention.payment_ids[0]
        self.assertEqual(pay.state, "paid")
        self.assertAlmostEqual(pay.amount, 120.0, places=2)

        invoice.invalidate_recordset()
        self.assertTrue(invoice.iva_voucher_number)
        self.assertEqual(invoice.count_iva_retention, 1)
        self.assertTrue(invoice.has_emited_iva_retention)

    def test_2_iva_manual_supplier_all_fields(self):
        invoice = self._create_invoice_reten_iva(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self.assertTrue(
            any(invoice.invoice_line_ids.mapped("tax_ids").filtered(lambda x: x.amount > 0))
        )
        invoice.with_context(move_action_post_alert=True).action_post()

        action_ref = self.env.ref('l10n_ve_payment_extension.action_retention_iva_supplier')
        action_data = action_ref.read()[0]
        ctx = safe_eval(action_data.get('context', '{}'))
        with Form(self.env[action_data['res_model']].with_context(ctx)) as ret_form:
            ret_form.partner_id = invoice.partner_id
            ret_form.date_accounting = fields.Date.today()
            #with ret_form.retention_line_ids.new() as ret_line:
            #    ret_line.move_id = invoice
            #    ret_line.invoice_amount = 1000.0
            #    ret_line.iva_amount = 160.0
            #    ret_line.invoice_total = 1160.0
            #    ret_line.aliquot = 16.0
            #    ret_line.related_percentage_tax_base = 75.0
        retention = ret_form.save()

        retention.action_post()

        line = retention.retention_line_ids[0]
        pay = retention.payment_ids[0]

        self.assertEqual(retention.type_retention, "iva")
        self.assertEqual(retention.type, "in_invoice")
        self.assertEqual(retention.partner_id, invoice.partner_id)
        self.assertEqual(retention.state, "emitted")
        self.assertTrue(retention.number)
        self.assertTrue(retention.name)
        self.assertEqual(retention.date_accounting, fields.Date.today())
        self.assertEqual(retention.date, fields.Date.today())
        self.assertEqual(retention.company_currency_id, self.currency_vef)
        self.assertEqual(retention.foreign_currency_id, self.currency_usd)
        self.assertTrue(retention.base_currency_is_vef)
        self.assertEqual(retention.total_invoice_amount, 1000.0)
        self.assertEqual(retention.total_retention_amount, 120.0)
        self.assertAlmostEqual(retention.foreign_total_invoice_amount, 1000.0 / self.rate, places=2)
        self.assertTrue(retention.payment_ids)
        self.assertTrue(retention.retention_line_ids)
        self.assertIn(invoice.id, retention.actual_invoice_ids.ids)

        self.assertEqual(line.move_id, invoice)
        self.assertEqual(line.retention_id, retention)
        self.assertEqual(line.invoice_amount, 1000.0)
        self.assertEqual(line.invoice_total, 1160.0)
        self.assertEqual(line.retention_amount, 120.0)
        self.assertEqual(line.state, "emitted")
        self.assertEqual(line.name, "Iva Retention")
        #self.assertEqual(line.invoice_type, "in_invoice")
        self.assertTrue(line.payment_id)
        self.assertEqual(line.company_currency_id, self.currency_vef)
        self.assertTrue(line.date_accounting)

        self.assertTrue(pay.is_retention)
        self.assertEqual(pay.payment_type_retention, "iva")
        self.assertEqual(pay.retention_id, retention)
        self.assertEqual(pay.state, "paid")
        self.assertAlmostEqual(pay.amount, 120.0, places=2)
        self.assertEqual(pay.partner_id, invoice.partner_id)
        self.assertEqual(pay.currency_id, self.currency_vef)
        self.assertEqual(pay.retention_ref, retention.number)
        self.assertAlmostEqual(pay.retention_foreign_amount, 120.0 / self.rate, places=2)
        self.assertTrue(pay.retention_line_ids)

        self.assertTrue(invoice.iva_voucher_number)
        self.assertEqual(invoice.count_iva_retention, 1)
        self.assertTrue(invoice.has_emited_iva_retention)

    def test_3_iva_manual_supplier_cancel(self):
        invoice = self._create_invoice_reten_iva(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self.assertTrue(
            any(invoice.invoice_line_ids.mapped("tax_ids").filtered(lambda x: x.amount > 0))
        )
        invoice.with_context(move_action_post_alert=True).action_post()

        action_ref = self.env.ref('l10n_ve_payment_extension.action_retention_iva_supplier')
        action_data = action_ref.read()[0]
        ctx = safe_eval(action_data.get('context', '{}'))
        with Form(self.env[action_data['res_model']].with_context(ctx)) as ret_form:
            ret_form.partner_id = invoice.partner_id
            ret_form.date_accounting = fields.Date.today()
            
        retention = ret_form.save()

        retention.action_post()

        line = retention.retention_line_ids[0]
        pay = retention.payment_ids[0]

        retention.action_cancel()
        line.invalidate_recordset()
        retention.invalidate_recordset()

        self.assertEqual(retention.state, "cancel")
        self.assertFalse(retention.payment_ids)
        self.assertTrue(retention.number, "Number preserved after cancel")
        self.assertFalse(invoice.retention_iva_line_ids)
        self.assertEqual(line.state, "cancel")
        self.assertFalse(line.payment_id)
        self.assertEqual(pay.state, "canceled")
        self.assertFalse(pay.retention_id)
        self.assertFalse(pay.is_retention)
        self.assertFalse(pay.payment_type_retention)
        self.assertFalse(pay.retention_ref)
        self.assertFalse(invoice.iva_voucher_number)
        self.assertEqual(invoice.count_iva_retention, 0)
        self.assertFalse(invoice.has_emited_iva_retention)

    # ═══════════════════════════════════════════════════════════════
    #   IVA Manual customer retention (Form + number required)
    #   retention_amount = 0.0 (model forces 0 for out_invoice)
    # ═══════════════════════════════════════════════════════════════

    def test_4_iva_manual_customer_flow(self):
        invoice = self._create_invoice_reten_iva(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="out_invoice", journal=self.sale_journal,
        )
        self.assertTrue(
            any(invoice.invoice_line_ids.mapped("tax_ids").filtered(lambda x: x.amount > 0))
        )
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, "posted")

        action_ref = self.env.ref('l10n_ve_payment_extension.action_retention_iva_client')
        action_data = action_ref.read()[0]
        ctx = safe_eval(action_data.get('context', '{}'))
        with Form(self.env[action_data['res_model']].with_context(ctx)) as ret_form:
            ret_form.partner_id = invoice.partner_id
            ret_form.number = "12345678901234"
            ret_form.date_accounting = fields.Date.today()
            
        retention = ret_form.save()

        self.assertTrue(retention.retention_line_ids)
        self.assertEqual(retention.state, "draft")
        line = retention.retention_line_ids[0]
        self.assertEqual(line.invoice_amount, 1000.0)
        self.assertEqual(line.invoice_total, 1160.0)
        self.assertEqual(line.retention_amount, 0.0,
                         "Customer IVA: model forces 0 for out_invoice")
        self.assertEqual(retention.total_retention_amount, 0.0)

        line.retention_amount = 120.0
        retention.action_post()

        self.assertEqual(retention.state, "emitted")
        self.assertTrue(retention.payment_ids)
        pay = retention.payment_ids[0]
        self.assertEqual(pay.state, "paid")
        self.assertAlmostEqual(pay.amount, 120.0, places=2)

        invoice.invalidate_recordset()
        self.assertTrue(invoice.iva_voucher_number)
        self.assertEqual(invoice.count_iva_retention, 1)
        self.assertTrue(invoice.has_emited_iva_retention)

    def test_5_iva_manual_customer_all_fields(self):
        invoice = self._create_invoice_reten_iva(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="out_invoice", journal=self.sale_journal,
        )
        self.assertTrue(
            any(invoice.invoice_line_ids.mapped("tax_ids").filtered(lambda x: x.amount > 0))
        )
        invoice.with_context(move_action_post_alert=True).action_post()

        action_ref = self.env.ref('l10n_ve_payment_extension.action_retention_iva_client')
        action_data = action_ref.read()[0]
        ctx = safe_eval(action_data.get('context', '{}'))
        with Form(self.env[action_data['res_model']].with_context(ctx)) as ret_form:
            ret_form.partner_id = invoice.partner_id
            ret_form.number = "12345678901234"
            ret_form.date_accounting = fields.Date.today()
            #with ret_form.retention_line_ids.edit(0) as ret_line:
                #ret_line.move_id = invoice
                #ret_line.invoice_amount = 1000.0
                #ret_line.iva_amount = 160.0
                #ret_line.retention_amount = 120
        retention = ret_form.save()

        line = retention.retention_line_ids[0]
        line.retention_amount = 120.0
        retention.action_post()

        pay = retention.payment_ids[0]

        self.assertEqual(retention.type_retention, "iva")
        self.assertEqual(retention.type, "out_invoice")
        self.assertEqual(retention.partner_id, invoice.partner_id)
        self.assertEqual(retention.state, "emitted")
        self.assertEqual(retention.number, "12345678901234")
        self.assertTrue(retention.name)
        self.assertEqual(retention.company_currency_id, self.currency_vef)
        self.assertEqual(retention.foreign_currency_id, self.currency_usd)
        self.assertEqual(retention.total_invoice_amount, 1000.0)
        self.assertEqual(retention.total_retention_amount, 120.0)
        self.assertAlmostEqual(retention.foreign_total_invoice_amount, 1000.0 / self.rate, places=2)

        self.assertEqual(line.move_id, invoice)
        self.assertEqual(line.invoice_amount, 1000.0)
        self.assertEqual(line.invoice_total, 1160.0)
        self.assertEqual(line.retention_amount, 120.0)
        self.assertEqual(line.state, "emitted")
        self.assertTrue(line.payment_id)

        self.assertTrue(pay.is_retention)
        self.assertEqual(pay.payment_type_retention, "iva")
        self.assertEqual(pay.retention_id, retention)
        self.assertEqual(pay.state, "paid")
        self.assertAlmostEqual(pay.amount, 120.0, places=2)

        self.assertTrue(invoice.iva_voucher_number)
        self.assertEqual(invoice.count_iva_retention, 1)
        self.assertTrue(invoice.has_emited_iva_retention)

    def test_6_iva_manual_customer_post_fail_no_amount(self):
        invoice = self._create_invoice_reten_iva(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="out_invoice", journal=self.sale_journal,
        )
        self.assertTrue(
            any(invoice.invoice_line_ids.mapped("tax_ids").filtered(lambda x: x.amount > 0))
        )
        invoice.with_context(move_action_post_alert=True).action_post()

        action_ref = self.env.ref('l10n_ve_payment_extension.action_retention_iva_client')
        action_data = action_ref.read()[0]
        ctx = safe_eval(action_data.get('context', '{}'))
        with Form(self.env[action_data['res_model']].with_context(ctx)) as ret_form:
            ret_form.partner_id = invoice.partner_id
            ret_form.number = "12345678901234"
            ret_form.date_accounting = fields.Date.today()
          
        retention = ret_form.save()

        with self.assertRaises(ValidationError) as cm:
            retention.action_post()
        self.assertIn("No registered lines found in the move to reconcile",
                      str(cm.exception))
        self.assertEqual(retention.state, "draft")

        pay = retention.payment_ids[0] if retention.payment_ids else None
        retention.action_cancel()
        retention.invalidate_recordset()

        self.assertEqual(retention.state, "cancel")
        self.assertFalse(retention.payment_ids)
        if pay:
            self.assertEqual(pay.state, "canceled")
            self.assertFalse(pay.retention_id)
            self.assertFalse(pay.is_retention)
        self.assertFalse(invoice.iva_voucher_number)
        self.assertEqual(invoice.count_iva_retention, 0)
        self.assertFalse(invoice.has_emited_iva_retention)

    def test_7_iva_manual_customer_cancel(self):
        invoice = self._create_invoice_reten_iva(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="out_invoice", journal=self.sale_journal,
        )
        self.assertTrue(
            any(invoice.invoice_line_ids.mapped("tax_ids").filtered(lambda x: x.amount > 0))
        )
        invoice.with_context(move_action_post_alert=True).action_post()

        action_ref = self.env.ref('l10n_ve_payment_extension.action_retention_iva_client')
        action_data = action_ref.read()[0]
        ctx = safe_eval(action_data.get('context', '{}'))
        with Form(self.env[action_data['res_model']].with_context(ctx)) as ret_form:
            ret_form.partner_id = invoice.partner_id
            ret_form.number = "12345678901234"
            ret_form.date_accounting = fields.Date.today()
           
        retention = ret_form.save()

        line = retention.retention_line_ids[0]
        line.retention_amount = 120.0
        retention.action_post()

        pay = retention.payment_ids[0]
        retention.action_cancel()
        line.invalidate_recordset()
        retention.invalidate_recordset()

        self.assertEqual(retention.state, "cancel")
        self.assertFalse(retention.payment_ids)
        self.assertEqual(retention.number, "12345678901234",
                         "Number preserved after cancel")
        self.assertFalse(invoice.retention_iva_line_ids)
        self.assertEqual(line.state, "cancel")
        self.assertFalse(line.payment_id)
        self.assertEqual(pay.state, "canceled")
        self.assertFalse(pay.retention_id)
        self.assertFalse(pay.is_retention)
        self.assertFalse(pay.payment_type_retention)
        self.assertFalse(pay.retention_ref)
        self.assertFalse(invoice.iva_voucher_number)
        self.assertEqual(invoice.count_iva_retention, 0)
        self.assertFalse(invoice.has_emited_iva_retention)

    # ═══════════════════════════════════════════════════════════════
    #   ISLR Manual supplier retention (Form + new line)
    # ═══════════════════════════════════════════════════════════════

    def test_8_islr_manual_supplier_flow(self):
        invoice = self._create_invoice_islr(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self.assertTrue(invoice.is_isrl_retention_available)
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, "posted")

        action_ref = self.env.ref('l10n_ve_payment_extension.action_retention_islr_supplier')
        action_data = action_ref.read()[0]
        ctx = safe_eval(action_data.get('context', '{}'))
        with Form(self.env[action_data['res_model']].with_context(ctx)) as ret_form:
            ret_form.partner_id = invoice.partner_id
            ret_form.date_accounting = fields.Date.today()
            with ret_form.retention_line_ids.new() as ret_line:
                ret_line.move_id = invoice
                ret_line.payment_concept_id = self.concept_one
        retention = ret_form.save()

        self.assertTrue(retention.retention_line_ids)
        self.assertEqual(retention.state, "draft")
        line = retention.retention_line_ids[0]
        self.assertEqual(line.invoice_amount, 1000.0)
        self.assertEqual(line.retention_amount, 27.0,
                         "Supplier ISLR: 1000 × 0.90 × 0.03 = 27.0")
        self.assertEqual(retention.total_retention_amount, 27.0)

        retention.action_post()

        self.assertEqual(retention.state, "emitted")
        self.assertTrue(retention.payment_ids)
        pay = retention.payment_ids[0]
        self.assertEqual(pay.state, "paid")
        self.assertAlmostEqual(pay.amount, 27.0, places=2)

        invoice.invalidate_recordset()
        self.assertTrue(invoice.islr_voucher_number)
        self.assertEqual(invoice.count_islr_retention, 1)
        self.assertTrue(invoice.has_emited_islr_retention)

    def test_9_islr_manual_supplier_all_fields(self):
        invoice = self._create_invoice_islr(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self.assertTrue(invoice.is_isrl_retention_available)
        invoice.with_context(move_action_post_alert=True).action_post()

        action_ref = self.env.ref('l10n_ve_payment_extension.action_retention_islr_supplier')
        action_data = action_ref.read()[0]
        ctx = safe_eval(action_data.get('context', '{}'))
        with Form(self.env[action_data['res_model']].with_context(ctx)) as ret_form:
            ret_form.partner_id = invoice.partner_id
            ret_form.date_accounting = fields.Date.today()
            with ret_form.retention_line_ids.new() as ret_line:
                ret_line.move_id = invoice
                ret_line.payment_concept_id = self.concept_one
        retention = ret_form.save()

        retention.action_post()

        line = retention.retention_line_ids[0]
        pay = retention.payment_ids[0]

        self.assertEqual(retention.type_retention, "islr")
        self.assertEqual(retention.type, "in_invoice")
        self.assertEqual(retention.partner_id, invoice.partner_id)
        self.assertEqual(retention.state, "emitted")
        self.assertTrue(retention.number)
        self.assertTrue(retention.name)
        self.assertEqual(retention.date_accounting, fields.Date.today())
        self.assertEqual(retention.date, fields.Date.today())
        self.assertEqual(retention.company_currency_id, self.currency_vef)
        self.assertEqual(retention.foreign_currency_id, self.currency_usd)
        self.assertTrue(retention.base_currency_is_vef)
        self.assertEqual(retention.total_invoice_amount, 1000.0)
        self.assertEqual(retention.total_iva_amount, 0.0)
        self.assertEqual(retention.total_retention_amount, 27.0)
        self.assertTrue(retention.payment_ids)
        self.assertTrue(retention.retention_line_ids)
        self.assertIn(invoice.id, retention.actual_invoice_ids.ids)

        self.assertEqual(line.move_id, invoice)
        self.assertEqual(line.retention_id, retention)
        self.assertEqual(line.invoice_total, 1000.0)
        self.assertEqual(line.retention_amount, 27.0)
        self.assertEqual(line.related_amount_subtract_fees, 0.0)
        self.assertEqual(line.state, "emitted")
        self.assertEqual(line.name, "ISLR Retention")
        self.assertTrue(line.payment_id)
        self.assertEqual(line.payment_concept_id, self.concept_one)
        self.assertEqual(line.company_currency_id, self.currency_vef)
        self.assertEqual(line.foreign_currency_id, self.currency_usd)

        self.assertTrue(pay.is_retention)
        self.assertEqual(pay.payment_type_retention, "islr")
        self.assertEqual(pay.retention_id, retention)
        self.assertEqual(pay.state, "paid")
        self.assertAlmostEqual(pay.amount, 27.0, places=2)
        self.assertEqual(pay.partner_id, invoice.partner_id)
        self.assertEqual(pay.currency_id, self.currency_vef)
        self.assertEqual(pay.retention_ref, retention.number)
        self.assertTrue(pay.retention_line_ids)

        self.assertTrue(invoice.islr_voucher_number)
        self.assertTrue(invoice.is_isrl_retention_available)
        self.assertEqual(invoice.count_islr_retention, 1)
        self.assertTrue(invoice.has_emited_islr_retention)

    def test_10_islr_manual_supplier_cancel(self):
        invoice = self._create_invoice_islr(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self.assertTrue(invoice.is_isrl_retention_available)
        invoice.with_context(move_action_post_alert=True).action_post()

        action_ref = self.env.ref('l10n_ve_payment_extension.action_retention_islr_supplier')
        action_data = action_ref.read()[0]
        ctx = safe_eval(action_data.get('context', '{}'))
        with Form(self.env[action_data['res_model']].with_context(ctx)) as ret_form:
            ret_form.partner_id = invoice.partner_id
            ret_form.date_accounting = fields.Date.today()
            with ret_form.retention_line_ids.new() as ret_line:
                ret_line.move_id = invoice
                ret_line.payment_concept_id = self.concept_one
        retention = ret_form.save()

        retention.action_post()

        line = retention.retention_line_ids[0]
        pay = retention.payment_ids[0]

        retention.action_cancel()
        line.invalidate_recordset()
        retention.invalidate_recordset()

        self.assertEqual(retention.state, "cancel")
        self.assertFalse(retention.payment_ids)
        self.assertFalse(invoice.retention_islr_line_ids)
        self.assertEqual(line.state, "cancel")
        self.assertFalse(line.payment_id)
        self.assertEqual(pay.state, "canceled")
        self.assertFalse(pay.retention_id)
        self.assertFalse(pay.is_retention)
        self.assertFalse(pay.payment_type_retention)
        self.assertFalse(pay.retention_ref)
        self.assertFalse(invoice.islr_voucher_number)
        self.assertEqual(invoice.count_islr_retention, 0)
        self.assertFalse(invoice.has_emited_islr_retention)

    # ═══════════════════════════════════════════════════════════════
    #   ISLR Manual customer retention (Form, 0 amounts draft)
    # ═══════════════════════════════════════════════════════════════

    def test_11_islr_manual_customer_draft(self):
        invoice = self._create_invoice_islr(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="out_invoice", journal=self.sale_journal,
        )
        self.assertTrue(invoice.is_isrl_retention_available)
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, "posted")

        action_ref = self.env.ref('l10n_ve_payment_extension.action_retention_islr_client')
        action_data = action_ref.read()[0]
        ctx = safe_eval(action_data.get('context', '{}'))
        with Form(self.env[action_data['res_model']].with_context(ctx)) as ret_form:
            ret_form.partner_id = invoice.partner_id
            ret_form.date_accounting = fields.Date.today()
            ret_form.number = "12345678901234"
            with ret_form.retention_line_ids.new() as ret_line:
                ret_line.move_id = invoice
                ret_line.payment_concept_id = self.concept_one
        retention = ret_form.save()

        self.assertEqual(retention.state, "draft")
        self.assertTrue(retention.number)
        self.assertTrue(retention.retention_line_ids)
        self.assertFalse(retention.payment_ids)

        line = retention.retention_line_ids[0]
        self.assertEqual(line.invoice_amount, 0.0)
        self.assertEqual(line.iva_amount, 0.0)
        self.assertEqual(line.invoice_total, 0.0,
                         "Customer ISLR: invoice_total stays 0 (no concept match)")
        self.assertEqual(line.retention_amount, 0.0,
                         "Customer ISLR: retention_amount stays 0")
        self.assertEqual(line.related_percentage_tax_base, 0.0)
        self.assertEqual(line.related_percentage_fees, 0.0)
        self.assertFalse(line.payment_id)

        with self.assertRaises(ValidationError) as cm:
            retention.action_post()
        self.assertIn("No registered lines found in the move to reconcile",
                      str(cm.exception))
        self.assertEqual(retention.state, "draft")

        retention.action_cancel()
        retention.invalidate_recordset()
        self.assertEqual(retention.state, "cancel")

    def test_12_islr_manual_customer_all_fields_draft(self):
        invoice = self._create_invoice_islr(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="out_invoice", journal=self.sale_journal,
        )
        self.assertTrue(invoice.is_isrl_retention_available)
        invoice.with_context(move_action_post_alert=True).action_post()

        action_ref = self.env.ref('l10n_ve_payment_extension.action_retention_islr_client')
        action_data = action_ref.read()[0]
        ctx = safe_eval(action_data.get('context', '{}'))
        with Form(self.env[action_data['res_model']].with_context(ctx)) as ret_form:
            ret_form.partner_id = invoice.partner_id
            ret_form.date_accounting = fields.Date.today()
            ret_form.number = "12345678901234"
            with ret_form.retention_line_ids.new() as ret_line:
                ret_line.move_id = invoice
                ret_line.payment_concept_id = self.concept_one
        retention = ret_form.save()

        line = retention.retention_line_ids[0]

        self.assertEqual(line.payment_concept_id, self.concept_one)
        self.assertEqual(retention.type_retention, "islr")
        self.assertEqual(retention.type, "out_invoice")
        self.assertEqual(retention.partner_id, invoice.partner_id)
        self.assertEqual(retention.state, "draft")
        self.assertTrue(retention.number)
        self.assertFalse(retention.payment_ids)
        self.assertTrue(retention.retention_line_ids)

        self.assertEqual(line.move_id, invoice)
        self.assertEqual(line.retention_id, retention)
        self.assertEqual(line.iva_amount, 0.0)
        self.assertEqual(line.invoice_total, 0.0,
                         "Customer ISLR: invoice_total stays 0 (no concept match)")
        self.assertEqual(line.retention_amount, 0.0)
        self.assertEqual(line.aliquot, 0.0)
        self.assertEqual(line.related_percentage_tax_base, 0.0)
        self.assertEqual(line.related_percentage_fees, 0.0)
        self.assertEqual(line.related_amount_subtract_fees, 0.0)
        self.assertEqual(line.state, "draft")
        self.assertEqual(line.name, "ISLR Retention")
        self.assertFalse(line.payment_id)
        self.assertEqual(line.payment_concept_id, self.concept_one)

        self.assertEqual(retention.total_invoice_amount, 0.0)
        self.assertEqual(retention.total_iva_amount, 0.0)
        self.assertEqual(retention.total_retention_amount, 0.0)
        self.assertEqual(retention.foreign_total_invoice_amount, 0.0)
        self.assertEqual(retention.foreign_total_iva_amount, 0.0)
        self.assertEqual(retention.foreign_total_retention_amount, 0.0)

    # ═══════════════════════════════════════════════════════════════
    #   ISLR — validate_islr() error cases (no Form needed)
    # ═══════════════════════════════════════════════════════════════

    def test_13_islr_manual_validate_errors(self):
        invoice_not_posted = self._create_invoice_islr(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self.assertTrue(invoice_not_posted.is_isrl_retention_available)
        with self.assertRaises(UserError) as cm:
            invoice_not_posted.validate_islr()
        self.assertIn("invoice", str(cm.exception).lower())

        invoice_no_concept = self._create_invoice_reten_iva(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        invoice_no_concept.with_context(move_action_post_alert=True).action_post()
        with self.assertRaises(UserError) as cm:
            invoice_no_concept.validate_islr()
        self.assertIn("concept", str(cm.exception).lower())

        invoice_emitted = self._create_invoice_islr(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self.assertTrue(invoice_emitted.is_isrl_retention_available)
        invoice_emitted.generate_islr_retention = True
        invoice_emitted.with_context(move_action_post_alert=True).action_post()
        self.assertTrue(invoice_emitted.has_emited_islr_retention)
        with self.assertRaises(UserError) as cm:
            invoice_emitted.validate_islr()
        self.assertIn("islr", str(cm.exception).lower())
