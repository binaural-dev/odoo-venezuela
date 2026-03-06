import logging
from odoo.tests import tagged , Form
from odoo.exceptions import UserError, ValidationError
from odoo import Command, fields

from .test_igtf_common_partner_formal_VEF import IGTFTestCommon 

_logger = logging.getLogger(__name__)

# Tasa de conversión: 1$ = 201.47bs
# docker exec -u odoo -it proj2 odoo --test-tags igtf -i binaural_advance_payment_igtf --without-demo=True --stop-after-init -d testneuvo5

@tagged("igtf_test", "igtf_run", "-at_install", "post_install")
class TestIGTFNEW(IGTFTestCommon): 
    
    def _assert_move_lines_equal(self, move, expected_lines):
        """
        Valida que el asiento contable tenga el número de líneas esperado y que
        los valores de Débito, Crédito y Cuenta coincidan para cada línea.
        """
        debug_info = "\n".join([
            f"Cuenta: {l.account_id.code} | Debe: {l.debit} | Haber: {l.credit}" 
            for l in move.line_ids
        ])

        self.assertEqual(
            len(move.line_ids), 
            len(expected_lines), 
            f"El asiento debe tener {len(expected_lines)} líneas, pero tiene {len(move.line_ids)}.\n"
            f"Detalle encontrado:\n{debug_info}"
        )

        for expected_line in expected_lines:
            expected_account = expected_line['account']
            expected_debit = expected_line.get('debit', False)
            expected_credit = expected_line.get('credit', False)

            expected_foreign_debit = expected_line.get('foreign_debit', False)
            expected_foreign_credit = expected_line.get('foreign_credit', False)

            expected_amount_currency = expected_line.get('amount_currency', False)
            found_line = move.line_ids.filtered(lambda l: l.account_id.id == expected_account.id)
            
            
            if not found_line:
                _logger.error(
                    f"FALLA DE LÍNEA: Cuenta esperada NO encontrada: "
                    f"'{expected_account.name}' - '{expected_account.name}'. "
                    f"Líneas reales en el asiento: {[(l.account_id.name, l.account_id.name, l.debit, l.credit) for l in move.line_ids]}"
                )
            else:
                _logger.info(
                    f"LÍNEA ENCONTRADA: Cuenta '{found_line.account_id.name}' - '{found_line.account_id.name}'. "
                    f"Débito Real: {found_line.debit}, Crédito Real: {found_line.credit}"
                    f"Débito Real Alterno: {found_line.foreign_debit}, Crédito Real Alterno: {found_line.foreign_credit}"
                )
            
            
            self.assertTrue(found_line, 
                f"Línea contable para la cuenta '{expected_account.name}' ({expected_account.name}) no encontrada.")
            
            if expected_debit and not expected_foreign_debit:
                self.assertAlmostEqual(found_line.debit, expected_debit, 2, 
                    f"Débito de la cuenta '{expected_account.name}' incorrecto. Esperado: {expected_debit}, Real: {found_line.debit}")
                
            if expected_credit and not expected_foreign_credit:
                self.assertAlmostEqual(found_line.credit, expected_credit, 2, 
                    f"Crédito de la cuenta '{expected_account.name}' incorrecto. Esperado: {expected_credit}, Real: {found_line.credit}")

            """  if expected_foreign_debit == 0.0 and expected_foreign_credit == 0.0:
                continue   """
            
            if expected_foreign_debit and not expected_debit:
                self.assertAlmostEqual(found_line.foreign_debit, expected_foreign_debit, 2, 
                    f"Débito foraneo de la cuenta '{expected_account.name}' incorrecto. Esperado: {expected_foreign_debit}, Real: {found_line.foreign_debit}")
                
            if expected_foreign_credit and not expected_credit: 
                self.assertAlmostEqual(found_line.foreign_credit, expected_foreign_credit, 2, 
                    f"Crédito foraneo de la cuenta '{expected_account.name}' incorrecto. Esperado: {expected_foreign_credit}, Real: {found_line.foreign_credit}")

            if expected_amount_currency:
                self.assertAlmostEqual(found_line.amount_currency, expected_amount_currency, 2, 
                    f"Crédito de la cuenta '{expected_account.name}' incorrecto. Esperado: {expected_amount_currency}, Real: {found_line.amount_currency}")
        
        total_debit = sum(line.debit for line in move.line_ids)
        total_credit = sum(line.credit for line in move.line_ids)

        self.assertAlmostEqual(total_debit, total_credit, 2, 
            "El asiento no balancea (Débito != Crédito).")
        
        _logger.info("Validación detallada de líneas contables: OK.")

   
    def test01_payment_from_invoice_with_igtf_journal(self):

        invoice_amount = 1000.00
        payment_amount = 600.00

        invoice = self._create_invoice_usd(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.save()
            pay_form.amount = payment_amount
            pay_form.save()

        payment = pay_form.record
        action = payment.action_create_payments()

        payment = self.env['account.payment'].browse(action.get('res_id'))
       
        
        self.assert_payment_values(payment, 600.00 ,18 ,'paid',self.acc_igtf_cli)

        expected_lines = [
            {'account': self.account_bank_usd, 'amount_currency': 600.00},
            {'account': self.acc_receivable, 'amount_currency': -582.00},
            {'account': self.acc_igtf_cli, 'amount_currency': -18.00 },
        ]
        self._assert_move_lines_equal(payment.move_id, expected_lines)

    
    def test02_payment_from_invoice_with_igtf_journal(self):

        invoice_amount = 1000.00
        payment_amount = 600.00

        invoice = self._create_invoice_usd(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.subtract(fields.Date.today(), days=1)

            pay_form.save()
            pay_form.amount = payment_amount
            pay_form.save()

        payment = pay_form.record
        action = payment.action_create_payments()

        payment = self.env['account.payment'].browse(action.get('res_id'))
      
        invoice = self.env['account.move'].browse(invoice.id)
        self.assert_invoice_values(invoice, 234176.67, 418.0, 'partial')
        cross_move_advance = self.env['account.move'].search([], order='id desc', limit=1)
        
        
        expected_lines = [
            {'account': self.account_bank_usd, 'debit': 228000.00, 'credit': 0.0},
            {'account': self.acc_receivable, 'debit': 0.0, 'credit': 221160.00},
            {'account': self.acc_igtf_cli, 'debit': 0.0, 'credit': 6840.00 },
        ]
        self._assert_move_lines_equal(cross_move_advance, expected_lines)


    def test03_payment_from_invoice_with_igtf_journal(self):

        invoice_amount = 1000.00
        payment_amount = 600.00

        invoice = self._create_invoice_usd(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
        context = {'default_payment_type': 'inbound', 'default_partner_type': 'customer', 'search_default_inbound_filter': 1, 'default_move_journal_types': ('bank', 'cash'), 'display_account_trust': True, 'default_is_advance_payment': True}
        with Form(self.env['account.payment'] .with_context(
               context
            )) as pay_form:
            pay_form.partner_id = self.partner
            pay_form.journal_id = self.bank_journal_usd
            #pay_form.date = fields.Date.subtract(fields.Date.today(), days=1)
            pay_form.amount = payment_amount
            
        payment =pay_form.save()
        payment.action_post()

        outstanding_line = payment.move_id.line_ids.filtered(
            lambda l: l.account_id == self.advance_cust_acc and l.credit > 0
        )

        invoice = self.env['account.move'].browse(invoice.id)
        invoice.with_context({}).js_assign_outstanding_line(outstanding_line.id)
        invoice = self.env['account.move'].browse(invoice.id)
        #self.assert_invoice_values(invoice, 228000.00, 163143.06, 'partial')
        cross_move_advance = self.env['account.move'].search([], order='id desc', limit=1)
        
        
        expected_lines = [
            {'account': self.advance_cust_acc, 'debit': 234176.64, 'credit': 0.0},
            {'account': self.acc_receivable, 'debit': 0.0, 'credit': 227151.34},
            {'account': self.acc_igtf_cli, 'debit': 0.0, 'credit': 7025.30 },
        ]
        self._assert_move_lines_equal(cross_move_advance, expected_lines)

    
    def test04_payment_from_invoice_with_igtf_journal(self):

        invoice_amount = 1000.00
        payment_amount = 500.00

        invoice = self._create_invoice_usd(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_eur
            pay_form.payment_date = fields.Date.today()

            pay_form.save()
            pay_form.amount = payment_amount
            pay_form.save()

        payment = pay_form.record
        action = payment.action_create_payments()

        payment = self.env['account.payment'].browse(action.get('res_id'))
        invoice = self.env['account.move'].browse(invoice.id)
        
        cross_move_advance = self.env['account.move'].search([], order='id desc', limit=1)
        
        expected_lines = [
            {'account': self.account_bank_eur, 'debit': 236415.00, 'credit': 0.0},
            {'account': self.acc_receivable, 'debit': 0.0, 'credit': 229322.55 },
            {'account': self.acc_igtf_cli, 'debit': 0.0, 'credit': 7092.45 },
        ]
        self._assert_move_lines_equal(cross_move_advance, expected_lines)
        self.assert_invoice_values(invoice, 236415.00, 412.44, 'partial')

    def test05_payment_from_invoice_with_igtf_journal(self):

        invoice_amount = 1000.00
        payment_amount = 1200.00

        invoice = self._create_invoice_eur(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()

            pay_form.save()
            pay_form.amount = payment_amount
            pay_form.save()

        payment = pay_form.record
        action = payment.action_create_payments()

        payment = self.env['account.payment'].browse(action.get('res_id'))
        invoice = self.env['account.move'].browse(invoice.id)
        
        cross_move_advance = self.env['account.move'].search([], order='id desc', limit=1)
        
        expected_lines = [
            {'account': self.account_bank_usd, 'debit': 468353.28, 'credit': 0.0},
            {'account': self.acc_receivable, 'debit': 0.0, 'credit': 454302.68 },
            {'account': self.acc_igtf_cli, 'debit': 0.0, 'credit': 14050.60 },
        ]
        self._assert_move_lines_equal(cross_move_advance, expected_lines)
        self.assert_invoice_values(invoice, 468353.28, 39.18, 'partial')

    def test06_payment_from_invoice_with_igtf_journal(self):

        invoice_amount = 500000.00
        payment_amount = 1000.00

        invoice = self._create_invoice_vef(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_eur
            pay_form.payment_date = fields.Date.today()

            pay_form.save()
            pay_form.amount = payment_amount
            pay_form.save()

        payment = pay_form.record
        action = payment.action_create_payments()

        payment = self.env['account.payment'].browse(action.get('res_id'))
        invoice = self.env['account.move'].browse(invoice.id)
        
        cross_move_advance = self.env['account.move'].search([], order='id desc', limit=1)
        
        expected_lines = [
            {'account': self.account_bank_eur, 'debit': 472830.00, 'credit': 0.0},
            {'account': self.acc_receivable, 'debit': 0.0, 'credit': 458645.1 },
            {'account': self.acc_igtf_cli, 'debit': 0.0, 'credit': 14184.90 },
        ]
        self._assert_move_lines_equal(cross_move_advance, expected_lines)
        self.assert_invoice_values(invoice, 472830.00, 41354.9, 'partial')

    
    def test07_payment_from_invoice_with_igtf_journal(self):

        invoice_amount = 500000.00
        payment_amount = 1000.00

        invoice = self._create_invoice_vef(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()

            pay_form.save()
            pay_form.amount = payment_amount
            pay_form.save()

        payment = pay_form.record
        action = payment.action_create_payments()

        payment = self.env['account.payment'].browse(action.get('res_id'))
        invoice = self.env['account.move'].browse(invoice.id)
        
        cross_move_advance = self.env['account.move'].search([], order='id desc', limit=1)
        
        expected_lines = [
            {'account': self.account_bank_usd, 'debit': 390294.40, 'credit': 0.0},
            {'account': self.acc_receivable, 'debit': 0.0, 'credit': 378585.57 },
            {'account': self.acc_igtf_cli, 'debit': 0.0, 'credit': 11708.83 },
        ]
        self._assert_move_lines_equal(cross_move_advance, expected_lines)
        self.assert_invoice_values(invoice, 390294.40, 121414.43, 'partial')

    
    def test08_payment_from_invoice_with_igtf_journal(self):

        invoice_amount = 1000.00
        payment_amount = 1500.00
        invoice_amount2 = 400.00

        invoice = self._create_invoice_usd(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()

            pay_form.save()
            pay_form.amount = payment_amount
            pay_form.save()

        payment = pay_form.record
        action = payment.action_create_payments()

        
        
        payment = self.env['account.payment'].browse(action.get('res_id'))

        rate = payment.move_id.expected_currency_rate

        self.assert_invoice_values(invoice, 390294.33, 0.0, 'paid')

        advance = len(payment.advanced_move_ids)
        self.assertAlmostEqual(advance, 1, 2, "Debe existir asiento de residual")
        
        residual_advance = self.env['account.move'].search([], order='id desc', limit=1)
        outstanding_line = residual_advance.line_ids.filtered(
            lambda l: l.account_id == self.advance_cust_acc and l.credit > 0
        )

        invoice = self.env['account.move'].browse(invoice.id)
        
        rate = payment.move_id.expected_currency_rate
        expected_lines = [
            {'account': self.account_bank_usd, 'debit': 1500.00 / rate, 'credit': 0.0},
            {'account': self.acc_receivable, 'debit': 0.0, 'credit': 1470.00 / rate},
            {'account': self.acc_igtf_cli, 'debit': 0.0, 'credit': 30.00 / rate },
        ]
        self._assert_move_lines_equal(payment.move_id, expected_lines)
        

        expected_lines = [
            {'account': self.advance_cust_acc, 'amount_currency': -470},
            {'account': self.acc_receivable,  'amount_currency': 470 },
            
        ]
        self._assert_move_lines_equal(residual_advance, expected_lines)

        invoice_2 = self._create_invoice_usd(invoice_amount2)
        invoice_2.with_context(move_action_post_alert=True).action_post()
        invoice_2.with_context({}).js_assign_outstanding_line(outstanding_line.id)

       
        cross_move_advance = self.env['account.move'].search([], order='id desc', limit=1)
        
        expected_lines = [
            {'account': self.advance_cust_acc, 'amount_currency': 412.00},
            {'account': self.acc_receivable, 'amount_currency': -400.00},
            {'account': self.acc_igtf_cli, 'amount_currency': -12.00 },
        ]
        self._assert_move_lines_equal(cross_move_advance, expected_lines)

        self.assert_invoice_values(invoice_2, 156117.67, 0.0, 'paid')

    def test08_payment_from_invoice_with_igtf_journal(self):

        invoice_amount = 1000.00
        payment_amount = 1500.00
        invoice_amount2 = 400.00
        invoice_amount3 = 300.00

        invoice = self._create_invoice_usd(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()

            pay_form.save()
            pay_form.amount = payment_amount
            pay_form.save()

        payment = pay_form.record
        action = payment.action_create_payments()

        
        
        payment = self.env['account.payment'].browse(action.get('res_id'))

        rate = payment.move_id.expected_currency_rate

        self.assert_invoice_values(invoice, 390294.33, 0.0, 'paid')

        advance = len(payment.advanced_move_ids)
        self.assertAlmostEqual(advance, 1, 2, "Debe existir asiento de residual")
        
        residual_advance = self.env['account.move'].search([], order='id desc', limit=1)
        outstanding_line = residual_advance.line_ids.filtered(
            lambda l: l.account_id == self.advance_cust_acc and l.credit > 0
        )

        invoice = self.env['account.move'].browse(invoice.id)
        
        rate = payment.move_id.expected_currency_rate
        expected_lines = [
            {'account': self.account_bank_usd, 'debit': 1500.00 / rate, 'credit': 0.0},
            {'account': self.acc_receivable, 'debit': 0.0, 'credit': 1470.00 / rate},
            {'account': self.acc_igtf_cli, 'debit': 0.0, 'credit': 30.00 / rate },
        ]
        self._assert_move_lines_equal(payment.move_id, expected_lines)
        

        expected_lines = [
            {'account': self.advance_cust_acc, 'amount_currency': -470},
            {'account': self.acc_receivable,  'amount_currency': 470 },
            
        ]
        self._assert_move_lines_equal(residual_advance, expected_lines)

        invoice_2 = self._create_invoice_usd(invoice_amount2)
        invoice_2.with_context(move_action_post_alert=True).action_post()
        invoice_2.with_context({}).js_assign_outstanding_line(outstanding_line.id)

       
        cross_move_advance = self.env['account.move'].search([], order='id desc', limit=1)
        
        expected_lines = [
            {'account': self.advance_cust_acc, 'amount_currency': 412.00},
            {'account': self.acc_receivable, 'amount_currency': -400.00},
            {'account': self.acc_igtf_cli, 'amount_currency': -12.00 },
        ]
        self._assert_move_lines_equal(cross_move_advance, expected_lines)

        self.assert_invoice_values(invoice_2, 156117.67, 0.0, 'paid')

        invoice_3 = self._create_invoice_usd(invoice_amount3)

        invoice_3.with_context(move_action_post_alert=True).action_post()
        
        with Form.from_action(self.env, invoice_3.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_bs
            pay_form.payment_date = fields.Date.today()
            pay_form.save()

        payment = pay_form.record
        action = payment.action_create_payments()
        payment = self.env['account.payment'].browse(action.get('res_id'))

        self.assert_invoice_values(invoice_3, 0.0, 0.0, 'paid')

    def test09_payment_from_invoice_with_igtf_journal(self):

        invoice_amount = 1500.00
        payment_amount = 1000.00

        invoice = self._create_invoice_eur(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_eur
            pay_form.payment_date = fields.Date.today()

            pay_form.save()
            pay_form.amount = payment_amount
            pay_form.save()

        payment = pay_form.record
        action = payment.action_create_payments()

        
        
        payment = self.env['account.payment'].browse(action.get('res_id'))

        self.assert_invoice_values(invoice, 472831.33, 530.0, 'partial')

        expected_lines = [
            {'account': self.account_bank_eur, 'amount_currency': 1000.00},
            {'account': self.acc_receivable, 'amount_currency': -970.00},
            {'account': self.acc_igtf_cli, 'amount_currency': -30.00 },
        ]
        self._assert_move_lines_equal(payment.move_id, expected_lines)

        invoice.with_context(move_action_post_alert=True).action_post()
        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_bs
            pay_form.payment_date = fields.Date.today()

            pay_form.save()
            pay_form.amount = 200000.00
            pay_form.save()

        payment = pay_form.record
        action = payment.action_create_payments()
        
        payment = self.env['account.payment'].browse(action.get('res_id'))

        expected_lines = [
            {'account': self.account_bank_vef, 'amount_currency': 200000.00},
            {'account': self.acc_receivable, 'amount_currency': -200000.00},
        ]
        self._assert_move_lines_equal(payment.move_id, expected_lines)

        self.assert_invoice_values(invoice, 472831.33, 107.02, 'partial')


    def test09_payment_from_invoice_with_igtf_journal(self):

        invoice_amount = 1500.00
        payment_amount = 1000.00
        payment_amount2 = 200000.00

        invoice = self._create_invoice_eur(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_eur
            pay_form.payment_date = fields.Date.today()

            pay_form.save()
            pay_form.amount = payment_amount
            pay_form.save()

        payment = pay_form.record
        action = payment.action_create_payments()

        
        
        payment = self.env['account.payment'].browse(action.get('res_id'))

        self.assert_invoice_values(invoice, 472831.33, 530.0, 'partial')

        expected_lines = [
            {'account': self.account_bank_eur, 'amount_currency': 1000.00},
            {'account': self.acc_receivable, 'amount_currency': -970.00},
            {'account': self.acc_igtf_cli, 'amount_currency': -30.00 },
        ]
        self._assert_move_lines_equal(payment.move_id, expected_lines)

        invoice.with_context(move_action_post_alert=True).action_post()
        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_bs
            pay_form.payment_date = fields.Date.today()

            pay_form.save()
            pay_form.amount = payment_amount2
            pay_form.save()

        payment = pay_form.record
        action = payment.action_create_payments()
        
        payment = self.env['account.payment'].browse(action.get('res_id'))

        expected_lines = [
            {'account': self.account_bank_vef, 'amount_currency': payment_amount2},
            {'account': self.acc_receivable, 'amount_currency': -payment_amount2},
        ]
        self._assert_move_lines_equal(payment.move_id, expected_lines)

        self.assert_invoice_values(invoice, 472831.33, 107.02, 'partial')
       

    
    def test10_payment_from_invoice_with_igtf_journal(self):

        invoice_amount = 500000.00
        payment_amount = 2000.00
        invoice_amount2 = 800.00

        invoice = self._create_invoice_vef(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()

            pay_form.save()
            pay_form.amount = payment_amount
            pay_form.save()

        payment = pay_form.record
        action = payment.action_create_payments()
        
        payment = self.env['account.payment'].browse(action.get('res_id'))

        self.assertTrue(payment, "Debe existir el pago restante como anticipo")

        self.assert_invoice_values(invoice, 499967.0, 0.0, 'paid')
        self.assert_payment_values(payment, 2000.00, 38.43, False, self.acc_igtf_cli)
        expected_lines = [
            {'account': self.account_bank_usd, 'amount_currency': 2000},
            {'account': self.acc_receivable, 'amount_currency': -1961.57},
            {'account': self.acc_igtf_cli, 'amount_currency': -38.43 },
        ]
        self._assert_move_lines_equal(payment.move_id, expected_lines)

        invoice2 = self._create_invoice_eur(invoice_amount2)
        invoice2.with_context(move_action_post_alert=True).action_post()

        advance = len(payment.advanced_move_ids)
        self.assertAlmostEqual(advance, 1, 2, "Debe existir asiento de residual")

        residual_advance = payment.advanced_move_ids[0]

        expected_lines = [
            {'account': self.advance_cust_acc, 'amount_currency': -680.49},
            {'account': self.acc_receivable, 'amount_currency': 680.49},
        ]
        self._assert_move_lines_equal(residual_advance, expected_lines)


        outstanding_line = residual_advance.line_ids.filtered(
            lambda l: l.account_id == self.advance_cust_acc and l.credit > 0
        )

        invoice2.with_context({}).js_assign_outstanding_line(outstanding_line.id)

        cross_move = self.env['account.move'].search([], order='id desc', limit=1)

        expected_lines = [
            {'account': self.advance_cust_acc, 'amount_currency': 680.49},
            {'account': self.acc_receivable, 'amount_currency': -660.08},
            {'account': self.acc_igtf_cli, 'amount_currency': -20.41 },
        ]
        self._assert_move_lines_equal(cross_move, expected_lines)

        self.assert_invoice_values(invoice2, 265591.33,  255.15, 'partial')
        


    def test11_payment_from_invoice_with_igtf_journal(self):

        invoice_amount = 1000.00
        payment_amount = 600.00

        invoice = self._create_invoice_usd(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
        context = {'default_payment_type': 'inbound', 'default_partner_type': 'customer', 'search_default_inbound_filter': 1, 'default_move_journal_types': ('bank', 'cash'), 'display_account_trust': True, 'default_is_advance_payment': True}
        with Form(self.env['account.payment'] .with_context(
               context
            )) as pay_form:
            pay_form.partner_id = self.partner
            pay_form.journal_id = self.bank_journal_usd
            #pay_form.date = fields.Date.subtract(fields.Date.today(), days=1)
            pay_form.amount = payment_amount
            
        payment =pay_form.save()
        payment.action_post()

        outstanding_line = payment.move_id.line_ids.filtered(
            lambda l: l.account_id == self.advance_cust_acc and l.credit > 0
        )

        invoice = self.env['account.move'].browse(invoice.id)
        invoice.with_context({}).js_assign_outstanding_line(outstanding_line.id)
        invoice = self.env['account.move'].browse(invoice.id)
        cross_move_advance = self.env['account.move'].search([], order='id desc', limit=1)
        
        
        expected_lines = [
            {'account': self.advance_cust_acc, 'debit': 234176.64, 'credit': 0.0},
            {'account': self.acc_receivable, 'debit': 0.0, 'credit': 227151.34},
            {'account': self.acc_igtf_cli, 'debit': 0.0, 'credit': 7025.30 },
        ]
        self._assert_move_lines_equal(cross_move_advance, expected_lines)
        
        invoice_receivable_line = invoice.line_ids.filtered(
            lambda l: l.account_id == self.acc_receivable and l.debit > 0
        )

        partial_reconcile = outstanding_line.matched_debit_ids.filtered(
            lambda p: p.debit_move_id == invoice_receivable_line
        )

        invoice.with_context({}).js_remove_outstanding_partial(partial_reconcile.id)
       

       

    """
    def test04_payment_from_invoice_with_igtf_journal(self):
        _logger.info("Iniciando test: tPago mayor a factura con IGtf (Test 04)")

        # Conversiones adicionales para Test 04:
        # 300.00 * 201.47 = 60441.00
        # 277.77 * 201.47 = 55962.32
        # 8.59 * 201.47 = 1730.63
        # 286.36 * 201.47 = 57692.95

        invoice_amount = 542196.06 #2691.20
        payment_amount = 4036.80 #813294.09
        expected_igtf = 80.736 # 16266.69
        cxc_credit_amount = 3956.0640000000003 #797027.41
        invoice_amount_2 = 950.00
        invoice_amount_3 = 300.00
        residual = 1264.864

        invoice = self._create_invoice_vef(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
        inverse_rate = invoice.expected_currency_rate

        action_data = invoice.action_register_payment()
        with Form(
            self.env['account.payment.register'].with_context(
               action_data['context']  
            )
        ) as pay_form:
            
            pay_form.journal_id = self.bank_journal_usd
            pay_form.currency_id = self.currency_usd
            pay_form.payment_date = fields.Date.today()
            
            
            pay_form.amount = payment_amount

        payment = pay_form.record
        action = payment.action_create_payments()


        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 

        self.assertAlmostEqual(payment.igtf_amount, expected_igtf, 2, "El IGTF calculado debe ser $80.74.")
        self.assertTrue(payment_move, "Debe haberse creado el asiento de pago asociado al payment.")
        self.assertAlmostEqual(invoice.payment_state, 'paid',"Debe estar pagado")
     
        expected_lines_p1 = [
            {
                'account': self.account_bank,      
                'debit': payment_amount / inverse_rate,       
                'credit': 0.0,
            },
           
            {
                'account': self.acc_receivable,
                'debit': 0.0,
                'credit': cxc_credit_amount / inverse_rate,   
            },
             {
                'account': self.acc_igtf_cli,  
                'debit': 0.0,
                'credit': expected_igtf / inverse_rate,       
            },
        ] 

        self._assert_move_lines_equal(payment.move_id, expected_lines_p1)

        # Factura 2 y cruce
        invoice_2 = self._create_invoice_vef(invoice_amount_2 / inverse_rate )
        invoice_2.with_context(move_action_post_alert=True).action_post()

        advance_widget = getattr(invoice_2, 'invoice_outstanding_credits_debits_widget_advance_payment', {})
        widget_content = advance_widget.get('content') or []
        advance_residual = widget_content[0]

        self.assertTrue(advance_residual, "Debe existir el pago restante como anticipo")
        last_record_move_id = advance_residual.get('move_id', False) 

        residual_advance = self.env['account.move'].browse(last_record_move_id)

        expected_lines = [
            {
                'account': self.acc_receivable,      
                'debit': residual/ inverse_rate,      
                'credit': 0.0
            },
           
            {
                'account': self.advance_cust_acc,
                'debit': 0.0,
                'credit': residual / inverse_rate,
            },
             
        ]

        self._assert_move_lines_equal(residual_advance, expected_lines)

        outstanding_line = residual_advance.line_ids.filtered(
            lambda l: l.account_id == self.acc_receivable and l.debit > 0
        )


        self.assertAlmostEqual(invoice_2.foreign_amount_residual, invoice_amount_2, 2, "Monto Alterno rEsidual Incorrecto")
        invoice_2.with_context({}).js_assign_outstanding_line(outstanding_line.id)

        cross_move_advance = self.env['account.move'].search([], order='id desc', limit=1)

        expected_lines = [
           
            {
                'account': self.acc_receivable,
                'debit': 0.0,
                'credit': 950.0 / inverse_rate,   
            },
             {
                'account': self.acc_igtf_cli,  
                'debit': 0.0,
                'credit': 28.5 / inverse_rate,       
            },
            {
                'account': self.advance_cust_acc,      
                'debit':   978.50 / inverse_rate, 
                'credit': 0.0
            },
        ]

        self._assert_move_lines_equal(cross_move_advance, expected_lines)
        invoice_3 = self._create_invoice_vef(invoice_amount_3 / inverse_rate)

        invoice_3.with_context(move_action_post_alert=True).action_post()
        
        invoice_3.with_context({}).js_assign_outstanding_line(outstanding_line.id)
        #CHEQUEAR ASIENTO CRUCE
        cross_move_advance1 = self.env['account.move'].search([], order='id desc', limit=1)

        #validacion Asiento de Cruce
        expected_lines = [
            {
                'account': self.advance_cust_acc,      
                'debit': 286.3640005956 / inverse_rate,       
                'credit': 0.0,
            },
           
            {
                'account': self.acc_receivable,
                'debit': 0.0,
                'credit': 277.773080577732 / inverse_rate,   
            },
             {
                'account': self.acc_igtf_cli,  
                'debit': 0.0,
                'credit': 8.590920017868 / inverse_rate,       
            },
        ]


    def test05_payment_from_invoice_with_igtf_journal(self):
        _logger.info("Iniciando test: tPago mayor a factura con IGtf")

        invoice_amount = 2691.20
        payment_amount = 4036.80
        expected_igtf = 80.74

        cxc_credit_amount= 3956.06

        invoice_amount_2 = 251837.5 #1250

        
        invoice = self._create_invoice_vef(invoice_amount / (1 / self.rate))
        
        invoice.with_context(move_action_post_alert=True).action_post()

        action_data = invoice.action_register_payment()

        with Form(
            self.env['account.payment.register'].with_context(
               action_data['context']  
            )
        ) as pay_form:
            
            pay_form.journal_id = self.bank_journal_usd
            pay_form.currency_id = self.currency_usd
            pay_form.payment_date = fields.Date.today()
            
            
            pay_form.amount = payment_amount
            

        payment = pay_form.record
        
        action = payment.action_create_payments()

        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 
        
        self.assertTrue(payment_move, "Debe haberse creado el asiento de pago asociado al payment.")
        self.assertAlmostEqual(payment.igtf_amount, expected_igtf, 2, "El IGTF calculado debe ser $80.74.")
        expected_lines = [
            {
                'account': self.account_bank,      
                'foreign_debit': payment_amount,       
                'credit': 0.0,
            },
           
            {
                'account': self.acc_receivable,
                'debit': 0.0,
                'foreign_credit': cxc_credit_amount,   
            },
             {
                'account': self.acc_igtf_cli,  
                'debit': 0.0,
                'foreign_credit': expected_igtf,       
            },
        ]
        

        self._assert_move_lines_equal(payment_move, expected_lines)

        #Factura#
        invoice_2 = self._create_invoice_vef(invoice_amount_2)
        
        invoice_2.with_context(move_action_post_alert=True).action_post()

        #CHEQUEAR ASIENTO RESTANTE
        advance_widget_value = getattr(invoice_2, 'invoice_outstanding_credits_debits_widget_advance_payment', False)
        advance_widget = advance_widget_value if isinstance(advance_widget_value, dict) else {} 
        widget_content = advance_widget.get('content') or [] 
        advance_residual = widget_content[0]

        self.assertTrue(advance_residual, "Debe existir el pago restante como anticipo")
        last_record_move_id = advance_residual.get('move_id', False) 

        residual_advance = self.env['account.move'].browse(last_record_move_id)
        expected_lines = [
            {
                'account': self.acc_receivable,      
                'foreign_debit': 1264.86,  
                'foreign_credit': 0.0, 
            },
           
            {
                'account': self.advance_cust_acc,
                'foreign_debit': 0.0,
                'foreign_credit':  1264.86,  
            },
             
        ]

        self._assert_move_lines_equal(residual_advance, expected_lines)

        ##Conciliar Asiento Restante
        outstanding_line = residual_advance.line_ids.filtered(
            lambda l: l.account_id == self.acc_receivable and l.debit > 0
        )
        invoice_2.with_context({}).js_assign_outstanding_line(outstanding_line.id)
        cross_move_advance = self.env['account.move'].search([], order='id desc', limit=1)

        #validacion Asiento de Cruce
        expected_lines = [
            
             {
                'account': self.acc_igtf_cli,  
                'debit': 0.0,
                'credit': 37.5 / invoice_2.foreign_inverse_rate,       
            },
            {
                'account': self.acc_receivable,
                'debit': 0.0,
                'foreign_credit': 1227.364019854 ,   
            },
            {
                'account': self.advance_cust_acc,      
                'foreign_debit': 1264.86,       
                'credit': 0.0,
            },
           
            
        ]

        self._assert_move_lines_equal(cross_move_advance, expected_lines)

    def test06_payment_from_invoice_with_igtf_journal(self):
        _logger.info("Iniciando test: tPago mayor a factura con IGtf")

      

        invoice_amount = 542196.06 
        payment_amount = 4036.80
        expected_igtf = 16265.88

        cxc_credit_amount= 797028.2142

        invoice_amount_2 = 402940.00

        
        invoice = self._create_invoice_vef(invoice_amount)
        
        invoice.with_context(move_action_post_alert=True).action_post()

        action_data = invoice.action_register_payment()

        with Form(
            self.env['account.payment.register'].with_context(
               action_data['context']  
            )
        ) as pay_form:
            
            pay_form.journal_id = self.bank_journal_usd
            pay_form.currency_id = self.currency_usd
            pay_form.payment_date = fields.Date.today()
            
            
            pay_form.amount = payment_amount
            

        payment = pay_form.record
        
        action = payment.action_create_payments()

        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 
        
        
        self.assertTrue(payment_move, "Debe haberse creado el asiento de pago asociado al payment.")
        self.assertAlmostEqual(payment.igtf_amount, 80.74, 2, "El IGTF calculado debe ser $80.74.")
        expected_lines = [
            {
                'account': self.account_bank,      
                'debit': 813294.096,       
                'credit': 0.0,
            },
           
            {
                'account': self.acc_receivable,
                'debit': 0.0,
                'credit': cxc_credit_amount,   
            },
             {
                'account': self.acc_igtf_cli,  
                'debit': 0.0,
                'credit': expected_igtf,       
            },
        ]
        

        self._assert_move_lines_equal(payment_move, expected_lines)

        #Factura#
        invoice_2 = self._create_invoice_vef(invoice_amount_2)
        
        invoice_2.with_context(move_action_post_alert=True).action_post()

        #CHEQUEAR ASIENTO RESTANTE
        advance_widget_value = getattr(invoice_2, 'invoice_outstanding_credits_debits_widget_advance_payment', False)
        advance_widget = advance_widget_value if isinstance(advance_widget_value, dict) else {} 
        widget_content = advance_widget.get('content') or [] 
        advance_residual = widget_content[0]

        self.assertTrue(advance_residual, "Debe existir el pago restante como anticipo")
        last_record_move_id = advance_residual.get('move_id', False) 

        residual_advance = self.env['account.move'].browse(last_record_move_id)
        expected_lines = [
            {
                'account': self.acc_receivable,      
                'debit':  254832.1542, 
                'credit': 0.0  
            },
           
            {
                'account': self.advance_cust_acc,
                'debit':  0.0,
                'credit': 254832.1542, 
            },
             
        ]

        self._assert_move_lines_equal(residual_advance, expected_lines)

        ##Conciliar Asiento Restante
        outstanding_line = residual_advance.line_ids.filtered(
            lambda l: l.account_id == self.acc_receivable and l.debit > 0
        )
        invoice_2.with_context({}).js_assign_outstanding_line(outstanding_line.id)
        cross_move_advance = self.env['account.move'].search([], order='id desc', limit=1)

        #validacion Asiento de Cruce
        expected_lines = [
            {
                'account': self.advance_cust_acc,      
                'debit': 254832.1542,       
                'credit': 0.0,
            },
           
            {
                'account': self.acc_receivable,
                'debit': 0.0,
                'credit': 247187.18957400107,   
            },
             {
                'account': self.acc_igtf_cli,  
                'debit': 0.0,
                'credit': 7644.964626000033,       
            },
        ]

        self._assert_move_lines_equal(cross_move_advance, expected_lines)

    def test07_payment_from_invoice_with_igtf_journal(self):
        
        invoice_amount = float(542196.06)
        payment_amount = float(2000.00)
        expected_igtf = 60
        invoice = self._create_invoice_vef(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
        
        action_data = invoice.action_register_payment()

        with Form(
            self.env['account.payment.register'].with_context(
               action_data['context']  
            )
        ) as pay_form:
            
            pay_form.journal_id = self.bank_journal_usd
            pay_form.currency_id = self.currency_usd
            pay_form.payment_date = fields.Date.today()
            
            
            pay_form.amount = payment_amount

        payment_register_wiz_2 = pay_form.record

        action = payment_register_wiz_2.action_create_payments()
        
        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 
        
        
        self.assertTrue(payment_move, "Debe haberse creado el asiento de pago asociado al payment.")
        self.assertAlmostEqual(payment.igtf_amount, expected_igtf, 2, "El IGTF calculado debe ser $60.00.")

        invoice = self.env['account.move'].browse(invoice.id)

       
        self.assertAlmostEqual(invoice.bi_igtf, 2000.00, 2, "El BI_IGTF calculado debe ser $2000.00.")
 
    def test08_payment_from_invoice_with_igtf_journal(self):
        
        invoice_amount = float(542196.06)
        payment_amount = 2691.20
        expected_igtf = 80.74

        invoice = self._create_invoice_vef(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
        
        action_data = invoice.action_register_payment()

        with Form(
            self.env['account.payment.register'].with_context(
               action_data['context']  
            )
        ) as pay_form:
            
            pay_form.journal_id = self.bank_journal_usd
            pay_form.currency_id = self.currency_usd
            pay_form.payment_date = fields.Date.today()
            
            
            pay_form.amount = payment_amount

        payment_register_wiz_2 = pay_form.record

        action = payment_register_wiz_2.action_create_payments()
        
        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 
        
        
        self.assertTrue(payment_move, "Debe haberse creado el asiento de pago asociado al payment.")
        self.assertAlmostEqual(payment.igtf_amount, expected_igtf, 2, "El IGTF calculado debe ser $60.00.")

        invoice = self.env['account.move'].browse(invoice.id)

        self.assertAlmostEqual(invoice.bi_igtf, 2691.199999999996, 2, "El BI_IGTF calculado debe ser $2691.20.00.")
        
    def test09_payment_from_invoice_with_igtf_journal(self):
        _logger.info("Iniciando test: tPago mayor a factura con IGtf")

        invoice_amount = float(542196.06)
        payment_amount = 2000.00
        expected_igtf = 60.00

        cxc_credit_amount= 390851.8

        advance_amount = 1000.00
        last_advance = 766.828347

        
        invoice = self._create_invoice_vef(invoice_amount)
        
        invoice.with_context(move_action_post_alert=True).action_post()
        action_data = invoice.action_register_payment()

        with Form(
            self.env['account.payment.register'].with_context(
               action_data['context']  
            )
        ) as pay_form:
            
            pay_form.journal_id = self.bank_journal_usd
            pay_form.currency_id = self.currency_usd
            pay_form.payment_date = fields.Date.today()
            
            
            pay_form.amount = payment_amount
            

        payment = pay_form.record
        
        action = payment.action_create_payments()

        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 
        
        
        self.assertTrue(payment_move, "Debe haberse creado el asiento de pago asociado al payment.")
        self.assertAlmostEqual(payment.igtf_amount, expected_igtf, 2, "El IGTF calculado debe ser $60.")
        expected_lines = [
            {
                'account': self.account_bank,      
                'debit': 402940.0,       
                'credit': 0.0,
            },
           
            {
                'account': self.acc_receivable,
                'debit': 0.0,
                'credit': cxc_credit_amount,   
            },
             {
                'account': self.acc_igtf_cli,  
                'debit': 0.0,
                'credit': 12088.2,       
            },
        ]
        

        self._assert_move_lines_equal(payment_move, expected_lines)
        invoice = self.env['account.move'].browse(invoice.id)
        self.assertEqual(invoice.payment_state, 'partial', "Estado incorrecto después del pago 1.")

        #PAgo 2
        action_data_2 = invoice.action_register_payment()
        with Form(
            self.env['account.payment.register'].with_context(
               action_data_2['context']  
            )
        ) as pay_form:
            
            pay_form.journal_id = self.bank_journal_bs
            pay_form.currency_id = self.currency_vef
            pay_form.payment_date = fields.Date.today()
            pay_form.amount = advance_amount
            

        payment_2 = pay_form.record
        
        action = payment_2.action_create_payments()

        payment_2 = self.env['account.payment'].browse(action.get('res_id'))
        payment_mov_2 = payment_2.move_id 

        self.assertTrue(payment_move, "Debe haberse creado el asiento de pago asociado al payment.")
        
        expected_lines = [
            {
                'account': self.acc_receivable,      
                'debit': 0.0,       
                'credit': advance_amount,
            },
           
            {
                'account': self.account_bank,
                'debit': advance_amount,
                'credit': 0.0,   
            },
            
        ]

        self._assert_move_lines_equal(payment_mov_2, expected_lines)
        

        #Anticipo  pago
        context = {'default_payment_type': 'inbound', 'default_partner_type': 'customer', 'search_default_inbound_filter': 1, 'default_move_journal_types': ('bank', 'cash'), 'display_account_trust': True, 'default_is_advance_payment': True}
        with Form(self.env['account.payment'] .with_context(
               context
            )) as pay_form:
            pay_form.partner_id = self.partner
            pay_form.journal_id = self.bank_journal_usd
            pay_form.currency_id = self.currency_usd
            pay_form.date = fields.Date.today()
            pay_form.amount = invoice.foreign_amount_residual
            
        payment =pay_form.save()
        payment.action_post()
        payment = self.env['account.payment'].search([], order='id desc', limit=1)


        payment_move_advance = payment.move_id 
        self.assertAlmostEqual(payment.currency_id.id, self.currency_usd.id, 2, "Moneda debe ser USD")
        self.assertAlmostEqual(payment.amount, 746.2364620043, 2, "Monto debe ser 746.2364620043 usd")
    
        expected_lines = [
        
            {
                'account': self.advance_cust_acc,      
                'debit': 0.0,       
                'credit': 150344.26
            },
           
            {
                'account': self.account_bank,
                'debit': 150344.26,
                'credit': 0.0,   
            },
            
        ]
        
        self._assert_move_lines_equal(payment_move_advance, expected_lines)

        #consiliar segundo pago Anticipo
        
        
        invoice = self.env['account.move'].browse(invoice.id)
        _logger.info(invoice.amount_residual)
      
        outstanding_line = payment_move_advance.line_ids.filtered(
            lambda l: l.account_id == self.advance_cust_acc and l.credit > 0
        )

        invoice.with_context({}).js_assign_outstanding_line(outstanding_line.id) 

        invoice = self.env['account.move'].browse(invoice.id)
        
        self.assertEqual(invoice.payment_state, 'partial', "Estado incorrecto después del ultimo pago")

    def test10_payment_from_invoice_with_igtf_journal(self):
        
        invoice_amount = float(542196.06)
        payment_amount = float(4036.80)
        expected_igtf = 80.736
        invoice = self._create_invoice_vef(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
     
        cxc_credit_amount =  813294.096 - 16265.88 

        action_data = invoice.action_register_payment()
        
        with Form(
            self.env['account.payment.register'].with_context(
               action_data['context']  
            )
        ) as pay_form:
            
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            
            
            pay_form.save()
            pay_form.amount = payment_amount

        payment_register_wiz_2 = pay_form.record

        action = payment_register_wiz_2.action_create_payments()
        
        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 
        
        
        self.assertTrue(payment_move, "Debe haberse creado el asiento de pago asociado al payment.")
        self.assertAlmostEqual(payment.igtf_amount, expected_igtf, 2, "El IGTF calculado debe ser $80.74.")

        expected_lines = [
            {
                'account': self.account_bank,      
                'debit': 813294.096,       
                'credit': 0.0,
            },
           
            {
                'account': self.acc_receivable,
                'debit': 0.0,
                'credit': cxc_credit_amount,   
            },
             {
                'account': self.acc_igtf_cli,  
                'debit': 0.0,
                'credit': 16265.88,       
            },
        ]
        
        self._assert_move_lines_equal(payment_move, expected_lines)
        
        self.assertEqual(
            invoice.payment_state, 
            'paid', 
            f"La factura debe estar en estado 'paid' (pagada), estado actual: {invoice.payment_state}"
        )

        self.assertAlmostEqual(invoice.bi_igtf,2691.20, 2, "Bi_igtf DEbe ser 2691.20 USD")

    def test11_payment_from_invoice_with_igtf_journal(self):
        
        invoice_amount = float(542196.06)
        payment_amount = float(2700.00)
        expected_igtf = 80.736
        invoice = self._create_invoice_vef(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
     
        cxc_credit_amount = 543969.00 - 16265.88 

        action_data = invoice.action_register_payment()
        
        with Form(
            self.env['account.payment.register'].with_context(
               action_data['context']  
            )
        ) as pay_form:
            
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            
            
            pay_form.save()
            pay_form.amount = payment_amount

        payment_register_wiz_2 = pay_form.record

        action = payment_register_wiz_2.action_create_payments()
        
        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 
        
        
        self.assertTrue(payment_move, "Debe haberse creado el asiento de pago asociado al payment.")
        self.assertAlmostEqual(payment.igtf_amount, expected_igtf, 2, "El IGTF calculado debe ser $80.74.")

        expected_lines = [
            {
                'account': self.account_bank,      
                'debit': 543969.00 ,       
                'credit': 0.0,
            },
           
            {
                'account': self.acc_receivable,
                'debit': 0.0,
                'credit': cxc_credit_amount,   
            },
             {
                'account': self.acc_igtf_cli,  
                'debit': 0.0,
                'credit': 16265.88 ,       
            },
        ]
        
        self._assert_move_lines_equal(payment_move, expected_lines)
        
        self.assertEqual(
            invoice.payment_state, 
            'partial', 
            f"La factura debe estar en estado 'partial' (parcialmente pagada), estado actual: {invoice.payment_state}"
        )

        self.assertAlmostEqual(invoice.bi_igtf,2691.20, 2, "Bi_igtf DEbe ser 2691.20 USD")
        self.assertAlmostEqual(invoice.amount_residual,14492.94180, 2, "Residual DEbe ser 14492.94180 (71.939) USD")

    def test12_payment_from_invoice_with_igtf_journal(self):
        
        invoice_amount = float(542196.06)
        payment_amount = float(2771.94)
        expected_igtf = 80.736
        invoice = self._create_invoice_vef(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
     
        cxc_credit_amount = 558461.9418 - 16265.88

        action_data = invoice.action_register_payment()
        
        with Form(
            self.env['account.payment.register'].with_context(
               action_data['context']  
            )
        ) as pay_form:
            
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            
            
            pay_form.save()
            pay_form.amount = payment_amount

        payment_register_wiz_2 = pay_form.record

        action = payment_register_wiz_2.action_create_payments()
        
        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 
        
        
        self.assertTrue(payment_move, "Debe haberse creado el asiento de pago asociado al payment.")
        self.assertAlmostEqual(payment.igtf_amount, expected_igtf, 2, "El IGTF calculado debe ser $80.74.")

        expected_lines = [
            {
                'account': self.account_bank,      
                'debit': 558461.9418,       
                'credit': 0.0,
            },
           
            {
                'account': self.acc_receivable,
                'debit': 0.0,
                'credit': cxc_credit_amount,   
            },
             {
                'account': self.acc_igtf_cli,  
                'debit': 0.0,
                'credit': 16265.88,       
            },
        ]
        
        self._assert_move_lines_equal(payment_move, expected_lines)
        
        self.assertEqual(
            invoice.payment_state, 
            'paid', 
            f"La factura debe estar en estado 'paid' (pagada), estado actual: {invoice.payment_state}"
        )

        self.assertAlmostEqual(invoice.bi_igtf,2691.20, 2, "Bi_igtf DEbe ser 2691.20 USD")
        self.assertAlmostEqual(invoice.amount_residual, 0.0, 2, "Residual DEbe ser 0.0 USD")

    def test12_1_payment_from_invoice_with_igtf_journal(self):
        
        invoice_amount = float(542196.06)
        payment_amount = float(1000.00)
        advance_amount = float(2700.00)

        expected_igtf = 0.00
        invoice = self._create_invoice_vef(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
     
        action_data = invoice.action_register_payment()
        
        with Form(
            self.env['account.payment.register'].with_context(
               action_data['context']  
            )
        ) as pay_form:
            
            pay_form.journal_id = self.bank_journal_bs
            pay_form.payment_date = fields.Date.today()
            
            pay_form.save()
            pay_form.amount = payment_amount

        payment_register_wiz_2 = pay_form.record

        action = payment_register_wiz_2.action_create_payments()
        
        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 
        
        
        self.assertTrue(payment_move, "Debe haberse creado el asiento de pago asociado al payment.")
        self.assertAlmostEqual(payment.igtf_amount, expected_igtf, 2, "El IGTF calculado debe ser $0.0.")

        expected_lines = [
            {
                'account': self.account_bank,      
                'debit': 1000.0,       
                'credit': 0.0,
            },
           
            {
                'account': self.acc_receivable,
                'debit': 0.0,
                'credit': 1000.0,   
            },
          
        ]
        
        self._assert_move_lines_equal(payment_move, expected_lines)
        
        self.assertEqual(
            invoice.payment_state, 
            'partial', 
            f"La factura debe estar en estado 'partial' (parcialmente pagada), estado actual: {invoice.payment_state}"
        )

        self.assertAlmostEqual(invoice.bi_igtf, 0.0, 2, "Bi_igtf DEbe ser 0 USD")
        self.assertAlmostEqual(invoice.amount_residual, (invoice.amount_total - payment_amount), 2, "Residual DEbe ser monto factura - pago USD")

        #Anticipo  pago
        context = {'default_payment_type': 'inbound', 'default_partner_type': 'customer', 'search_default_inbound_filter': 1, 'default_move_journal_types': ('bank', 'cash'), 'display_account_trust': True, 'default_is_advance_payment': True}
        with Form(self.env['account.payment'] .with_context(
               context
            )) as pay_form:
            pay_form.partner_id = self.partner
            pay_form.journal_id = self.bank_journal_usd
            pay_form.currency_id = self.currency_usd
            pay_form.date = fields.Date.today()
            pay_form.amount = advance_amount
            
        payment =pay_form.save()
        payment.action_post()
        payment = self.env['account.payment'].search([], order='id desc', limit=1)

        payment_move_advance = payment.move_id 

        self.assertAlmostEqual(payment.currency_id.id, self.currency_usd.id, 2, "Moneda debe ser USD")
        self.assertAlmostEqual(payment.amount, advance_amount, 2, "Monto debe ser 2700 usd")
    
        expected_lines = [
        
            {
                'account': self.advance_cust_acc,      
                'debit': 0.0,       
                'credit': 543969.0 ,
            },
           
            {
                'account': self.account_bank,
                'debit': 543969.0 ,
                'credit': 0.0,   
            },
            
        ]
        
        self._assert_move_lines_equal(payment_move_advance, expected_lines)

        #consiliar segundo pago Anticipo
        invoice = self.env['account.move'].browse(invoice.id)
      
        outstanding_line = payment_move_advance.line_ids.filtered(
            lambda l: l.account_id == self.advance_cust_acc and l.credit > 0
        )

        invoice.with_context({}).js_assign_outstanding_line(outstanding_line.id)

        cross_move_advance = self.env['account.move'].search([], order='id desc', limit=1)
        igtf_expected = 80.58709445575023
        #validacion Asiento de Cruce
        expected_lines = [
            {
                'account': self.advance_cust_acc,      
                'debit': 543969.0,       
                'credit': 0.0,
            },
           
            
             {
                'account': self.acc_igtf_cli,  
                'debit': 0.0,
                'credit': igtf_expected / invoice.expected_currency_rate,       
            },
            {
                'account': self.acc_receivable,
                'debit': 0.0,
                'credit': (2700.00 - igtf_expected) / invoice.expected_currency_rate,   
            },
        ]

        self._assert_move_lines_equal(cross_move_advance, expected_lines)

    def test13_payment_from_invoice_with_igtf_journal(self):
        
        invoice_amount = float(542196.06)
        advance_amount = float(2691.20)

        invoice = self._create_invoice_vef(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
     

        #Anticipo  pago
        context = {'default_payment_type': 'inbound', 'default_partner_type': 'customer', 'search_default_inbound_filter': 1, 'default_move_journal_types': ('bank', 'cash'), 'display_account_trust': True, 'default_is_advance_payment': True}
        with Form(self.env['account.payment'] .with_context(
               context
            )) as pay_form:
            pay_form.partner_id = self.partner
            pay_form.journal_id = self.bank_journal_usd
            pay_form.currency_id = self.currency_usd
            pay_form.date = fields.Date.today()
            pay_form.amount = advance_amount
            
        payment =pay_form.save()
        payment.action_post()
        payment = self.env['account.payment'].search([], order='id desc', limit=1)

        payment_move_advance = payment.move_id 

        self.assertAlmostEqual(payment.currency_id.id, self.currency_usd.id, 2, "Moneda debe ser USD")
        self.assertAlmostEqual(payment.amount, advance_amount, 2, "Monto debe ser 2691.20 usd")
    
        expected_lines = [
        
            {
                'account': self.advance_cust_acc,      
                'debit': 0.0,       
                'credit': 542196.064,
            },
           
            {
                'account': self.account_bank,
                'debit': 542196.064,
                'credit': 0.0,   
            },
            
        ]
        
        self._assert_move_lines_equal(payment_move_advance, expected_lines)

        #consiliar segundo pago Anticipo
        invoice = self.env['account.move'].browse(invoice.id)
      
        outstanding_line = payment_move_advance.line_ids.filtered(
            lambda l: l.account_id == self.advance_cust_acc and l.credit > 0
        )

        invoice.with_context({}).js_assign_outstanding_line(outstanding_line.id)

        cross_move_advance = self.env['account.move'].search([], order='id desc', limit=1)
        igtf_expected = 16265.8818
        #validacion Asiento de Cruce
        expected_lines = [
            {
                'account': self.advance_cust_acc,      
                'debit': 542196.064,      
                'credit': 0.0,
            },
           
            
             {
                'account': self.acc_igtf_cli,  
                'debit': 0.0,
                'credit': igtf_expected,       
            },
            {
                'account': self.acc_receivable,
                'debit': 0.0,
                'credit': 542196.064 - igtf_expected,   
            },
        ]

        self._assert_move_lines_equal(cross_move_advance, expected_lines)

    def test14_payment_from_invoice_with_igtf_journal(self):
        
        invoice_amount = float(542196.06)
        payment_amount_vef = float(1345.60)  # equivalente a 1345.60 USD
        advance_amount = float(1345.60)

        invoice = self._create_invoice_vef(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
     
        action_data = invoice.action_register_payment()
        
        with Form(
            self.env['account.payment.register'].with_context(
               action_data['context']  
            )
        ) as pay_form:
            
            pay_form.journal_id = self.bank_journal_bs
            pay_form.currency_id = self.currency_vef
            pay_form.payment_date = fields.Date.today()
            
            pay_form.save()
            pay_form.amount = payment_amount_vef / invoice.expected_currency_rate

        payment_register_wiz_2 = pay_form.record

        action = payment_register_wiz_2.action_create_payments()
        
        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 

        self.assertAlmostEqual(payment_move.currency_id.id, self.currency_vef.id, 2, "Moneda debe ser VEF")
        self.assertAlmostEqual(payment_move.origin_payment_id.amount, payment_amount_vef / invoice.expected_currency_rate, 2, "Monto debe ser 270098.032 VEF")
    
        expected_lines = [
        
            {
                'account': self.acc_receivable,      
                'debit': 0.0,       
                'credit': 1345.60 / invoice.expected_currency_rate,
            },
           
            {
                'account': self.account_bank,
                'debit': 1345.60 / invoice.expected_currency_rate,
                'credit': 0.0,   
            },
            
        ]

        self._assert_move_lines_equal(payment_move, expected_lines)

        invoice = self.env['account.move'].browse(invoice.id)

        self.assertAlmostEqual(invoice.bi_igtf, 0.0, 2, "Bi_igtf DEbe ser 0 USD")
        self.assertAlmostEqual(invoice.amount_residual, 271098.03, 2, "Monto residual de la factura debe ser 271098.03 (1345.60) usd")
        
        action_data_2 = invoice.action_register_payment()
        
        with Form(
            self.env['account.payment.register'].with_context(
               action_data_2['context']  
            )
        ) as pay_form:
            
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            
            pay_form.save()
            pay_form.amount = advance_amount

        payment_register_wiz = pay_form.record

        action = payment_register_wiz.action_create_payments()
        
        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 

        self.assertEqual(
            invoice.payment_state, 
            'partial', 
            f"La factura debe estar en estado 'partial' (parcialmente pagada), estado actual: {invoice.payment_state}"
        )

        self.assertAlmostEqual(payment_move.currency_id.id, self.currency_usd.id, 2, "Moneda debe ser USD")
        self.assertAlmostEqual(payment_move.origin_payment_id.amount, advance_amount, 2, "Monto debe ser monto del pago")

        igtf_expected = 8132.9409
        expected_lines = [
            {
                'account': self.account_bank,      
                'debit': advance_amount / invoice.expected_currency_rate ,       
                'credit': 0.0,
            },
           
            
             {
                'account': self.acc_igtf_cli,  
                'debit': 0.0,
                'credit': igtf_expected,       
            },
            {
                'account': self.acc_receivable,
                'debit': 0.0,
                'credit': (advance_amount / invoice.expected_currency_rate) - igtf_expected,   
            },
        ]

        self._assert_move_lines_equal(payment_move, expected_lines)

        self.assertAlmostEqual(invoice.amount_residual, 8132.938840000075 , 2, "Monto residual de la factura debe ser  8132.938840000075(40.369) usd")


        invoice = self.env['account.move'].browse(invoice.id)

        self.assertAlmostEqual(invoice.bi_igtf, 1345.5999801459286, 2, "Bi_igtf DEbe ser 1345.60 USD")
        
        action_data_2 = invoice.action_register_payment()
        
        last_advance = 41.57904

        with Form(
            self.env['account.payment.register'].with_context(
               action_data_2['context']  
            )
        ) as pay_form:
            
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            
            pay_form.save()
            pay_form.amount = last_advance 

        payment_register_wiz = pay_form.record

        action = payment_register_wiz.action_create_payments()
        
        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 

        self.assertAlmostEqual(payment_move.currency_id.id, self.currency_usd.id, 2, "Moneda debe ser USD")
        self.assertAlmostEqual(payment_move.origin_payment_id.amount, last_advance, 2, "Monto debe ser 270098.032 USD")

        expected_lines = [
            {
                'account': self.account_bank,      
                'debit': last_advance / invoice.expected_currency_rate,       
                'credit': 0.0,
            },
           
            {
                'account': self.acc_receivable,
                'debit': 0.0,
                'credit': last_advance / invoice.expected_currency_rate,   
            },
        ]

        

        self._assert_move_lines_equal(payment_move, expected_lines)

        self.assertEqual(
            invoice.payment_state, 
            'paid', 
            f"La factura debe estar en estado 'paid' (pagada), estado actual: {invoice.payment_state}"
        )
    
        self.assertAlmostEqual(invoice.alter_bi_igtf, 40.36799 , 2, "Monto BI_igtf de la factura debe ser 40.36799 usd")
        self.assertAlmostEqual(invoice.igtf_top_aply, 40.36799 , 2, "Igtf Aplicado debe ser 40.36799999 usd")
        self.assertAlmostEqual(invoice.amount_residual,0.0 , 2, "Monto residual de la factura debe ser 0.0 usd")
        self.assertAlmostEqual(invoice.bi_igtf,advance_amount  , 2, "Monto Bi_Igtf de la factura debe ser 1345.60 usd")

    def test15_payment_from_invoice_with_igtf_journal(self):
        
        invoice_amount = float(20147.00)
        payment_amount_vef = float(10.00)  # equivalente a 1345.60 USD
        advance_amount = float(40.00)

        invoice = self._create_invoice_vef(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
        action_data = invoice.action_register_payment()
        
        with Form(
            self.env['account.payment.register'].with_context(
               action_data['context']  
            )
        ) as pay_form:
            
            pay_form.journal_id = self.bank_journal_bs
            pay_form.payment_date = fields.Date.today()
            
            pay_form.save()
            pay_form.amount = payment_amount_vef / invoice.expected_currency_rate
        payment_register_wiz_2 = pay_form.record

        action = payment_register_wiz_2.action_create_payments()
        
        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 

        self.assertAlmostEqual(payment_move.currency_id.id, self.currency_vef.id, 2, "Moneda debe ser VEF")
        self.assertAlmostEqual(payment_move.origin_payment_id.amount, payment_amount_vef / invoice.expected_currency_rate, 2, "Monto Incorrecto en pago")
    
        expected_lines = [
        
            {
                'account': self.acc_receivable,      
                'debit': 0.0,       
                'credit': payment_amount_vef / invoice.expected_currency_rate,
            },
           
            {
                'account': self.account_bank,
                'debit': payment_amount_vef  / invoice.expected_currency_rate,
                'credit': 0.0,   
            },
            
        ]

        self._assert_move_lines_equal(payment_move, expected_lines)

        invoice = self.env['account.move'].browse(invoice.id)

        self.assertAlmostEqual(invoice.bi_igtf, 0.0, 2, "Bi_igtf DEbe ser 0 USD")
        self.assertAlmostEqual(invoice.amount_residual, 18132.3 , 2, "Monto residual de la factura debe ser 18132.3 (90.00) usd")
        
        action_data_2 = invoice.action_register_payment()
        
        with Form(
            self.env['account.payment.register'].with_context(
               action_data_2['context']  
            )
        ) as pay_form:
            
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            
            pay_form.save()
            pay_form.amount = advance_amount

        payment_register_wiz = pay_form.record

        action = payment_register_wiz.action_create_payments()
        
        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 

        self.assertEqual(
            invoice.payment_state, 
            'partial', 
            f"La factura debe estar en estado 'partial' (parcialmente pagada), estado actual: {invoice.payment_state}"
        )

        self.assertAlmostEqual(payment_move.currency_id.id, self.currency_usd.id, 2, "Moneda debe ser USD")
        self.assertAlmostEqual(payment_move.origin_payment_id.amount, advance_amount, 2, "Monto debe ser 40.00 USD")

        igtf_expected = (advance_amount * 0.03) / invoice.expected_currency_rate
        expected_lines = [
            {
                'account': self.account_bank,      
                'debit': advance_amount / invoice.expected_currency_rate,       
                'credit': 0.0,
            },
           
            
             {
                'account': self.acc_igtf_cli,  
                'debit': 0.0,
                'credit': igtf_expected,       
            },
            {
                'account': self.acc_receivable,
                'debit': 0.0,
                'credit': (advance_amount / invoice.expected_currency_rate) - igtf_expected,   
            },
        ]

        self._assert_move_lines_equal(payment_move, expected_lines)

        self.assertAlmostEqual(invoice.foreign_amount_residual,51.2 , 2, "Monto residual de la factura debe ser 51.2 usd")


        invoice = self.env['account.move'].browse(invoice.id)

        self.assertAlmostEqual(invoice.bi_igtf, advance_amount, 2, "Bi_igtf DEbe ser 40.00 USD")
        
        action_data_2 = invoice.action_register_payment()
        
        last_advance = 52.7

        with Form(
            self.env['account.payment.register'].with_context(
               action_data_2['context']  
            )
        ) as pay_form:
            
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            
            pay_form.save()
            pay_form.amount = last_advance

        payment_register_wiz = pay_form.record

        action = payment_register_wiz.action_create_payments()
        
        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 
        igtf_expected = 1.5
        self.assertEqual(
            invoice.payment_state, 
            'paid', 
            f"La factura debe estar en estado 'paid' (pagada), estado actual: {invoice.payment_state}"
        )

        self.assertAlmostEqual(payment_move.currency_id.id, self.currency_usd.id, 2, "Moneda debe ser USD")
        self.assertAlmostEqual(payment_move.origin_payment_id.amount, last_advance, 2, "Monto debe ser 40.00 USD")

        expected_lines = [
            {
                'account': self.account_bank,      
                'debit': last_advance / invoice.expected_currency_rate,       
                'credit': 0.0,
            },

             {
                'account': self.acc_igtf_cli,  
                'debit': 0.0,
                'credit': igtf_expected / invoice.expected_currency_rate,       
            },

            {
                'account': self.acc_receivable,
                'debit': 0.0,
                'credit': (last_advance / invoice.expected_currency_rate) - (igtf_expected / invoice.expected_currency_rate),   
            },
        ]

        self._assert_move_lines_equal(payment_move, expected_lines)
    
        self.assertAlmostEqual(invoice.alter_bi_igtf, 1.20 , 2, "Monto BI_igtf de la factura debe ser 1.20 usd")
        self.assertAlmostEqual(invoice.igtf_top_aply, 2.7 , 2, "Igtf Aplicado debe ser 2.7 usd")
        self.assertAlmostEqual(invoice.amount_residual,0.0 , 2, "Monto residual de la factura debe ser 0.0 usd")
        self.assertAlmostEqual(invoice.bi_igtf,90.00  , 2, "Monto Bi_Igtf de la factura debe ser 90.00 usd")

    def test16_payment_from_invoice_with_igtf_journal_desconciliation(self):
        
        invoice_amount = float(542196.06)
        payment_amount = float(4036.80)
        expected_igtf = 80.74
        invoice = self._create_invoice_vef(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
     
        

        action_data = invoice.action_register_payment()
        
        with Form(
            self.env['account.payment.register'].with_context(
               action_data['context']  
            )
        ) as pay_form:
            
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            
            
            pay_form.save()
            pay_form.amount = payment_amount

        payment_register_wiz_2 = pay_form.record

        action = payment_register_wiz_2.action_create_payments()
        
        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 
        
        
        self.assertTrue(payment_move, "Debe haberse creado el asiento de pago asociado al payment.")
        self.assertAlmostEqual(payment.igtf_amount, expected_igtf, 2, "El IGTF calculado debe ser $80.74.")
        cxc_credit_amount = 797028.2142
        expected_lines = [
            {
                'account': self.account_bank,      
                'debit': payment_amount / invoice.expected_currency_rate,       
                'credit': 0.0,
            },
           
            {
                'account': self.acc_receivable,
                'debit': 0.0,
                'credit': cxc_credit_amount,   
            },
             {
                'account': self.acc_igtf_cli,  
                'debit': 0.0,
                'credit': 16265.88179,       
            },
        ]
        
        self._assert_move_lines_equal(payment_move, expected_lines)
        
        self.assertEqual(
            invoice.payment_state, 
            'paid', 
            f"La factura debe estar en estado 'paid' (pagada), estado actual: {invoice.payment_state}"
        )

        self.assertAlmostEqual(invoice.bi_igtf,2691.20, 2, "Bi_igtf DEbe ser 2691.20 USD")
        
        outstanding_line = payment_move.line_ids.filtered(
            lambda l: l.account_id == self.acc_receivable and l.credit > 0
        )

        invoice = self.env['account.move'].browse(invoice.id)
        
        invoice_receivable_line = invoice.line_ids.filtered(
            lambda l: l.account_id == self.acc_receivable and l.debit > 0
        )

        partial_reconcile = outstanding_line.matched_debit_ids.filtered(
            lambda p: p.debit_move_id == invoice_receivable_line
        )

        action = invoice.with_context({}).js_remove_outstanding_partial(partial_reconcile.id)
        self.assertEqual(action.get('res_model'), 'move.action.cancel.advance.payment.wizard')

        wizard_context = action.get('context', {})
        wizard = self.env['move.action.cancel.advance.payment.wizard'].with_context(wizard_context).create({
            'move_id': wizard_context.get('default_move_id'),
            'payment_id': wizard_context.get('default_payment_id'),
            # Llena otros campos requeridos si es necesario
        })

        wizard.action_confirm()

        self.assertAlmostEqual(invoice.bi_igtf,0.0, 2, "Bi_igtf DEbe ser 0.0 USD")
        self.assertEqual(
            invoice.payment_state, 
            'not_paid', 
            f"La factura debe estar en estado 'not_paid' (no pagada), estado actual: {invoice.payment_state}"
        )

        #Ahora es un anticipo
        outstanding_line = payment_move.line_ids.filtered(
            lambda l: l.account_id == self.advance_cust_acc and l.credit > 0
        )

        invoice.with_context({}).js_assign_outstanding_line(outstanding_line.id)

        self.assertEqual(
            invoice.payment_state, 
            'paid', 
            f"La factura debe estar en estado 'paid' (pagada), estado actual: {invoice.payment_state}"
        )



    def test17_payment_from_invoice_with_igtf_journal_desconciliation(self):
        
        invoice_amount = float(540181.364)
        payment_amount = float(2000.00)
        expected_igtf = 60.00
        invoice = self._create_invoice_vef(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
     
        
        action_data = invoice.action_register_payment()
        
        with Form(
            self.env['account.payment.register'].with_context(
               action_data['context']  
            )
        ) as pay_form:
            
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            
            
            pay_form.save()
            pay_form.amount = payment_amount

        payment_register_wiz_2 = pay_form.record

        action = payment_register_wiz_2.action_create_payments()
        
        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 
        
        
        self.assertTrue(payment_move, "Debe haberse creado el asiento de pago asociado al payment.")
        self.assertAlmostEqual(payment.igtf_amount, expected_igtf, 2, "El IGTF calculado debe ser 60.00.")

        cxc_credit_amount = (payment_amount / invoice.expected_currency_rate) - (expected_igtf / invoice.expected_currency_rate)

        expected_lines = [
            {
                'account': self.account_bank,      
                'debit': payment_amount / invoice.expected_currency_rate,       
                'credit': 0.0,
            },
           
            {
                'account': self.acc_receivable,
                'debit': 0.0,
                'credit': cxc_credit_amount,   
            },
             {
                'account': self.acc_igtf_cli,  
                'debit': 0.0,
                'credit': expected_igtf / invoice.expected_currency_rate,       
            },
        ]
        
        self._assert_move_lines_equal(payment_move, expected_lines)
        
        self.assertEqual(
            invoice.payment_state, 
            'partial', 
            f"La factura debe estar en estado 'partial' (parcialmente pagada), estado actual: {invoice.payment_state}"
        )

        self.assertAlmostEqual(invoice.bi_igtf,2000.00, 2, "Bi_igtf DEbe ser 2000.00 USD")
        
        outstanding_line = payment_move.line_ids.filtered(
            lambda l: l.account_id == self.acc_receivable and l.credit > 0
        )

        invoice = self.env['account.move'].browse(invoice.id)
        
        invoice_receivable_line = invoice.line_ids.filtered(
            lambda l: l.account_id == self.acc_receivable and l.debit > 0
        )

        partial_reconcile = outstanding_line.matched_debit_ids.filtered(
            lambda p: p.debit_move_id == invoice_receivable_line
        )

        invoice.with_context({}).js_remove_outstanding_partial(partial_reconcile.id)
        
        invoice = self.env['account.move'].browse(invoice.id)
        self.assertAlmostEqual(invoice.bi_igtf,0.0, 2, "Bi_igtf DEbe ser 0.0 USD")
        self.assertEqual(
            invoice.payment_state, 
            'not_paid', 
            f"La factura debe estar en estado 'not_paid' (no pagada), estado actual: {invoice.payment_state}"
        )

        #Ahora es un anticipo
        outstanding_line = payment_move.line_ids.filtered(
            lambda l: l.account_id == self.advance_cust_acc and l.credit > 0
        )

        invoice.with_context({}).js_assign_outstanding_line(outstanding_line.id)

        cross_move_advance = self.env['account.move'].search([], order='id desc', limit=1, offset=1)
        lol = cross_move_advance.line_ids.read(['name', 'account_id', 'debit', 'credit','balance','foreign_balance'])
        outstanding_line = cross_move_advance.line_ids.filtered(
            lambda l: l.account_id == self.acc_receivable and l.credit > 0
        )


        invoice = self.env['account.move'].browse(invoice.id)
        self.assertEqual(
            invoice.payment_state, 
            'partial', 
            f"La factura debe estar en estado 'partial' (parcialmente    pagada), estado actual: {invoice.payment_state}"
        )

        self.assertAlmostEqual(invoice.bi_igtf,2000.00, 2, "Bi_igtf DEbe ser 2000.00 USD")

        payment.action_draft()
        payment.action_cancel()
        
  """