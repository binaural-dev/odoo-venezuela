import logging
from odoo.tests.common import Form
from odoo.tests import tagged
from odoo.exceptions import UserError, ValidationError
from odoo import Command, fields

from .new_igtf_common_providers import IGTFTestCommon 

_logger = logging.getLogger(__name__)


@tagged("igtf_providers", "igtf_run", "-at_install", "post_install")
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
            expected_debit = expected_line['debit']
            expected_credit = expected_line['credit']

            expected_foreign_debit = expected_line.get('foreign_debit', 0.0)
            expected_foreign_credit = expected_line.get('foreign_credit', 0.0)

            
            found_line = move.line_ids.filtered(lambda l: l.account_id.id == expected_account.id)
            
            
            if not found_line:
                _logger.error(
                    f"FALLA DE LÍNEA: Cuenta esperada NO encontrada: "
                    f"'{expected_account.code}' - '{expected_account.name}'. "
                    f"Líneas reales en el asiento: {[(l.account_id.code, l.account_id.name, l.debit, l.credit) for l in move.line_ids]}"
                )
            else:
                _logger.info(
                    f"LÍNEA ENCONTRADA: Cuenta '{found_line.account_id.code}' - '{found_line.account_id.name}'. "
                    f"Débito Real: {found_line.debit}, Crédito Real: {found_line.credit}"
                )
            
            
            self.assertTrue(found_line, 
                f"Línea contable para la cuenta '{expected_account.code}' ({expected_account.name}) no encontrada.")
            
            
            self.assertAlmostEqual(found_line.debit, expected_debit, 2, 
                f"Débito de la cuenta '{expected_account.code}' incorrecto. Esperado: {expected_debit}, Real: {found_line.debit}")
            
            
            self.assertAlmostEqual(found_line.credit, expected_credit, 2, 
                f"Crédito de la cuenta '{expected_account.code}' incorrecto. Esperado: {expected_credit}, Real: {found_line.credit}")

            if expected_foreign_debit == 0.0 and expected_foreign_credit == 0.0:
                continue  

            self.assertAlmostEqual(found_line.foreign_debit, expected_foreign_debit, 2, 
                f"Débito foraneo de la cuenta '{expected_account.code}' incorrecto. Esperado: {expected_foreign_debit}, Real: {found_line.foreign_debit}")

            self.assertAlmostEqual(found_line.foreign_credit, expected_foreign_credit, 2, 
                f"Crédito foraneo de la cuenta '{expected_account.code}' incorrecto. Esperado: {expected_foreign_credit}, Real: {found_line.foreign_credit}")

        
        total_debit = sum(line.debit for line in move.line_ids)
        total_credit = sum(line.credit for line in move.line_ids)

        self.assertAlmostEqual(total_debit, total_credit, 2, 
            "El asiento no balancea (Débito != Crédito).")
        
        _logger.info("Validación detallada de líneas contables: OK.")

    def test01_payment_from_invoice_with_igtf_journal(self):
        _logger.info("Iniciando test: test01_payment_from_invoice_with_igtf_journal")
        
        invoice_amount = 2681.20
        payment_amount = 2000.00
        
        
        invoice = self._create_invoice_usd(invoice_amount)
        #invoice.with_context(move_action_post_alert=True).action_post()
        

        
        pct = self.company.igtf_percentage 
        expected_igtf = round(payment_amount * pct / 100, 2) 
        cxc_credit_amount = payment_amount - expected_igtf 

        expected_residual = invoice_amount - payment_amount + expected_igtf

        payment_register_wiz = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids
        ).create({})
        
        payment_register_wiz.write({
            'amount': payment_amount, 
            'journal_id': self.bank_journal_usd.id,
            'is_igtf_on_foreign_exchange': True, 
        })

        
        action = payment_register_wiz.action_create_payments()
        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 
        
        
        self.assertTrue(payment_move, "Debe haberse creado el asiento de pago asociado al payment.")
        self.assertAlmostEqual(payment.igtf_amount, expected_igtf, 2, "El IGTF calculado debe ser $60.00.")

        expected_lines = [
            {
                'account': self.account_bank,      
                'debit': 0.0,       
                'credit': payment_amount,
            },
           
            {
                'account': self.acc_payable,
                'debit': cxc_credit_amount,
                'credit': 0.0,
            },
             {
                'account': self.acc_igtf_cli,  
                'debit': expected_igtf,
                'credit': 0.0,       
            },
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
            f"El monto residual de la factura debe ser ${expected_residual}, pero es ${invoice.amount_residual}"
        )
        
        _logger.info("test01_payment_from_invoice_with_igtf_journal superado.")


    def test02_payment_from_invoice_with_igtf_journal(self):
        _logger.info("Iniciando test: test02_payment_from_invoice_with_igtf_journal")

        invoice_amount = 2681.20
        payment_amount = 2000.00
        
        
        invoice = self._create_invoice_usd(invoice_amount)
        #invoice.with_context(move_action_post_alert=True).action_post()
        

        pct = self.company.igtf_percentage
        expected_igtf = round(payment_amount * pct / 100, 2)
        cxc_credit_amount = payment_amount - expected_igtf 

        expected_residual = invoice_amount - payment_amount + expected_igtf

        amount_to_pay_2 = invoice_amount - cxc_credit_amount

        
        payment_register_wiz = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids
        ).create({})
        
        payment_register_wiz.write({
            'amount': payment_amount, 
            'journal_id': self.bank_journal_usd.id,
            'is_igtf_on_foreign_exchange': True, 
        })

        
        action = payment_register_wiz.action_create_payments()
        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id 
        
        
        self.assertTrue(payment_move, "Debe haberse creado el asiento de pago asociado al payment.")
        self.assertAlmostEqual(payment.igtf_amount, expected_igtf, 2, "El IGTF calculado debe ser $60.00.")
        expected_lines = [
            {
                'account': self.account_bank,      
                'debit': 0.0,       
                'credit': payment_amount,
            },
           
            {
                'account': self.acc_payable,
                'debit': cxc_credit_amount,
                'credit': 0.0,
            },
             {
                'account': self.acc_igtf_cli,  
                'debit': expected_igtf,
                'credit': 0.0,       
            },
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
            f"El monto residual de la factura debe ser ${expected_residual}, pero es ${invoice.amount_residual}"
        )
        
        _logger.info("--- PRIMER PAGO SUPERADO. ---")
        _logger.info("--- SEGUNDO PAGO . ---")

        payment_amount_2 = amount_to_pay_2 / (1 - pct / 100) 
        payment_amount_2 = round(payment_amount_2, 2)
        
        expected_igtf_2 = round(payment_amount_2 * pct / 100, 2)
        cxc_credit_amount_2 = payment_amount_2 - expected_igtf_2 
        
        cxc_credit_amount_2 = invoice.amount_residual 

        expected_igtf_2 = round(payment_amount_2 * pct / 100, 2) 

        
        payment_register_wiz_2 = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids
        ).create({})
        
        payment_register_wiz_2.write({
            'amount': payment_amount_2, 
            'journal_id': self.bank_journal_usd.id,
            'is_igtf_on_foreign_exchange': True, 
        })

        
        action_2 = payment_register_wiz_2.action_create_payments()
        payment_2 = self.env['account.payment'].browse(action_2.get('res_id'))
        payment_move_2 = payment_2.move_id 
        
        
        self.assertTrue(payment_move_2, "Debe haberse creado el asiento de pago 2.")
        self.assertAlmostEqual(payment_2.igtf_amount, expected_igtf_2, 2, "El IGTF calculado del pago 2 debe ser correcto.")

        
        expected_lines_2 = [
            {
                'account': self.account_bank,      
                'debit': 0.0,       
                'credit': payment_amount_2,
            },
           
            {
                'account': self.acc_payable,
                'debit': cxc_credit_amount_2,
                'credit': 0.0,
            },
             {
                'account': self.acc_igtf_cli,  
                'debit': expected_igtf_2,
                'credit': 0.0,       
            },
        ]
        
        self._assert_move_lines_equal(payment_move_2, expected_lines_2)

        _logger.info("--- SEGUNDO PAGO SUPERADO. ---")
        
        self.assertEqual(
            invoice.payment_state, 
            'paid', 
            f"La factura debe estar en estado 'paid' o 'in_payment', estado actual: {invoice.payment_state}"
        )

        self.assertAlmostEqual(
            invoice.amount_residual, 
            0.0, 
            2, 
            f"El monto residual final de la factura debe ser $0.00, pero es ${invoice.amount_residual}"
        )
        
        _logger.info("test01_payment_from_invoice_with_igtf_journal completamente superado (pago parcial + pago final).")


    def test03_payment_from_invoice_with_igtf_journal(self):
        _logger.info("Iniciando test: test03_payment_from_invoice_with_igtf_journal - Flujo de Desconciliación")

        invoice_amount = 2681.20
        payment_amount_1 = 2000.00 
        
        invoice = self._create_invoice_usd(invoice_amount)
        #invoice.with_context(move_action_post_alert=True).action_post()
        
        pct = self.company.igtf_percentage 
        expected_igtf_1 = round(payment_amount_1 * pct / 100, 2) 
        cxc_credit_amount_1 = payment_amount_1 - expected_igtf_1 

        expected_residual_1 = invoice_amount - cxc_credit_amount_1
        amount_to_pay_2 = expected_residual_1 
        payment_register_wiz_1 = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids
        ).create({})
        
        payment_register_wiz_1.write({
            'amount': payment_amount_1, 
            'journal_id': self.bank_journal_usd.id,
            'is_igtf_on_foreign_exchange': True, 
        })

        
        action_1 = payment_register_wiz_1.action_create_payments()
        payment_1 = self.env['account.payment'].browse(action_1.get('res_id'))
        payment_move_1 = payment_1.move_id 
        
        
        
        self.assertEqual(invoice.payment_state, 'partial', "Estado incorrecto después del pago 1.")
        self.assertAlmostEqual(invoice.amount_residual, expected_residual_1, 2, "Residual incorrecto después del pago 1.")
        _logger.info("--- PRIMER PAGO SUPERADO. Estado: partial. ---")

        payment_amount_2 = amount_to_pay_2 / (1 - pct / 100)
        payment_amount_2 = round(payment_amount_2, 2)
        
        expected_igtf_2 = round(payment_amount_2 * pct / 100, 2)
        cxc_credit_amount_2 = amount_to_pay_2 
        
        
        payment_register_wiz_2 = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids
        ).create({})
        
        payment_register_wiz_2.write({
            'amount': payment_amount_2, 
            'journal_id': self.bank_journal_usd.id,
            'is_igtf_on_foreign_exchange': True, 
        })

        
        action_2 = payment_register_wiz_2.action_create_payments()
        payment_2 = self.env['account.payment'].browse(action_2.get('res_id'))
        payment_move_2 = payment_2.move_id 
        
        
        expected_lines_2 = [
            {'account': self.account_bank, 'debit': 0.0, 'credit': payment_amount_2},
            {'account': self.acc_payable, 'debit': cxc_credit_amount_2, 'credit': 0.0},
            {'account': self.acc_igtf_cli, 'debit': expected_igtf_2, 'credit': 0.0},
        ]
        self._assert_move_lines_equal(payment_move_2, expected_lines_2)
        
        
        self.assertIn(invoice.payment_state, ('paid', 'in_payment'), "La factura no está pagada antes de desconciliar.")
        self.assertAlmostEqual(invoice.amount_residual, 0.0, 2, "Residual no es $0.00 antes de desconciliar.")
        _logger.info("--- SEGUNDO PAGO Y CONCILIACIÓN INICIAL SUPERADO. Estado: paid. ---")
        
        invoice_receivable_line = invoice.line_ids.filtered(
            lambda l: l.account_id == self.acc_payable and l.credit > 0
        )

        self.assertTrue(invoice_receivable_line, "No se encontró la línea CxC a desconciliar en la factura.")

        _logger.info(invoice_receivable_line.display_name)

        payment_2_receivable_line = payment_move_2.line_ids.filtered(
            lambda l: l.account_id == self.acc_payable and l.debit > 0
        )
        _logger.info(f"Línea CxC del Pago 2 encontrada: {payment_2_receivable_line.mapped(lambda l: (l.account_id.name, l.debit, l.credit))}")
        self.assertTrue(payment_2_receivable_line, "No se encontró la línea CxC del pago 2.")

        partial_reconcile = payment_2_receivable_line.matched_credit_ids.filtered(
            lambda p: p.credit_move_id == invoice_receivable_line
        )
        _logger.info(f"Partial Reconcile encontrado: {partial_reconcile.mapped(lambda p: (p.id, p.credit_move_id.id, p.debit_move_id.id))}")
        self.assertTrue(partial_reconcile, "No se halló la conciliación parcial (account.partial.reconcile) a eliminar.")
        self.assertEqual(len(partial_reconcile), 1, "Se esperaba exactamente una conciliación parcial para el pago 2.")

        invoice.js_remove_outstanding_partial(partial_reconcile.id)

        _logger.info(f"Desconciliación del Pago 2 realizada con éxito usando js_remove_outstanding_partial con Partial ID: {partial_reconcile.id}")

        self.assertEqual(
            invoice.payment_state, 
            'partial', 
            f"Tras la desconciliación, el estado debe volver a 'partial', estado actual: {invoice.payment_state}"
        )

        
        self.assertAlmostEqual(
            invoice.amount_residual, 
            expected_residual_1, 
            2, 
            f"Tras la desconciliación, el residual debe ser ${expected_residual_1}, pero es ${invoice.amount_residual}"
        )

        _logger.info(f"Estado post-desconciliación: {invoice.payment_state}, Residual post-desconciliación: {invoice.amount_residual},esperado: {expected_residual_1}   ")
        
        _logger.info("test03_payment_from_invoice_with_igtf_journal (Flujo Desconciliación) superado.")

    def test04_payment_from_invoice_with_igtf_journal_currency_usd(self):
        _logger.info("Iniciando test: test04_payment_from_invoice_with_igtf_journal_currency_usd - Flujo de Desconciliación ")
        invoice_amount = 2681.20
        payment_amount_1 = 2000.00 
        
        invoice = self._create_invoice_usd(invoice_amount)
        #invoice.with_context(move_action_post_alert=True).action_post()
        
        pct = self.company.igtf_percentage 
        expected_igtf_1 = round(payment_amount_1 * pct / 100, 2) 
        cxc_credit_amount_1 = payment_amount_1 - expected_igtf_1 
        expected_residual_1 = invoice_amount - cxc_credit_amount_1
        amount_to_pay_2 = expected_residual_1 
        payment_register_wiz_1 = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids
        ).create({})
        
        payment_register_wiz_1.write({
            'amount': payment_amount_1, 
            'journal_id': self.bank_journal_usd.id,
            'is_igtf_on_foreign_exchange': True, 
        })

        
        action_1 = payment_register_wiz_1.action_create_payments()
        payment_1 = self.env['account.payment'].browse(action_1.get('res_id'))
        payment_move_1 = payment_1.move_id 
        
        
        
        self.assertEqual(invoice.payment_state, 'partial', "Estado incorrecto después del pago 1.")
        self.assertAlmostEqual(invoice.amount_residual, expected_residual_1, 2, "Residual incorrecto después del pago 1.")
        _logger.info("--- PRIMER PAGO SUPERADO. Estado: partial. ---")
        payment_amount_2 = amount_to_pay_2 / (1 - pct / 100)
        payment_amount_2 = round(payment_amount_2, 2)
        
        expected_igtf_2 = round(payment_amount_2 * pct / 100, 2)
        cxc_credit_amount_2 = amount_to_pay_2 
        
        
        payment_register_wiz_2 = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids
        ).create({})
        
        payment_register_wiz_2.write({
            'amount': payment_amount_2, 
            'journal_id': self.bank_journal_usd.id,
            'is_igtf_on_foreign_exchange': True, 
        })

        
        action_2 = payment_register_wiz_2.action_create_payments()
        payment_2 = self.env['account.payment'].browse(action_2.get('res_id'))
        payment_move_2 = payment_2.move_id 
        
        
        expected_lines_2 = [
            {'account': self.account_bank, 'debit': 0.0, 'credit': payment_amount_2},
            {'account': self.acc_payable, 'debit': cxc_credit_amount_2, 'credit': 0.0},
            {'account': self.acc_igtf_cli, 'debit': expected_igtf_2, 'credit': 0.0},
        ]
        self._assert_move_lines_equal(payment_move_2, expected_lines_2)
        
        
        self.assertIn(invoice.payment_state, ('paid', 'in_payment'), "La factura no está pagada antes de desconciliar.")
        self.assertAlmostEqual(invoice.amount_residual, 0.0, 2, "Residual no es $0.00 antes de desconciliar.")
        _logger.info("--- SEGUNDO PAGO Y CONCILIACIÓN INICIAL SUPERADO. Estado: paid. ---")
        

        
        invoice_receivable_line = invoice.line_ids.filtered(
            lambda l: l.account_id == self.acc_payable and l.credit > 0
        )
        self.assertTrue(invoice_receivable_line, "No se encontró la línea CxC a desconciliar en la factura.")

        
        payment_2_receivable_line = payment_move_2.line_ids.filtered(
            lambda l: l.account_id == self.acc_payable and l.debit > 0
        )
        _logger.info(f"Línea CxC del Pago 2 encontrada: {payment_2_receivable_line.mapped(lambda l: (l.account_id.code, l.debit, l.credit))}")
        self.assertTrue(bool(payment_2_receivable_line), "No se encontró la línea CxC del pago 2.")

        

        partial_reconcile = payment_2_receivable_line.matched_credit_ids.filtered(
            lambda p: p.credit_move_id == invoice_receivable_line
        )

        _logger.info(f"Partial Reconcile encontrado: {partial_reconcile.mapped(lambda p: (p.id, p.debit_move_id.id, p.credit_move_id.id))}")
        self.assertTrue(partial_reconcile, "No se halló la conciliación parcial (account.partial.reconcile) a eliminar.")
        self.assertEqual(len(partial_reconcile), 1, "Se esperaba exactamente una conciliación parcial para el pago 2.")

        invoice.js_remove_outstanding_partial(partial_reconcile.id)

        _logger.info(f"Desconciliación del Pago 2 realizada con éxito usando js_remove_outstanding_partial con Partial ID: {partial_reconcile.id}")

        self.assertEqual(
            invoice.payment_state, 
            'partial', 
            f"Tras la desconciliación, el estado debe volver a 'partial', estado actual: {invoice.payment_state}"
        )

        
        self.assertAlmostEqual(
            invoice.amount_residual, 
            expected_residual_1, 
            2, 
            f"Tras la desconciliación, el residual debe ser ${expected_residual_1}, pero es ${invoice.amount_residual}"
        )

        _logger.info(f"Estado post-desconciliación: {invoice.payment_state}, Residual post-desconciliación: {invoice.amount_residual},esperado: {expected_residual_1}   ")

       
        invoice_receivable_line = invoice.line_ids.filtered(
            lambda l: l.account_id == self.acc_payable and l.credit > 0
        )

        self.assertTrue(invoice_receivable_line, "No se encontró la línea CxC a desconciliar en la factura.")


        payment_1_receivable_line = payment_move_1.line_ids.filtered(
            lambda l: l.account_id == self.acc_payable and l.debit > 0
        )
        _logger.info(f"Línea CxC del Pago 1 encontrada: {payment_1_receivable_line.mapped(lambda l: (l.account_id.code, l.debit, l.credit))}")
        self.assertTrue(bool(payment_1_receivable_line), "No se encontró la línea CxC del pago 1.")

        partial_reconcile = payment_1_receivable_line.matched_credit_ids.filtered(
            lambda p: p.credit_move_id == invoice_receivable_line
        )
        _logger.info(f"Partial Reconcile encontrado: {partial_reconcile.mapped(lambda p: (p.id, p.debit_move_id.id, p.credit_move_id.id))}")
        self.assertTrue(partial_reconcile, "No se halló la conciliación parcial (account.partial.reconcile) a eliminar.")
        self.assertEqual(len(partial_reconcile), 1, "Se esperaba exactamente una conciliación parcial para el pago 1.")

        invoice.js_remove_outstanding_partial(partial_reconcile.id)

        _logger.info(f"Desconciliación del Pago 1 realizada con éxito usando js_remove_outstanding_partial con Partial ID: {partial_reconcile.id}")

        self.assertEqual(
            invoice.payment_state, 
            'not_paid', 
            f"Tras la desconciliación, el estado debe volver a 'not_paid', estado actual: {invoice.payment_state}"
        )

        
        self.assertAlmostEqual(
            invoice.amount_residual, 
            invoice_amount, 
            2, 
            f"Tras la desconciliación, el residual debe ser ${invoice_amount} pero es ${invoice.amount_residual}"
        )
        _logger.info("test04_payment_from_invoice_with_igtf_journal_currency_usd (Flujo Desconciliación Total USD) superado.")


    def test05_payment_from_invoice_with_igtf_journal_mixed_currency(self):
        _logger.info("Iniciando test: test05_payment_from_invoice_with_igtf_journal_mixed_currency - Flujo de Desconciliación (Pago Final en VES)")

        invoice_amount = 2681.20
        payment_amount_1 = 2000.00 
        rate = self.rate 
        
        
        invoice = self._create_invoice_rate(invoice_amount)
        invoice.with_context(move_action_post_alert=True).action_post()
        
        pct = self.company.igtf_percentage 
        expected_igtf_1 = round(payment_amount_1 * pct / 100, 2) 
        cxc_credit_amount_1 = payment_amount_1 - expected_igtf_1 

        
        expected_residual_1 = invoice_amount - cxc_credit_amount_1 
        amount_to_pay_2_usd = expected_residual_1 

        
        payment_register_wiz_1 = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids
        ).create({})

        payment_register_wiz_1.write({
            'amount': payment_amount_1, 'journal_id': self.bank_journal_usd.id,
            'is_igtf_on_foreign_exchange': True, 
        })


        action_1 = payment_register_wiz_1.action_create_payments()
        payment_1 = self.env['account.payment'].browse(action_1.get('res_id'))
        payment_move_1 = payment_1.move_id

        _logger.info("Residual después del primer pago: " + str(invoice.amount_residual))
        self.assertAlmostEqual(payment_1.igtf_amount, expected_igtf_1, 2, "El IGTF calculado debe ser $60.00.")

        expected_lines = [
            {
                'account': self.account_bank,      
                'debit': 0.0,       
                'credit': payment_amount_1,
            },
           
            {
                'account': self.acc_payable,
                'debit': cxc_credit_amount_1,
                'credit': 0.0,
            },
             {
                'account': self.acc_igtf_cli,  
                'debit': expected_igtf_1,
                'credit': 0.0,
            },
        ]

        self._assert_move_lines_equal(payment_move_1, expected_lines)

        self.assertEqual(invoice.payment_state, 'partial')
        _logger.info(f"Por pagar: {invoice.amount_residual}")
        _logger.info("--- PRIMER PAGO (USD) SUPERADO. ---")
        _logger.info("--- SEGUNDO PAGO (Para liquidar el residual, PAGO EN VES) ---")

        cxc_liquidation_ves = expected_residual_1 * rate
        payment_amount_2_ves = cxc_liquidation_ves
        payment_amount_2_ves = round(payment_amount_2_ves, 2) 
        
        
        invoice_1 = self.env['account.move'].browse(invoice.id)

        
        with Form(
            self.env['account.payment.register'].with_context(
                active_model='account.move', active_ids=invoice_1.ids,
                
            )
        ) as pay_form:
            
            
            pay_form.journal_id = self.bank_journal_bs 
            pay_form.currency_id = self.currency_vef
            pay_form.payment_date = fields.Date.today()
            
            pay_form.foreign_currency_id = self.currency_vef 

            pay_form.foreign_rate = invoice.foreign_rate

            pay_form.amount = payment_amount_2_ves
 

        payment_register_wiz_2 = pay_form.record

        action_2 = payment_register_wiz_2.action_create_payments()

        _logger.info('SEGUNDO PAGO REALIZADO' )

        payment_2 = self.env['account.payment'].browse(action_2.get('res_id'))
        payment_move_2 = payment_2.move_id 


        _logger.info('SEGUNDO PAGO VALIDACION ASIENTO')

        expected_lines_2 = [
            {
                'account': self.account_bank_bsf,      
                'debit': 0.0,  
                'foreign_credit':payment_amount_2_ves,   
                'credit': amount_to_pay_2_usd,
            },
           
            {
                'account': self.acc_payable,
                'debit': amount_to_pay_2_usd,
                'credit': 0.0,   
                'foreign_debit':payment_amount_2_ves,   

            }
             
        ]

        _logger.info(expected_lines_2)

        self.assertEqual(
            payment_move_2.state, 
            'posted', 
            f"el estado del pago debe estar en estado 'posted' , estado actual: {payment_move_2.state}"
        )

        self._assert_move_lines_equal(payment_move_2, expected_lines_2)

        _logger.info(invoice_1.payment_state)
        _logger.info('SEGUNDO PAGO VALIDACION ASIENTO SUPERADA')


        self.assertAlmostEqual(invoice_1.amount_residual, 0.0, 2, "Residual no es $0.00 antes de desconciliar.")

        self.assertIn(
            invoice_1.payment_state, 
            ['paid', 'in_payment'], 
            f"La factura debe estar en estado 'paid' o 'in_payment', estado actual: {invoice_1.payment_state}"
        )


        self.assertAlmostEqual(invoice_1.amount_residual, 0.0, 2, "Residual no es $0.00 antes de desconciliar.")
        _logger.info("--- SEGUNDO PAGO (VES) Y CONCILIACIÓN INICIAL SUPERADO. Estado: paid. ---")
        
        
        invoice_receivable_line = invoice_1.line_ids.filtered(
            lambda l: l.account_id == self.acc_payable and l.credit > 0
        )
        self.assertTrue(invoice_receivable_line, "No se encontró la línea CxC a desconciliar en la factura.")

        
        payment_2_receivable_line = payment_move_2.line_ids.filtered(
            lambda l: l.account_id == self.acc_payable and l.debit > 0
        )
        _logger.info(f"Línea CxC del Pago 2 encontrada: {payment_2_receivable_line.mapped(lambda l: (l.account_id.code, l.debit, l.credit))}")
        self.assertTrue(bool(payment_2_receivable_line), "No se encontró la línea CxC del pago 2.")

        
        
        partial_reconcile = payment_2_receivable_line.matched_credit_ids.filtered(
            lambda p: p.credit_move_id == invoice_receivable_line
        )
        _logger.info(f"Partial Reconcile encontrado: {partial_reconcile.mapped(lambda p: (p.id, p.debit_move_id.id, p.credit_move_id.id))}")
        self.assertTrue(partial_reconcile, "No se halló la conciliación parcial (account.partial.reconcile) a eliminar.")
        self.assertEqual(len(partial_reconcile), 1, "Se esperaba exactamente una conciliación parcial para el pago 2.")

        
        
        invoice.js_remove_outstanding_partial(partial_reconcile.id)

        _logger.info(f"Desconciliación del Pago 2 realizada con éxito usando js_remove_outstanding_partial con Partial ID: {partial_reconcile.id}")

        
        self.assertEqual(
            invoice.payment_state, 
            'partial', 
            f"Tras la desconciliación, el estado debe volver a 'partial', estado actual: {invoice.payment_state}"
        )

        
        self.assertAlmostEqual(
            invoice.amount_residual, 
            expected_residual_1, 
            2, 
            f"Tras la desconciliación, el residual debe ser ${expected_residual_1}, pero es ${invoice.amount_residual}"
        )

        _logger.info(f"Estado post-desconciliación: {invoice.payment_state}, Residual post-desconciliación: {invoice.amount_residual},esperado: {expected_residual_1}   ")

        invoice_receivable_line = invoice.line_ids.filtered(
            lambda l: l.account_id == self.acc_payable and l.credit > 0
        )
        self.assertTrue(invoice_receivable_line, "No se encontró la línea CxC a desconciliar en la factura.")


        payment_1_receivable_line = payment_move_1.line_ids.filtered(
            lambda l: l.account_id == self.acc_payable and l.debit > 0
        )
        _logger.info(f"Línea CxC del Pago 1 encontrada: {payment_1_receivable_line.mapped(lambda l: (l.account_id.code, l.debit, l.credit))}")
        self.assertTrue(bool(payment_1_receivable_line), "No se encontró la línea CxC del pago 1.")

        partial_reconcile = payment_1_receivable_line.matched_credit_ids.filtered(
            lambda p: p.credit_move_id == invoice_receivable_line
        )
        _logger.info(f"Partial Reconcile encontrado: {partial_reconcile.mapped(lambda p: (p.id, p.debit_move_id.id, p.credit_move_id.id))}")
        self.assertTrue(partial_reconcile, "No se halló la conciliación parcial (account.partial.reconcile) a eliminar.")
        self.assertEqual(len(partial_reconcile), 1, "Se esperaba exactamente una conciliación parcial para el pago 1.")

        invoice.js_remove_outstanding_partial(partial_reconcile.id)

        _logger.info(f"Desconciliación del Pago 1 realizada con éxito usando js_remove_outstanding_partial con Partial ID: {partial_reconcile.id}")

        self.assertEqual(
            invoice.payment_state, 
            'not_paid', 
            f"Tras la desconciliación total, el estado debe volver a 'not_paid', estado actual: {invoice.payment_state}"
        )

        
        self.assertAlmostEqual(
            invoice.amount_residual, 
            invoice_amount, 
            2, 
            f"Tras la desconciliación total, el residual debe ser ${invoice_amount}, pero es ${invoice.amount_residual}"
        )
        
        _logger.info("test05_payment_from_invoice_with_igtf_journal_mixed_currency (Flujo Desconciliación Total Mixta) superado.")


    def test06_payment_from_invoice_with_overpayment_and_reconciliation(self):
        _logger.info("Iniciando test: Flujo de Sobrepago (4036.80) con Sobrante y Conciliación de Factura Secundaria (950.00)")

        # --- Variables y Configuración Inicial ---
        invoice_amount_1 = 2681.20 # Monto de la Factura 1 original
        payment_amount_1 = 4036.80 # Monto del Primer Pago (Sobrepago)
        invoice_amount_2 = 950.00  # Monto de la Factura 2
        
        # Asumimos que self.company.igtf_percentage es 3.0
        pct = self.company.igtf_percentage 

        # --- Cálculos Esperados para el Sobrepago ---
        # IGTF calculado sobre el monto total del pago
        expected_igtf_1 = round(payment_amount_1 * pct / 100, 2) # 4036.80 * 0.03 = 121.10
        # Monto que realmente se aplica a la cuenta por cobrar/pagar
        cxc_credit_amount_1 = payment_amount_1 - expected_igtf_1  # 4036.80 - 121.10 = 3915.70

        # Sobrante inicial después de liquidar la Factura 1
        sobrante_1 = cxc_credit_amount_1 - invoice_amount_1 # 3915.70 - 2681.20 = 1234.50
        
        _logger.info(f"Factura 1 (Original): {invoice_amount_1}")
        _logger.info(f"Pago 1 (Total): {payment_amount_1}, IGTF: {expected_igtf_1}, Crédito Aplicado (CxC/CxP): {cxc_credit_amount_1}")
        _logger.info(f"Sobrante Inicial (Crédito Pendiente): {sobrante_1}")
        
        # --- 1. Creación y Registro de Factura 1 ---
        invoice_1 = self._create_invoice_rate(invoice_amount_1)
        invoice_1.with_context(move_action_post_alert=True).action_post()
        
        # --- 2. Primer Pago (Sobrepago) ---
        payment_register_wiz_1 = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice_1.ids
        ).create({})

        payment_register_wiz_1.write({
            'amount': payment_amount_1, 
            'journal_id': self.bank_journal_usd.id,
            'is_igtf_on_foreign_exchange': True, 
        })

        action_1 = payment_register_wiz_1.action_create_payments()
        payment_1 = self.env['account.payment'].browse(action_1.get('res_id'))
        payment_move_1 = payment_1.move_id

        # --- 3. Verificación de Asientos del Primer Pago (Sobrepago) ---
        if 'is_advance_payment' in payment_1._fields:
            self.assertFalse(payment_1.is_advance_payment, 
                "El pago de sobrepago debería estar marcado como 'is_advance_payment' False.")
            _logger.info(f"VALIDACIÓN CAMPO: 'is_advance_payment' existe. Valor: {payment_1.is_advance_payment}")
        else:
            _logger.warning("VALIDACIÓN CAMPO: El campo 'is_advance_payment' no existe en el modelo 'account.payment'. Omitiendo validación de valor.")
        
        _logger.info("Verificando asientos del Pago 1 (Sobrepago)...")
        
        # El asiento debe reflejar: Banco (Crédito), CxC/CxP (Débito, con sobrante), Gasto IGTF (Débito)
        expected_lines_1 = [
            {
                'account': self.account_bank,      
                'debit': 0.0,       
                'credit': payment_amount_1,
            },
            {
                'account': self.acc_payable, # Línea que recibe el crédito aplicado y tendrá el sobrante
                'debit': cxc_credit_amount_1,
                'credit': 0.0,
            },
            {
                'account': self.acc_igtf_cli,  
                'debit': expected_igtf_1,
                'credit': 0.0,
            },
        ]
        self._assert_move_lines_equal(payment_move_1, expected_lines_1)
        _logger.info("Asientos del Pago 1 verificados correctamente.")

        # Verificar que la Factura 1 quede totalmente pagada
        self.assertEqual(invoice_1.payment_state, 'paid', "La Factura 1 debe quedar totalmente pagada ('paid') debido al sobrepago.")
        self.assertAlmostEqual(invoice_1.amount_residual, 0.0, 2, "Residual de Factura 1 debe ser $0.00.")
        _logger.info("Factura 1 pagada totalmente. Sobrante inicial de $" + str(sobrante_1) + " pendiente de conciliar.")

        # --- 4. Registro de Factura 2 ---
        _logger.info(f"Registrando Factura 2 por: {invoice_amount_2}")
        
        invoice_2 = self._create_invoice_rate(invoice_amount_2)
        invoice_2.with_context(move_action_post_alert=True).action_post()
        
        self.assertEqual(invoice_2.payment_state, 'not_paid', "La Factura 2 debe iniciar en estado 'not_paid'.")

        # --- 5. Conciliación y Aplicación del Sobrante desde el Widget (Segundo "Pago") ---
        
        # 5a. Encontrar la línea de crédito pendiente (sobrante) del Pago 1
        outstanding_line = payment_move_1.line_ids.filtered(
            lambda l: l.account_id == self.acc_payable and l.debit > 0
        )
        
        self.assertTrue(outstanding_line, "Error: No se encontró la línea contable del sobrante para conciliar.")
        
        # Usamos js_assign_outstanding_line para simular la acción del widget de conciliación
        outstanding_line_id = outstanding_line.id
        
        _logger.info(f"Aplicando crédito pendiente (ID {outstanding_line_id}) a Factura 2 por {invoice_amount_2}")
        invoice_2.js_assign_outstanding_line(outstanding_line_id)
        _logger.info("Sobrante aplicado a Factura 2.")

        # Encontrar la línea CxC/CxP de la Factura 2 para las verificaciones
        invoice_2_payable_line = invoice_2.line_ids.filtered(
            lambda l: l.account_id == self.acc_payable and l.credit > 0
        )
        self.assertTrue(invoice_2_payable_line, "Error: No se encontró la línea CxC/CxP (Crédito) de la Factura 2.")

        # 5b. VERIFICACIÓN DEL ASIENTO/REGISTRO DE CONCILIACIÓN (Segundo "Pago")
        # Buscamos el registro account.partial.reconcile que confirma que el crédito se aplicó.
        partial_reconcile = outstanding_line.matched_credit_ids.filtered(
            lambda p: p.credit_move_id == invoice_2_payable_line
        )
        
        self.assertTrue(partial_reconcile, "Error: No se encontró el registro de conciliación parcial (asiento de aplicación del crédito).")
        self.assertAlmostEqual(partial_reconcile.amount, invoice_amount_2, 2, 
                            "El monto conciliado en el registro de conciliación es incorrecto.")
        
        
        _logger.info("Asiento/Registro de Conciliación de Factura 2 (Aplicación de Crédito) verificado. Monto conciliado: " + str(partial_reconcile.amount))

        # --- 6. Verificación Final (Factura 2 y Sobrante) ---
        _logger.info("Verificando Factura 2 y Sobrante Final...")
        
        # Factura 2 debe quedar 'paid'
        self.assertEqual(invoice_2.payment_state, 'paid', "La Factura 2 debe quedar totalmente pagada ('paid').")
        self.assertAlmostEqual(invoice_2.amount_residual, 0.0, 2, "Residual de Factura 2 debe ser $0.00.")
        
        # Verificación de la línea contable de Factura 2 (residual debe ser 0.0)
        self.assertAlmostEqual(
            invoice_2_payable_line.amount_residual, 
            0.0, 
            2, 
            "La línea CxC/CxP de la Factura 2 no está completamente liquidada (residual 0.0)."
        )
        _logger.info("Factura 2: Línea CxC/CxP totalmente liquidada (residual 0.0).")
        
        # Verificar el sobrante final
        sobrante_final = sobrante_1 - invoice_amount_2 # 1234.50 - 950.00 = 284.50
        
        # Recargar la línea de pago para ver el residual después de la conciliación
        #outstanding_line.invalidate_cache()
        
        self.assertAlmostEqual(
            outstanding_line.amount_residual, 
            sobrante_final, 
            2, 
            f"El sobrante final esperado es ${sobrante_final}, pero el residual de la línea es ${outstanding_line.amount_residual}"
        )
        
        _logger.info(f"Sobrante final verificado en la línea de pago: ${sobrante_final}.")
        _logger.info("Test de Flujo de Sobrepago y Conciliación superado.")

    def test07_payment_from_invoice_with_overpayment_and_reconciliation(self):
        _logger.info("Iniciando test: Flujo de Sobrepago (4036.80) con Sobrante y Conciliación de Factura Secundaria (950.00) y posterior DESCONCILIACIÓN.")

        # --- Variables y Configuración Inicial ---
        invoice_amount_1 = 2681.20 # Monto de la Factura 1 original
        payment_amount_1 = 4036.80 # Monto del Primer Pago (Sobrepago)
        invoice_amount_2 = 950.00  # Monto de la Factura 2
        
        # Asumimos que self.company.igtf_percentage es 3.0
        pct = self.company.igtf_percentage 

        # --- Cálculos Esperados para el Sobrepago ---
        # IGTF calculado sobre el monto total del pago
        expected_igtf_1 = round(payment_amount_1 * pct / 100, 2) # 4036.80 * 0.03 = 121.10
        # Monto que realmente se aplica a la cuenta por cobrar/pagar
        cxc_credit_amount_1 = payment_amount_1 - expected_igtf_1  # 4036.80 - 121.10 = 3915.70

        # Sobrante inicial después de liquidar la Factura 1
        sobrante_1 = cxc_credit_amount_1 - invoice_amount_1 # 3915.70 - 2681.20 = 1234.50
        
        _logger.info(f"Factura 1 (Original): {invoice_amount_1}")
        _logger.info(f"Pago 1 (Total): {payment_amount_1}, IGTF: {expected_igtf_1}, Crédito Aplicado (CxC/CxP): {cxc_credit_amount_1}")
        _logger.info(f"Sobrante Inicial (Crédito Pendiente): {sobrante_1}")
        
        # --- 1. Creación y Registro de Factura 1 ---
        invoice_1 = self._create_invoice_rate(invoice_amount_1)
        invoice_1.with_context(move_action_post_alert=True).action_post()
        
        # --- 2. Primer Pago (Sobrepago) ---
        payment_register_wiz_1 = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice_1.ids
        ).create({})

        payment_register_wiz_1.write({
            'amount': payment_amount_1, 
            'journal_id': self.bank_journal_usd.id,
            'is_igtf_on_foreign_exchange': True, 
        })

        action_1 = payment_register_wiz_1.action_create_payments()
        payment_1 = self.env['account.payment'].browse(action_1.get('res_id'))
        payment_move_1 = payment_1.move_id

        # 🚩 INICIO: Validación del campo 'is_advance_payment' en account.payment
        if 'is_advance_payment' in payment_1._fields:
            self.assertFalse(payment_1.is_advance_payment, 
                "El pago de sobrepago NO debería estar marcado como 'is_advance_payment' True.")
            _logger.info(f"VALIDACIÓN CAMPO: 'is_advance_payment' existe. Valor: {payment_1.is_advance_payment}")
        else:
            _logger.warning("VALIDACIÓN CAMPO: El campo 'is_advance_payment' no existe en el modelo 'account.payment'. Omitiendo validación de valor.")
        # 🚩 FIN: Validación del campo 'is_advance_payment'

        # --- 3. Verificación de Asientos del Primer Pago (Sobrepago) ---
        _logger.info("Verificando asientos del Pago 1 (Sobrepago)...")
        
        # VALIDACIÓN DEL PAGO 1: El asiento debe reflejar: Banco (Crédito), CxC/CxP (Débito, con sobrante), Gasto IGTF (Débito)
        expected_lines_1 = [
            {
                'account': self.account_bank,      
                'debit': 0.0,       
                'credit': payment_amount_1,
            },
            {
                'account': self.acc_payable, # Línea que recibe el crédito aplicado y tendrá el sobrante
                'debit': cxc_credit_amount_1,
                'credit': 0.0,
            },
            {
                'account': self.acc_igtf_cli,  
                'debit': expected_igtf_1,
                'credit': 0.0,
            },
        ]
        self._assert_move_lines_equal(payment_move_1, expected_lines_1)
        _logger.info("Asientos del Pago 1 verificados correctamente.")

        # Línea de débito del Pago 1 (línea de crédito pendiente/sobrante)
        outstanding_line = payment_move_1.line_ids.filtered(
            lambda l: l.account_id == self.acc_payable and l.debit > 0
        )
        
        # Línea de crédito de la Factura 1 (deuda)
        invoice_1_payable_line = invoice_1.line_ids.filtered(
            lambda l: l.account_id == self.acc_payable and l.credit > 0
        )
        
        # --- 4. Registro de Factura 2 ---
        _logger.info(f"Registrando Factura 2 por: {invoice_amount_2}")
        
        invoice_2 = self._create_invoice_rate(invoice_amount_2)
        invoice_2.with_context(move_action_post_alert=True).action_post()
        
        self.assertEqual(invoice_2.payment_state, 'not_paid', "La Factura 2 debe iniciar en estado 'not_paid'.")

        # --- 5. Conciliación y Aplicación del Sobrante (Segundo "Pago") ---
        
        # 5a. Aplicación del sobrante a Factura 2
        outstanding_line_id = outstanding_line.id
        
        _logger.info(f"Aplicando crédito pendiente (ID {outstanding_line_id}) a Factura 2 por {invoice_amount_2}")
        invoice_2.js_assign_outstanding_line(outstanding_line_id)
        _logger.info("Sobrante aplicado a Factura 2. Ambas facturas en 'paid'.")

        # Encontrar la línea CxC/CxP de la Factura 2 para las verificaciones
        invoice_2_payable_line = invoice_2.line_ids.filtered(
            lambda l: l.account_id == self.acc_payable and l.credit > 0
        )
        self.assertTrue(invoice_2_payable_line, "Error: No se encontró la línea CxC/CxP (Crédito) de la Factura 2.")
        
        # Verificar que ambas facturas están pagadas
        invoice_1 = self.env['account.move'].browse(invoice_1.id)
        invoice_2 = self.env['account.move'].browse(invoice_2.id)
        self.assertEqual(invoice_1.payment_state, 'paid', "Factura 1 debe estar pagada.")
        self.assertEqual(invoice_2.payment_state, 'paid', "Factura 2 debe estar pagada.")

        # --- 6. DESCONCILIACIÓN (Un-Reconcile) ---
        
        _logger.info("INICIANDO PROCESO DE DESCONCILIACIÓN (Orden: Factura 1, luego Factura 2).")
        
        # 6a. Desconciliar Factura 1 (Conciliación entre Pago 1 y Factura 1)
        # partial_reconcile_1: Registro de la aplicación de $2681.20
        partial_reconcile_1 = outstanding_line.matched_credit_ids.filtered(
            lambda p: p.credit_move_id == invoice_1_payable_line
        )
        self.assertTrue(partial_reconcile_1, "Error: No se encontró el registro de conciliación parcial para Factura 1.")

        invoice_1.js_remove_outstanding_partial(partial_reconcile_1.id)
        _logger.info("6a. Desconciliación de Factura 1 (Pago Inicial) realizada con éxito.")

        # Validar estado de Factura 1
        #invoice_1.refresh()
        self.assertEqual(invoice_1.payment_state, 'not_paid', "La Factura 1 debe volver a 'not_paid' después de desconciliar.")

        
        # 6b. Desconciliar Factura 2 (Conciliación entre Sobrante y Factura 2)
        # partial_reconcile_2: Registro de la aplicación de $950.00
        partial_reconcile_2 = outstanding_line.matched_credit_ids.filtered(
            lambda p: p.credit_move_id == invoice_2_payable_line
        )
        self.assertTrue(partial_reconcile_2, "Error: No se encontró el registro de conciliación parcial para Factura 2.")
        
        invoice_2.js_remove_outstanding_partial(partial_reconcile_2.id)
        _logger.info("6b. Desconciliación de Factura 2 (Uso de Sobrante) realizada con éxito.")
        
        # Validar estado de Factura 2
        #invoice_2.refresh()
        self.assertEqual(invoice_2.payment_state, 'not_paid', "La Factura 2 debe volver a 'not_paid' después de desconciliar.")

        # --- 7. VALIDACIÓN FINAL DEL PAGO (Crédito Pendiente) ---
        
        # Recargar la línea de débito del Pago 1 para verificar el residual
        #outstanding_line.invalidate_cache() 

        _logger.info("Verificando estado final de las líneas contables.")

        # El residual de la línea de Pago 1 debe ser igual al monto total del crédito aplicado (cxc_credit_amount_1)
        # Ya que ambas conciliaciones fueron deshechas, el monto completo es un sobrante/crédito pendiente.
        self.assertAlmostEqual(
            outstanding_line.amount_residual,
            cxc_credit_amount_1,
            2,
            f"El residual final de la línea de Pago 1 debe ser el monto original del crédito ({cxc_credit_amount_1}), pero es {outstanding_line.amount_residual}"
        )
        
        # La línea de pago no debe tener registros de conciliación asociados
        self.assertFalse(outstanding_line.matched_credit_ids, "La línea de Pago 1 no debe tener registros de conciliación pendientes.")
        
        _logger.info(f"RESULTADO FINAL: Sobrante/Crédito pendiente: ${outstanding_line.amount_residual} (Original: ${cxc_credit_amount_1}).")
        _logger.info("Test de Desconciliación superado.")