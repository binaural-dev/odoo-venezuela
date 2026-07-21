import logging
from odoo.tests import TransactionCase, tagged
from odoo import fields, Command
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_accountant")
class TestAccountMoveLinePhase1(TransactionCase):

    def setUp(self):
        super().setUp()
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")
        self.company.write({
            "currency_id": self.currency_usd.id,
            "currency_foreign_id": self.currency_vef.id,
        })
        self.Line = self.env['account.move.line']
        self.Move = self.env['account.move']

        self._ensure_rate(self.currency_usd.id, '2025-07-28', 120.439)
        self._ensure_rate(self.currency_vef.id, '2025-07-28', 120.439)

        self.bank_journal = (
            self.env['account.journal'].search(
                [("type", "=", "bank"), ("currency_id", "=", self.currency_usd.id), ("company_id", "=", self.company.id)],
                limit=1,
            )
            or self.env['account.journal'].create({
                "name": "Banco USD", "code": "BNKUS", "type": "bank",
                "currency_id": self.currency_usd.id,
            })
        )

        self.tax_iva16 = self.env['account.tax'].create({
            'name': 'IVA 16%', 'amount': 16, 'amount_type': 'percent',
            'type_tax_use': 'sale', 'company_id': self.company.id,
        })

        self.product = self.env['product.product'].create({
            'name': 'Producto', 'type': 'service', 'list_price': 100,
            'taxes_id': [(6, 0, [self.tax_iva16.id])], 'company_id': False,
        })

        self.partner = self.env['res.partner'].create({
            'name': 'Partner A', 'customer_rank': 1, 'company_id': False,
        })

        self.sale_journal = (
            self.env['account.journal'].search([
                ('type', '=', 'sale'), ('company_id', '=', self.company.id)
            ], limit=1)
            or self.env['account.journal'].create({
                'name': 'Sales', 'code': 'SAJT', 'type': 'sale',
                'company_id': self.company.id,
            })
        )

        self.account_income = self.env['account.account'].create({
            'name': 'VENTAS', 'code': '703000', 'account_type': 'income',
        })

        display_sel = dict(self.Line._fields['display_type'].selection or [])
        self.display_product = 'product' in display_sel

    def _ensure_rate(self, currency_id, date_str, inverse_rate):
        existing = self.env['res.currency.rate'].search([
            ('currency_id', '=', currency_id),
            ('company_id', '=', self.company.id),
            ('name', '=', fields.Date.from_string(date_str)),
        ], limit=1)
        if not existing:
            self.env['res.currency.rate'].create({
                'name': fields.Date.from_string(date_str),
                'currency_id': currency_id,
                'inverse_company_rate': inverse_rate,
                'company_id': self.company.id,
            })

    def _make_invoice(self, lines=None, **kw):
        dt = 'product' if self.display_product else False
        if lines is None:
            lines = [{'name': 'L1', 'product': self.product, 'qty': 1, 'price': 100, 'taxes': [self.tax_iva16.id]}]
        inv_lines = []
        for ld in lines:
            line_display = ld.get('display_type', dt)
            if line_display is True:
                line_display = dt
            v = {
                'name': ld.get('name', 'L'),
                'product_id': ld.get('product') and ld['product'].id or False,
                'quantity': ld.get('qty', 1),
                'price_unit': ld.get('price', 100),
                'account_id': ld.get('account') and ld['account'].id or (self.account_income.id if line_display == 'product' else False),
                'tax_ids': [(6, 0, ld.get('taxes', []))],
            }
            if line_display:
                v['display_type'] = line_display
            inv_lines.append(Command.create(v))
        return self.Move.create({
            'move_type': kw.get('move_type', 'out_invoice'),
            'partner_id': self.partner.id,
            'invoice_date': kw.get('date', fields.Date.from_string('2025-07-28')),
            'journal_id': self.sale_journal.id,
            'invoice_line_ids': inv_lines,
        })

    def _post(self, inv):
        inv.with_context(move_action_post_alert=True).action_post()

    # ---- Foreign Price ----

    def test_foreign_price_computed(self):
        inv = self._make_invoice()
        line = inv.invoice_line_ids[:1]
        self.assertTrue(line.foreign_price > 0)
        self.assertAlmostEqual(line.foreign_price, line.price_unit * line.foreign_inverse_rate, places=4)

    # ---- Foreign Subtotal ----

    def test_foreign_subtotal_last_line_rounding(self):
        if not self.display_product:
            self.skipTest("display_type='product' not supported")
        inv = self._make_invoice(lines=[
            {'name': 'A', 'product': self.product, 'qty': 3, 'price': 33.33, 'taxes': [self.tax_iva16.id], 'display_type': True},
            {'name': 'B', 'product': self.product, 'qty': 1, 'price': 100, 'taxes': [self.tax_iva16.id], 'display_type': True},
        ])
        lines = inv.invoice_line_ids.filtered(lambda l: l.display_type == 'product')
        target = sum(l.foreign_price * l.quantity * (1 - l.discount / 100) for l in lines)
        accumulated = sum(l.foreign_subtotal for l in lines[:-1])
        last = lines[-1]
        self.assertAlmostEqual(last.foreign_subtotal, target - accumulated, places=2)

    # ---- Foreign Debit/Credit ----

    def test_calculate_from_product(self):
        if not self.display_product:
            self.skipTest("display_type='product' not supported")
        inv = self._make_invoice(lines=[
            {'name': 'Prod', 'product': self.product, 'qty': 1, 'price': 100, 'taxes': [self.tax_iva16.id], 'display_type': True},
        ])
        self._post(inv)
        prod_line = inv.line_ids.filtered(lambda l: l.display_type == 'product')[:1]
        self.assertTrue(prod_line.foreign_debit > 0 or prod_line.foreign_credit > 0)

    def test_calculate_zero_for_section(self):
        if not self.display_product:
            self.skipTest("display_type='product' not supported")
        inv = self._make_invoice(lines=[
            {'name': 'Section', 'product': False, 'qty': 0, 'price': 0, 'taxes': [], 'display_type': 'line_section'},
            {'name': 'Prod', 'product': self.product, 'qty': 1, 'price': 100, 'taxes': [self.tax_iva16.id], 'display_type': True},
        ])
        self._post(inv)
        section = inv.line_ids.filtered(lambda l: l.display_type == 'line_section')
        if section:
            self.assertEqual(section.foreign_debit, 0)
            self.assertEqual(section.foreign_credit, 0)

    def test_calculate_for_non_invoice(self):
        move = self.Move.create({
            'move_type': 'entry',
            'date': fields.Date.from_string('2025-07-28'),
            'line_ids': [
                Command.create({'name': 'D', 'account_id': self.account_income.id, 'debit': 100}),
                Command.create({'name': 'C', 'account_id': self.account_income.id, 'credit': 100}),
            ]
        })
        move.write({'foreign_inverse_rate': 120.0})
        move.line_ids._compute_foreign_debit_credit()
        debit_line = move.line_ids.filtered(lambda l: l.debit > 0)
        self.assertTrue(debit_line.foreign_debit > 0)

    def test_calculate_from_adjustment(self):
        inv = self._make_invoice()
        self._post(inv)
        line = inv.line_ids[:1]
        line.write({'foreign_debit_adjustment': 999, 'foreign_credit_adjustment': 0})
        line._compute_foreign_debit_credit()
        self.assertEqual(line.foreign_debit, 999)

    def test_calculate_from_amount_currency(self):
        # Create an unposted journal entry line in foreign currency
        move = self.Move.create({
            'move_type': 'entry',
            'date': fields.Date.from_string('2025-07-28'),
            'line_ids': [
                Command.create({
                    'name': 'Foreign',
                    'account_id': self.account_income.id,
                    'currency_id': self.currency_vef.id,
                    'amount_currency': 500,
                    'debit': 500 / 120.439,
                }),
                Command.create({
                    'name': 'Balance',
                    'account_id': self.account_income.id,
                    'credit': 500 / 120.439,
                }),
            ]
        })
        line = move.line_ids.filtered(lambda l: l.debit > 0)
        line._compute_foreign_debit_credit()
        self.assertEqual(line.foreign_debit, 500)

    # ---- Foreign Balance ----

    def test_foreign_balance(self):
        inv = self._make_invoice()
        self._post(inv)
        line = inv.line_ids[:1]
        line._compute_foreign_balance()
        self.assertAlmostEqual(line.foreign_balance, line.foreign_debit - line.foreign_credit, places=2)

    def test_inverse_foreign_balance(self):
        inv = self._make_invoice()
        self._post(inv)
        line = inv.line_ids[:1]
        line.foreign_balance = 500
        line._inverse_foreign_balance()
        self.assertEqual(line.foreign_debit, 500)
        self.assertEqual(line.foreign_credit, 0)

    # ---- Onchange ----

    def test_onchange_quantity_negative(self):
        inv = self._make_invoice()
        line = inv.invoice_line_ids[:1]
        with self.assertRaises(ValidationError):
            line.quantity = -1
            line._onchange_quantity()

    def test_onchange_price_unit_negative(self):
        inv = self._make_invoice()
        line = inv.invoice_line_ids[:1]
        with self.assertRaises(ValidationError):
            line.price_unit = -10
            line._onchange_price_unit()

    # ---- Residual ----

    def test_compute_amount_residual(self):
        inv = self._make_invoice()
        self._post(inv)
        rec_line = inv.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')[:1]
        self.assertTrue(rec_line.amount_residual > 0)
        self.assertTrue(rec_line.foreign_amount_residual >= 0)

    def test_get_manual_foreign_amount_residual(self):
        inv = self._make_invoice()
        self._post(inv)
        line = inv.line_ids.filtered(lambda l: l.foreign_debit > 0)[:1]
        if line:
            residual, available = line._get_manual_foreign_amount_residual()
            self.assertTrue(available)

    def test_compute_foreign_amount_residuals(self):
        inv = self._make_invoice()
        self._post(inv)
        line = inv.line_ids.filtered(lambda l: l.foreign_debit > 0)[:1]
        if line:
            line._compute_foreign_amount_residuals()
            self.assertIsNotNone(line.foreign_amount_residual)
            self.assertIsNotNone(line.foreign_amount_residual_currency)

    # ---- Write ----

    def test_write_logs_foreign_debit_change(self):
        inv = self._make_invoice()
        self._post(inv)
        line = inv.line_ids[:1]
        old_val = line.foreign_debit
        line.write({'foreign_debit': old_val + 100})
        messages = self.env['mail.message'].search([
            ('model', '=', 'account.move'),
            ('res_id', '=', inv.id),
        ])
        self.assertTrue(messages)

    # ---- All Tax ----

    def test_compute_all_tax_foreign_balance(self):
        if not self.display_product:
            self.skipTest("display_type='product' not supported")
        inv = self._make_invoice(lines=[
            {'name': 'Prod', 'product': self.product, 'qty': 1, 'price': 100, 'taxes': [self.tax_iva16.id], 'display_type': True},
        ])
        inv.invoice_line_ids._compute_all_tax()
        tax_lines = inv.invoice_line_ids.filtered(lambda l: l.display_type == 'tax')
        for tl in tax_lines:
            self.assertIsNotNone(tl.compute_all_tax)

    # ---- Reconciliation ----

    def test_prepare_reconciliation_single_partial(self):
        inv = self._make_invoice()
        self._post(inv)
        payment_method = self.env['account.payment.method'].search(
            [('code', '=', 'manual'), ('payment_type', '=', 'inbound')], limit=1
        ) or self.env.ref('account.account_payment_method_manual_in')

        pm_line = self.env["account.payment.method.line"].search(
            [("journal_id", "=", self.bank_journal.id), ("payment_method_id", "=", payment_method.id)],
            limit=1,
        ) or self.env["account.payment.method.line"].create({
            "journal_id": self.bank_journal.id,
            "payment_method_id": payment_method.id,
        })

        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'amount': 50.0,
            'currency_id': self.currency_usd.id,
            'journal_id': self.bank_journal.id,
            'payment_method_line_id': pm_line.id,
            'date': fields.Date.from_string('2025-07-28'),
        })
        payment.action_post()

        inv_rec = inv.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
        pay_rec = payment.move_id.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')

        if inv_rec and pay_rec:
            (inv_rec + pay_rec).reconcile()
            self.assertTrue(inv_rec.foreign_amount_residual >= 0)

    # ---- Prepare Analytic ----

    def test_prepare_analytic_distribution_line(self):
        inv = self._make_invoice()
        self._post(inv)
        plan = self.env['account.analytic.plan'].search([], limit=1) or self.env['account.analytic.plan'].create({'name': 'Default Plan'})
        analytic = self.env['account.analytic.account'].create({'name': 'Test', 'code': 'TA001', 'plan_id': plan.id})
        line = inv.line_ids[:1]
        line.write({'analytic_distribution': {str(analytic.id): 100}})
        res = line._prepare_analytic_distribution_line(
            distribution=100, account_id=str(analytic.id), distribution_on_each_plan={analytic.root_plan_id: 0}
        )
        self.assertIn('foreign_amount', res)

    # ---- _compute_name ----

    def test_compute_name_receivable(self):
        if not self.display_product:
            self.skipTest("display_type='product' not supported")
        inv = self._make_invoice()
        self._post(inv)
        rec_line = inv.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')[:1]
        if rec_line:
            self.assertEqual(rec_line.name, inv.name)

    # ---- abs_amount_lines_ids_adjust ----

    def test_abs_amount_lines_ids_adjust(self):
        inv = self._make_invoice()
        self._post(inv)
        line = inv.line_ids[:1]
        line.write({
            'foreign_debit_adjustment': -100,
            'foreign_credit_adjustment': -200,
            'foreign_debit': -300,
            'foreign_credit': -400,
        })
        line.abs_amount_lines_ids_adjust()
        self.assertEqual(line.foreign_debit_adjustment, 100)
        self.assertEqual(line.foreign_credit_adjustment, 200)
        self.assertEqual(line.foreign_debit, 300)
        self.assertEqual(line.foreign_credit, 400)

    # ---- _inverse_amount_currency ----

    def test_inverse_amount_currency_base_currency(self):
        inv = self._make_invoice()
        self._post(inv)
        line = inv.line_ids[:1]
        line.currency_id = self.company.currency_id
        line.amount_currency = line.balance + 1
        line._inverse_amount_currency()
        self.assertEqual(line.balance, line.amount_currency)

    # ---- _compute_amount_currency ----

    def test_compute_amount_currency(self):
        inv = self._make_invoice()
        self._post(inv)
        line = inv.line_ids[:1]
        line.amount_currency = False
        line._compute_amount_currency()
        self.assertIsNotNone(line.amount_currency)
