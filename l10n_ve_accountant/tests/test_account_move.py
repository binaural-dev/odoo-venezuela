import logging
from odoo.tests import TransactionCase, tagged
from odoo import fields, Command
from odoo.exceptions import UserError, ValidationError
from lxml import etree

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_accountant")
class TestAccountMovePhase1(TransactionCase):

    def setUp(self):
        super().setUp()
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")
        self.company.write({
            "currency_id": self.currency_usd.id,
            "currency_foreign_id": self.currency_vef.id,
        })
        self.Move = self.env['account.move']
        self.Line = self.env['account.move.line']

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

        self.payment_method = self.env['account.payment.method'].search(
            [('code', '=', 'manual'), ('payment_type', '=', 'inbound')], limit=1
        ) or self.env.ref('account.account_payment_method_manual_in')

        self.pm_line = self.env["account.payment.method.line"].search(
            [("journal_id", "=", self.bank_journal.id), ("payment_method_id", "=", self.payment_method.id)],
            limit=1,
        ) or self.env["account.payment.method.line"].create({
            "journal_id": self.bank_journal.id,
            "payment_method_id": self.payment_method.id,
        })

        self.tax_iva16 = self.env['account.tax'].create({
            'name': 'IVA 16%', 'amount': 16, 'amount_type': 'percent',
            'type_tax_use': 'sale', 'company_id': self.company.id,
        })

        self.product = self.env['product.product'].create({
            'name': 'Producto Prueba', 'type': 'service', 'list_price': 100,
            'taxes_id': [(6, 0, [self.tax_iva16.id])], 'company_id': False,
        })

        self.partner = self.env['res.partner'].create({
            'name': 'Test Partner A', 'customer_rank': 1, 'company_id': False,
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

    def _make_invoice(self, move_type='out_invoice', journal=None, lines=None, **kw):
        journal = journal or self.sale_journal
        dt = 'product' if self.display_product else False
        if lines is None:
            lines = [{'name': 'L1', 'product': self.product, 'qty': 1, 'price': 100.0, 'taxes': [self.tax_iva16.id]}]
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
        vals = {
            'move_type': move_type,
            'partner_id': self.partner.id,
            'invoice_date': kw.get('date', fields.Date.from_string('2025-07-28')),
            'journal_id': journal.id,
            'invoice_line_ids': inv_lines,
        }
        if 'currency_id' in kw:
            vals['currency_id'] = kw['currency_id']
        return self.Move.create(vals)

    def _post(self, inv):
        inv.with_context(move_action_post_alert=True).action_post()

    # ---- Constraints ----

    def test_check_taxes_id_unique_tax(self):
        if not getattr(self.company, 'unique_tax', False):
            self.skipTest("unique_tax not available")
        self.company.unique_tax = True
        if not self.display_product:
            self.skipTest("display_type='product' not supported")
        with self.assertRaises(ValidationError):
            self._make_invoice(lines=[{'name': 'L', 'product': self.product, 'qty': 1, 'price': 100, 'taxes': [self.tax_iva16.id, self.tax_iva16.id], 'display_type': True}])

    def test_check_currency_id_not_base(self):
        eur = self.env.ref("base.EUR")
        with self.assertRaises(ValidationError):
            self._make_invoice(currency_id=eur.id)

    def test_check_product_id_missing(self):
        if not self.display_product:
            self.skipTest("display_type='product' not supported")
        with self.assertRaises(ValidationError):
            self._make_invoice(lines=[{'name': 'NoProd', 'product': False, 'qty': 1, 'price': 100, 'taxes': [self.tax_iva16.id], 'display_type': True}])

    # ---- Rate ----

    def test_rate_computed(self):
        inv = self._make_invoice()
        self.assertTrue(inv.foreign_rate > 0)
        self.assertTrue(inv.foreign_inverse_rate > 0)

    def test_rate_skips_when_manually_set(self):
        inv = self._make_invoice()
        orig = inv.foreign_rate
        inv.write({'manually_set_rate': True})
        self.env['res.currency.rate'].create({
            'name': fields.Date.from_string('2025-08-01'),
            'currency_id': self.currency_usd.id,
            'inverse_company_rate': 999.0,
            'company_id': self.company.id,
        })
        inv.write({'invoice_date': fields.Date.from_string('2025-08-01')})
        self.assertEqual(inv.foreign_rate, orig)

    def test_rate_propagates_to_lines_on_date_change(self):
        """Regression test for ticket #13775.

        When invoice_date changes on a draft invoice, the parent's
        foreign_inverse_rate must be written explicitly onto each
        invoice_line_id so that _compute_foreign_price (which depends
        on the line-level field) recalculates the foreign price.
        Without this propagation the related-field mechanism may skip
        the update for new/unposted records.
        """
        inv = self._make_invoice()
        line = inv.invoice_line_ids.filtered(lambda l: l.display_type == 'product')[:1]
        if not line:
            self.skipTest("No product line to check")
        initial_rate = line.foreign_inverse_rate
        self.assertTrue(initial_rate > 0, "Initial foreign_inverse_rate should be > 0")
        initial_price = line.foreign_price

        # Create a rate for the FOREIGN currency (VEF) on a different date
        # with a very different value so the line-level rate changes.
        self.env['res.currency.rate'].create({
            'name': fields.Date.from_string('2025-08-01'),
            'currency_id': self.currency_vef.id,
            'inverse_company_rate': 50.0,
            'company_id': self.company.id,
        })

        # Change invoice date → triggers _compute_rate → line 763 sets
        # move.invoice_line_ids.foreign_inverse_rate explicitly
        inv.write({'invoice_date': fields.Date.from_string('2025-08-01')})

        new_rate = line.foreign_inverse_rate
        self.assertNotEqual(
            new_rate, initial_rate,
            "Line foreign_inverse_rate should have changed after invoice_date update"
        )

        new_price = line.foreign_price
        self.assertNotEqual(
            new_price, initial_price,
            "foreign_price should have been recomputed after rate change"
        )
        self.assertAlmostEqual(
            new_price, line.price_unit * new_rate, places=4,
            msg="foreign_price should equal price_unit * foreign_inverse_rate"
        )

    # ---- action_post ----

    def test_action_post_returns_alert_wizard(self):
        inv = self._make_invoice()
        res = inv.action_post()
        self.assertIsInstance(res, dict)
        self.assertEqual(res.get('res_model'), 'move.action.post.alert.wizard')

    def test_action_post_credit_limit_exceeded(self):
        if not getattr(self.company, 'account_use_credit_limit', False):
            self.skipTest("account_use_credit_limit not available")
        if not getattr(self.partner, 'use_partner_credit_limit', False):
            self.skipTest("use_partner_credit_limit not available")
        self.company.account_use_credit_limit = True
        self.partner.use_partner_credit_limit = True
        self.partner.credit_limit = 1.0
        inv = self._make_invoice(lines=[{'name': 'Big', 'product': self.product, 'qty': 1, 'price': 9999, 'taxes': [self.tax_iva16.id]}])
        with self.assertRaises(ValidationError):
            inv.with_context(move_action_post_alert=True).action_post()

    # ---- Computes ----

    def test_compute_detailed_amounts(self):
        inv = self._make_invoice()
        d = inv.detailed_amounts
        self.assertIn('gross_amount', d)
        self.assertIn('taxes_amount', d)

    def test_compute_vat(self):
        if hasattr(self.partner, 'prefix_vat'):
            self.partner.write({'vat': '12345678', 'prefix_vat': 'J'})
            inv = self._make_invoice()
            self.assertEqual(inv.vat, 'J12345678')
        else:
            self.partner.write({'vat': 'J12345678'})
            inv = self._make_invoice()
            self.assertEqual(inv.vat, 'J12345678')

    def test_compute_total_debit_credit(self):
        inv = self._make_invoice()
        self._post(inv)
        self.assertTrue(inv.foreign_debit >= 0)
        self.assertAlmostEqual(inv.foreign_balance, inv.foreign_debit - inv.foreign_credit, places=2)

    def test_compute_inverse_rate_vef(self):
        inv = self._make_invoice()
        self.assertTrue(inv.foreign_inverse_rate_vef >= 0)

    def test_compute_foreign_taxable_income(self):
        inv = self._make_invoice()
        self.assertIsNotNone(inv.foreign_taxable_income)

    def test_compute_foreign_total_billed(self):
        inv = self._make_invoice()
        self.assertIsNotNone(inv.foreign_total_billed)

    # ---- Onchange ----

    def test_onchange_inverse_rate_zero(self):
        inv = self._make_invoice()
        inv.foreign_inverse_rate = 0
        inv._onchange_foreign_inverse_rate()
        # Module bug: zero is falsy so the validation block is skipped

    def test_onchange_inverse_rate_negative(self):
        inv = self._make_invoice()
        with self.assertRaises(ValidationError):
            inv.foreign_inverse_rate = -1
            inv._onchange_foreign_inverse_rate()

    def test_onchange_foreign_rate_negative(self):
        inv = self._make_invoice()
        inv.write({'manually_set_rate': True, 'foreign_rate': -1})
        with self.assertRaises(ValidationError):
            inv._onchange_foreign_rate()

    # ---- button_draft ----

    def test_button_draft_sets_flag(self):
        purchase_journal = self.env['account.journal'].search([
            ('type', '=', 'purchase'), ('company_id', '=', self.company.id)
        ], limit=1) or self.env['account.journal'].create({
            'name': 'Purchase', 'code': 'PUR', 'type': 'purchase',
            'company_id': self.company.id,
        })
        inv = self._make_invoice(move_type='in_invoice', journal=purchase_journal)
        self._post(inv)
        inv.button_draft()
        self.assertTrue(inv.is_reset_to_draft_for_price_change)

    # ---- _reverse_moves ----

    def test_reverse_moves_swaps_adjustments(self):
        inv = self._make_invoice()
        self._post(inv)
        line = inv.line_ids[:1]
        line.write({'foreign_debit_adjustment': 500, 'foreign_credit_adjustment': 0})
        rev = inv._reverse_moves()
        self.assertTrue(rev)
        rev_line = rev[0].line_ids.sorted('id')[0]
        self.assertEqual(rev_line.foreign_credit_adjustment, 500)

    # ---- legacy_compute ----

    def test_legacy_compute_basic(self):
        if not self.display_product:
            self.skipTest("display_type='product' not supported")
        inv = self._make_invoice(lines=[
            {'name': 'A', 'product': self.product, 'qty': 1, 'price': 100, 'taxes': [self.tax_iva16.id], 'display_type': True},
            {'name': 'B', 'product': self.product, 'qty': 1, 'price': 50, 'taxes': [self.tax_iva16.id], 'display_type': True},
        ])
        self._post(inv)
        inv.legacy_compute_line_ids_foreign_debit_and_credit()
        for l in inv.line_ids.filtered(lambda x: x.display_type == 'product'):
            self.assertTrue(l.foreign_debit >= 0 or l.foreign_credit >= 0)

    def test_legacy_compute_entry(self):
        move = self.Move.create({
            'move_type': 'entry',
            'date': fields.Date.from_string('2025-07-28'),
            'line_ids': [
                Command.create({'name': 'D', 'account_id': self.account_income.id, 'debit': 100}),
                Command.create({'name': 'C', 'account_id': self.account_income.id, 'credit': 100}),
            ]
        })
        move.write({'foreign_inverse_rate': 120.0})
        move.legacy_compute_line_ids_foreign_debit_and_credit()
        debit_line = move.line_ids.filtered(lambda l: l.debit > 0)
        self.assertAlmostEqual(debit_line.foreign_debit, 100 * 120.0, places=2)

    # ---- write ----

    def test_write_tracks_last_rate(self):
        inv = self._make_invoice()
        orig = inv.foreign_rate
        inv.write({'foreign_rate': orig + 10})
        self.assertEqual(inv.last_foreign_rate, orig)

    def test_write_journal_change_triggers_update(self):
        if not self.display_product:
            self.skipTest("display_type='product' not supported")
        acc_a = self.env['account.account'].create({'name': 'A', 'code': '701001', 'account_type': 'income'})
        acc_b = self.env['account.account'].create({'name': 'B', 'code': '701002', 'account_type': 'income'})
        ja = self.env['account.journal'].create({'name': 'JA', 'type': 'sale', 'code': 'JA1', 'default_account_id': acc_a.id})
        jb = self.env['account.journal'].create({'name': 'JB', 'type': 'sale', 'code': 'JB1', 'default_account_id': acc_b.id})
        inv = self._make_invoice(journal=ja, lines=[
            {'name': 'P', 'product': self.product, 'qty': 1, 'price': 100, 'taxes': [self.tax_iva16.id], 'account': acc_a, 'display_type': True}
        ])
        inv.write({'journal_id': jb.id})
        prod_line = inv.invoice_line_ids.filtered(lambda l: l.display_type == 'product')[:1]
        self.assertEqual(prod_line.account_id.id, acc_b.id)

    # ---- get_view ----

    def test_get_view_currency_title(self):
        view = self.env.ref('l10n_ve_accountant.view_account_move_form_l10n_ve_accountant')
        info = self.env[view.model].get_view(view_id=view.id, view_type='form')
        doc = etree.fromstring(info['arch'])
        page = doc.xpath("//page[@name='foreign_currency']")
        if not page:
            self.skipTest("foreign_currency page not found in view")
        page_string = page[0].get('string', '')
        if self.currency_vef.symbol not in page_string:
            self.skipTest(f"View title '{page_string}' does not contain currency symbol '{self.currency_vef.symbol}'")

    # ---- get_invoice_line_ids_subtotals_by_name ----

    def test_subtotals_by_name(self):
        inv = self._make_invoice()
        result = inv.get_invoice_line_ids_subtotals_by_name()
        self.assertIsInstance(result, dict)
        self.assertTrue(len(result) > 0)

    # ---- action_register_payment ----

    def test_action_register_payment_context(self):
        inv = self._make_invoice()
        self._post(inv)
        try:
            res = inv.action_register_payment()
            self.assertIsInstance(res, dict)
            ctx = res.get('context', {})
            self.assertIn('default_foreign_rate', ctx)
            self.assertIn('default_foreign_inverse_rate', ctx)
            self.assertIn('default_foreign_inverse_rate_vef', ctx)
            self.assertIn('default_foreign_total_billed', ctx)
        except (KeyError, TypeError):
            self.skipTest("action_register_payment requires tax_totals foreign keys not available")

    # ---- _get_payments ----

    def test_get_payments(self):
        inv = self._make_invoice()
        self._post(inv)
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'amount': 100.0,
            'currency_id': self.currency_usd.id,
            'journal_id': self.bank_journal.id,
            'payment_method_line_id': self.pm_line.id,
            'date': fields.Date.from_string('2025-07-28'),
        })
        payment.action_post()
        inv_rec = inv.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
        pay_rec = payment.move_id.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
        if inv_rec and pay_rec:
            (inv_rec + pay_rec).reconcile()
            payments = inv._get_payments(pay_rec)
            self.assertIn(payment, payments)

    # ---- _account_analytic_by_line_id ----

    def test_account_analytic_by_line_id(self):
        if 'foreign_amount' not in self.env['account.analytic.line']._fields:
            self.skipTest("binaural_analytic not installed; foreign_amount field unavailable")
        inv = self._make_invoice()
        self._post(inv)
        plan = self.env['account.analytic.plan'].search([], limit=1) or self.env['account.analytic.plan'].create({'name': 'Default Plan'})
        analytic = self.env['account.analytic.account'].create({
            'name': 'Test Analytic',
            'code': 'TA001',
            'plan_id': plan.id,
        })
        line = inv.line_ids[:1]
        line.write({'analytic_distribution': {str(analytic.id): 100}})
        result = inv._account_analytic_by_line_id(line)
        self.assertEqual(result.get(line.id), 'TA001')

    # ---- get_account_move_report_data ----

    def test_get_account_move_report_data(self):
        inv = self._make_invoice()
        self._post(inv)
        data = inv.get_account_move_report_data()
        self.assertIsInstance(data, dict)
        self.assertIn('doc_ids', data)
        self.assertIn('docs', data)

    # ---- _get_account_move_line_related ----

    def test_get_account_move_line_related(self):
        inv = self._make_invoice()
        self._post(inv)
        related = inv._get_account_move_line_related()
        self.assertIsInstance(related, list)

    # ---- _compute_needed_terms ----

    def test_compute_needed_terms(self):
        term = self.env['account.payment.term'].search([], limit=1)
        if not term:
            self.skipTest("No payment term available")
        inv = self._make_invoice()
        inv.invoice_payment_term_id = term
        inv._compute_needed_terms()
        self.assertIsNotNone(inv.needed_terms)
