import logging
from odoo.tests import tagged , Form
from odoo.exceptions import UserError, ValidationError
from odoo import Command, fields

from .test_igtf_common_providers_formal_VEF import IGTFTestCommon 

_logger = logging.getLogger(__name__)


@tagged("igtf_providers_vef", "igtf_run", "-at_install", "post_install")
class TestIGTFNEW(IGTFTestCommon): 
        
    
    
    def _assert_move_lines_equal(self, move, expected_lines):
        """
        Valida que el asiento contable tenga el número de líneas esperado y que
        los valores de Débito, Crédito y Cuenta coincidan para cada línea.
        """
        self.assertEqual(len(move.line_ids), len(expected_lines), 
            f"El asiento debe tener {len(expected_lines)} líneas, pero tiene {len(move.line_ids)}.")

        for expected_line in expected_lines:
            expected_account = expected_line['account']
            expected_debit = expected_line.get('debit', False)
            expected_credit = expected_line.get('credit', False)

            expected_foreign_debit = expected_line.get('foreign_debit', False)
            expected_foreign_credit = expected_line.get('foreign_credit', False)

            
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

        
        total_debit = sum(line.debit for line in move.line_ids)
        total_credit = sum(line.credit for line in move.line_ids)

        self.assertAlmostEqual(total_debit, total_credit, 2, 
            "El asiento no balancea (Débito != Crédito).")
        
        _logger.info("Validación detallada de líneas contables: OK.")

    def test01_payment_from_invoice_with_igtf_journal(self):
        
        # USD 2681.20 * 201.47 = 540,181.36
        # 741.2 * 201.47 = 149329.56
        invoice_amount = float(540181.36)
        payment_amount = float(2000.00)
        expected_igtf = 60
        
        invoice = self._create_invoice_vef(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
        
        cxc_credit_amount = payment_amount - expected_igtf 
        expected_residual = 149329.56
        action_data = invoice.action_register_payment()
        
        with Form(self.env['account.payment.register'].with_context(action_data['context'])) as pay_form:

            pay_form.journal_id = self.bank_journal_usd
            pay_form.currency_id = self.currency_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.foreign_currency_id = self.currency_usd
            pay_form.foreign_rate = invoice.foreign_rate
            pay_form.amount = payment_amount

        payment_register_wiz_2 = pay_form.record
        action = payment_register_wiz_2.action_create_payments()
        
        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 
        
        
        self.assertTrue(payment_move, "Debe haberse creado el asiento de pago asociado al payment.")
        self.assertAlmostEqual(payment.igtf_amount, expected_igtf, 2, "El IGTF calculado debe ser $60.00.")

        expected_lines = [
            {'account': self.account_bank, 'foreign_debit': 0.0, 'foreign_credit': payment_amount},
            {'account': self.acc_payable, 'foreign_debit': cxc_credit_amount, 'foreign_credit': 0.0},
            {'account': self.acc_igtf_prov, 'foreign_debit': expected_igtf, 'foreign_credit': 0.0},
        ]
      
        self._assert_move_lines_equal(payment_move, expected_lines)

        self.assertEqual(
            invoice.payment_state, 
            'partial', 
            f"La factura debe estar en estado 'partial' (parcialmente pagada), estado actual: {invoice.payment_state}"
        )

        self.assertAlmostEqual(
            invoice.amount_residual, 
            expected_residual, 
            2, 
            f"El monto residual de la factura debe ser VEF{expected_residual}, pero es VEF{invoice.amount_residual}"
        )

    def test02_payment_from_invoice_with_igtf_journal(self):

        # Conversiones (201.47):
        # 2681.20 * 201.47 = 540181.36
        # 2000.00 * 201.47 = 402940.00
        # 60.00 * 201.47 = 12088.20
        # 741.2 * 201.47 = 149329.56
        
        invoice_amount = 540181.36
        payment_amount = 2000.00
        expected_igtf = 60.00
        cxc_credit_amount = payment_amount - expected_igtf 
        expected_residual = 149329.56

        
        invoice = self._create_invoice_vef(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()        
        
        action_data = invoice.action_register_payment()

        with Form(self.env['account.payment.register'].with_context(action_data['context'])) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.currency_id = self.currency_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.foreign_currency_id = self.currency_usd
            pay_form.foreign_rate = invoice.foreign_rate
            pay_form.amount = payment_amount

        payment = pay_form.record
        action = payment.action_create_payments()
        
        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 
        
        self.assertTrue(payment_move, "Debe haberse creado el asiento de pago asociado al payment.")
        self.assertAlmostEqual(payment.igtf_amount, expected_igtf, 2, f"El IGTF calculado debe ser {expected_igtf} Bs.")
        
        

        expected_lines = [
            {'account': self.account_bank, 'foreign_debit': 0.0, 'foreign_credit': payment_amount},
            {'account': self.acc_payable, 'foreign_debit': cxc_credit_amount, 'foreign_credit': 0.0},
            {'account': self.acc_igtf_prov, 'foreign_debit': expected_igtf, 'foreign_credit': 0.0},
        ]
        
        self._assert_move_lines_equal(payment_move, expected_lines)
        self.assertEqual(invoice.payment_state, 'partial')

        self.assertAlmostEqual(
            invoice.amount_residual, 
            expected_residual, 
            2, 
            f"El monto residual de la factura debe ser {expected_residual} Bs, pero es {invoice.amount_residual}"
        )
        
       
        invoice = self.env['account.move'].browse(invoice.id)
        amount_2 = expected_residual # El residual exacto para saldar en VES
       
        action_data = invoice.action_register_payment()

        with Form(self.env['account.payment.register'].with_context(action_data['context'])) as pay_form:
            pay_form.journal_id = self.bank_journal_bs
            # No se especifica amount_2 porque el asistente de Odoo toma el residual por defecto

        payment = pay_form.record
        action_2 = payment.action_create_payments()
        payment_2 = self.env['account.payment'].browse(action_2.get('res_id'))
        payment_move_2 = payment_2.move_id 
        
        self.assertTrue(payment_move_2, "Debe haberse creado el asiento de pago 2.")
        
        
        expected_lines_2 = [
            {'account': self.account_bank, 'debit': 0.0, 'credit': amount_2},
            {'account': self.acc_payable, 'debit': amount_2, 'credit': 0.0},
        ]
        
        self._assert_move_lines_equal(payment_move_2, expected_lines_2)

        
        self.assertEqual(invoice.payment_state, 'paid')
        self.assertAlmostEqual(invoice.amount_residual, 0.0, 2)
        
    def test03_payment_from_invoice_with_igtf_journal(self):

        # Conversiones:
        # 2691.20 * 201.47 = 542196.06
        # 4036.80 * 201.47 = 813294.09
        # 80.74 * 201.47 = 16266.69
        # 3956.06 * 201.47 = 797027.41
        # 950.00 * 201.47 = 191396.50
        # 1264.86 * 201.47 = 254831.34
        # 978.50 * 201.47 = 197138.40
        # 28.50 * 201.47 = 5741.90

        invoice_amount = 542196.06
        payment_amount = 4036.80
        
        residual = 1264.864
        invoice_amount_2 = 950.0
        
        invoice = self._create_invoice_vef(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
        inverse_rate = invoice.foreign_inverse_rate

        expected_igtf = 80.74 
        cxc_credit_amount= 3956.0640000000003
        igtf_cross = 28.5
        
        action_data = invoice.action_register_payment()

        with Form(
            self.env['account.payment.register'].with_context(
               action_data['context']  
            )
        ) as pay_form:
            
            pay_form.journal_id = self.bank_journal_usd
            pay_form.currency_id = self.currency_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.foreign_currency_id = self.currency_usd
            pay_form.foreign_rate = invoice.foreign_rate
            pay_form.amount = payment_amount

        payment = pay_form.record
        
        action = payment.action_create_payments()

        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 
        
        self.assertTrue(payment_move, "Debe haberse creado el asiento de pago asociado al payment.")
        self.assertAlmostEqual(payment.igtf_amount, expected_igtf, 2, "El IGTF calculado debe ser $80.74.")
        
        expected_lines = [
            {'account': self.account_bank, 'credit': payment_amount / inverse_rate, 'debit': 0.0},
            {'account': self.acc_payable, 'credit': 0.0, 'debit': cxc_credit_amount /inverse_rate},
            {'account': self.acc_igtf_prov, 'credit': 0.0, 'debit': 16265.881920030806},
        ]
        
        self._assert_move_lines_equal(payment_move, expected_lines)
    
        invoice_2 = self._create_invoice_vef(invoice_amount_2 / inverse_rate)
        invoice_2.with_context(move_action_post_alert=True).action_post()

        advance_widget_value = getattr(invoice_2, 'invoice_outstanding_credits_debits_widget_advance_payment', False)
        advance_widget = advance_widget_value if isinstance(advance_widget_value, dict) else {} 
        widget_content = advance_widget.get('content') or [] 
        advance_residual = widget_content[0]

        self.assertTrue(advance_residual, "Debe existir el pago restante como anticipo")
        last_record_move_id = advance_residual.get('move_id', False) 

        residual_advance = self.env['account.move'].browse(last_record_move_id)

        expected_lines = [
            {'account': self.acc_payable, 'debit': 254832.1542, 'credit': 0.0},
            {'account': self.advance_supp_acc, 'debit': 0.0, 'credit': 254832.1542},
        ]

        self._assert_move_lines_equal(residual_advance, expected_lines)

        outstanding_line = residual_advance.line_ids.filtered(
            lambda l: l.account_id == self.acc_payable and l.debit > 0
        )
        invoice_2.with_context({}).js_assign_outstanding_line(outstanding_line.id)
        cross_move_advance = self.env['account.move'].search([], order='id desc', limit=1)

        expected_lines = [
            {'account': self.advance_supp_acc, 'credit': 978.50 / inverse_rate, 'debit': 0.0},
            {'account': self.acc_payable, 'credit': 0.0, 'debit': 950.00 / inverse_rate},
            {'account': self.acc_igtf_prov, 'credit': 0.0, 'debit':28.50 / inverse_rate},
        ]

        self._assert_move_lines_equal(cross_move_advance, expected_lines)

    def test04_payment_from_invoice_with_igtf_journal(self):

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
        inverse_rate = invoice.foreign_inverse_rate
        action_data = invoice.action_register_payment()
        with Form(
            self.env['account.payment.register'].with_context(
               action_data['context']  
            )
        ) as pay_form:
            
            pay_form.journal_id = self.bank_journal_usd
            pay_form.currency_id = self.currency_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.foreign_currency_id = self.currency_usd
            pay_form.foreign_rate = invoice.foreign_rate
            pay_form.amount = payment_amount

        payment = pay_form.record
        
        action = payment.action_create_payments()

        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 

        self.assertAlmostEqual(payment.igtf_amount, expected_igtf, 2, "El IGTF calculado debe ser $80.74.")
        self.assertTrue(payment_move, "Debe haberse creado el asiento de pago asociado al payment.")

        expected_lines_p1 = [
            {
                'account': self.account_bank,      
                'debit': 0.0,       
                'credit': payment_amount / inverse_rate,
            },
           
            {
                'account': self.acc_payable,
                'debit': cxc_credit_amount / inverse_rate,
                'credit': 0.0,   
            },
             {
                'account': self.acc_igtf_prov,  
                'debit': expected_igtf / inverse_rate,
                'credit': 0.0,       
            },
        ]

        self._assert_move_lines_equal(payment.move_id, expected_lines_p1)

        # Factura 2 y cruce
        invoice_2 = self._create_invoice_vef(invoice_amount_2 / inverse_rate)
        invoice_2.with_context(move_action_post_alert=True).action_post()

        advance_widget = getattr(invoice_2, 'invoice_outstanding_credits_debits_widget_advance_payment', {})
        widget_content = advance_widget.get('content') or []
        advance_residual = widget_content[0]

        self.assertTrue(advance_residual, "Debe existir el pago restante como anticipo")
        last_record_move_id = advance_residual.get('move_id', False) 

        residual_advance = self.env['account.move'].browse(last_record_move_id)

        expected_lines = [
            {
                'account': self.acc_payable,      
                'debit': residual/ inverse_rate,      
                'credit': 0.0
            },
           
            {
                'account': self.advance_supp_acc,
                'debit': 0.0,
                'credit': residual / inverse_rate,
            },
             
        ]
        

        self._assert_move_lines_equal(residual_advance, expected_lines)

        outstanding_line = residual_advance.line_ids.filtered(
            lambda l: l.account_id == self.acc_payable and l.debit > 0
        )
        invoice_2.with_context({}).js_assign_outstanding_line(outstanding_line.id)

        cross_move_advance = self.env['account.move'].search([], order='id desc', limit=1)

        expected_lines = [
           
            {
                'account': self.acc_payable,
                'credit': 0.0,
                'debit': 950.0 / inverse_rate,   
            },
             {
                'account': self.acc_igtf_prov,  
                'credit': 0.0,
                'debit': 28.50 / inverse_rate,       
            },
            {
                'account': self.advance_supp_acc,      
                'credit':   978.50 / inverse_rate, 
                'debit': 0.0
            },
        ]

        
        self._assert_move_lines_equal(cross_move_advance, expected_lines)
        invoice_3 = self._create_invoice_vef(invoice_amount_3  / inverse_rate)

        #invoice_3 = self.env['account.move'].browse(invoice_3.id)
        invoice_3.with_context(move_action_post_alert=True).action_post()
        
        invoice_3.with_context({}).js_assign_outstanding_line(outstanding_line.id)
        #CHEQUEAR ASIENTO CRUCE
        cross_move_advance = self.env['account.move'].search([], order='id desc', limit=1)

        #validacion Asiento de Cruce

        expected_lines = [
            {
                'account': self.advance_supp_acc,      
                'credit': 286.3640005956 / inverse_rate,       
                'debit': 0.0,
            },
           
            {
                'account': self.acc_payable,
                'credit': 0.0,
                'debit': 277.773080577732 / inverse_rate,   
            },
             {
                'account': self.acc_igtf_prov,  
                'credit': 0.0,
                'debit': 8.590920017868 / inverse_rate,       
            },
        ]

    def test05_payment_from_invoice_with_igtf_journal(self):

        invoice_amount = 542196.06 
        payment_amount = 4036.80
        expected_igtf = 80.74

        cxc_credit_amount= 3956.06

        invoice_amount_2 = 251837.5 #1250

        
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
            pay_form.foreign_currency_id = self.currency_usd
            pay_form.foreign_rate = invoice.foreign_rate
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
                'foreign_debit': 0.0,       
                'foreign_credit': payment_amount,
            },
           
            {
                'account': self.acc_payable,
                'foreign_debit': cxc_credit_amount,
                'foreign_credit': 0.0,   
            },
             {
                'account': self.acc_igtf_prov,  
                'foreign_debit': expected_igtf,
                'foreign_credit': 0.0,       
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
                'account': self.acc_payable,      
                'foreign_debit': 1264.86,  
                'foreign_credit': 0.0, 
            },
           
            {
                'account': self.advance_supp_acc,
                'foreign_debit': 0.0,
                'foreign_credit': 1264.86,  
            },
             
        ]

        self._assert_move_lines_equal(residual_advance, expected_lines)

        ##Conciliar Asiento Restante
        outstanding_line = residual_advance.line_ids.filtered(
            lambda l: l.account_id == self.acc_payable and l.debit > 0
        )
        invoice_2.with_context({}).js_assign_outstanding_line(outstanding_line.id)
        cross_move_advance = self.env['account.move'].search([], order='id desc', limit=1)

        #validacion Asiento de Cruce
        expected_lines = [
            
             {
                'account': self.acc_igtf_prov,  
                'foreign_credit': 0.0,
                'debit': 37.5 / invoice_2.foreign_inverse_rate,      
            },
            {
                'account': self.acc_payable,
                'foreign_credit': 0.0,
                'foreign_debit':  1227.364019854 ,    
            },
            {
                'account': self.advance_supp_acc,      
                'foreign_credit': 1264.86,       
                'foreign_debit': 0.0,
            },
           
            
        ]

        self._assert_move_lines_equal(cross_move_advance, expected_lines)

    def test06_payment_from_invoice_with_igtf_journal(self):

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
            pay_form.foreign_currency_id = self.currency_usd
            pay_form.foreign_rate = invoice.foreign_rate
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
                'debit': 0.0,       
                'credit': 813294.096,
            },
           
            {
                'account': self.acc_payable,
                'debit': cxc_credit_amount,
                'credit': 0.0,   
            },
             {
                'account': self.acc_igtf_prov,  
                'debit': expected_igtf,
                'credit': 0.0,       
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
                'account': self.acc_payable,      
                'debit': 254832.1542, 
                'credit': 0.0  
            },
           
            {
                'account': self.advance_supp_acc,
                'debit': 0.0,
                'credit': 254832.1542, 
            },
             
        ]

        self._assert_move_lines_equal(residual_advance, expected_lines)

        ##Conciliar Asiento Restante
        outstanding_line = residual_advance.line_ids.filtered(
            lambda l: l.account_id == self.acc_payable and l.debit > 0
        )
        invoice_2.with_context({}).js_assign_outstanding_line(outstanding_line.id)
        cross_move_advance = self.env['account.move'].search([], order='id desc', limit=1)

        #validacion Asiento de Cruce
        expected_lines = [
            {
                'account': self.advance_supp_acc,      
                'debit': 0.0,       
                'credit': 254832.1542,
            },
           
            {
                'account': self.acc_payable,
                'debit': 247187.18957400107,
                'credit': 0.0,   
            },
             {
                'account': self.acc_igtf_prov,  
                'debit': 7644.964626000033,
                'credit': 0.0,       
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
            pay_form.foreign_currency_id = self.currency_usd
            pay_form.foreign_rate = invoice.foreign_rate
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
            pay_form.foreign_currency_id = self.currency_usd
            pay_form.foreign_rate = invoice.foreign_rate
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
            pay_form.foreign_currency_id = self.currency_usd
            pay_form.foreign_rate = invoice.foreign_rate
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
                'debit': 0.0,       
                'credit': 402940.0,
            },
           
            {
                'account': self.acc_payable,
                'debit': cxc_credit_amount,
                'credit': 0.0,   
            },
             {
                'account': self.acc_igtf_prov,  
                'debit': 12088.2,
                'credit': 0.0,       
            },
        ]
        

        self._assert_move_lines_equal(payment_move, expected_lines)
        invoice = self.env['account.move'].browse(invoice.id)
        self.assertEqual(invoice.payment_state, 'partial', "Estado incorrecto después del pago 1.")

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
                'account': self.acc_payable,      
                'debit': advance_amount,       
                'credit': 0.0,
            },
           
            {
                'account': self.account_bank,
                'debit': 0.0,
                'credit': advance_amount,   
            },
            
        ]

        self._assert_move_lines_equal(payment_mov_2, expected_lines)
        

        #Anticipo  pago
        context = {'default_payment_type': 'outbound', 'default_partner_type': 'supplier', 'search_default_outbound_filter': 1, 'default_move_journal_types': ('bank', 'cash'), 'display_account_trust': True, 'default_is_advance_payment': True}
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
                'account': self.advance_supp_acc,      
                'debit': 150344.26,       
                'credit': 0.0,
            },
           
            {
                'account': self.account_bank,
                'debit': 0.0,
                'credit': 150344.26,   
            },
            
        ]
        
        self._assert_move_lines_equal(payment_move_advance, expected_lines)

        #consiliar segundo pago Anticipo
        invoice = self.env['account.move'].browse(invoice.id)
      
        outstanding_line = payment_move_advance.line_ids.filtered(
            lambda l: l.account_id == self.advance_supp_acc and l.debit > 0
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
            pay_form.foreign_currency_id = self.currency_usd
            pay_form.foreign_rate = invoice.foreign_rate
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
                'debit': 0.0,       
                'credit': 813294.096,
            },
           
            {
                'account': self.acc_payable,
                'debit': cxc_credit_amount,
                'credit': 0.0,   
            },
             {
                'account': self.acc_igtf_prov,  
                'debit': 16265.88,
                'credit': 0.0,       
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
            pay_form.foreign_currency_id = self.currency_usd
            pay_form.foreign_rate = invoice.foreign_rate
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
                'debit': 0.0,       
                'credit': 543969.00,
            },
           
            {
                'account': self.acc_payable,
                'debit': cxc_credit_amount,
                'credit': 0.0,   
            },
             {
                'account': self.acc_igtf_prov,  
                'debit': 16265.88,
                'credit': 0.0,       
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
            pay_form.foreign_currency_id = self.currency_usd
            pay_form.foreign_rate = invoice.foreign_rate
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
                'debit': 0.0,       
                'credit': 558461.9418,
            },
           
            {
                'account': self.acc_payable,
                'debit': cxc_credit_amount,
                'credit': 0.0,   
            },
             {
                'account': self.acc_igtf_prov,  
                'debit': 16265.88,
                'credit': 0.0,       
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
            pay_form.foreign_rate = invoice.foreign_rate
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
                'debit': 0.0,       
                'credit': 1000.0,
            },
           
            {
                'account': self.acc_payable,
                'debit': 1000.0,
                'credit': 0.0,   
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
        context = {'default_payment_type': 'outbound', 'default_partner_type': 'supplier', 'search_default_outbound_filter': 1, 'default_move_journal_types': ('bank', 'cash'), 'display_account_trust': True, 'default_is_advance_payment': True}
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
                'account': self.advance_supp_acc,      
                'debit': 543969.0,       
                'credit': 0.0,
            },
           
            {
                'account': self.account_bank,
                'debit': 0.0,
                'credit': 543969.0,   
            },
            
        ]
        
        self._assert_move_lines_equal(payment_move_advance, expected_lines)

        #consiliar segundo pago Anticipo
        invoice = self.env['account.move'].browse(invoice.id)
      
        outstanding_line = payment_move_advance.line_ids.filtered(
            lambda l: l.account_id == self.advance_supp_acc and l.debit > 0
        )

        invoice.with_context({}).js_assign_outstanding_line(outstanding_line.id)

        cross_move_advance = self.env['account.move'].search([], order='id desc', limit=1)
        igtf_expected = 80.58709445575023
        #validacion Asiento de Cruce
        expected_lines = [
            {
                'account': self.advance_supp_acc,      
                'debit': 0.0,       
                'credit': 543969.0,
            },
           
            {
                'account': self.acc_igtf_prov,  
                'debit': igtf_expected / invoice.foreign_inverse_rate, 
                'foreign_credit': 0.0,       
            },
            {
                'account': self.acc_payable,
                'debit': (2700.00 - igtf_expected) / invoice.foreign_inverse_rate,
                'credit': 0.0,   
            },
        ]

        self._assert_move_lines_equal(cross_move_advance, expected_lines)

    def test13_payment_from_invoice_with_igtf_journal(self):
        
        invoice_amount = float(542196.06)
        advance_amount = float(2691.20)

        invoice = self._create_invoice_vef(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
     

        #Anticipo  pago
        context = {'default_payment_type': 'outbound', 'default_partner_type': 'supplier', 'search_default_outbound_filter': 1, 'default_move_journal_types': ('bank', 'cash'), 'display_account_trust': True, 'default_is_advance_payment': True}
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
                'account': self.advance_supp_acc,      
                'debit': 542196.064,       
                'credit': 0.0,
            },
           
            {
                'account': self.account_bank,
                'debit': 0.0,
                'credit': 542196.064,   
            },
            
        ]
        
        self._assert_move_lines_equal(payment_move_advance, expected_lines)

        #consiliar segundo pago Anticipo
        invoice = self.env['account.move'].browse(invoice.id)
      
        outstanding_line = payment_move_advance.line_ids.filtered(
            lambda l: l.account_id == self.advance_supp_acc and l.debit > 0
        )

        invoice.with_context({}).js_assign_outstanding_line(outstanding_line.id)

        cross_move_advance = self.env['account.move'].search([], order='id desc', limit=1)
        igtf_expected = 16265.8818
        #validacion Asiento de Cruce
        expected_lines = [
            {
                'account': self.advance_supp_acc,      
                'debit': 0.0,       
                'credit': 542196.064,
            },
           
             {
                'account': self.acc_igtf_prov,  
                'debit': igtf_expected,
                'credit': 0.0,       
            },
            {
                'account': self.acc_payable,
                'debit': 542196.064 - igtf_expected,
                'credit': 0.0,   
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
            pay_form.payment_date = fields.Date.today()
            pay_form.foreign_rate = invoice.foreign_rate
            pay_form.save()
            pay_form.amount = payment_amount_vef / invoice.foreign_inverse_rate

        payment_register_wiz_2 = pay_form.record

        action = payment_register_wiz_2.action_create_payments()
        
        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 

        self.assertAlmostEqual(payment_move.currency_id.id, self.currency_vef.id, 2, "Moneda debe ser VEF")
        self.assertAlmostEqual(payment_move.payment_id.amount, payment_amount_vef / invoice.foreign_inverse_rate, 2, "Monto debe ser 270098.032 VEF")
    
        expected_lines = [

            {
                'account': self.acc_payable,      
                'debit': 1345.60 / invoice.foreign_inverse_rate,       
                'credit': 0.0,
            },
           
            {
                'account': self.account_bank,
                'debit': 0.0,
                'credit': 1345.60 / invoice.foreign_inverse_rate,   
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
            pay_form.foreign_rate = invoice.foreign_rate
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
        self.assertAlmostEqual(payment_move.payment_id.amount, advance_amount, 2, "Monto debe ser monto del pago")

        igtf_expected = 8132.9409
        expected_lines = [
            {
                'account': self.account_bank,      
                'debit': 0.0,       
                'credit': advance_amount / invoice.foreign_inverse_rate,
            },
           
             {
                'account': self.acc_igtf_prov,  
                'debit': igtf_expected,
                'credit': 0.0,       
            },
            {
                'account': self.acc_payable,
                'debit': (advance_amount / invoice.foreign_inverse_rate) - igtf_expected,
                'credit': 0.0,   
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
            pay_form.foreign_rate = invoice.foreign_rate
            pay_form.save()
            pay_form.amount = last_advance 

        payment_register_wiz = pay_form.record

        action = payment_register_wiz.action_create_payments()
        
        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 

        self.assertEqual(
            invoice.payment_state, 
            'paid', 
            f"La factura debe estar en estado 'paid' (pagada), estado actual: {invoice.payment_state}"
        )

        self.assertAlmostEqual(payment_move.currency_id.id, self.currency_usd.id, 2, "Moneda debe ser USD")
        self.assertAlmostEqual(payment_move.payment_id.amount, last_advance, 2, "Monto debe ser 270098.032 USD")

        expected_lines = [
            {
                'account': self.account_bank,      
                'debit': 0.0,       
                'credit': last_advance / invoice.foreign_inverse_rate,
            },
           
            {
                'account': self.acc_payable,
                'debit': last_advance / invoice.foreign_inverse_rate,
                'credit': 0.0,   
            },
        ]

        self._assert_move_lines_equal(payment_move, expected_lines)
    
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
            pay_form.foreign_rate = invoice.foreign_rate
            pay_form.save()
            pay_form.amount = payment_amount_vef / invoice.foreign_inverse_rate
        payment_register_wiz_2 = pay_form.record

        action = payment_register_wiz_2.action_create_payments()
        
        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 

        self.assertAlmostEqual(payment_move.currency_id.id, self.currency_vef.id, 2, "Moneda debe ser VEF")
        self.assertAlmostEqual(payment_move.payment_id.amount, payment_amount_vef / invoice.foreign_inverse_rate, 2, "Monto Incorrecto en pago")
    
        expected_lines = [
        
            {
                'account': self.acc_payable,      
                'debit': payment_amount_vef / invoice.foreign_inverse_rate,       
                'credit': 0.0,
            },
           
            {
                'account': self.account_bank,
                'debit': 0.0,
                'credit': payment_amount_vef / invoice.foreign_inverse_rate,   
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
            pay_form.foreign_rate = invoice.foreign_rate
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
        self.assertAlmostEqual(payment_move.payment_id.amount, advance_amount, 2, "Monto debe ser 40.00 USD")

        igtf_expected = (advance_amount * 0.03) / invoice.foreign_inverse_rate
        expected_lines = [
            {
                'account': self.account_bank,      
                'debit': 0.0,       
                'credit': advance_amount / invoice.foreign_inverse_rate,
            },
           
             {
                'account': self.acc_igtf_prov,  
                'debit': igtf_expected,
                'credit': 0.0,       
            },
            {
                'account': self.acc_payable,
                'debit': (advance_amount / invoice.foreign_inverse_rate) - igtf_expected,
                'credit': 0.0,   
            },
        ]

        self._assert_move_lines_equal(payment_move, expected_lines)

        self.assertAlmostEqual(invoice.foreign_amount_residual,51.2 , 2, "Monto residual de la factura debe ser 51.2 usd")


        invoice = self.env['account.move'].browse(invoice.id)

        self.assertAlmostEqual(invoice.bi_igtf, advance_amount , 2, "Bi_igtf DEbe ser 40.00 USD")
        
        action_data_2 = invoice.action_register_payment()
        
        last_advance = 52.7

        with Form(
            self.env['account.payment.register'].with_context(
               action_data_2['context']  
            )
        ) as pay_form:
            
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.foreign_rate = invoice.foreign_rate
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
        self.assertAlmostEqual(payment_move.payment_id.amount, last_advance, 2, "Monto debe ser 40.00 USD")

        expected_lines = [
            {
                'account': self.account_bank,      
                'debit': 0.0,       
                'credit': last_advance / invoice.foreign_inverse_rate,
            },

             {
                'account': self.acc_igtf_prov,  
                'debit': igtf_expected / invoice.foreign_inverse_rate,
                'credit': 0.0,       
            },

            {
                'account': self.acc_payable,
                'debit': (last_advance / invoice.foreign_inverse_rate) - (igtf_expected / invoice.foreign_inverse_rate),
                'credit': 0.0,   
            },
        ]

        self._assert_move_lines_equal(payment_move, expected_lines)
    
        self.assertAlmostEqual(invoice.alter_bi_igtf,1.20 , 2, "Monto BI_igtf de la factura debe ser 1.20 usd")
        self.assertAlmostEqual(invoice.igtf_top_aply, 2.7 , 2, "Igtf Aplicado debe ser 2.7 usd")
        self.assertAlmostEqual(invoice.amount_residual,0.0 , 2, "Monto residual de la factura debe ser 0.0 usd")
        self.assertAlmostEqual(invoice.bi_igtf,90.00  , 2, "Monto Bi_Igtf de la factura debe ser 90.00 usd")

    def test16_payment_from_invoice_with_igtf_journal_desconciliation(self):
        
        invoice_amount = float(542196.0699)
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
            pay_form.foreign_currency_id = self.currency_usd
            pay_form.foreign_rate = invoice.foreign_rate
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
                'debit': 0.0,       
                'credit': payment_amount / invoice.foreign_inverse_rate,
            },
           
            {
                'account': self.acc_payable,
                'debit': cxc_credit_amount,
                'credit': 0.0,   
            },
             {
                'account': self.acc_igtf_prov,  
                'debit': 16265.88179,
                'credit': 0.0,       
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
            lambda l: l.account_id == self.acc_payable and l.debit > 0
        )

        invoice = self.env['account.move'].browse(invoice.id)
        
        invoice_receivable_line = invoice.line_ids.filtered(
            lambda l: l.account_id == self.acc_payable and l.credit > 0
        )

        partial_reconcile = outstanding_line.matched_credit_ids.filtered(
            lambda p: p.credit_move_id == invoice_receivable_line
        )

        self.assertTrue(partial_reconcile, "Debe haberse existir reconciliación.")

        action = invoice.with_context({}).js_remove_outstanding_partial(partial_reconcile.id)

        #if action:
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
            lambda l: l.account_id == self.advance_supp_acc and l.debit > 0
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
            pay_form.foreign_currency_id = self.currency_usd
            pay_form.foreign_rate = invoice.foreign_rate
            pay_form.save()
            pay_form.amount = payment_amount

        payment_register_wiz_2 = pay_form.record

        action = payment_register_wiz_2.action_create_payments()
        
        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 
        
        
        self.assertTrue(payment_move, "Debe haberse creado el asiento de pago asociado al payment.")
        self.assertAlmostEqual(payment.igtf_amount, expected_igtf, 2, "El IGTF calculado debe ser 60.00.")

        cxc_credit_amount = (payment_amount / invoice.foreign_inverse_rate) - (expected_igtf / invoice.foreign_inverse_rate)

        expected_lines = [
            {
                'account': self.account_bank,      
                'debit': 0.0,       
                'credit': payment_amount / invoice.foreign_inverse_rate,
            },
           
            {
                'account': self.acc_payable,
                'debit': cxc_credit_amount,
                'credit': 0.0,   
            },
             {
                'account': self.acc_igtf_prov,  
                'debit': expected_igtf / invoice.foreign_inverse_rate,
                'credit': 0.0,       
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
            lambda l: l.account_id == self.acc_payable and l.debit > 0
        )

        invoice = self.env['account.move'].browse(invoice.id)
        
        invoice_receivable_line = invoice.line_ids.filtered(
            lambda l: l.account_id == self.acc_payable and l.credit > 0
        )

        partial_reconcile = outstanding_line.matched_credit_ids.filtered(
            lambda p: p.credit_move_id == invoice_receivable_line
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
            lambda l: l.account_id == self.advance_supp_acc and l.debit > 0
        )

        invoice.with_context({}).js_assign_outstanding_line(outstanding_line.id)


        invoice = self.env['account.move'].browse(invoice.id)
        self.assertEqual(
            invoice.payment_state, 
            'partial', 
            f"La factura debe estar en estado 'partial' (parcialmente    pagada), estado actual: {invoice.payment_state}"
        )

        self.assertAlmostEqual(invoice.bi_igtf,2000.00, 2, "Bi_igtf DEbe ser 2000.00 USD")

        payment.action_draft()
        payment.action_cancel()
        


        
  