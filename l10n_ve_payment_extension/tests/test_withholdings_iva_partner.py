import logging
from odoo.tests import tagged , Form
from odoo.exceptions import UserError, ValidationError
from odoo import Command, fields

from .test_withholding_common_VEF import RetentionTestCommon 

_logger = logging.getLogger(__name__)


@tagged("iva_retention_partner", "-at_install", "post_install")
class TestRetention(RetentionTestCommon): 
    def _assert_invoice_taxes(self, invoice, expect_taxes, islr=None):
        """
        Valida si la factura contiene impuestos mayores a 0% según el resultado esperado.
        :param invoice: Registro de la factura (account.move)
        :param expect_taxes: Boolean (True si debe tener impuestos, False si no debe tener)
        """
        has_taxes = any(
            invoice.invoice_line_ids.mapped("tax_ids").filtered(lambda x: x.amount > 0)
        )
        
        # Mensaje personalizado en caso de que falle la prueba
        msg = (
            "Se esperaba que la factura tuviera impuestos activos, pero no se encontró ninguno."
            if expect_taxes else 
            "Se esperaba una factura EXENTA (sin impuestos > 0), pero se detectaron impuestos aplicados."
        )

        if islr != None:
            if islr:
                self.assertEqual(invoice.is_isrl_retention_available, islr ,"La factura no es valida para retención de ISLR y no se deberían aplicar")
            else:
                self.assertEqual(invoice.is_isrl_retention_available, islr, "La factura es valida para retención de ISLR y se deberían aplicar")
        
        # Valida que el estado real coincida con el esperado
        self.assertEqual(has_taxes, expect_taxes, msg)

    def test_invoice_withholding_available(self):
        
        # Crear factura de venta con retención de IVA
        invoice = self._create_invoice_reten_iva(amount=1000, partner=self.partner_pnr_100, out_invoice="out_invoice", journal=self.sale_journal)
        
        self._assert_invoice_taxes(invoice, expect_taxes=True)

        invoice_islr = self._create_invoice_islr(amount=1000, partner=self.partner_pnr_100, out_invoice="out_invoice", journal=self.sale_journal)
        
        self._assert_invoice_taxes(invoice_islr, expect_taxes=False, islr=True)

        invoice_islr_iva = self._create_invoice_islr_iva(amount=1000, partner=self.partner_pnr_100, out_invoice="out_invoice", journal=self.sale_journal)
        
        self._assert_invoice_taxes(invoice_islr_iva, expect_taxes=True, islr=True)

        # Crear factura de compra con retención de IVA

        invoice_pr = self._create_invoice_reten_iva(amount=1000, partner=self.partner_pnr_100, out_invoice="in_invoice", journal=self.purchase_journal)
        
        self._assert_invoice_taxes(invoice_pr, expect_taxes=True, islr=False)

        invoice_islr_pr = self._create_invoice_islr(amount=1000, partner=self.partner_pnr_100, out_invoice="in_invoice", journal=self.purchase_journal)
        
        self._assert_invoice_taxes(invoice_islr_pr, expect_taxes=False)

        invoice_islr_iva_pr = self._create_invoice_islr_iva(amount=1000, partner=self.partner_pnr_100, out_invoice="in_invoice", journal=self.purchase_journal)
        
        self._assert_invoice_taxes(invoice_islr_iva_pr, expect_taxes=True, islr=True)


    def test_iva_withholding_validations(self):
        
        # Crear factura de venta con retención de IVA
        invoice = self._create_invoice_reten_iva(amount=1000.0, partner=self.partner_pnr_100, out_invoice="out_invoice", journal=self.sale_journal)
        
        self._assert_invoice_taxes(invoice, expect_taxes=True)
        invoice.generate_iva_retention = True
        invoice.with_context(move_action_post_alert=True).action_post()

        self.assertEqual(invoice.count_iva_retention, 1)
        self.assertFalse(invoice.has_emited_iva_retention, "La factura no debería tener la retención de IVA emitida después de la publicación, para clientes")
        self.assertEqual(invoice.retention_iva_line_ids[0].state, "draft", "La retención de IVA debería estar en estado borrador para clientes")
        self.assertEqual(invoice.retention_iva_line_ids[0].retention_id.total_retention_amount, 0.0, "La retención de IVA debería tener un monto total de 0 para clientes cuando esta en borrador")
        
        with self.assertRaises(UserError) as cm:
            invoice.retention_iva_line_ids[0].retention_id.action_post()
            
        # Validamos que el texto del error contenga una frase específica esperada
        Message = "No registered lines found in the move to reconcile."
        self.assertIn(Message, str(cm.exception), "No se puede publicar la retencion porq no las lineas de retenciones no tienen monto a retener")

        self.assertEqual(invoice.retention_iva_line_ids[0].invoice_amount, 1000.0, "base imponible debe ser 1000.0")
        self.assertEqual(invoice.retention_iva_line_ids[0].invoice_total, 1160.0, "total de factura debe ser 1160.0")

        self.assertEqual(invoice.retention_iva_line_ids[0].retention_id.total_invoice_amount,1000.0, "total de facturado en la retencion debe ser 1160.0")
        self.assertEqual(invoice.retention_iva_line_ids[0].retention_id.total_iva_amount, 160.0, "total de facturado en la retencion debe ser 160")
        
        
        invoice_islr_iva = self._create_invoice_islr_iva(amount=1000.0, partner=self.partner_pnr_100, out_invoice="out_invoice", journal=self.sale_journal)
        
        self._assert_invoice_taxes(invoice_islr_iva, expect_taxes=True)

        # Crear factura de compra con retención de IVA

        invoice_pr = self._create_invoice_reten_iva(amount=1000.0, partner=self.partner_pnr_100, out_invoice="in_invoice", journal=self.purchase_journal)
        
        self._assert_invoice_taxes(invoice_pr, expect_taxes=True)

        

        invoice_islr_iva_pr = self._create_invoice_islr_iva(amount=1000.0, partner=self.partner_pnr_100, out_invoice="in_invoice", journal=self.purchase_journal)
        
        self._assert_invoice_taxes(invoice_islr_iva_pr, expect_taxes=True, islr=True)

    def test_iva_supplier_flow_complete(self):

        invoice = self._create_invoice_reten_iva(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self._assert_invoice_taxes(invoice, expect_taxes=True)
        invoice.generate_iva_retention = True
        invoice.with_context(move_action_post_alert=True).action_post()

        self.assertEqual(invoice.count_iva_retention, 1)
        self.assertTrue(invoice.iva_voucher_number, "Supplier invoice must have voucher number after retention generation")
        self.assertEqual(invoice.retention_iva_line_ids[0].state, "emitted",
                         "Retention must be in emmited after creation for supplier from invoice")
        ret = invoice.retention_iva_line_ids[0].retention_id
        self.assertEqual(ret.type_retention, "iva")
        self.assertEqual(ret.type, "in_invoice")
        self.assertGreater(ret.total_invoice_amount, 0,
                           "Total invoice amount must be > 0 for supplier retention")
        self.assertGreater(ret.total_iva_amount, 0,
                           "Total IVA amount must be > 0 for supplier retention")
        self.assertGreater(ret.total_retention_amount, 0,
                           "Total retention amount must be > 0 for supplier retention")

    def test_iva_partner_without_withholding_type(self):

        invoice = self._create_invoice_reten_iva(
            amount=1000.0, partner=self.partner_ordinary,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        invoice.generate_iva_retention = True
        with self.assertRaises(UserError) as cm:
            invoice.with_context(move_action_post_alert=True).action_post()
        self.assertIn("withholding type", str(cm.exception).lower(),
                      "Must raise UserError about missing withholding type")

    def test_iva_no_taxes_raises_error(self):

        invoice = self._create_invoice_islr(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        invoice.generate_iva_retention = True
        with self.assertRaises(UserError) as cm:
            invoice.with_context(move_action_post_alert=True).action_post()
        self.assertIn("tax", str(cm.exception).lower(),
                      "Must raise UserError about missing tax on invoice")

    def test_iva_cancel_supplier_retention(self):
        invoice = self._create_invoice_reten_iva(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self._assert_invoice_taxes(invoice, expect_taxes=True)
        invoice.generate_iva_retention = True
        invoice.with_context(move_action_post_alert=True).action_post()

        ret = invoice.retention_iva_line_ids[0].retention_id
        payment = ret.payment_ids[0]

        self.assertEqual(ret.state, "emitted")
        self.assertTrue(invoice.iva_voucher_number)

        ret.action_cancel()
        self.assertEqual(ret.state, "cancel")

        self.assertFalse(invoice.iva_voucher_number, "Voucher must be removed from invoice after cancel")
        self.assertFalse(ret.payment_ids, "Retention must have no payments after cancel")
        self.assertEqual(payment.state, "canceled", "Payment must be cancelled")
        self.assertFalse(payment.retention_id, "Payment must have no retention after cancel")
        self.assertFalse(payment.is_retention, "Payment must not be flagged as retention after cancel")
        self.assertFalse(invoice.retention_iva_line_ids, "Invoice must have no active retention lines after cancel")
        self.assertEqual(invoice.count_iva_retention, 0, "count_iva_retention must be 0 after cancel")
        self.assertFalse(invoice.has_emited_iva_retention, "has_emited_iva_retention must be False after cancel")

    def test_iva_customer_pnr_75_amounts(self):
        invoice = self._create_invoice_reten_iva(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="out_invoice", journal=self.sale_journal,
        )
        self._assert_invoice_taxes(invoice, expect_taxes=True)
        invoice.generate_iva_retention = True
        invoice.with_context(move_action_post_alert=True).action_post()

        self.assertEqual(invoice.count_iva_retention, 1)
        self.assertFalse(invoice.has_emited_iva_retention,
                         "Customer must not have emitted retention")
        line = invoice.retention_iva_line_ids[0]
        ret = line.retention_id

        self.assertEqual(ret.state, "draft",
                         "Customer retention must stay in draft")
        self.assertEqual(line.state, "draft",
                         "Customer retention line must be draft")
        self.assertEqual(
            line.related_percentage_tax_base, 75.0,
            "Withholding % must be 75 for partner_pnr_75")
        self.assertEqual(line.invoice_amount, 1000.0,
                         "Base amount must be 1000")
        self.assertEqual(line.iva_amount, 160.0,
                         "IVA amount must be 160 (16% of 1000)")
        self.assertEqual(line.invoice_total, 1160.0,
                         "Invoice total must be 1000+160")
        self.assertEqual(ret.total_retention_amount, 0.0,
                         "Customer retention amount must be 0 in draft")
        self.assertEqual(ret.total_invoice_amount, 1000.0)
        self.assertEqual(ret.total_iva_amount, 160.0)

    def test_iva_customer_pnr_100_amounts(self):
        invoice = self._create_invoice_reten_iva(
            amount=1000.0, partner=self.partner_pnr_100,
            out_invoice="out_invoice", journal=self.sale_journal,
        )
        self._assert_invoice_taxes(invoice, expect_taxes=True)
        invoice.generate_iva_retention = True
        invoice.with_context(move_action_post_alert=True).action_post()

        line = invoice.retention_iva_line_ids[0]
        self.assertEqual(
            line.related_percentage_tax_base, 100.0,
            "Withholding % must be 100 for partner_pnr_100")
        self.assertEqual(line.invoice_amount, 1000.0)
        self.assertEqual(line.iva_amount, 160.0)
        self.assertEqual(line.invoice_total, 1160.0)
        ret = line.retention_id
        self.assertEqual(ret.total_iva_amount, 160.0)
        self.assertEqual(ret.total_invoice_amount, 1000.0)
        self.assertEqual(ret.total_retention_amount, 0.0)

    def test_iva_customer_pnnr_100_amounts(self):
        invoice = self._create_invoice_reten_iva(
            amount=2000.0, partner=self.partner_pnnr_100,
            out_invoice="out_invoice", journal=self.sale_journal,
        )
        self._assert_invoice_taxes(invoice, expect_taxes=True)
        invoice.generate_iva_retention = True
        invoice.with_context(move_action_post_alert=True).action_post()

        line = invoice.retention_iva_line_ids[0]
        self.assertEqual(
            line.related_percentage_tax_base, 100.0,
            "Withholding % must be 100 for partner_pnnr_100")
        self.assertEqual(line.invoice_amount, 2000.0)
        self.assertEqual(line.iva_amount, 320.0,
                         "IVA must be 320 (16% of 2000)")
        self.assertEqual(line.invoice_total, 2320.0)
        ret = line.retention_id
        self.assertEqual(ret.total_iva_amount, 320.0)
        self.assertEqual(ret.total_invoice_amount, 2000.0)

    def test_iva_customer_50_percent(self):
        wt_50 = self.env["account.withholding.type"].create({
            "name": "50%", "value": 50.0, "state": True,
        })
        partner_50 = self.env["res.partner"].create({
            "name": "Cliente 50%", "vat": "J500000001",
            "property_account_receivable_id": self.acc_receivable.id,
            "property_account_payable_id": self.acc_payable.id,
            "taxpayer_type": "formal",
            "withholding_type_id": wt_50.id,
        })
        invoice = self._create_invoice_reten_iva(
            amount=1000.0, partner=partner_50,
            out_invoice="out_invoice", journal=self.sale_journal,
        )
        self._assert_invoice_taxes(invoice, expect_taxes=True)
        invoice.generate_iva_retention = True
        invoice.with_context(move_action_post_alert=True).action_post()

        line = invoice.retention_iva_line_ids[0]
        self.assertEqual(
            line.related_percentage_tax_base, 50.0,
            "Withholding % must be 50 for custom partner")
        self.assertEqual(line.iva_amount, 160.0)
        self.assertEqual(line.invoice_amount, 1000.0)
        ret = line.retention_id
        self.assertEqual(ret.total_iva_amount, 160.0)
        self.assertEqual(ret.total_invoice_amount, 1000.0)

    def test_iva_customer_cancel(self):
        invoice = self._create_invoice_reten_iva(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="out_invoice", journal=self.sale_journal,
        )
        self._assert_invoice_taxes(invoice, expect_taxes=True)
        invoice.generate_iva_retention = True
        invoice.with_context(move_action_post_alert=True).action_post()

        ret = invoice.retention_iva_line_ids[0].retention_id

        self.assertEqual(ret.state, "draft")
        ret.action_cancel()

        self.assertEqual(ret.state, "cancel")
        self.assertFalse(ret.payment_ids, "No payments on retention after cancel")
        self.assertFalse(invoice.retention_iva_line_ids,
                         "No active retention lines after cancel")
        self.assertEqual(invoice.count_iva_retention, 0)
        self.assertFalse(invoice.has_emited_iva_retention)

    def test_iva_supplier_all_fields(self):
        invoice = self._create_invoice_reten_iva(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self._assert_invoice_taxes(invoice, expect_taxes=True)
        invoice.generate_iva_retention = True
        invoice.with_context(move_action_post_alert=True).action_post()

        ret = invoice.retention_iva_line_ids[0].retention_id
        line = invoice.retention_iva_line_ids[0]
        pay = ret.payment_ids[0]

        # ── account.retention ──
        self.assertEqual(ret.type_retention, "iva")
        self.assertEqual(ret.type, "in_invoice")
        self.assertEqual(ret.partner_id, invoice.partner_id)
        self.assertEqual(ret.state, "emitted")
        self.assertTrue(ret.number, "Supplier retention must have auto-generated number")
        self.assertTrue(ret.name, "Name must be set")
        self.assertEqual(ret.date_accounting, fields.Date.today())
        self.assertEqual(ret.date, fields.Date.today())
        self.assertEqual(ret.company_currency_id, self.currency_vef)
        self.assertEqual(ret.foreign_currency_id, self.currency_usd)
        self.assertTrue(ret.base_currency_is_vef)
        self.assertEqual(ret.total_invoice_amount, 1000.0)
        self.assertEqual(ret.total_iva_amount, 160.0)
        self.assertEqual(ret.total_retention_amount, 120.0)
        self.assertAlmostEqual(ret.foreign_total_invoice_amount, 1000.0 / self.rate, places=2)
        self.assertAlmostEqual(ret.foreign_total_iva_amount, 160.0 / self.rate, places=2)
        self.assertAlmostEqual(ret.foreign_total_retention_amount, 120.0 / self.rate, places=2)
        self.assertTrue(ret.payment_ids)
        self.assertTrue(ret.retention_line_ids)
        self.assertIn(invoice.id, ret.actual_invoice_ids.ids)

        # ── account.retention.line ──
        self.assertEqual(line.move_id, invoice)
        self.assertEqual(line.retention_id, ret)
        self.assertEqual(line.invoice_amount, 1000.0)
        self.assertEqual(line.iva_amount, 160.0)
        self.assertEqual(line.invoice_total, 1160.0)
        self.assertEqual(line.retention_amount, 120.0)
        self.assertEqual(line.aliquot, 16.0)
        self.assertEqual(line.related_percentage_tax_base, 75.0)
        self.assertEqual(line.state, "emitted")
        self.assertEqual(line.name, "Iva Retention")
        self.assertEqual(line.invoice_type, "in_invoice")
        self.assertTrue(line.payment_id)
        self.assertAlmostEqual(line.foreign_invoice_amount, 1000.0 / self.rate, places=2)
        self.assertAlmostEqual(line.foreign_iva_amount, 160.0 / self.rate, places=2)
        self.assertAlmostEqual(line.foreign_invoice_total, 1160.0 / self.rate, places=2)
        self.assertEqual(line.company_currency_id, self.currency_vef)
        self.assertEqual(line.foreign_currency_id, self.currency_usd)
        self.assertTrue(line.date_accounting, fields.Date.today())

        # ── account.payment ──
        self.assertTrue(pay.is_retention)
        self.assertEqual(pay.payment_type_retention, "iva")
        self.assertEqual(pay.retention_id, ret)
        self.assertEqual(pay.state, "paid")
        self.assertAlmostEqual(pay.amount, 120.0, places=2)
        self.assertEqual(pay.partner_id, invoice.partner_id)
        self.assertEqual(pay.currency_id, self.currency_vef)
        self.assertEqual(pay.retention_ref, ret.number)
        self.assertAlmostEqual(pay.retention_foreign_amount, 120.0 / self.rate, places=2)
        self.assertTrue(pay.retention_line_ids)

        # ── account.move (invoice) ──
        self.assertTrue(invoice.iva_voucher_number)
        self.assertEqual(invoice.count_iva_retention, 1)
        self.assertTrue(invoice.has_emited_iva_retention)

    def test_iva_supplier_100_percent_all_fields(self):
        invoice = self._create_invoice_reten_iva(
            amount=1000.0, partner=self.partner_pnr_100,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self._assert_invoice_taxes(invoice, expect_taxes=True)
        invoice.generate_iva_retention = True
        invoice.with_context(move_action_post_alert=True).action_post()

        ret = invoice.retention_iva_line_ids[0].retention_id
        line = invoice.retention_iva_line_ids[0]
        pay = ret.payment_ids[0]

        self.assertEqual(ret.total_invoice_amount, 1000.0)
        self.assertEqual(ret.total_iva_amount, 160.0)
        self.assertEqual(ret.total_retention_amount, 160.0,
                         "100% withholding must retain full IVA")
        self.assertEqual(line.related_percentage_tax_base, 100.0)
        self.assertEqual(line.retention_amount, 160.0)
        self.assertEqual(line.iva_amount, 160.0)
        self.assertEqual(line.invoice_amount, 1000.0)
        self.assertAlmostEqual(pay.amount, 160.0, places=2)
        self.assertEqual(pay.state, "paid")
        self.assertEqual(ret.state, "emitted")
        self.assertTrue(invoice.iva_voucher_number)
        self.assertEqual(invoice.count_iva_retention, 1)
        self.assertTrue(invoice.has_emited_iva_retention)

    def test_iva_supplier_cancel_all_fields(self):
        invoice = self._create_invoice_reten_iva(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self._assert_invoice_taxes(invoice, expect_taxes=True)
        invoice.generate_iva_retention = True
        invoice.with_context(move_action_post_alert=True).action_post()

        ret = invoice.retention_iva_line_ids[0].retention_id
        line = invoice.retention_iva_line_ids[0]
        pay = ret.payment_ids[0]

        ret.action_cancel()
        line.invalidate_recordset()
        ret.invalidate_recordset()

        # retention
        self.assertEqual(ret.state, "cancel")
        self.assertFalse(ret.payment_ids)
        self.assertTrue(ret.number, "Number must be preserved after cancel")

        # line-domain hide cancelled, so retention_iva_line_ids is empty
        self.assertFalse(invoice.retention_iva_line_ids)
        # but the line record still exists
        self.assertEqual(line.state, "cancel")
        self.assertFalse(line.payment_id, "Payment link must be cleared on line")

        # payment
        self.assertEqual(pay.state, "canceled")
        self.assertFalse(pay.retention_id)
        self.assertFalse(pay.is_retention)
        self.assertFalse(pay.payment_type_retention)
        self.assertFalse(pay.retention_ref)

        # invoice
        self.assertFalse(invoice.iva_voucher_number)
        self.assertEqual(invoice.count_iva_retention, 0)
        self.assertFalse(invoice.has_emited_iva_retention)

    def test_iva_customer_all_fields_draft(self):
        invoice = self._create_invoice_reten_iva(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="out_invoice", journal=self.sale_journal,
        )
        self._assert_invoice_taxes(invoice, expect_taxes=True)
        invoice.generate_iva_retention = True
        invoice.with_context(move_action_post_alert=True).action_post()

        ret = invoice.retention_iva_line_ids[0].retention_id
        line = invoice.retention_iva_line_ids[0]

        # retention (draft)
        self.assertEqual(ret.type_retention, "iva")
        self.assertEqual(ret.type, "out_invoice")
        self.assertEqual(ret.partner_id, invoice.partner_id)
        self.assertEqual(ret.state, "draft",
                         "Customer retention must stay in draft on creation")
        self.assertTrue(ret.number, "Customer retention gets auto-number in draft")
        self.assertEqual(ret.company_currency_id, self.currency_vef)
        self.assertEqual(ret.foreign_currency_id, self.currency_usd)
        self.assertEqual(ret.total_invoice_amount, 1000.0)
        self.assertEqual(ret.total_iva_amount, 160.0)
        self.assertEqual(ret.total_retention_amount, 0.0)
        self.assertAlmostEqual(ret.foreign_total_invoice_amount, 1000.0 / self.rate, places=2)
        self.assertAlmostEqual(ret.foreign_total_iva_amount, 160.0 / self.rate, places=2)
        self.assertFalse(ret.payment_ids)
        self.assertTrue(ret.retention_line_ids)

        # line (draft, retention_amount=0)
        self.assertEqual(line.move_id, invoice)
        self.assertEqual(line.retention_id, ret)
        self.assertEqual(line.invoice_amount, 1000.0)
        self.assertEqual(line.iva_amount, 160.0)
        self.assertEqual(line.invoice_total, 1160.0)
        self.assertEqual(line.retention_amount, 0.0,
                         "Customer retention line must have 0 amount in draft")
        self.assertEqual(line.aliquot, 16.0)
        self.assertEqual(line.related_percentage_tax_base, 75.0)
        self.assertEqual(line.state, "draft")
        self.assertEqual(line.name, "Iva Retention")
        self.assertEqual(line.invoice_type, "out_invoice")
        self.assertFalse(line.payment_id, "Line must not be linked to a payment in draft")
        self.assertAlmostEqual(line.foreign_invoice_amount, 1000.0 / self.rate, places=2)
        self.assertAlmostEqual(line.foreign_iva_amount, 160.0 / self.rate, places=2)

        # invoice
        self.assertTrue(invoice.iva_voucher_number,
                        "Customer invoice gets voucher number even on draft retention")
        self.assertEqual(invoice.count_iva_retention, 1)
        self.assertFalse(invoice.has_emited_iva_retention)

    def test_iva_customer_post_and_cancel_all_fields(self):
        invoice = self._create_invoice_reten_iva(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="out_invoice", journal=self.sale_journal,
        )
        self._assert_invoice_taxes(invoice, expect_taxes=True)
        invoice.generate_iva_retention = True
        invoice.with_context(move_action_post_alert=True).action_post()

        ret = invoice.retention_iva_line_ids[0].retention_id
        

        # Check draft state
        self.assertEqual(ret.state, "draft")
        self.assertEqual(ret.total_retention_amount, 0.0,
                         "Customer retention amount must be 0 in draft")
        self.assertTrue(ret.number, "Customer retention has number in draft")
        self.assertTrue(invoice.iva_voucher_number,
                        "Invoice gets voucher number from draft retention")

        # Posting a customer retention with 0 amount fails at reconciliation
        ret.number = "12345678901234"
        with self.assertRaises(ValidationError) as cm:
            ret.action_post()
        self.assertIn("No registered lines found in the move to reconcile",
                      str(cm.exception))

        # State unchanged (still draft after failed post)
        self.assertEqual(ret.state, "draft")

        # ── Cancel draft retention ──
        ret.action_cancel()
        ret.invalidate_recordset()
        self.assertEqual(ret.state, "cancel")
        self.assertFalse(ret.payment_ids)
        self.assertFalse(invoice.iva_voucher_number)
        self.assertEqual(invoice.count_iva_retention, 0)
        self.assertFalse(invoice.has_emited_iva_retention)