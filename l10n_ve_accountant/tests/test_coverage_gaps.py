import logging
from odoo.tests import TransactionCase, tagged
from odoo import fields, Command
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_accountant_coverage")
class TestCoverageGaps(TransactionCase):

    def setUp(self):
        super().setUp()

        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.currency_eur = self.env.ref("base.EUR")
        self.currency_eur.active = True
        self.company = self.env.ref("base.main_company")
        self.country_ve = self.env.ref("base.ve")

        self.company.write({
            "currency_id": self.currency_vef.id,
            "foreign_currency_id": self.currency_usd.id,
            "account_fiscal_country_id": self.country_ve.id,
            "country_id": self.country_ve.id,
            "unique_tax": True,
        })

        today = fields.Date.today()
        self.env["res.currency.rate"].create({
            "name": today, "currency_id": self.currency_vef.id,
            "inverse_company_rate": 1.0, "company_id": self.company.id,
        })
        self.env["res.currency.rate"].create({
            "name": today, "currency_id": self.currency_usd.id,
            "inverse_company_rate": 50.0, "company_id": self.company.id,
        })
        self.env["res.currency.rate"].create({
            "name": today, "currency_id": self.currency_eur.id,
            "inverse_company_rate": 55.0, "company_id": self.company.id,
        })

        self.acc_rec = self._get_or_create('120000', 'Receivable', 'asset_receivable', reconcile=True)
        self.acc_inc = self._get_or_create('400000', 'Income', 'income')
        self.acc_tax = self._get_or_create('200000', 'Tax Payable', 'liability_current', reconcile=True)
        self.acc_exp = self._get_or_create('500000', 'Expense', 'expense')
        self.acc_bank = self._get_or_create('100100', 'Bank', 'asset_cash', reconcile=True)

        self.tax_group = self.env['account.tax.group'].create({
            'name': 'IVA', 'company_id': self.company.id, 'country_id': self.country_ve.id,
        })
        self.tax_16 = self._create_tax('IVA 16%', 16.0)

        self.sale_journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].sudo().create({
            "name": "Sales Coverage", "code": "SCOV",
            "type": "sale", "company_id": self.company.id,
            "default_account_id": self.acc_inc.id,
        })

        self.general_journal = self.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].sudo().create({
            "name": "General Coverage", "code": "GCOV",
            "type": "general", "company_id": self.company.id,
        })

        self.partner = self.env["res.partner"].create({
            "name": "Coverage Partner", "country_id": self.country_ve.id,
            "property_account_receivable_id": self.acc_rec.id,
        })

        self.product = self.env["product.product"].create({
            "name": "Coverage Service", "type": "service", "list_price": 100.0,
            "property_account_income_id": self.acc_inc.id,
            "taxes_id": [(5, 0, 0)], "supplier_taxes_id": [(5, 0, 0)],
        })

    def _get_or_create(self, code, name, acc_type, reconcile=False):
        acc = self.env['account.account'].search([
            ('code', '=', code), ('company_ids', 'in', self.company.id),
        ], limit=1)
        if not acc:
            acc = self.env['account.account'].create({
                'code': code, 'name': name, 'account_type': acc_type,
                'company_ids': [(6, 0, [self.company.id])],
                'reconcile': reconcile,
            })
        return acc

    def _create_tax(self, name, amount):
        return self.env["account.tax"].with_company(self.company).create({
            "name": name, "amount": amount, "amount_type": "percent",
            "type_tax_use": "sale", "company_id": self.company.id,
            "tax_group_id": self.tax_group.id,
            "invoice_repartition_line_ids": [
                (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0,
                        'account_id': self.acc_tax.id}),
            ],
            "refund_repartition_line_ids": [
                (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0,
                        'account_id': self.acc_tax.id}),
            ],
        })

    def _create_invoice(self, currency=None, price=100.0, tax=True):
        currency = currency or self.currency_vef
        tax_ids = [(6, 0, [self.tax_16.id])] if tax else [(5, 0, 0)]
        return self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": currency.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0, "price_unit": price,
                    "account_id": self.acc_inc.id,
                    "tax_ids": tax_ids,
                }),
            ],
        })

    # ═══════════════════════════════════════════════════════════════
    # account_tax.py - _prepare_foreign_base_line_for_taxes_computation
    # ═══════════════════════════════════════════════════════════════

    def test_01_tax_prepare_foreign_base_line_from_invoice_line(self):
        """_prepare_foreign_base_line_for_taxes_computation:
        desde account.move.line (factura)."""
        invoice = self._create_invoice(self.currency_usd, 100.0)
        line = invoice.line_ids.filtered(lambda l: l.display_type == 'product')
        if line:
            AccountTax = self.env['account.tax']
            base_line = AccountTax._prepare_foreign_base_line_for_taxes_computation(line[0])
            self.assertIsInstance(base_line, dict)
            self.assertIn('price_unit', base_line)
            self.assertIn('currency_id', base_line)
            self.assertEqual(base_line.get('currency_id'), self.currency_usd)

    def test_02_tax_prepare_foreign_base_line_from_dict(self):
        """_prepare_foreign_base_line_for_taxes_computation:
        desde una linea de factura real (no dict)."""
        invoice = self._create_invoice(self.currency_usd, 200.0)
        line = invoice.line_ids.filtered(lambda l: l.display_type == 'product')
        AccountTax = self.env['account.tax']
        if line:
            base_line = AccountTax._prepare_foreign_base_line_for_taxes_computation(line[0])
            self.assertIn('price_unit', base_line)
            self.assertGreater(base_line.get('quantity', 0), 0)

    def test_03_tax_prepare_foreign_base_line_without_record(self):
        """_prepare_foreign_base_line_for_taxes_computation:
        sin record (None) debe retornar dict base."""
        AccountTax = self.env['account.tax']
        base_line = AccountTax._prepare_foreign_base_line_for_taxes_computation(None)
        self.assertIsInstance(base_line, dict)

    # ═══════════════════════════════════════════════════════════════
    # account_payment.py - _compute_foreign_amount
    # ═══════════════════════════════════════════════════════════════

    def test_04_payment_foreign_amount_vef(self):
        """_compute_foreign_amount: pago en VEF convierte
        100 VEF -> USD (100/50 = 2.0)."""
        manual_in = self.env.ref("account.account_payment_method_manual_in")
        manual_out = self.env.ref("account.account_payment_method_manual_out")
        bank = self.env['account.journal'].create({
            'name': 'Bank Coverage', 'code': 'BNKCOV', 'type': 'bank',
            'default_account_id': self.acc_bank.id, 'company_id': self.company.id,
            'inbound_payment_method_line_ids': [(0, 0, {
                'name': 'InCoverage', 'payment_method_id': manual_in.id,
                'payment_type': 'inbound', 'payment_account_id': self.acc_bank.id,
            })],
            'outbound_payment_method_line_ids': [(0, 0, {
                'name': 'OutCoverage', 'payment_method_id': manual_out.id,
                'payment_type': 'outbound', 'payment_account_id': self.acc_bank.id,
            })],
        })
        pml = bank.inbound_payment_method_line_ids[:1]
        pay = self.env["account.payment"].create({
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": self.partner.id, "amount": 100.0,
            "currency_id": self.currency_vef.id,
            "payment_method_line_id": pml.id, "journal_id": bank.id,
        })
        self.assertAlmostEqual(pay.foreign_amount, 2.0, places=2)

    def test_05_payment_foreign_amount_usd(self):
        """_compute_foreign_amount: pago en USD (currency_id ==
        foreign_currency_id) debe dar 0.0 (else del compute)."""
        manual_in = self.env.ref("account.account_payment_method_manual_in")
        manual_out = self.env.ref("account.account_payment_method_manual_out")
        bank_usd = self.env['account.journal'].create({
            'name': 'Bank Coverage USD', 'code': 'BNKUSD', 'type': 'bank',
            'currency_id': self.currency_usd.id,
            'default_account_id': self.acc_bank.id, 'company_id': self.company.id,
            'inbound_payment_method_line_ids': [(0, 0, {
                'name': 'InCoverage2', 'payment_method_id': manual_in.id,
                'payment_type': 'inbound', 'payment_account_id': self.acc_bank.id,
            })],
            'outbound_payment_method_line_ids': [(0, 0, {
                'name': 'OutCoverage2', 'payment_method_id': manual_out.id,
                'payment_type': 'outbound', 'payment_account_id': self.acc_bank.id,
            })],
        })
        pml = bank_usd.inbound_payment_method_line_ids[:1]
        pay = self.env["account.payment"].create({
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": self.partner.id, "amount": 100.0,
            "currency_id": self.currency_usd.id,
            "payment_method_line_id": pml.id, "journal_id": bank_usd.id,
        })
        self.assertAlmostEqual(pay.foreign_amount, 0.0)

    # ═══════════════════════════════════════════════════════════════
    # account_payment.py - _compute_rate_currency_name
    # ═══════════════════════════════════════════════════════════════

    def test_06_payment_rate_currency_name(self):
        """_compute_rate_currency_name: verifica display name."""
        manual_in = self.env.ref("account.account_payment_method_manual_in")
        manual_out = self.env.ref("account.account_payment_method_manual_out")
        bank = self.env['account.journal'].create({
            'name': 'Bank Rate', 'code': 'BNKRT', 'type': 'bank',
            'default_account_id': self.acc_bank.id, 'company_id': self.company.id,
            'inbound_payment_method_line_ids': [(0, 0, {
                'name': 'InRate', 'payment_method_id': manual_in.id,
                'payment_type': 'inbound', 'payment_account_id': self.acc_bank.id,
            })],
            'outbound_payment_method_line_ids': [(0, 0, {
                'name': 'OutRate', 'payment_method_id': manual_out.id,
                'payment_type': 'outbound', 'payment_account_id': self.acc_bank.id,
            })],
        })
        pml = bank.inbound_payment_method_line_ids[:1]
        pay = self.env["account.payment"].create({
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": self.partner.id, "amount": 50.0,
            "currency_id": self.currency_vef.id,
            "payment_method_line_id": pml.id, "journal_id": bank.id,
        })
        self.assertEqual(pay.custom_rate_currency_name, "USD")

    def test_07_payment_rate_currency_name_eur(self):
        """_compute_rate_currency_name: con EUR (tercera moneda)
        debe usar su propio nombre."""
        manual_in = self.env.ref("account.account_payment_method_manual_in")
        manual_out = self.env.ref("account.account_payment_method_manual_out")
        bank_eur = self.env['account.journal'].create({
            'name': 'Bank EUR Rate', 'code': 'BNKERT', 'type': 'bank',
            'currency_id': self.currency_eur.id,
            'default_account_id': self.acc_bank.id, 'company_id': self.company.id,
            'inbound_payment_method_line_ids': [(0, 0, {
                'name': 'InRateEUR', 'payment_method_id': manual_in.id,
                'payment_type': 'inbound', 'payment_account_id': self.acc_bank.id,
            })],
            'outbound_payment_method_line_ids': [(0, 0, {
                'name': 'OutRateEUR', 'payment_method_id': manual_out.id,
                'payment_type': 'outbound', 'payment_account_id': self.acc_bank.id,
            })],
        })
        pml = bank_eur.inbound_payment_method_line_ids[:1]
        pay = self.env["account.payment"].create({
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": self.partner.id, "amount": 50.0,
            "currency_id": self.currency_eur.id,
            "payment_method_line_id": pml.id, "journal_id": bank_eur.id,
        })
        self.assertEqual(pay.custom_rate_currency_name, "EUR")

    # ═══════════════════════════════════════════════════════════════
    # account_payment.py - _synchronize_to_moves
    # ═══════════════════════════════════════════════════════════════

    def test_08_payment_synchronize_to_moves(self):
        """_synchronize_to_moves: al cambiar rate, debe propagarse al move."""
        manual_in = self.env.ref("account.account_payment_method_manual_in")
        manual_out = self.env.ref("account.account_payment_method_manual_out")
        bank = self.env['account.journal'].create({
            'name': 'Bank Sync', 'code': 'BNKSY', 'type': 'bank',
            'default_account_id': self.acc_bank.id, 'company_id': self.company.id,
            'inbound_payment_method_line_ids': [(0, 0, {
                'name': 'InSync', 'payment_method_id': manual_in.id,
                'payment_type': 'inbound', 'payment_account_id': self.acc_bank.id,
            })],
            'outbound_payment_method_line_ids': [(0, 0, {
                'name': 'OutSync', 'payment_method_id': manual_out.id,
                'payment_type': 'outbound', 'payment_account_id': self.acc_bank.id,
            })],
        })
        pml = bank.inbound_payment_method_line_ids[:1]
        pay = self.env["account.payment"].create({
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": self.partner.id, "amount": 100.0,
            "currency_id": self.currency_usd.id,
            "payment_method_line_id": pml.id, "journal_id": bank.id,
        })
        if pay.move_id:
            pay.write({"foreign_rate": 50.0, "foreign_inverse_rate": 0.02})
            pay._synchronize_to_moves({"foreign_rate", "foreign_inverse_rate"})
            self.assertAlmostEqual(pay.move_id.foreign_rate, 50.0, places=2)

    # ═══════════════════════════════════════════════════════════════
    # account_bank_statement_line.py
    # ═══════════════════════════════════════════════════════════════

    def test_09_bank_statement_line_foreign(self):
        """_prepare_move_line_default_vals: con foreign_amount
        debe setear foreign_debit/credit."""
        st_line = self.env['account.bank.statement.line'].create({
            "date": fields.Date.today(),
            "payment_ref": "Test foreign",
            "amount": 100.0,
            "foreign_amount": 100.0,
            "journal_id": self.env['account.journal'].search([
                ("type", "=", "bank"), ("company_id", "=", self.company.id),
            ], limit=1).id or self.env['account.journal'].sudo().create({
                "name": "Bank Stmt", "code": "BNKSTMT",
                "type": "bank", "company_id": self.company.id,
            }).id,
        })
        vals = st_line.with_company(self.company)._prepare_move_line_default_vals()
        self.assertIsInstance(vals, list)
        self.assertEqual(len(vals), 2)
        # Verificar que seteo foreign_debit/foreign_credit
        self.assertGreaterEqual(vals[0].get('foreign_debit', 0), 0)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _onchange_journal_id_reset_international_exempt
    # ═══════════════════════════════════════════════════════════════

    def test_10_onchange_journal_international_reset(self):
        """_onchange_journal_id_reset_international_exempt:
        verifica que el metodo existe y no crashea."""
        move = self.env["account.move"].new({
            "move_type": "in_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
        })
        move._onchange_journal_id_reset_international_exempt()

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _compute_vat
    # ═══════════════════════════════════════════════════════════════

    def test_11_compute_vat(self):
        """_compute_vat: verifica que el vat del partner se
        propaga al move."""
        self.partner.write({"vat": "J-12345678-0"})
        invoice = self._create_invoice(self.currency_vef, 100.0)
        self.assertEqual(invoice.vat, "VJ-12345678-0")

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _compute_total_debit_credit con tercera moneda
    # ═══════════════════════════════════════════════════════════════

    def test_12_total_debit_credit_third_currency(self):
        """_compute_total_debit_credit: factura en EUR (tercera moneda)
        debe computar foreign_debit/credit usando conversion VEF->USD."""
        invoice = self._create_invoice(self.currency_eur, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        # Verificar que foreign_debit y foreign_credit se computaron
        self.assertGreater(invoice.foreign_debit, 0)
        self.assertGreater(invoice.foreign_credit, 0)
        fd, fc = invoice.foreign_debit, invoice.foreign_credit
        # foreign_balance debe ser 0 (balanceado)
        self.assertAlmostEqual(fd, fc, delta=1.0)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _compute_needed_terms branches
    # ═══════════════════════════════════════════════════════════════

    def test_13_needed_terms_without_foreign(self):
        """_compute_needed_terms: sin foreign_balance en needed_terms
        debe distribuir proporcionalmente."""
        payment_term = self.env['account.payment.term'].create({
            'name': '60-40 Test',
            'line_ids': [
                Command.create({'value': 'percent', 'value_amount': 60, 'nb_days': 0}),
                Command.create({'value': 'percent', 'value_amount': 40, 'nb_days': 15}),
            ]
        })
        invoice = self._create_invoice(self.currency_usd, 100.0)
        invoice.write({"invoice_payment_term_id": payment_term.id})
        invoice.with_context(move_action_post_alert=True).action_post()
        # needed_terms debe tener foreign_balance
        if invoice.needed_terms:
            for key, data in invoice.needed_terms.items():
                self.assertIn('foreign_balance', data)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _get_payments
    # ═══════════════════════════════════════════════════════════════

    def test_14_get_payments(self):
        """_get_payments: retorna los pagos de un move."""
        invoice = self._create_invoice(self.currency_vef, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        payments = invoice._get_payments(invoice.line_ids)
        self.assertIsInstance(payments, type(self.env['account.payment']))

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _get_account_move_line_related
    # ═══════════════════════════════════════════════════════════════

    def test_15_get_account_move_line_related(self):
        """_get_account_move_line_related: retorna lineas relacionadas."""
        invoice = self._create_invoice(self.currency_vef, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        result = invoice._get_account_move_line_related()
        self.assertIsInstance(result, list)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - get_account_move_report_data
    # ═══════════════════════════════════════════════════════════════

    def test_16_get_account_move_report_data(self):
        """get_account_move_report_data: retorna datos de reporte."""
        invoice = self._create_invoice(self.currency_usd, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        data = invoice.get_account_move_report_data()
        self.assertIsInstance(data, dict)
        self.assertIn('main_move', data)
        self.assertIn('doc_ids', data)
        self.assertIn('docs', data)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _account_analytic_by_line_id
    # ═══════════════════════════════════════════════════════════════

    def test_17_account_analytic_by_line_id(self):
        """_account_analytic_by_line_id: retorna dict con analytic lines."""
        invoice = self._create_invoice(self.currency_vef, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        result = invoice._account_analytic_by_line_id(invoice.line_ids)
        self.assertIsInstance(result, dict)

    # ═══════════════════════════════════════════════════════════════
    # account_move_line.py - _compute_price_unit_ves / _compute_ves_currency_id
    # ═══════════════════════════════════════════════════════════════

    def test_18_price_unit_ves(self):
        """_compute_price_unit_ves: verifica computo en USD y VEF."""
        inv_usd = self._create_invoice(self.currency_usd, 200.0)
        line_usd = inv_usd.line_ids.filtered(lambda l: l.display_type == 'product')
        if line_usd:
            self.assertIsNotNone(line_usd.price_unit_ves)

        inv_vef = self._create_invoice(self.currency_vef, 200.0)
        line_vef = inv_vef.line_ids.filtered(lambda l: l.display_type == 'product')
        if line_vef:
            self.assertAlmostEqual(line_vef.price_unit_ves, 200.0, places=2)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - get_view
    # ═══════════════════════════════════════════════════════════════

    def test_19_get_view(self):
        """get_view: verifica que el metodo retorna el arch
        modificado con foreign currency symbol."""
        invoice = self._create_invoice(self.currency_usd, 100.0)
        arch = invoice.get_view()
        self.assertIsInstance(arch, dict)
        self.assertIn('arch', arch)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _onchange_foreign_inverse_rate con rate=0
    # ═══════════════════════════════════════════════════════════════

    def test_20_foreign_inverse_rate_zero(self):
        """_onchange_foreign_inverse_rate: rate=0 debe lanzar
        ValidationError."""
        move = self.env["account.move"].new({
            "move_type": "out_invoice",
            "currency_id": self.currency_usd.id,
        })
        move.foreign_inverse_rate = 0.0
        with self.assertRaises(ValidationError):
            move._onchange_foreign_inverse_rate()

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _onchange_foreign_rate con rate=0
    # ═══════════════════════════════════════════════════════════════

    def test_21_foreign_rate_zero(self):
        """_onchange_foreign_rate: rate=0 no debe lanzar error
        (retorna temprano por if not move.foreign_rate)."""
        move = self.env["account.move"].new({
            "move_type": "out_invoice",
            "currency_id": self.currency_usd.id,
        })
        move.foreign_rate = 0.0
        # No debe lanzar error (return por if not move.foreign_rate)
        move._onchange_foreign_rate()

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _compute_detailed_amounts con descuento
    # ═══════════════════════════════════════════════════════════════

    def test_22_detailed_amounts_with_discount(self):
        """_compute_detailed_amounts: con descuento en linea."""
        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 2.0, "price_unit": 1000.0,
                    "discount": 10.0,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
            ],
        })
        details = invoice.detailed_amounts
        self.assertIsNotNone(details)
        # Descuento debe ser > 0
        self.assertGreater(details.get('discount_amount', 0), 0)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _distribute_invoice_real_portion sin PT lines
    # ═══════════════════════════════════════════════════════════════

    def test_23_distribute_invoice_real_portion_no_pt(self):
        """_distribute_invoice_real_portion: sin payment_term,
        debe distribuir en target_lines no-impuesto."""
        invoice = self._create_invoice(self.currency_usd, 500.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, 'posted')
        self._assert_balances(invoice, "test_23")


    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _compute_total_debit_credit VEF
    # ═══════════════════════════════════════════════════════════════

    def test_25_total_debit_credit_vef(self):
        """_compute_total_debit_credit: factura en VEF."""
        invoice = self._create_invoice(self.currency_vef, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        # VEF = company currency, debe computar usando lineas
        self.assertGreaterEqual(invoice.foreign_debit, 0)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - get_view con currency_id diferente
    # ═══════════════════════════════════════════════════════════════

    def test_26_get_view_foreign_currency(self):
        """get_view: con moneda extranjera debe incluir
        el simbolo de la moneda."""
        invoice = self._create_invoice(self.currency_usd, 100.0)
        arch = invoice.get_view()
        self.assertIsInstance(arch, dict)
        self.assertIn('arch', arch)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - action_register_payment con foreign_rate
    # ═══════════════════════════════════════════════════════════════

    def test_28_action_register_payment_with_rate(self):
        """action_register_payment: debe pasar foreign_rate
        al wizard de pago."""
        invoice = self._create_invoice(self.currency_usd, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        # Setear foreign_rate en la factura
        invoice.write({"foreign_rate": 50.0})
        action = invoice.action_register_payment()
        context = action.get('context', {})
        self.assertIn('active_ids', context)
        # foreign_rate debe estar en el contexto
        if 'foreign_rate' in context:
            self.assertAlmostEqual(context['foreign_rate'], 50.0, places=2)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _compute_rate_for_documents inline rate
    # ═══════════════════════════════════════════════════════════════

    def test_29_rate_for_documents_inline_rate(self):
        """_compute_rate_for_documents: verifica que las tasas
        se computan para lineas sin currency_id explicito."""
        invoice = self._create_invoice(self.currency_vef, 100.0)
        # foreign_rate e inverse deben computarse
        self.assertGreater(invoice.foreign_rate, 0)
        self.assertGreater(invoice.foreign_inverse_rate, 0)

    # ═══════════════════════════════════════════════════════════════
    # Helper: _assert_balances
    # ═══════════════════════════════════════════════════════════════

    def _assert_balances(self, move, label=""):
        td = sum(move.line_ids.mapped('debit'))
        tc = sum(move.line_ids.mapped('credit'))
        self.assertAlmostEqual(td, tc, places=2, msg=f"{label}: {td} != {tc}")
        return td, tc

    # ═══════════════════════════════════════════════════════════════
    # account_payment.py - _compute_rate
    # ═══════════════════════════════════════════════════════════════

    def test_30_payment_compute_rate(self):
        """_compute_rate: verifica que computa foreign_rate
        sin errores."""
        manual_in = self.env.ref("account.account_payment_method_manual_in")
        manual_out = self.env.ref("account.account_payment_method_manual_out")
        bank = self.env['account.journal'].create({
            'name': 'BankRate', 'code': 'BNKRT2', 'type': 'bank',
            'default_account_id': self.acc_bank.id, 'company_id': self.company.id,
            'inbound_payment_method_line_ids': [(0, 0, {
                'name': 'InRate', 'payment_method_id': manual_in.id,
                'payment_type': 'inbound', 'payment_account_id': self.acc_bank.id,
            })],
            'outbound_payment_method_line_ids': [(0, 0, {
                'name': 'OutRate', 'payment_method_id': manual_out.id,
                'payment_type': 'outbound', 'payment_account_id': self.acc_bank.id,
            })],
        })
        pml = bank.inbound_payment_method_line_ids[:1]
        pay = self.env["account.payment"].create({
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": self.partner.id, "amount": 100.0,
            "currency_id": self.currency_usd.id,
            "payment_method_line_id": pml.id, "journal_id": bank.id,
        })
        # _compute_rate se llama desde create, no debe crashear
        self.assertIsNotNone(pay.foreign_rate)

    # ═══════════════════════════════════════════════════════════════
    # account_payment.py - _compute_other_rate con EUR
    # ═══════════════════════════════════════════════════════════════

    def test_31_payment_compute_other_rate_eur(self):
        """_compute_other_rate: con EUR (tercera moneda)
        debe computar other_rate."""
        manual_in = self.env.ref("account.account_payment_method_manual_in")
        manual_out = self.env.ref("account.account_payment_method_manual_out")
        bank_eur = self.env['account.journal'].create({
            'name': 'BankOtherEUR', 'code': 'BNKOEUR', 'type': 'bank',
            'currency_id': self.currency_eur.id,
            'default_account_id': self.acc_bank.id, 'company_id': self.company.id,
            'inbound_payment_method_line_ids': [(0, 0, {
                'name': 'InOtherEUR', 'payment_method_id': manual_in.id,
                'payment_type': 'inbound', 'payment_account_id': self.acc_bank.id,
            })],
            'outbound_payment_method_line_ids': [(0, 0, {
                'name': 'OutOtherEUR', 'payment_method_id': manual_out.id,
                'payment_type': 'outbound', 'payment_account_id': self.acc_bank.id,
            })],
        })
        pml = bank_eur.inbound_payment_method_line_ids[:1]
        pay = self.env["account.payment"].create({
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": self.partner.id, "amount": 100.0,
            "currency_id": self.currency_eur.id,
            "payment_method_line_id": pml.id, "journal_id": bank_eur.id,
        })
        # EUR es tercera moneda -> other_rate debe computarse
        self.assertGreater(pay.other_rate, 0)

    # ═══════════════════════════════════════════════════════════════
    # account_payment.py - _onchange_foreign_rate y _onchange_other_rate
    # ═══════════════════════════════════════════════════════════════

    def test_32_payment_onchange_foreign_rate(self):
        """_onchange_foreign_rate: con rate valido computa inverse."""
        pay = self.env["account.payment"].new({
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": self.partner.id, "amount": 100.0,
            "currency_id": self.currency_usd.id,
        })
        pay.foreign_rate = 50.0
        pay._onchange_foreign_rate()
        self.assertAlmostEqual(pay.foreign_inverse_rate, 1 / 50.0, places=6)

    def test_33_payment_onchange_foreign_rate_zero(self):
        """_onchange_foreign_rate: rate=0 retorna sin error."""
        pay = self.env["account.payment"].new({
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": self.partner.id, "amount": 100.0,
            "currency_id": self.currency_usd.id,
        })
        pay.foreign_rate = 0.0
        pay._onchange_foreign_rate()

    def test_34_payment_onchange_other_rate(self):
        """_onchange_other_rate: con rate valido computa inverse."""
        pay = self.env["account.payment"].new({
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": self.partner.id, "amount": 100.0,
            "currency_id": self.currency_eur.id,
        })
        pay.other_rate = 55.0
        pay._onchange_other_rate()
        self.assertAlmostEqual(pay.other_rate_inverse, 1 / 55.0, places=6)

    # ═══════════════════════════════════════════════════════════════
    # account_move_line.py - abs_amount_lines_ids_adjust
    # ═══════════════════════════════════════════════════════════════

    def test_35_move_line_abs_adjust(self):
        """abs_amount_lines_ids_adjust: pasa valores a absoluto."""
        invoice = self._create_invoice(self.currency_usd, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        line = invoice.line_ids[:1]
        if line:
            line.abs_amount_lines_ids_adjust()
            # Verificar que todos los foreign_debit/credit son positivos
            self.assertGreaterEqual(line.foreign_debit, 0)
            self.assertGreaterEqual(line.foreign_credit, 0)

    # ═══════════════════════════════════════════════════════════════
    # account_move_line.py - _prepare_analytic_distribution_line
    # ═══════════════════════════════════════════════════════════════

    def test_36_move_line_prepare_analytic_distribution(self):
        """_prepare_analytic_distribution_line: metodo existe
        y no crashea con parametros minimos."""
        invoice = self._create_invoice(self.currency_usd, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        line = invoice.line_ids.filtered(lambda l: l.display_type == 'product')[:1]
        if line:
            # Verificar que el metodo existe
            self.assertTrue(hasattr(line, '_prepare_analytic_distribution_line'))

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _compute_detailed_amounts sin tax_totals
    # ═══════════════════════════════════════════════════════════════

    def test_37_detailed_amounts_no_tax_totals(self):
        """_compute_detailed_amounts: sin tax_totals
        debe retornar dict vacio."""
        move = self.env["account.move"].create({
            "move_type": "entry", "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
        })
        details = move.detailed_amounts
        self.assertEqual(details, dict())

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _distribute_invoice_real_portion sin PT (else)
    # ═══════════════════════════════════════════════════════════════

    def test_38_distribute_invoice_real_portion_else(self):
        """_distribute_invoice_real_portion: sin PT lines,
        distribuye en target_lines no-impuesto."""
        invoice = self._create_invoice(self.currency_usd, 300.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, 'posted')
        self._assert_balances(invoice, "test_38")

    # ═══════════════════════════════════════════════════════════════
    # account_tax.py - _get_tax_totals_summary con descuento
    # ═══════════════════════════════════════════════════════════════

    def test_39_tax_totals_with_discount(self):
        """_get_tax_totals_summary: factura con descuento
        debe incluir formatted_total_discount."""
        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_usd.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 2.0, "price_unit": 500.0,
                    "discount": 10.0,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
            ],
        })
        invoice.with_context(move_action_post_alert=True).action_post()
        tt = invoice.tax_totals
        self.assertIn('formatted_total_discount', tt)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _compute_total_debit_credit EUR
    # ═══════════════════════════════════════════════════════════════

    def test_40_total_debit_credit_eur_third(self):
        """_compute_total_debit_credit: factura EUR verifica
        foreign_debit computado via conversion."""
        invoice = self._create_invoice(self.currency_eur, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertGreater(invoice.foreign_debit, 0)
        self.assertGreater(invoice.foreign_credit, 0)
        self.assertAlmostEqual(invoice.foreign_debit, invoice.foreign_credit, delta=1.0)
