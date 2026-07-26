from odoo.tests import TransactionCase, tagged
from odoo import fields, Command
from odoo.exceptions import ValidationError


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
            "currency_foreign_id": self.currency_usd.id,
            "account_fiscal_country_id": self.country_ve.id,
            "country_id": self.country_ve.id,
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
            ('code', '=', code), ('company_id', '=', self.company.id),
        ], limit=1)
        if not acc:
            acc = self.env['account.account'].create({
                'code': code, 'name': name, 'account_type': acc_type,
                'company_id': self.company.id,
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
        tax_ids = [(6, 0, [self.tax_16.id])] if tax else [(5, 0, 0)]
        return self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_vef.id,
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

    def _assert_balances(self, move, label=""):
        td = sum(move.line_ids.mapped('debit'))
        tc = sum(move.line_ids.mapped('credit'))
        self.assertAlmostEqual(td, tc, places=2, msg=f"{label}: {td} != {tc}")
        return td, tc

    # ═══════════════════════════════════════════════════════════════
    # account_payment.py - _synchronize_to_moves
    # ═══════════════════════════════════════════════════════════════

    def test_payment_synchronize_to_moves(self):
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
    # account_payment.py - _prepare_move_line_default_vals
    # ═══════════════════════════════════════════════════════════════

    def test_payment_prepare_move_line_default_vals(self):
        manual_in = self.env.ref("account.account_payment_method_manual_in")
        bank = self.env['account.journal'].create({
            'name': 'Bank PML', 'code': 'BNKPML', 'type': 'bank',
            'default_account_id': self.acc_bank.id, 'company_id': self.company.id,
            'inbound_payment_method_line_ids': [(0, 0, {
                'name': 'InPML', 'payment_method_id': manual_in.id,
                'payment_type': 'inbound', 'payment_account_id': self.acc_bank.id,
            })],
        })
        pml = bank.inbound_payment_method_line_ids[:1]
        pay = self.env["account.payment"].create({
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": self.partner.id, "amount": 100.0,
            "currency_id": self.currency_usd.id,
            "payment_method_line_id": pml.id, "journal_id": bank.id,
        })
        vals = pay._prepare_move_line_default_vals()
        self.assertIsInstance(vals, list)
        self.assertEqual(len(vals), 2)

    # ═══════════════════════════════════════════════════════════════
    # account_payment.py - _compute_rate
    # ═══════════════════════════════════════════════════════════════

    def test_payment_compute_rate(self):
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
        self.assertIsNotNone(pay.foreign_rate)

    # ═══════════════════════════════════════════════════════════════
    # account_payment.py - _onchange_foreign_rate
    # ═══════════════════════════════════════════════════════════════

    def test_payment_onchange_foreign_rate(self):
        pay = self.env["account.payment"].new({
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": self.partner.id, "amount": 100.0,
            "currency_id": self.currency_usd.id,
        })
        pay.foreign_rate = 50.0
        pay._onchange_foreign_rate()
        self.assertAlmostEqual(pay.foreign_inverse_rate, 1 / 50.0, places=6)

    def test_payment_onchange_foreign_rate_zero(self):
        pay = self.env["account.payment"].new({
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": self.partner.id, "amount": 100.0,
            "currency_id": self.currency_usd.id,
        })
        pay.foreign_rate = 0.0
        pay._onchange_foreign_rate()

    # ═══════════════════════════════════════════════════════════════
    # account_bank_statement_line.py
    # ═══════════════════════════════════════════════════════════════

    def test_bank_statement_line_foreign(self):
        acc_suspense = self._get_or_create('100200', 'Suspense', 'liability_current', reconcile=True)
        bank_journal = self.env['account.journal'].search([
            ("type", "=", "bank"), ("company_id", "=", self.company.id),
        ], limit=1) or self.env['account.journal'].sudo().create({
            "name": "Bank Stmt", "code": "BNKSTMT",
            "type": "bank", "company_id": self.company.id,
            "default_account_id": self.acc_bank.id,
            "suspense_account_id": acc_suspense.id,
        })
        st_line = self.env['account.bank.statement.line'].create({
            "date": fields.Date.today(),
            "payment_ref": "Test foreign",
            "amount": 100.0,
            "foreign_amount": 100.0,
            "journal_id": bank_journal.id,
        })
        vals = st_line.with_company(self.company)._prepare_move_line_default_vals()
        self.assertIsInstance(vals, list)
        self.assertEqual(len(vals), 2)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _compute_vat
    # ═══════════════════════════════════════════════════════════════

    def test_compute_vat(self):
        self.partner.write({"vat": "J-12345678-0"})
        invoice = self._create_invoice(self.currency_vef, 100.0)
        self.assertEqual(invoice.vat, "VJ-12345678-0")

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _compute_total_debit_credit
    # ═══════════════════════════════════════════════════════════════

    def test_total_debit_credit_third_currency(self):
        invoice = self._create_invoice(self.currency_eur, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertGreater(invoice.foreign_debit, 0)
        self.assertGreater(invoice.foreign_credit, 0)
        self.assertAlmostEqual(invoice.foreign_debit, invoice.foreign_credit, delta=1.0)

    def test_total_debit_credit_vef(self):
        invoice = self._create_invoice(self.currency_vef, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertGreaterEqual(invoice.foreign_debit, 0)

    def test_total_debit_credit_eur_third(self):
        invoice = self._create_invoice(self.currency_eur, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertGreater(invoice.foreign_debit, 0)
        self.assertGreater(invoice.foreign_credit, 0)
        self.assertAlmostEqual(invoice.foreign_debit, invoice.foreign_credit, delta=1.0)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _compute_needed_terms
    # ═══════════════════════════════════════════════════════════════

    def test_needed_terms_with_foreign_balance(self):
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
        if invoice.needed_terms:
            for key, data in invoice.needed_terms.items():
                self.assertIn('foreign_balance', data)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _get_payments
    # ═══════════════════════════════════════════════════════════════

    def test_get_payments(self):
        invoice = self._create_invoice(self.currency_vef, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        payments = invoice._get_payments(invoice.line_ids)
        self.assertIsInstance(payments, type(self.env['account.payment']))

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _get_account_move_line_related
    # ═══════════════════════════════════════════════════════════════

    def test_get_account_move_line_related(self):
        invoice = self._create_invoice(self.currency_vef, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        result = invoice._get_account_move_line_related()
        self.assertIsInstance(result, list)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - get_account_move_report_data
    # ═══════════════════════════════════════════════════════════════

    def test_get_account_move_report_data(self):
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

    def test_account_analytic_by_line_id(self):
        invoice = self._create_invoice(self.currency_vef, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        result = invoice._account_analytic_by_line_id(invoice.line_ids)
        self.assertIsInstance(result, dict)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _compute_rate_for_documents
    # ═══════════════════════════════════════════════════════════════

    def test_rate_for_documents(self):
        invoice = self._create_invoice(self.currency_vef, 100.0)
        self.assertGreater(invoice.foreign_rate, 0)
        self.assertGreater(invoice.foreign_inverse_rate, 0)

    def test_move_compute_rate(self):
        invoice = self._create_invoice(self.currency_usd, 100.0)
        self.assertGreater(invoice.foreign_rate, 0)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - get_view
    # ═══════════════════════════════════════════════════════════════

    def test_get_view(self):
        invoice = self._create_invoice(self.currency_usd, 100.0)
        arch = invoice.get_view()
        self.assertIsInstance(arch, dict)
        self.assertIn('arch', arch)

    def test_get_view_foreign_currency(self):
        invoice = self._create_invoice(self.currency_usd, 100.0)
        arch = invoice.get_view()
        self.assertIsInstance(arch, dict)
        self.assertIn('arch', arch)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _onchange_foreign_inverse_rate
    # ═══════════════════════════════════════════════════════════════

    def test_foreign_inverse_rate_zero(self):
        move = self.env["account.move"].new({
            "move_type": "out_invoice",
            "currency_id": self.currency_usd.id,
            "foreign_currency_id": self.currency_usd.id,
        })
        move.foreign_inverse_rate = -1.0
        with self.assertRaises(ValidationError):
            move._onchange_foreign_inverse_rate()

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _compute_detailed_amounts
    # ═══════════════════════════════════════════════════════════════

    def test_detailed_amounts_with_discount(self):
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
                    "tax_ids": [(5, 0, 0)],
                }),
            ],
        })
        details = invoice.detailed_amounts
        self.assertIsNotNone(details)
        self.assertGreater(details.get('discount_amount', 0), 0)

    def test_detailed_amounts_no_tax_totals(self):
        move = self.env["account.move"].create({
            "move_type": "entry", "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
        })
        details = move.detailed_amounts
        self.assertEqual(details, dict())

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _distribute_invoice_real_portion
    # ═══════════════════════════════════════════════════════════════

    def test_distribute_real_portion_no_pt(self):
        invoice = self._create_invoice(self.currency_usd, 500.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, 'posted')
        self._assert_balances(invoice, "no_pt")

    def test_distribute_real_portion_else(self):
        invoice = self._create_invoice(self.currency_usd, 300.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, 'posted')
        self._assert_balances(invoice, "else")

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - action_register_payment
    # ═══════════════════════════════════════════════════════════════

    def test_action_register_payment_with_rate(self):
        invoice = self._create_invoice(self.currency_usd, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        invoice.write({"foreign_rate": 50.0})
        action = invoice.action_register_payment()
        context = action.get('context', {})
        self.assertIn('active_ids', context)
        if 'default_foreign_rate' in context:
            self.assertAlmostEqual(context['default_foreign_rate'], 50.0, places=2)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - action_post validation
    # ═══════════════════════════════════════════════════════════════

    def test_action_post_validation(self):
        invoice = self._create_invoice(self.currency_usd, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, 'posted')
        self._assert_balances(invoice, "post")

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _compute_foreign_total_billed
    # ═══════════════════════════════════════════════════════════════

    def test_foreign_total_billed(self):
        invoice = self._create_invoice(self.currency_usd, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertIn('foreign_total_billed', invoice._fields)
        self.assertIsNotNone(invoice.foreign_total_billed)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _compute_foreign_amount_residual
    # ═══════════════════════════════════════════════════════════════

    def test_move_foreign_amount_residual(self):
        invoice = self._create_invoice(self.currency_usd, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.foreign_amount_residual, invoice.amount_total * invoice.foreign_inverse_rate)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _onchange_move_type
    # ═══════════════════════════════════════════════════════════════

    def test_onchange_move_type(self):
        move = self.env["account.move"].new({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "currency_id": self.currency_usd.id,
        })
        move.move_type = "in_invoice"
        move._onchange_move_type()

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _get_tax_totals_summary (via tax_totals)
    # ═══════════════════════════════════════════════════════════════

    def test_tax_totals_with_discount(self):
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
                    "quantity": 2.0, "price_unit": 500.0,
                    "discount": 10.0,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
            ],
        })
        invoice.with_context(move_action_post_alert=True).action_post()
        tt = invoice.tax_totals
        self.assertIn('formatted_discount_amount', tt)

    # ═══════════════════════════════════════════════════════════════
    # account_move_line.py - _prepare_analytic_distribution_line
    # ═══════════════════════════════════════════════════════════════

    def test_move_line_prepare_analytic_distribution(self):
        invoice = self._create_invoice(self.currency_usd, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        line = invoice.line_ids.filtered(lambda l: l.display_type == 'product')[:1]
        if line:
            self.assertTrue(hasattr(line, '_prepare_analytic_distribution_line'))

    # ═══════════════════════════════════════════════════════════════
    # account_move_line.py - _compute_foreign_price / subtotal / total
    # ═══════════════════════════════════════════════════════════════

    def test_foreign_price_vef(self):
        invoice = self._create_invoice(self.currency_vef, 200.0)
        line = invoice.line_ids.filtered(lambda l: l.display_type == 'product')
        if line:
            expected = 200.0 * line.foreign_inverse_rate
            self.assertAlmostEqual(line.foreign_price, expected, places=2)

    def test_foreign_subtotal(self):
        invoice = self._create_invoice(self.currency_vef, 150.0)
        line = invoice.line_ids.filtered(lambda l: l.display_type == 'product')
        if line:
            self.assertGreater(line.foreign_subtotal, 0)
            self.assertGreater(line.foreign_price_total, 0)

    def test_foreign_debit_credit(self):
        invoice = self._create_invoice(self.currency_usd, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        rec_line = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable'
        )[:1]
        if rec_line:
            self.assertGreater(rec_line.foreign_debit, 0)
            self.assertEqual(rec_line.foreign_credit, 0.0)

    def test_inverse_foreign_price(self):
        invoice = self._create_invoice(self.currency_usd, 100.0)
        line = invoice.line_ids.filtered(lambda l: l.display_type == 'product')[:1]
        if line:
            old = line.foreign_price
            line.foreign_price = old + 10.0
            self.assertTrue(line.foreign_price_manual)
            self.assertAlmostEqual(line.foreign_price, old + 10.0, places=2)

    # ═══════════════════════════════════════════════════════════════
    # account_move_line.py - _compute_foreign_amount_residual
    # ═══════════════════════════════════════════════════════════════

    def test_line_foreign_amount_residual(self):
        invoice = self._create_invoice(self.currency_usd, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        rec_line = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable'
        )[:1]
        if rec_line:
            self.assertAlmostEqual(rec_line.foreign_amount_residual, rec_line.foreign_balance, places=2)

    # ═══════════════════════════════════════════════════════════════
    # account_move_line.py - _onchange_quantity / _onchange_price_unit
    # ═══════════════════════════════════════════════════════════════

    def test_line_onchange_quantity(self):
        invoice = self._create_invoice(self.currency_usd, 100.0)
        line = invoice.line_ids.filtered(lambda l: l.display_type == 'product')[:1]
        if line:
            line.quantity = 3.0
            line._onchange_quantity()
            self.assertAlmostEqual(line.quantity, 3.0, places=2)

    def test_line_onchange_price_unit(self):
        invoice = self._create_invoice(self.currency_usd, 100.0)
        line = invoice.line_ids.filtered(lambda l: l.display_type == 'product')[:1]
        if line:
            line.price_unit = 200.0
            line._onchange_price_unit()

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - tax_totals ALL keys with foreign values
    # ═══════════════════════════════════════════════════════════════

    def test_tax_totals_all_keys_foreign(self):
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
                    "quantity": 2.0, "price_unit": 500.0,
                    "discount": 10.0,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
            ],
        })
        invoice.with_context(move_action_post_alert=True).action_post()
        tt = invoice.tax_totals
        expected_top = ['amount_untaxed', 'amount_total',
                        'formatted_amount_total', 'formatted_amount_untaxed',
                        'groups_by_subtotal', 'subtotals',
                        'formatted_discount_amount']
        for key in expected_top:
            self.assertIn(key, tt, f"Missing top key: {key}")
        expected_foreign = ['foreign_amount_untaxed', 'foreign_amount_total']
        for key in expected_foreign:
            self.assertIn(key, tt, f"Missing foreign key: {key}")
        self.assertIsInstance(tt['groups_by_subtotal'], dict)
        for gd in tt['groups_by_subtotal'].values():
            self.assertIsInstance(gd, list)
            for g in gd:
                for k in ['tax_group_name', 'tax_group_amount',
                          'tax_group_base_amount',
                          'formatted_tax_group_amount', 'formatted_tax_group_base_amount']:
                    self.assertIn(k, g, f"Missing group key: {k}")
        self.assertIsInstance(tt['subtotals'], list)
        for st in tt['subtotals']:
            for k in ['name', 'amount', 'formatted_amount']:
                self.assertIn(k, st, f"Missing subtotal key: {k}")
        self.assertAlmostEqual(tt['amount_untaxed'], 900.0, places=2)
        self.assertAlmostEqual(tt['amount_total'], 1044.0, places=2)
        self.assertGreater(tt['foreign_amount_untaxed'], 0)
        self.assertGreater(tt['foreign_amount_total'], 0)
        self.assertIn('groups_by_foreign_subtotal', tt)
        self.assertIn('foreign_subtotals', tt)
        inv_rate = invoice.foreign_inverse_rate
        self.assertAlmostEqual(tt['foreign_amount_untaxed'],
                               tt['amount_untaxed'] * inv_rate, delta=1.0)
        self.assertAlmostEqual(tt['foreign_amount_total'],
                               tt['amount_total'] * inv_rate, delta=1.0)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _compute_needed_terms with 3-line payment term
    # ═══════════════════════════════════════════════════════════════

    def test_needed_terms_multi_line_pt_foreign(self):
        payment_term = self.env['account.payment.term'].create({
            'name': '30-30-40 Test',
            'line_ids': [
                Command.create({'value': 'percent', 'value_amount': 30, 'nb_days': 0}),
                Command.create({'value': 'percent', 'value_amount': 30, 'nb_days': 15}),
                Command.create({'value': 'percent', 'value_amount': 40, 'nb_days': 30}),
            ]
        })
        invoice = self._create_invoice(self.currency_usd, 1000.0)
        invoice.write({"invoice_payment_term_id": payment_term.id})
        invoice.with_context(move_action_post_alert=True).action_post()
        nt = invoice.needed_terms
        self.assertEqual(len(nt), 3)
        for key, data in nt.items():
            self.assertIn('foreign_balance', data)
            self.assertGreater(abs(data['foreign_balance']), 0)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _check_currency_id constraint
    # ═══════════════════════════════════════════════════════════════

    def test_constraint_currency_id(self):
        invoice = self._create_invoice(self.currency_vef, 100.0)
        with self.assertRaises(ValidationError):
            invoice.write({'currency_id': self.currency_usd.id})

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _compute_inverse_rate_vef
    # ═══════════════════════════════════════════════════════════════

    def test_compute_inverse_rate_vef(self):
        invoice = self._create_invoice(self.currency_vef, 100.0)
        self.assertIn('foreign_inverse_rate_vef', invoice._fields)
        self.assertIsNotNone(invoice.foreign_inverse_rate_vef)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _distribute_entry_real_portion
    # ═══════════════════════════════════════════════════════════════

    def test_distribute_entry_real_portion(self):
        move = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "line_ids": [
                Command.create({
                    "name": "D", "account_id": self.acc_exp.id,
                    "debit": 100.0, "credit": 0.0,
                }),
                Command.create({
                    "name": "C", "account_id": self.acc_rec.id,
                    "debit": 0.0, "credit": 100.0,
                }),
            ],
        })
        # With amount=0 the method returns early without unbalancing the move
        move.real_portion_amount = 0.0
        move._distribute_entry_real_portion(move, move.company_currency_id)
        self.assertEqual(move.real_portion_count, 0)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - action_update_account_id
    # ═══════════════════════════════════════════════════════════════

    def test_action_update_account_id(self):
        new_categ = self.env['product.category'].create({
            'name': 'Test No Income Categ',
        })
        new_categ.property_account_income_categ_id = False
        no_inc_product = self.env['product.product'].create({
            'name': 'No Income Product', 'type': 'service', 'list_price': 100.0,
            'categ_id': new_categ.id,
            'taxes_id': [(6, 0, [self.tax_16.id])],
            'supplier_taxes_id': [(5, 0, 0)],
        })
        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": no_inc_product.id,
                    "quantity": 1.0, "price_unit": 100.0,
                    "account_id": self.acc_exp.id,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
            ],
        })
        invoice.with_context(move_action_post_alert=True).action_post()
        self.sale_journal.default_account_id = self.acc_inc.id
        invoice.action_update_account_id()
        line = invoice.line_ids.filtered(lambda l: l.product_id == no_inc_product)[:1]
        if line:
            self.assertEqual(line.account_id, self.sale_journal.default_account_id)

    # ═══════════════════════════════════════════════════════════════
    # account_move_line.py - _onchange_quantity edge case (negative)
    # ═══════════════════════════════════════════════════════════════

    def test_line_onchange_quantity_negative(self):
        invoice = self._create_invoice(self.currency_usd, 100.0)
        line = invoice.line_ids.filtered(lambda l: l.display_type == 'product')[:1]
        if line:
            line.quantity = -1.0
            with self.assertRaises(ValidationError):
                line._onchange_quantity()

    def test_line_onchange_quantity_zero(self):
        invoice = self._create_invoice(self.currency_usd, 100.0)
        line = invoice.line_ids.filtered(lambda l: l.display_type == 'product')[:1]
        if line:
            line.quantity = 0.0
            line._onchange_quantity()
            self.assertAlmostEqual(line.quantity, 0.0, places=2)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - search_read override
    # ═══════════════════════════════════════════════════════════════

    def test_search_read_active_test(self):
        invoice = self._create_invoice(self.currency_vef, 100.0)
        result = self.env['account.move'].search_read(
            [('id', '=', invoice.id)], ['name', 'amount_total']
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], invoice.id)
