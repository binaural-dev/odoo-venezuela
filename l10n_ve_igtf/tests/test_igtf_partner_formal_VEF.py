import logging
from odoo.tests import tagged , Form
from odoo.exceptions import UserError, ValidationError
from odoo import Command, fields

from .test_igtf_common_partner_formal_VEF import IGTFTestCommon 

_logger = logging.getLogger(__name__)

# Tasa de conversión: 1$ = 201.47bs
# docker exec -u odoo -it proj2 odoo --test-tags igtf -i binaural_advance_payment_igtf --without-demo=True --stop-after-init -d testneuvo5

@tagged("igtf_client", "igtf_run", "-at_install", "post_install")
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
                    f"Débito amount_currency: {found_line.foreign_debit}, Crédito Real Alterno: {found_line.foreign_credit}"
                    F"Monto en moneda: {found_line.amount_currency}"
                )
            
            
            self.assertTrue(found_line, 
                f"Línea contable para la cuenta '{expected_account.name}' ({expected_account.name}) no encontrada.")
            
            if expected_debit and not expected_foreign_debit:
                self.assertAlmostEqual(found_line.debit, expected_debit, 2, 
                    f"Débito de la cuenta '{expected_account.name}' incorrecto. Esperado: {expected_debit}, Real: {found_line.debit}")
                
            if expected_credit and not expected_foreign_credit:
                self.assertAlmostEqual(found_line.credit, expected_credit, 2, 
                    f"Crédito de la cuenta '{expected_account.name}' incorrecto. Esperado: {expected_credit}, Real: {found_line.credit}")

            
            if expected_foreign_debit and not expected_debit:
                self.assertAlmostEqual(found_line.foreign_debit, expected_foreign_debit, 2, 
                    f"Débito foraneo de la cuenta '{expected_account.name}' incorrecto. Esperado: {expected_foreign_debit}, Real: {found_line.foreign_debit}")
                
            if expected_foreign_credit and not expected_credit: 
                self.assertAlmostEqual(found_line.foreign_credit, expected_foreign_credit, 2, 
                    f"Crédito foraneo de la cuenta '{expected_account.name}' incorrecto. Esperado: {expected_foreign_credit}, Real: {found_line.foreign_credit}")

            if expected_amount_currency:
                self.assertAlmostEqual(found_line.amount_currency, expected_amount_currency, 2, 
                    f"Monto en moneda de la cuenta '{expected_account.name}' incorrecto. Esperado: {expected_amount_currency}, Real: {found_line.amount_currency}")
        
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
       
        self.assert_payment_values(payment, 600.00 , 18.0 ,'paid',self.acc_igtf_cli)

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
            pay_form.payment_date =fields.Date.today()
            pay_form.save()
            pay_form.amount = payment_amount
            pay_form.save()

        payment = pay_form.record
        action = payment.action_create_payments()

        payment = self.env['account.payment'].browse(action.get('res_id'))
      
        invoice = self.env['account.move'].browse(invoice.id)
        self.assert_invoice_values(invoice, 600, 418.0, 'partial')
        cross_move_advance = self.env['account.move'].search([], order='id desc', limit=1)
        
        
        expected_lines = [
            {'account': self.account_bank_usd, 'amount_currency': 600.00},
            {'account': self.acc_receivable, 'amount_currency': -582.00},
            {'account': self.acc_igtf_cli, 'amount_currency': -18.00 },
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
        self.assert_invoice_values(invoice, 605.74, 412.44, 'partial')

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
        self.assert_invoice_values(invoice, 990.53, 39.18, 'partial')

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
        self.assert_invoice_values(invoice, 472830.0, 41354.9, 'partial')

    
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
        self.assert_invoice_values(invoice, 390294.4, 121414.43, 'partial')

    
    def test08_payment_from_invoice_with_igtf_journal_1(self):

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


        self.assert_invoice_values(invoice, 1000.00, 0.0, 'paid')

        advance = len(payment.advanced_move_ids)
        self.assertAlmostEqual(advance, 1, 2, "Debe existir asiento de residual")
        
        residual_advance = self.env['account.move'].search([], order='id desc', limit=1)
        outstanding_line = residual_advance.line_ids.filtered(
            lambda l: l.account_id == self.advance_cust_acc and l.credit > 0
        )

        invoice = self.env['account.move'].browse(invoice.id)

        expected_lines = [
            {'account': self.account_bank_usd, 'amount_currency': 1500.00 },
            {'account': self.acc_receivable,  'amount_currency': -1470.00 },
            {'account': self.acc_igtf_cli, 'amount_currency': -30.00 },
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

        self.assert_invoice_values(invoice_2, 400, 0.0, 'paid')

    def test08_payment_from_invoice_with_igtf_journal_2(self):

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

        invoice = self.env['account.move'].browse(invoice.id)
        self.assert_invoice_values(invoice, 1000.00, 0.0, 'paid')

        advance = len(payment.advanced_move_ids)
        self.assertAlmostEqual(advance, 1, 2, "Debe existir asiento de residual")
        
        residual_advance = self.env['account.move'].search([], order='id desc', limit=1)
        outstanding_line = residual_advance.line_ids.filtered(
            lambda l: l.account_id == self.advance_cust_acc and l.credit > 0
        )

        invoice = self.env['account.move'].browse(invoice.id)
        
        expected_lines = [
            {'account': self.account_bank_usd, 'amount_currency': 1500.00 },
            {'account': self.acc_receivable,  'amount_currency': -1470.00 },
            {'account': self.acc_igtf_cli, 'amount_currency': -30.00 },
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

        self.assert_invoice_values(invoice_2, 400.00, 0.0, 'paid')

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

    def test09_payment_from_invoice_with_igtf_journal_1(self):

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

        self.assert_invoice_values(invoice, 1000.00, 530.0, 'partial')

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

        self.assert_invoice_values(invoice, 1000.00, 107.01, 'partial')


    def test09_payment_from_invoice_with_igtf_journal_2(self):

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

        self.assert_invoice_values(invoice, 1000.0, 530.0, 'partial')

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

        self.assert_invoice_values(invoice, 1000.00, 107.01, 'partial')
       

    
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

        self.assert_invoice_values(invoice, 500000.00, 0.0, 'paid')
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

        cross_move = self.env['account.move'].search([], order='id desc', limit=2)

        expected_lines = [
            {'account': self.advance_cust_acc, 'amount_currency': 680.49},
            {'account': self.acc_receivable, 'amount_currency': -660.08},
            {'account': self.acc_igtf_cli, 'amount_currency': -20.41 },
        ]
        self._assert_move_lines_equal(cross_move[1], expected_lines)

        self.assert_invoice_values(invoice2, 561.71,  255.14, 'partial')
        


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
        
    def test12_payment_from_invoice_with_igtf_journal_desconciliation(self):
        
        invoice_amount = float(2691.20)
        payment_amount = float(4036.80)
        expected_igtf = 80.74
        invoice = self._create_invoice_usd(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
     
        cxc_credit_amount = payment_amount - expected_igtf 

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
            pay_form.save()

        payment_register_wiz_2 = pay_form.record

        action = payment_register_wiz_2.action_create_payments()
        
        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 
        
        
        self.assertTrue(payment_move, "Debe haberse creado el asiento de pago asociado al payment.")
        self.assertAlmostEqual(payment.igtf_amount, expected_igtf, 2, "El IGTF calculado debe ser $80.74.")

        expected_lines = [
            {
                'account': self.account_bank_usd,      
                'amount_currency': payment_amount,       
            },
           
            {
                'account': self.acc_receivable,
                'amount_currency': -cxc_credit_amount,   
            },
             {
                'account': self.acc_igtf_cli,  
                'amount_currency': -expected_igtf,       
            },
        ]
        
        self._assert_move_lines_equal(payment_move, expected_lines)
        
        self.assertEqual(
            invoice.payment_state, 
            'paid', 
            f"La factura debe estar en estado 'paid' (pagada), estado actual: {invoice.payment_state}"
        )

        self.assertAlmostEqual(invoice.foreign_bi_igtf,2691.2, 2, "Bi_igtf DEbe ser 2691.2 usd")
        
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

        self.assertAlmostEqual(invoice.bi_igtf,1050360.29, 2, "Bi_igtf DEbe ser 1050360.29 vef")

    def test13_payment_from_invoice_with_igtf_journal_desconciliation(self):
        
        invoice_amount = float(2691.20)
        payment_amount = float(2000.00)
        expected_igtf = 60.00
        invoice = self._create_invoice_usd(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
     
        cxc_credit_amount = payment_amount - expected_igtf 

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
            pay_form.save()

        payment_register_wiz_2 = pay_form.record

        action = payment_register_wiz_2.action_create_payments()
        
        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 
        
        
        self.assertTrue(payment_move, "Debe haberse creado el asiento de pago asociado al payment.")
        self.assertAlmostEqual(payment.igtf_amount, expected_igtf, 2, "El IGTF calculado debe ser $80.74.")

        expected_lines = [
            {
                'account': self.account_bank_usd,      
                'amount_currency': payment_amount,       
            },
           
            {
                'account': self.acc_receivable,
                'amount_currency': -cxc_credit_amount,   
            },
             {
                'account': self.acc_igtf_cli,  
                'amount_currency': -expected_igtf,       
            },
        ]
        
        self._assert_move_lines_equal(payment_move, expected_lines)
        
        self.assertEqual(
            invoice.payment_state, 
            'partial', 
            f"La factura debe estar en estado 'partial' (parcialmente pagada), estado actual: {invoice.payment_state}"
        )

        self.assertAlmostEqual(invoice.foreign_bi_igtf,2000.00, 2, "Bi_igtf DEbe ser 2000.00 usd")
        
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

        invoice = self.env['account.move'].browse(invoice.id)
        invoice.with_context({}).js_remove_outstanding_partial(partial_reconcile.id)

        self.assertAlmostEqual(invoice.foreign_bi_igtf,0.0, 2, "Bi_igtf DEbe ser 0.0 USD")
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
            'partial', 
            f"La factura debe estar en estado 'partial' (parcialmente    pagada), estado actual: {invoice.payment_state}"
        )

        self.assertAlmostEqual(invoice.foreign_bi_igtf,2000.00, 2, "Bi_igtf DEbe ser 2000.00 usd")

    def test13b_vef_invoice_usd_payment_rate_gap_desconciliation_reaplica_sin_residuo(self):
        """Regression for a real case: VEF invoice paid in USD with a rate
        gap between invoice and payment dates. Two bugs lived here: (1)
        `is_payment()` didn't recognize the advance-cross move, using the
        invoice date's rate instead of the cross's real rate; (2) the IGTF
        guard never fired on a full reapply, leaving an IGTF-sized residual.
        """
        yesterday = fields.Date.subtract(fields.Date.today(), days=1)
        invoice_amount = 100000.00
        invoice = self._create_invoice_vef(invoice_amount, date=yesterday)
        invoice.with_context(move_action_post_alert=True).action_post()

        self.assertAlmostEqual(
            invoice.amount_residual, invoice_amount, 2,
            "La factura recién posteada debe tener el residual completo."
        )

        # Wizard de pago: se deja que el propio wizard proponga el monto
        # (deuda + IGTF a la tasa de HOY) -- no se hardcodea a mano para no
        # depender de una réplica manual de `calculate_igtf_for_payment`.
        action_data = invoice.action_register_payment()
        with Form(
            self.env['account.payment.register'].with_context(
                action_data['context']
            )
        ) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.save()

        payment_register_wiz = pay_form.record
        action = payment_register_wiz.action_create_payments()

        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id

        self.assertTrue(payment_move, "Debe haberse creado el asiento de pago asociado al payment.")
        self.assertEqual(
            invoice.payment_state, 'paid',
            f"La factura debe quedar 'paid' tras el pago inicial, estado actual: {invoice.payment_state}"
        )
        self.assertAlmostEqual(invoice.amount_residual, 0.0, 2)

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
        self.assertTrue(partial_reconcile, "Debe existir la conciliación factura<->pago a deshacer.")

        # 1) Desconciliar: la factura debe volver a NO PAGADA por el
        #    residual COMPLETO -- no debe quedar un "medio residuo".
        invoice.with_context({}).js_remove_outstanding_partial(partial_reconcile.id)

        self.assertEqual(
            invoice.payment_state, 'not_paid',
            f"Tras desconciliar debe volver a 'not_paid', estado actual: {invoice.payment_state}"
        )
        self.assertAlmostEqual(
            invoice.amount_residual, invoice_amount, 2,
            "Tras desconciliar el residual debe ser la deuda completa otra vez."
        )

        # 2) Reaplicar el mismo anticipo (ahora vive en la cuenta de
        #    Anticipo/Clientes) -- ESTA es la aserción que fallaba antes
        #    del fix: la factura debe cerrar 'paid' sin ningún residuo,
        #    ni por el bug de tasa ni por el bug de reparto del IGTF.
        outstanding_line = payment_move.line_ids.filtered(
            lambda l: l.account_id == self.advance_cust_acc and l.credit > 0
        )
        self.assertTrue(outstanding_line, "El pago debe haber quedado disponible como anticipo.")
        invoice.with_context({}).js_assign_outstanding_line(outstanding_line.id)

        self.assertEqual(
            invoice.payment_state, 'paid',
            f"Tras reaplicar el anticipo la factura debe cerrar 'paid' sin residuo, "
            f"estado actual: {invoice.payment_state} (residual: {invoice.amount_residual})"
        )
        self.assertAlmostEqual(
            invoice.amount_residual, 0.0, 2,
            msg=(
                f"Quedó un residuo de {invoice.amount_residual} Bs.F tras reaplicar el "
                f"anticipo -- volvió el bug de tasa (is_payment) y/o el de reparto del IGTF."
            ),
        )

    def test13c_vef_invoice_usd_full_payment_does_not_create_spurious_exchange_difference(self):
        """Paying a VEF invoice in full with USD shouldn't leave a spurious
        "exchange difference" entry -- that gap is pure USD-cent rounding
        from two conversions, not a real gain/loss. Fix: also compare in
        the payment currency, not just VEF, before forcing the residual.
        """
        yesterday = fields.Date.subtract(fields.Date.today(), days=1)
        invoice_amount = 100000.00
        invoice = self._create_invoice_vef(invoice_amount, date=yesterday)
        invoice.with_context(move_action_post_alert=True).action_post()

        action_data = invoice.action_register_payment()
        with Form(
            self.env['account.payment.register'].with_context(action_data['context'])
        ) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.save()

        payment = self.env['account.payment'].browse(
            pay_form.record.action_create_payments().get('res_id')
        )
        payment_move = payment.move_id
        invoice = self.env['account.move'].browse(invoice.id)

        cxc_line = payment_move.line_ids.filtered(lambda l: l.account_id == self.acc_receivable)
        self.assertAlmostEqual(
            cxc_line.balance, -invoice_amount, 2,
            msg=(
                f"El balance de la línea de CxC del pago ({cxc_line.balance}) debe calzar "
                f"exacto con la deuda de la factura ({-invoice_amount}), no solo 'cerca'."
            ),
        )
        self.assertEqual(invoice.payment_state, 'paid')
        self.assertAlmostEqual(invoice.amount_residual, 0.0, 2)

        exchange_moves = self.env['account.move'].search([
            ('journal_id.name', '=', 'Exchange Difference'),
            ('company_id', '=', self.company.id),
        ])
        self.assertFalse(
            exchange_moves,
            msg=(
                f"Un pago que liquida la factura completa no debe generar asientos de "
                f"diferencial cambiario -- se encontraron {len(exchange_moves)}: "
                f"{exchange_moves.mapped('id')}."
            ),
        )

    # ── Casos borde: la comparación en moneda de pago de test13c no debe
    # "tragarse" una diferencia real -- solo debe absorber redondeo de
    # centavos, nunca un pago genuinamente parcial, insuficiente o con
    # sobrante grande. ──────────────────────────────────────────────────

    def test13d_vef_invoice_usd_genuine_partial_payment_stays_partial(self):
        """Caso borde: pagar deliberadamente ~50% de la deuda NO debe
        forzarse a 'paid'. La comparación en moneda de pago (test13c) solo
        puede disparar cuando la diferencia es de centavos de USD -- un
        pago a mitad de camino está a miles de bolívares de distancia, muy
        por fuera de esa tolerancia.
        """
        yesterday = fields.Date.subtract(fields.Date.today(), days=1)
        invoice_amount = 100000.00
        invoice = self._create_invoice_vef(invoice_amount, date=yesterday)
        invoice.with_context(move_action_post_alert=True).action_post()

        action_data = invoice.action_register_payment()
        with Form(
            self.env['account.payment.register'].with_context(action_data['context'])
        ) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.save()
            full_amount = pay_form.amount
            pay_form.amount = round(full_amount / 2, 2)
            pay_form.save()

        payment = self.env['account.payment'].browse(
            pay_form.record.action_create_payments().get('res_id')
        )
        invoice = self.env['account.move'].browse(invoice.id)

        self.assertEqual(
            invoice.payment_state, 'partial',
            f"Un pago de ~50% no debe promoverse a 'paid', estado actual: {invoice.payment_state}"
        )
        self.assertGreater(
            invoice.amount_residual, invoice_amount * 0.3,
            f"El residual tras pagar ~mitad debe seguir siendo grande (~50.000,00), "
            f"no casi 0: {invoice.amount_residual} (pagado: {payment.amount} USD de {full_amount} USD)"
        )

    def test13e_vef_invoice_usd_meaningful_underpayment_keeps_correct_residual(self):
        """Caso borde: subpagar por un monto claramente NO redondeo (aquí,
        20 USD menos de lo que hacía falta -- unos 7.800 Bs a esta tasa,
        muy por encima del centavo de tolerancia) debe dejar el residual
        EXACTO de esa diferencia, no acercarlo a 0.
        """
        yesterday = fields.Date.subtract(fields.Date.today(), days=1)
        invoice_amount = 100000.00
        invoice = self._create_invoice_vef(invoice_amount, date=yesterday)
        invoice.with_context(move_action_post_alert=True).action_post()

        action_data = invoice.action_register_payment()
        with Form(
            self.env['account.payment.register'].with_context(action_data['context'])
        ) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.save()
            full_amount = pay_form.amount
            underpaid_amount = round(full_amount - 20.0, 2)
            pay_form.amount = underpaid_amount
            pay_form.save()

        payment = self.env['account.payment'].browse(
            pay_form.record.action_create_payments().get('res_id')
        )
        invoice = self.env['account.move'].browse(invoice.id)

        self.assertEqual(
            invoice.payment_state, 'partial',
            f"Subpagar por 20 USD no debe promoverse a 'paid', estado actual: {invoice.payment_state}"
        )
        # A la tasa de la factura (yesterday), 20 USD son ~7.600-7.700 Bs --
        # el residual debe rondar esa magnitud, no 0.
        self.assertGreater(
            invoice.amount_residual, 5000.0,
            f"El residual tras subpagar 20 USD debe reflejar esa diferencia real "
            f"(varios miles de Bs), no habérsele tragado como redondeo: {invoice.amount_residual}"
        )

    def test13f_vef_invoice_usd_overpayment_creates_change_not_silently_absorbed(self):
        """Caso borde: pagar de MÁS (sobrepago claro, no centavos) debe
        seguir generando el mecanismo normal de vuelto/anticipo -- no debe
        "desaparecer" el sobrante ni marcarse como si calzara exacto.
        """
        yesterday = fields.Date.subtract(fields.Date.today(), days=1)
        invoice_amount = 100000.00
        invoice = self._create_invoice_vef(invoice_amount, date=yesterday)
        invoice.with_context(move_action_post_alert=True).action_post()

        action_data = invoice.action_register_payment()
        with Form(
            self.env['account.payment.register'].with_context(action_data['context'])
        ) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.save()
            full_amount = pay_form.amount
            pay_form.amount = round(full_amount + 30.0, 2)
            pay_form.save()

        payment = self.env['account.payment'].browse(
            pay_form.record.action_create_payments().get('res_id')
        )
        invoice = self.env['account.move'].browse(invoice.id)

        self.assertEqual(
            invoice.payment_state, 'paid',
            f"Con un sobrepago la factura sí debe cerrar 'paid', estado actual: {invoice.payment_state}"
        )
        self.assertAlmostEqual(invoice.amount_residual, 0.0, 2)

        # El sobrante (~30 USD) debe seguir viviendo en alguna cuenta de
        # anticipo/cambio -- no debe "esfumarse" silenciosamente.
        advance_lines = payment.move_id.line_ids.filtered(
            lambda l: l.account_id.is_advance_account
        ) or self.env['account.move'].search([
            ('partner_id', '=', invoice.partner_id.id),
            ('ref', 'like', 'RESTANTE'),
        ]).line_ids.filtered(lambda l: l.account_id.is_advance_account)
        self.assertTrue(
            advance_lines,
            "El sobrepago (~30 USD) debe quedar registrado como anticipo/vuelto, "
            "no absorbido silenciosamente por el ajuste de test13c."
        )

    def test13g_vef_invoice_decimal_quantity_and_high_precision_price(self):
        """Caso borde: factura con CANTIDAD decimal (0,5248) y PRECIO
        unitario con más de 2 decimales (precisión 6 -- como una factura
        real cuyo precio viene de convertir a BCV). Los tres fixes (guard
        de IGTF, is_payment del cruce, comparación en moneda de pago) se
        probaron hasta ahora con montos "redondos" (100.000,00) -- este
        caso confirma que también funcionan con montos "sucios" de punta a
        punta, no solo cuando los números caen convenientemente exactos.
        """
        dp_price = self.env['decimal.precision'].search([('name', '=', 'Product Price')], limit=1)
        if dp_price:
            dp_price.digits = 6

        yesterday = fields.Date.subtract(fields.Date.today(), days=1)
        sale_journal = self.Journal.search(
            [("type", "=", "sale"), ("company_id", "=", self.company.id), ("is_debit", "=", False)],
            limit=1,
        )
        with Form(self.env["account.move"].with_context(
            default_move_type='out_invoice', default_journal_id=sale_journal,
        )) as inv_form:
            inv_form.partner_id = self.partner
            inv_form.invoice_date = yesterday
            inv_form.currency_id = self.currency_vef
            inv_form.save()
        inv = inv_form.save()
        with Form(inv) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product
                line.quantity = 0.5248
                line.price_unit = 190905.223344
        invoice = inv_form_edit.save()
        invoice.with_context(move_action_post_alert=True).action_post()

        invoice_amount = invoice.amount_total
        self.assertGreater(invoice_amount, 0.0, "La factura con decimales debe postearse con un total > 0.")
        _logger.info(f"test13g: invoice quantity=0.5248, price_unit=190905.223344 -> amount_total={invoice_amount}")

        action_data = invoice.action_register_payment()
        with Form(
            self.env['account.payment.register'].with_context(action_data['context'])
        ) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.save()

        payment = self.env['account.payment'].browse(
            pay_form.record.action_create_payments().get('res_id')
        )
        payment_move = payment.move_id
        invoice = self.env['account.move'].browse(invoice.id)

        cxc_line = payment_move.line_ids.filtered(lambda l: l.account_id == self.acc_receivable)
        self.assertAlmostEqual(
            cxc_line.balance, -invoice_amount, 2,
            msg=(
                f"CxC del pago ({cxc_line.balance}) debe calzar exacto con la deuda "
                f"({-invoice_amount}) aun con cantidad/precio decimales."
            ),
        )
        self.assertEqual(
            invoice.payment_state, 'paid',
            f"La factura con decimales debe cerrar 'paid', estado actual: {invoice.payment_state}"
        )
        self.assertAlmostEqual(invoice.amount_residual, 0.0, 2)

        exchange_moves = self.env['account.move'].search([
            ('journal_id.name', '=', 'Exchange Difference'),
            ('company_id', '=', self.company.id),
        ])
        self.assertFalse(
            exchange_moves,
            msg=(
                f"No debe haber diferencial cambiario espurio con montos decimales de "
                f"alta precisión: {exchange_moves.mapped('id')}"
            ),
        )

    def test14_payment_from_invoice_with_igtf_journal_paiment_multi_invoice(self):

        invoice_amount = float(2691.20)
        expected_igtf = 80.736

        invoices = self.env['account.move']
        for i in range(2):
            invoice = self._create_invoice_usd(invoice_amount)
            invoice.with_context(move_action_post_alert=True).action_post()
            invoices |= invoice


       
        lines_to_pay = invoices.line_ids.filtered(
            lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable') 
            and not l.reconciled  # Solo las que no han sido pagadas totalmente
        )

        # 2. Obtener el contexto de la acción desde esas líneas
        action = lines_to_pay.action_register_payment()
        ctx = action['context']
        
        # Aseguramos que el active_model pay_form.save() sea el correcto para el wizard
        ctx.update({
            'active_model': 'account.move.line',
            'active_ids': lines_to_pay.ids,
        })
        
        with Form(
            self.env['account.payment.register'].with_context(
               ctx
            )
        ) as pay_form:
            
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.save()
            pay_form.group_payment = False
            pay_form.save()

        payment_register_wiz_2 = pay_form.record
        
        
        action = payment_register_wiz_2.action_create_payments()
    
        payments = self.env['account.payment'].search(action.get('domain'))

        
        for pay in payments:
            
            expected_lines = [
                {
                    'account': self.account_bank_usd,      
                    'amount_currency': 2771.9359999999997,       
                },
            
                {
                    'account': self.acc_igtf_cli,  
                    'amount_currency': -expected_igtf,       
                },
                {
                    'account': self.acc_receivable,
                    'amount_currency': -invoice_amount,   
                },
            ]

            self._assert_move_lines_equal(pay.move_id, expected_lines)

        for rec in invoices:

            self.assertAlmostEqual(rec.foreign_bi_igtf,2691.20, 2, "Bi_igtf DEbe ser 2691.20 vef")

    
    def test15_payment_from_invoice_with_igtf_journal_paiment_multi_invoice(self):
        
        invoice_amount = float(2691.20)

        invoices = self.env['account.move']
        for i in range(2):
            invoice = self._create_invoice_usd(invoice_amount)
            invoice.with_context(move_action_post_alert=True).action_post()
            invoices |= invoice



        lines_to_pay = invoices.line_ids

        # 2. Obtener el contexto de la acción desde esas líneas
        action = lines_to_pay.action_register_payment()
        ctx = action['context']
        
        # Aseguramos que el active_model pay_form.save() sea el correcto para el wizard
        ctx.update({
            'active_model': 'account.move.line',
            'active_ids': lines_to_pay.ids,
        })
        
        with Form(
            self.env['account.payment.register'].with_context(
               ctx
            )
        ) as pay_form:
            
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.group_payment = True
            pay_form.save()

        payment_register_wiz_2 = pay_form.record
        
        action = payment_register_wiz_2.action_create_payments()

        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 


        expected_lines = [
            {
                'account': self.account_bank_usd,      
                'amount_currency': 5543.87,
            },
            {
                'account': self.acc_igtf_cli,  
                'amount_currency': -161.47,
            },
            {
                'account': self.acc_receivable,
                'amount_currency': -5382.4
            },
        ]

        self._assert_move_lines_equal(payment_move, expected_lines)

