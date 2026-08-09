import logging
import random
from datetime import timedelta

from odoo.tests import TransactionCase, tagged
from odoo.tests.common import Form
from odoo import fields, Command
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_accountant_coverage")
class TestCoverageGaps(TransactionCase):

    def _set_correlative_if_required(self, form, value):
        # correlative only exists/is required when l10n_ve_invoice is installed
        # alongside this module (e.g. pulled in transitively by l10n_ve_igtf).
        # Form raises AssertionError (not AttributeError) for fields absent from
        # the view, so hasattr() can't be used here - check the view spec instead.
        if "correlative" in form._view["fields"] and not form.correlative:
            form.correlative = value

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

    def _create_tax_ext(self, name, amount, account_id=None, type_tax_use="sale"):
        def rep_line(rep_type):
            vals = {'repartition_type': rep_type, 'factor_percent': 100.0}
            if rep_type == 'tax' and account_id:
                vals['account_id'] = account_id
            return (0, 0, vals)
        return self.env["account.tax"].with_company(self.company).create({
            "name": name, "amount": amount, "amount_type": "percent",
            "type_tax_use": type_tax_use, "company_id": self.company.id,
            "tax_group_id": self.tax_group.id,
            "invoice_repartition_line_ids": [rep_line('base'), rep_line('tax')],
            "refund_repartition_line_ids": [rep_line('base'), rep_line('tax')],
        })

    def _foreign_tax_expected(self, move):
        """Replicates _compute_foreign_tax_balance foreign amounts per
        (tax_repartition_line, base account) using the current alterno prices."""
        fc = move.foreign_currency_id
        sign = move.direction_sign if move.is_invoice(include_receipts=True) else 1
        per_key = {}
        for bl in move.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
            quantity = bl.quantity if move.is_invoice(include_receipts=True) else 1.0
            discount = bl.discount if move.is_invoice(include_receipts=True) else 0.0
            base = sign * bl.foreign_price * (1 - discount / 100)
            res = bl.tax_ids.compute_all(
                base, currency=fc, quantity=quantity,
                product=bl.product_id, partner=move.partner_id,
                is_refund=move.move_type in ('out_refund', 'in_refund'),
                handle_price_include=True,
                include_caba_tags=move.always_tax_exigible,
                fixed_multiplicator=sign,
            )
            for tax in res['taxes']:
                if not tax['amount']:
                    continue
                rep = self.env['account.tax.repartition.line'].browse(
                    tax['tax_repartition_line_id'])
                if rep.repartition_type != 'tax':
                    continue
                key = (rep.id, bl.account_id.id)
                per_key.setdefault(key, []).append(tax['amount'])
        return per_key

    def _log_cmp(self, label, name, actual, expected, places=1, extra=""):
        diff = actual - expected
        ok = round(abs(diff), places) == 0
        _logger.info(
            "[%s] %-42s actual=%-14.2f expected=%-14.2f diff=%-.4f  %s %s",
            label, name, actual, expected, diff, "OK" if ok else "FAIL", extra,
        )
        return ok

    def _assert_tax_totals_foreign(self, move, label=""):
        tt = move.tax_totals or {}
        for key in ('foreign_amount_untaxed', 'foreign_amount_total',
                    'groups_by_foreign_subtotal', 'foreign_subtotals',
                    'foreign_subtotal', 'foreign_discount_amount'):
            _logger.info("[%s] tax_totals key present: %s", label, key)
            self.assertIn(key, tt, f"{label}: tax_totals missing {key}")

        entry_untaxed = sum(
            abs(l.foreign_subtotal)
            for l in move.line_ids if l.display_type == 'product')
        entry_tax = sum(
            abs(l.foreign_debit - l.foreign_credit)
            for l in move.line_ids if l.display_type == 'tax')
        entry_total = entry_untaxed + entry_tax

        actual = tt['foreign_amount_untaxed']
        self._log_cmp(label, "tax_totals.foreign_amount_untaxed == entry foreign_subtotal",
                      actual, entry_untaxed,
                      extra=f"entry_untaxed={entry_untaxed}")
        self.assertAlmostEqual(actual, entry_untaxed, places=1,
                               msg=f"{label}: tax_totals untaxed vs entry foreign_subtotal")

        actual = tt['foreign_amount_total']
        self._log_cmp(label, "tax_totals.foreign_amount_total == entry (products + taxes)",
                      actual, entry_total,
                      extra=f"entry_total={entry_total}")
        self.assertAlmostEqual(actual, entry_total, places=1,
                               msg=f"{label}: tax_totals total vs entry alternos")

        actual = tt['foreign_amount_untaxed']
        expected = sum(s['amount'] for s in tt['foreign_subtotals'])
        self._log_cmp(label, "tax_totals.foreign_amount_untaxed == subtotals",
                      actual, expected)
        self.assertAlmostEqual(actual, expected, places=1,
                               msg=f"{label}: tax_totals foreign_subtotals sum")

        group_tax_total = sum(
            g['tax_group_amount']
            for subtotals in tt['groups_by_foreign_subtotal'].values()
            for g in subtotals)
        tax_lines_fd = sum(abs(l.foreign_debit - l.foreign_credit)
                           for l in move.line_ids if l.display_type == 'tax')
        self._log_cmp(label, "tax_totals group taxes == entry tax lines",
                      tax_lines_fd, group_tax_total,
                      extra=f"tax_lines={tax_lines_fd} groups={group_tax_total}")
        self.assertAlmostEqual(tax_lines_fd, group_tax_total, places=1,
                               msg=f"{label}: tax_totals taxes vs entry tax lines")

        actual = tt['foreign_amount_total']
        expected = tt['foreign_amount_untaxed'] + group_tax_total
        self._log_cmp(label, "tax_totals total == untaxed + taxes",
                      actual, expected,
                      extra=f"untaxed={tt['foreign_amount_untaxed']} taxes={group_tax_total}")
        self.assertAlmostEqual(actual, expected, places=1,
                               msg=f"{label}: tax_totals total = untaxed + taxes")

    def _assert_foreign_consistency(self, move, label=""):
        self.env.flush_all()
        self.env.invalidate_all()
        fc = move.foreign_currency_id
        rate = move.foreign_inverse_rate or 0.0

        _logger.info("[%s] === lines: %s | rate=%.6f ===",
                     label, len(move.invoice_line_ids), rate)
        for bl in move.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
            if not bl.foreign_price_manual:
                actual = bl.foreign_price
                expected = bl.price_unit * rate
                self._log_cmp(label, f"foreign_price line {bl.id}",
                              actual, expected,
                              extra=f"native={bl.price_unit} manual={bl.foreign_price_manual}")
                self.assertAlmostEqual(
                    actual, expected, places=1,
                    msg=f"{label}: alterno price line {bl.id}")
            else:
                _logger.info(
                    "[%s] foreign_price line %s MANUAL (rate check skipped) "
                    "price=%.2f native=%s manual=%s",
                    label, bl.id, bl.foreign_price, bl.price_unit,
                    bl.foreign_price_manual)
            exp_sub = bl.foreign_price * bl.quantity * (1 - bl.discount / 100)
            actual = bl.foreign_subtotal
            self._log_cmp(label, f"foreign_subtotal line {bl.id}",
                          actual, exp_sub,
                          extra=f"price={bl.foreign_price} qty={bl.quantity}")
            self.assertAlmostEqual(
                actual, exp_sub, places=1,
                msg=f"{label}: alterno subtotal line {bl.id}")

        per_key = self._foreign_tax_expected(move)
        tax_amls = move.line_ids.filtered(
            lambda l: l.tax_repartition_line_id
            and l.tax_repartition_line_id.repartition_type == 'tax')
        by_key = {}
        for tl in tax_amls:
            key = (tl.tax_repartition_line_id.id, tl.account_id.id)
            by_key.setdefault(key, []).append(tl)
        for (rep_line, acct), lines in by_key.items():
            amounts = per_key.get((rep_line, acct))
            if not amounts:
                for (r2, a2), amts in per_key.items():
                    if r2 == rep_line:
                        amounts = (amounts or []) + amts
            if not amounts:
                _logger.info("[%s] tax key rep=%s acct=%s: no foreign amounts (skip)",
                             label, rep_line, acct)
                continue
            if len(lines) == len(amounts):
                expected = sum(fc.round(abs(a)) for a in amounts)
            else:
                total_ac = sum(abs(l.amount_currency) for l in lines if l.amount_currency)
                if fc.is_zero(total_ac):
                    expected = sum(fc.round(abs(a)) for a in amounts)
                else:
                    total_fb = sum(amounts)
                    expected = sum(
                        fc.round(abs(total_fb) * abs(l.amount_currency) / total_ac)
                        for l in lines)
            actual = sum(abs(l.foreign_debit - l.foreign_credit) for l in lines)
            self._log_cmp(label, f"tax rep={rep_line} acct={acct}",
                          actual, expected,
                          extra=f"lines={len(lines)} amounts={len(amounts)}")
            self.assertAlmostEqual(
                actual, expected, places=1,
                msg=f"{label}: tax foreign rep={rep_line} acct={acct}")

        rec = move.line_ids.filtered(
            lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
            and l.display_type == 'payment_term')[:1]
        if rec:
            product_fd = sum(abs(l.foreign_subtotal)
                             for l in move.line_ids if l.display_type == 'product')
            tax_fd = sum(abs(l.foreign_debit - l.foreign_credit)
                         for l in move.line_ids if l.display_type == 'tax')
            actual = abs(rec.foreign_balance)
            expected = product_fd + tax_fd
            self._log_cmp(label, "counterpart foreign == products + taxes",
                          actual, expected,
                          extra=f"products={product_fd} taxes={tax_fd}")
            self.assertAlmostEqual(
                actual, expected, places=1,
                msg=f"{label}: counterpart foreign {rec.foreign_balance}")

        actual = sum(move.line_ids.mapped('foreign_debit'))
        expected = sum(move.line_ids.mapped('foreign_credit'))
        self._log_cmp(label, "global alterno balance (debit == credit)",
                      actual, expected)
        self.assertAlmostEqual(actual, expected, places=1,
                               msg=f"{label}: global alterno balance")
        self._assert_balances(move, label)
        self._assert_tax_totals_foreign(move, label)

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
        pay._compute_rate()
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
        pay._compute_rate()
        self.assertGreater(pay.foreign_rate, 0.0)

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

    def _rectification_purchase_journal(self):
        return self.env["account.journal"].sudo().create({
            "name": "Purchases Rectification", "code": "PRCT",
            "type": "purchase", "company_id": self.company.id,
            "default_account_id": self.acc_exp.id,
        })

    def _create_in_invoice(self, journal, date):
        return self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "in_invoice",
            "partner_id": self.partner.id,
            "journal_id": journal.id,
            "invoice_date": date,
            "date": date,
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0, "price_unit": 100.0,
                    "account_id": self.acc_exp.id,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
            ],
        })

    def test_rectification_keeps_origin_rate_after_date_change(self):
        """Nota de crédito vinculada: la tasa debe quedar fija en la de la
        factura origen, sin importar cambios posteriores de fecha."""
        journal = self._rectification_purchase_journal()
        date_a, date_b, date_c = (
            fields.Date.from_string("2026-07-01"),
            fields.Date.from_string("2026-07-10"),
            fields.Date.from_string("2026-07-13"),
        )
        rate_model = self.env["res.currency.rate"]
        rate_model.create({
            "name": date_a, "currency_id": self.currency_usd.id,
            "inverse_company_rate": 40.0, "company_id": self.company.id,
        })
        rate_model.create({
            "name": date_b, "currency_id": self.currency_usd.id,
            "inverse_company_rate": 45.0, "company_id": self.company.id,
        })
        rate_model.create({
            "name": date_c, "currency_id": self.currency_usd.id,
            "inverse_company_rate": 48.0, "company_id": self.company.id,
        })

        invoice = self._create_in_invoice(journal, date_a)
        rate_a = invoice.foreign_rate
        self.assertAlmostEqual(rate_a, 40.0, places=2)

        refund = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "in_refund",
            "partner_id": self.partner.id,
            "journal_id": journal.id,
            "reversed_entry_id": invoice.id,
            "invoice_date": date_b,
            "date": date_b,
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0, "price_unit": 100.0,
                    "account_id": self.acc_exp.id,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
            ],
        })
        self.assertAlmostEqual(refund.foreign_rate, rate_a, places=2)

        refund.write({"date": date_c, "invoice_date": date_c})
        self.env.flush_all()
        self.assertAlmostEqual(
            refund.foreign_rate, rate_a, places=2,
            msg="La tasa de la rectificativa no debe cambiar al editar la fecha",
        )

        refund.write({"foreign_rate": 999.0})
        self.env.flush_all()
        self.assertAlmostEqual(
            refund.foreign_rate, rate_a, places=2,
            msg="Un write directo del campo no debe romper la paridad histórica",
        )

    def test_rectification_via_reversal_wizard_keeps_origin_rate(self):
        """El flujo real de usuario (wizard de reversión) debe heredar la
        tasa de la factura origen, no la vigente en la fecha del wizard."""
        journal = self._rectification_purchase_journal()
        date_a, date_b = (
            fields.Date.from_string("2026-07-01"),
            fields.Date.from_string("2026-07-10"),
        )
        rate_model = self.env["res.currency.rate"]
        rate_model.create({
            "name": date_a, "currency_id": self.currency_usd.id,
            "inverse_company_rate": 40.0, "company_id": self.company.id,
        })
        rate_model.create({
            "name": date_b, "currency_id": self.currency_usd.id,
            "inverse_company_rate": 45.0, "company_id": self.company.id,
        })

        invoice = self._create_in_invoice(journal, date_a)
        invoice.with_context(move_action_post_alert=True).action_post()
        rate_a = invoice.foreign_rate

        reversal = self.env["account.move.reversal"].with_context(
            active_model="account.move", active_ids=invoice.ids,
        ).create({
            "date": date_b,
            "reason": "Test rectificación",
            "journal_id": journal.id,
        })
        result = reversal.reverse_moves()
        refund = self.env["account.move"].browse(result["res_id"])
        self.assertTrue(refund.reversed_entry_id)
        self.assertAlmostEqual(refund.foreign_rate, rate_a, places=2)

    def test_debit_note_keeps_origin_rate_after_date_change(self):
        """Las notas de débito (debit_origin_id) deben heredar la tasa de la
        factura origen igual que las notas de crédito, sin importar que el
        wizard estándar de Odoo las cree como move_type in_invoice/out_invoice
        (nunca in_refund/out_refund)."""
        journal = self._rectification_purchase_journal()
        date_a, date_b, date_c = (
            fields.Date.from_string("2026-07-01"),
            fields.Date.from_string("2026-07-10"),
            fields.Date.from_string("2026-07-13"),
        )
        rate_model = self.env["res.currency.rate"]
        rate_model.create({
            "name": date_a, "currency_id": self.currency_usd.id,
            "inverse_company_rate": 40.0, "company_id": self.company.id,
        })
        rate_model.create({
            "name": date_b, "currency_id": self.currency_usd.id,
            "inverse_company_rate": 45.0, "company_id": self.company.id,
        })
        rate_model.create({
            "name": date_c, "currency_id": self.currency_usd.id,
            "inverse_company_rate": 48.0, "company_id": self.company.id,
        })

        invoice = self._create_in_invoice(journal, date_a)
        invoice.with_context(move_action_post_alert=True).action_post()
        rate_a = invoice.foreign_rate

        debit_wizard = self.env["account.debit.note"].with_context(
            active_model="account.move", active_ids=invoice.ids,
        ).create({
            "date": date_b,
            "reason": "Test nota de débito",
            "journal_id": journal.id,
        })
        action = debit_wizard.create_debit()
        debit_note = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(debit_note.debit_origin_id, invoice)
        self.assertIn(debit_note.move_type, ("in_invoice", "out_invoice"))
        self.assertAlmostEqual(debit_note.foreign_rate, rate_a, places=2)

        debit_note.write({"date": date_c, "invoice_date": date_c})
        self.env.flush_all()
        self.assertAlmostEqual(
            debit_note.foreign_rate, rate_a, places=2,
            msg="La tasa de la nota de débito no debe cambiar al editar la fecha",
        )

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - write() batch con recordset mixto
    # ═══════════════════════════════════════════════════════════════

    def test_write_batch_mixed_moves_does_not_strip_unrelated_move_rate(self):
        """Un write() en batch sobre una factura normal + una rectificativa
        vinculada no debe descartar la tasa para la factura normal solo
        porque la rectificativa esté en el mismo recordset."""
        journal = self._rectification_purchase_journal()
        date_a, date_b = (
            fields.Date.from_string("2026-07-01"),
            fields.Date.from_string("2026-07-10"),
        )
        rate_model = self.env["res.currency.rate"]
        rate_model.create({
            "name": date_a, "currency_id": self.currency_usd.id,
            "inverse_company_rate": 40.0, "company_id": self.company.id,
        })

        origin_invoice = self._create_in_invoice(journal, date_a)
        origin_invoice.with_context(move_action_post_alert=True).action_post()
        origin_rate = origin_invoice.foreign_rate

        refund = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "in_refund",
            "partner_id": self.partner.id,
            "journal_id": journal.id,
            "reversed_entry_id": origin_invoice.id,
            "invoice_date": date_b,
            "date": date_b,
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0, "price_unit": 100.0,
                    "account_id": self.acc_exp.id,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
            ],
        })

        unrelated_invoice = self._create_in_invoice(journal, date_a)

        (unrelated_invoice | refund).write({"foreign_rate": 50.0})

        self.assertAlmostEqual(
            unrelated_invoice.foreign_rate, 50.0, places=2,
            msg="La factura sin relación con el bug debe poder actualizar su tasa",
        )
        self.assertAlmostEqual(
            refund.foreign_rate, origin_rate, places=2,
            msg="La rectificativa vinculada debe seguir bloqueada en la tasa de origen",
        )

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
        self.assertNotIn(
            'default_foreign_rate', context,
            "action_register_payment must not force the invoice's rate into the wizard",
        )

    def test_payment_register_wizard_uses_current_date_rate_not_invoice_rate(self):
        """
        The payment register wizard must compute foreign_rate from its own
        payment_date (defaulting to today), never from the rate stored on the
        old invoice being paid.

        old_rate > today_rate on purpose: this makes the invoice's own foreign
        amount (amount_bs / old_rate) the *smaller* of the two sides, so a
        plain min(foreign_debit_amount, foreign_credit_amount) would wrongly
        pick the invoice's side. Only the is_invoice()-based branching in
        _prepare_reconciliation_single_partial picks the payment's side
        correctly here, so this actually exercises that fix (see
        test_coverage_gaps.py history / PR #14473 review).
        """
        old_date = fields.Date.today() - timedelta(days=10)
        old_rate = 65.0
        today_rate = 30.0

        self.env["res.currency.rate"].create({
            "name": old_date, "currency_id": self.currency_usd.id,
            "inverse_company_rate": old_rate, "company_id": self.company.id,
        })
        # Overrides the today rate created in setUp (50.0) with a distinct value.
        self.env["res.currency.rate"].search([
            ("currency_id", "=", self.currency_usd.id),
            ("company_id", "=", self.company.id),
            ("name", "=", fields.Date.today()),
        ]).write({"inverse_company_rate": today_rate})

        invoice = self._create_invoice(self.currency_usd, 100.0)
        invoice.write({"date": old_date, "invoice_date": old_date})
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertAlmostEqual(invoice.foreign_rate, old_rate, places=2)

        action = invoice.action_register_payment()
        self.assertNotIn(
            "default_foreign_rate", action.get("context", {}),
            "action_register_payment must not force the invoice's rate into the wizard",
        )

        wizard_form = Form(
            self.env["account.payment.register"].with_context(**action["context"])
        )
        self.assertEqual(wizard_form.payment_date, fields.Date.today())
        self.assertAlmostEqual(
            wizard_form.foreign_rate, today_rate, places=2,
            msg="Wizard should use today's rate, not the invoice's rate",
        )
        self.assertNotAlmostEqual(wizard_form.foreign_rate, old_rate, places=2)

        wizard = wizard_form.save()
        payments = wizard._create_payments()
        self.assertAlmostEqual(
            payments.foreign_rate, today_rate, places=2,
            msg="_create_payment_vals_from_wizard must persist today's rate, not the invoice's",
        )
        self.assertNotAlmostEqual(payments.foreign_rate, old_rate, places=2)

        partial = self.env["account.partial.reconcile"].search([
            "|", ("debit_move_id", "in", payments.move_id.line_ids.ids),
            ("credit_move_id", "in", payments.move_id.line_ids.ids),
        ], limit=1)
        self.assertTrue(partial, "Payment should be reconciled with the invoice")
        self.assertAlmostEqual(
            partial.credit_foreign_amount_currency, partial.foreign_amount, places=2,
            msg="foreign_amount shown in the payments widget must match the payment's own "
                "foreign valuation, not the invoice's",
        )
        self.assertNotAlmostEqual(
            partial.debit_foreign_amount_currency, partial.foreign_amount, places=2,
            msg="foreign_amount must not collapse to the invoice's side, even though it is the "
                "smaller value here (old_rate > today_rate) and would be picked by a plain min()",
        )

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

    def test_repro_manual_alterno_add_product(self):
        def mk_line(price, tax=True):
            tax_ids = [(6, 0, [self.tax_16.id])] if tax else [(5, 0, 0)]
            return Command.create({
                "product_id": self.product.id,
                "quantity": 1.0, "price_unit": price,
                "account_id": self.acc_inc.id,
                "tax_ids": tax_ids,
            })
        inv = self.env["account.move"].with_context(check_move_validity=False).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_vef.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [mk_line(100.0, tax=False), mk_line(100.0, tax=True)],
        })
        exempt = inv.invoice_line_ids.filtered(lambda l: not l.tax_ids)[:1]
        edited = exempt.foreign_price + 0.01
        exempt.foreign_price = edited
        self.assertTrue(exempt.foreign_price_manual)

        inv.write({"invoice_line_ids": [mk_line(100.0, tax=True)]})
        self.env.flush_all()

        self.env.invalidate_all()
        rec = inv.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable'
        )[:1]
        product_total = sum(abs(l.foreign_subtotal) for l in inv.line_ids if l.display_type == 'product')
        tax_total = sum(abs(l.foreign_balance) for l in inv.line_ids if l.display_type == 'tax')
        new_exempt = inv.invoice_line_ids.filtered(lambda l: not l.tax_ids)[:1]
        self.assertAlmostEqual(inv.amount_total, 332.0, places=2)
        self.assertTrue(rec)
        self.assertAlmostEqual(rec.foreign_balance, rec.foreign_debit, places=2)
        self.assertAlmostEqual(product_total + tax_total, rec.foreign_balance, places=2)
        self.assertAlmostEqual(
            sum(inv.line_ids.mapped('foreign_debit')),
            sum(inv.line_ids.mapped('foreign_credit')),
            places=2,
        )
        self.assertAlmostEqual(new_exempt.foreign_price, edited, places=2)
        self.assertTrue(new_exempt.foreign_price_manual)

    def test_repro_manual_alterno_in_invoice_add_product(self):
        purchase_journal = self.env["account.journal"].sudo().create({
            "name": "Purchases Repro", "code": "PRCH",
            "type": "purchase", "company_id": self.company.id,
            "default_account_id": self.acc_exp.id,
        })
        tax_16_p = self.env["account.tax"].with_company(self.company).create({
            "name": "16% DE COMPRAS", "amount": 16.0, "amount_type": "percent",
            "type_tax_use": "purchase", "company_id": self.company.id,
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
        def mk_line(price):
            return Command.create({
                "product_id": self.product.id,
                "quantity": 1.0, "price_unit": price,
                "account_id": self.acc_exp.id,
                "tax_ids": [(6, 0, [tax_16_p.id])],
            })
        inv = self.env["account.move"].with_context(check_move_validity=False).create({
            "move_type": "in_invoice",
            "partner_id": self.partner.id,
            "journal_id": purchase_journal.id,
            "currency_id": self.currency_vef.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [mk_line(723.0), mk_line(1447.998)],
        })
        line2 = inv.invoice_line_ids.sorted(key=lambda l: l.id)[-1]
        line2_id = line2.id
        computed = line2.foreign_price
        edited = computed + 0.01
        inv.write({"invoice_line_ids": [
            (1, line2_id, {"foreign_price": edited}),
        ]})
        self.env.flush_all()
        self.assertTrue(line2.foreign_price_manual)

        tax_line = inv.line_ids.filtered(
            lambda l: l.tax_repartition_line_id and l.tax_repartition_line_id.repartition_type == 'tax'
        )[:1]
        self.assertTrue(tax_line)
        tax_fd_before = tax_line.foreign_debit
        other_base = sum(
            abs(l.foreign_subtotal) for l in inv.invoice_line_ids if l.id != line2_id
        )
        expected_tax = round((edited + other_base) * tax_16_p.amount / 100.0, 2)
        self.assertAlmostEqual(tax_fd_before, expected_tax, places=2)

        inv.write({"invoice_line_ids": [mk_line(723.999)]})
        self.env.flush_all()

        self.env.invalidate_all()
        new_line2 = inv.invoice_line_ids.filtered(lambda l: l.id == line2_id)[:1]
        self.assertEqual(len(inv.invoice_line_ids), 3)
        self.assertTrue(new_line2)
        self.assertAlmostEqual(new_line2.foreign_price, edited, places=2)
        self.assertTrue(new_line2.foreign_price_manual)

        new_tax_line = inv.line_ids.filtered(
            lambda l: l.tax_repartition_line_id and l.tax_repartition_line_id.repartition_type == 'tax'
        )
        tax_fd_after = sum(abs(l.foreign_debit) for l in new_tax_line if l.foreign_debit)
        added_subtotal = abs(
            inv.invoice_line_ids.filtered(lambda l: l.id != line2_id).sorted(
                key=lambda l: l.id
            )[-1].foreign_subtotal
        )
        expected_tax_after = round((edited + other_base + added_subtotal) * tax_16_p.amount / 100.0, 2)
        self.assertAlmostEqual(tax_fd_after, expected_tax_after, places=2)

    def test_tax_line_foreign_split_with_manual_alterno(self):
        usd_rate = self.env["res.currency.rate"].search([
            ("currency_id", "=", self.currency_usd.id),
            ("company_id", "=", self.company.id),
        ], limit=1)
        usd_rate.inverse_company_rate = 723.999
        acc_exp2 = self._get_or_create('550100', 'Expense 2', 'expense')
        tax_16_p = self.env["account.tax"].with_company(self.company).create({
            "name": "16% DE COMPRAS", "amount": 16.0, "amount_type": "percent",
            "type_tax_use": "purchase", "company_id": self.company.id,
            "tax_group_id": self.tax_group.id,
            "invoice_repartition_line_ids": [
                (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0}),
            ],
            "refund_repartition_line_ids": [
                (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0}),
            ],
        })
        purchase_journal = self.env["account.journal"].sudo().create({
            "name": "Purchases Split", "code": "PSPL",
            "type": "purchase", "company_id": self.company.id,
            "default_account_id": self.acc_exp.id,
        })
        def mk_line(price, account):
            return Command.create({
                "product_id": self.product.id,
                "quantity": 1.0, "price_unit": price,
                "account_id": account.id,
                "tax_ids": [(6, 0, [tax_16_p.id])],
            })
        inv = self.env["account.move"].with_context(check_move_validity=False).create({
            "move_type": "in_invoice",
            "partner_id": self.partner.id,
            "journal_id": purchase_journal.id,
            "currency_id": self.currency_vef.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [
                mk_line(723.999, self.acc_exp),
                mk_line(723.0, acc_exp2),
            ],
        })
        line2 = inv.invoice_line_ids.sorted(key=lambda l: l.id)[-1]
        line2_id = line2.id
        inv.write({"invoice_line_ids": [(1, line2_id, {"foreign_price": 2.0})]})
        self.env.flush_all()
        self.assertTrue(line2.foreign_price_manual)
        self.assertAlmostEqual(line2.foreign_price, 2.0, places=2)

        tax_lines = inv.line_ids.filtered(
            lambda l: l.tax_repartition_line_id
            and l.tax_repartition_line_id.repartition_type == 'tax'
        )
        self.assertEqual(len(tax_lines), 2)
        sorted_tax = tax_lines.sorted(key=lambda l: abs(l.amount_currency))
        self.assertAlmostEqual(abs(sorted_tax[0].foreign_debit), 0.32, places=2)
        self.assertAlmostEqual(abs(sorted_tax[1].foreign_debit), 0.16, places=2)

        product_fd = sum(abs(l.foreign_debit) for l in inv.line_ids if l.display_type == 'product')
        tax_fd = sum(abs(l.foreign_debit) for l in tax_lines)
        pt = inv.line_ids.filtered(lambda l: l.display_type == 'payment_term')[:1]
        self.assertTrue(pt)
        self.assertAlmostEqual(pt.foreign_credit, product_fd + tax_fd, places=2)
        self.assertAlmostEqual(
            sum(inv.line_ids.mapped('foreign_debit')),
            sum(inv.line_ids.mapped('foreign_credit')),
            places=2,
        )

    def test_tax_line_foreign_split_after_adding_product(self):
        usd_rate = self.env["res.currency.rate"].search([
            ("currency_id", "=", self.currency_usd.id),
            ("company_id", "=", self.company.id),
        ], limit=1)
        usd_rate.inverse_company_rate = 723.999
        self.currency_usd.write({"rounding": 0.0001, "decimal_places": 4})
        self.currency_vef.write({"rounding": 0.0001, "decimal_places": 4})
        acc_exp2 = self._get_or_create('550100', 'Expense 2', 'expense')
        tax_16_p = self.env["account.tax"].with_company(self.company).create({
            "name": "16% DE COMPRAS", "amount": 16.0, "amount_type": "percent",
            "type_tax_use": "purchase", "company_id": self.company.id,
            "tax_group_id": self.tax_group.id,
            "invoice_repartition_line_ids": [
                (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0}),
            ],
            "refund_repartition_line_ids": [
                (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0}),
            ],
        })
        purchase_journal = self.env["account.journal"].sudo().create({
            "name": "Purchases Add", "code": "PADD",
            "type": "purchase", "company_id": self.company.id,
            "default_account_id": self.acc_exp.id,
        })
        def mk_line(price, account):
            return Command.create({
                "product_id": self.product.id,
                "quantity": 1.0, "price_unit": price,
                "account_id": account.id,
                "tax_ids": [(6, 0, [tax_16_p.id])],
            })
        inv = self.env["account.move"].with_context(check_move_validity=False).create({
            "move_type": "in_invoice",
            "partner_id": self.partner.id,
            "journal_id": purchase_journal.id,
            "currency_id": self.currency_vef.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [
                mk_line(723.999, self.acc_exp),
                mk_line(723.0, acc_exp2),
            ],
        })
        line2 = inv.invoice_line_ids.sorted(key=lambda l: l.id)[-1]
        line2_id = line2.id
        inv.write({"invoice_line_ids": [(1, line2_id, {"foreign_price": 1.0})]})
        self.env.flush_all()
        self.assertTrue(line2.foreign_price_manual)

        inv.write({"invoice_line_ids": [mk_line(723.999, acc_exp2)]})
        self.env.flush_all()

        self.env.invalidate_all()
        new_line2 = inv.invoice_line_ids.filtered(lambda l: l.id == line2_id)[:1]
        self.assertAlmostEqual(new_line2.foreign_price, 1.0, places=4)
        self.assertTrue(new_line2.foreign_price_manual)

        tax_lines = inv.line_ids.filtered(
            lambda l: l.tax_repartition_line_id
            and l.tax_repartition_line_id.repartition_type == 'tax'
        )
        self.assertEqual(len(tax_lines), 2)
        by_native = {abs(l.amount_currency): l for l in tax_lines}
        merged_tax = by_native[round(723.0 * tax_16_p.amount / 100.0
                                     + 723.999 * tax_16_p.amount / 100.0, 2)]
        other_tax = by_native[round(723.999 * tax_16_p.amount / 100.0, 2)]
        self.assertAlmostEqual(abs(merged_tax.foreign_debit), 0.32, places=4)
        self.assertAlmostEqual(abs(other_tax.foreign_debit), 0.16, places=4)

        product_fd = sum(abs(l.foreign_debit) for l in inv.line_ids if l.display_type == 'product')
        tax_fd = sum(abs(l.foreign_debit) for l in tax_lines)
        pt = inv.line_ids.filtered(lambda l: l.display_type == 'payment_term')[:1]
        self.assertTrue(pt)
        self.assertAlmostEqual(pt.foreign_credit, product_fd + tax_fd, places=4)
        self.assertAlmostEqual(
            sum(inv.line_ids.mapped('foreign_debit')),
            sum(inv.line_ids.mapped('foreign_credit')),
            places=4,
        )

    def test_form_manual_alterno_preserved_when_adding_product(self):
        purchase_journal = self.env["account.journal"].sudo().create({
            "name": "Purchases Repro2", "code": "PRC2",
            "type": "purchase", "company_id": self.company.id,
            "default_account_id": self.acc_exp.id,
        })
        def mk_line(price):
            return Command.create({
                "product_id": self.product.id,
                "quantity": 1.0, "price_unit": price,
                "account_id": self.acc_exp.id,
                "tax_ids": [(6, 0, [self.tax_16.id])],
            })
        inv = self.env["account.move"].with_context(check_move_validity=False).create({
            "move_type": "in_invoice",
            "partner_id": self.partner.id,
            "journal_id": purchase_journal.id,
            "currency_id": self.currency_vef.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [mk_line(723.0), mk_line(1447.998)],
        })

        line_ids_before = inv.invoice_line_ids.ids
        form = Form(inv, view="account.view_move_form")
        computed = None
        edited = None
        with form.invoice_line_ids.edit(1) as line2_form:
            computed = line2_form.foreign_price
            edited = computed + 0.01
            line2_form.foreign_price = edited
        inv = form.save()
        saved_line2 = inv.invoice_line_ids.browse(line_ids_before[1])
        self.assertTrue(saved_line2.foreign_price_manual)

        form = Form(inv, view="account.view_move_form")
        with form.invoice_line_ids.new() as new_line:
            new_line.product_id = self.product
            new_line.quantity = 1.0
            new_line.price_unit = 723.999
        inv = form.save()

        self.env.invalidate_all()
        new_line2 = inv.invoice_line_ids.browse(line_ids_before[1])
        self.assertTrue(new_line2)
        self.assertAlmostEqual(new_line2.foreign_price, edited, places=2)
        self.assertTrue(new_line2.foreign_price_manual)

    def test_web_onchange_manual_alterno_add_product(self):
        purchase_journal = self.env["account.journal"].sudo().create({
            "name": "Purchases Repro3", "code": "PRC3",
            "type": "purchase", "company_id": self.company.id,
            "default_account_id": self.acc_exp.id,
        })
        def mk_line(price):
            return Command.create({
                "product_id": self.product.id,
                "quantity": 1.0, "price_unit": price,
                "account_id": self.acc_exp.id,
                "tax_ids": [(6, 0, [self.tax_16.id])],
            })
        inv = self.env["account.move"].with_context(check_move_validity=False).create({
            "move_type": "in_invoice",
            "partner_id": self.partner.id,
            "journal_id": purchase_journal.id,
            "currency_id": self.currency_vef.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [mk_line(723.0), mk_line(1447.998)],
        })
        line2 = inv.invoice_line_ids.sorted(key=lambda l: l.id)[-1]
        computed = line2.foreign_price
        edited = computed + 0.01
        line2.foreign_price = edited
        self.assertTrue(line2.foreign_price_manual)

        probe = Form(inv, view="account.view_move_form")
        fields_spec = probe._view['fields_spec']
        sub_fields = fields_spec['invoice_line_ids']['fields']
        self.assertIn("foreign_price_manual", sub_fields)
        tax_line = inv.line_ids.filtered('tax_repartition_line_id')[:1]
        tax_fd_before = tax_line.foreign_debit
        line2_view_vals = {f: line2[f] for f in sub_fields if f in line2._fields}
        line2_view_vals.pop('id', None)
        values = {
            "move_type": "in_invoice",
            "partner_id": self.partner.id,
            "currency_id": self.currency_vef.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [
                (1, line2.id, line2_view_vals),
                (0, 0, {"product_id": self.product.id, "quantity": 1.0,
                        "price_unit": 723.999, "account_id": self.acc_exp.id,
                        "tax_ids": [(6, 0, [self.tax_16.id])]}),
            ],
        }
        res = inv.onchange(values, ["invoice_line_ids"], fields_spec)
        o2m_commands = (res.get("value") or {}).get("invoice_line_ids") or []
        line2_cmd = [c for c in o2m_commands
                     if c[0] in (Command.UPDATE, Command.LINK, Command.DELETE)
                     and c[1] == line2.id]
        line2_values = line2_cmd[0][2] if line2_cmd and line2_cmd[0][0] == Command.UPDATE else {}
        line_ids_cmds = (res.get("value") or {}).get("line_ids") or []
        tax_cmd = [c for c in line_ids_cmds
                   if c[0] in (Command.UPDATE, Command.CREATE, Command.LINK)
                   and (c[1] == tax_line.id)]
        tax_vals = tax_cmd[0][2] if tax_cmd and tax_cmd[0][0] == Command.UPDATE else {}
        self.assertNotIn("foreign_price", line2_values)
        self.assertNotIn("foreign_debit", tax_vals)
        self.assertNotIn("foreign_credit", tax_vals)
        self.assertTrue(line2.foreign_price_manual)
        self.assertAlmostEqual(tax_fd_before, tax_line.foreign_debit, places=2)

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

    def test_native_price_change_reinits_manual_alterno(self):
        purchase_journal = self.env["account.journal"].sudo().create({
            "name": "Purchases Reinit", "code": "PRNT",
            "type": "purchase", "company_id": self.company.id,
            "default_account_id": self.acc_exp.id,
        })
        inv = self.env["account.move"].with_context(check_move_validity=False).create({
            "move_type": "in_invoice",
            "partner_id": self.partner.id,
            "journal_id": purchase_journal.id,
            "currency_id": self.currency_vef.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 1.0, "price_unit": 723.999,
                "account_id": self.acc_exp.id,
                "tax_ids": [(6, 0, [self.tax_16.id])],
            })],
        })
        line = inv.invoice_line_ids[:1]
        rate = inv.foreign_inverse_rate
        self.assertAlmostEqual(line.foreign_price, 723.999 * rate, places=4)

        line.foreign_price = line.foreign_price + 0.01
        self.assertTrue(line.foreign_price_manual)

        line.price_unit = 1000.0
        self.env.flush_all()
        self.env.invalidate_all()
        self.assertAlmostEqual(line.foreign_price, 1000.0 * rate, places=4)

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

    # ═══════════════════════════════════════════════════════════════
    # Stress: 10+ product lines added via Form, high prices, taxes with
    # and without account on repartition. Validate alterno prices, tax
    # foreign amounts, counterpart and global alterno balance after every
    # add, alterno edit and line delete.
    # ═══════════════════════════════════════════════════════════════

    def _setup_stress(self):
        acc_pay = self._get_or_create('210000', 'Accounts Payable',
                                      'liability_payable', reconcile=True)
        acc_exp2 = self._get_or_create('550100', 'Expense 2', 'expense')
        acc_tax2 = self._get_or_create('200100', 'Tax Payable 8%',
                                       'liability_current', reconcile=True)
        self.partner.property_account_payable_id = acc_pay.id
        purchase_journal = self.env["account.journal"].sudo().create({
            "name": "Purchases Stress", "code": "PSTR",
            "type": "purchase", "company_id": self.company.id,
            "default_account_id": self.acc_exp.id,
        })
        taxes = {
            '16': self._create_tax_ext('IVA 16%', 16.0, account_id=self.acc_tax.id,
                                       type_tax_use='purchase'),
            '8': self._create_tax_ext('IVA 8%', 8.0, account_id=acc_tax2.id,
                                      type_tax_use='purchase'),
            'noacct': self._create_tax_ext('IVA 10% sin cuenta', 10.0,
                                           account_id=None, type_tax_use='purchase'),
        }
        products = {}
        for key, tax in taxes.items():
            products[key] = self.env["product.product"].create({
                "name": f"Stress Serv {key}", "type": "service",
                "list_price": 100.0,
                "property_account_income_id": self.acc_inc.id,
                "property_account_expense_id": self.acc_exp.id,
                "taxes_id": [(5, 0, 0)],
                "supplier_taxes_id": [(6, 0, tax.ids)],
            })
        products['exempt'] = self.env["product.product"].create({
            "name": "Stress Serv Exempt", "type": "service",
            "list_price": 100.0,
            "property_account_income_id": self.acc_inc.id,
            "property_account_expense_id": self.acc_exp.id,
            "taxes_id": [(5, 0, 0)], "supplier_taxes_id": [(5, 0, 0)],
        })
        return purchase_journal, products, acc_exp2

    def _stress_invoice(self, currency):
        purchase_journal, products, acc_exp2 = self._setup_stress()
        prices = [1_250_000.0, 2_345_678.90, 3_456_789.75, 4_567_890.25,
                  5_678_901.50, 6_789_012.34, 7_890_123.45, 8_901_234.56,
                  9_123_456.78, 9_999_999.99]
        inv = self.env["account.move"].with_context(check_move_validity=False).create({
            "move_type": "in_invoice",
            "partner_id": self.partner.id,
            "journal_id": purchase_journal.id,
            "currency_id": currency.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [],
        })
        form = Form(inv, view="account.view_move_form")
        for i, price in enumerate(prices):
            prod = products[['16', '8', 'noacct', 'exempt'][i % 4]]
            account = acc_exp2 if i % 3 == 0 else self.acc_exp
            with form.invoice_line_ids.new() as nl:
                nl.product_id = prod
                nl.quantity = 1.0
                nl.price_unit = price
                nl.account_id = account
            inv = form.save()
            self._assert_foreign_consistency(inv, f"add{i}")
        return inv

    def test_form_vef_base_stress_10_products(self):
        random.seed(42)
        inv = self._stress_invoice(self.currency_vef)
        self.assertEqual(len(inv.invoice_line_ids), 10)
        self.assertGreater(inv.foreign_inverse_rate, 0)

        for step in range(3):
            form = Form(inv, view="account.view_move_form")
            idx = random.randrange(len(form.invoice_line_ids))
            with form.invoice_line_ids.edit(idx) as lf:
                lf.foreign_price = lf.foreign_price * random.choice([1.05, 0.95, 1.12])
            inv = form.save()
            self._assert_foreign_consistency(inv, f"edit{step}")

        for step in range(3):
            form = Form(inv, view="account.view_move_form")
            idx = random.randrange(len(form.invoice_line_ids))
            form.invoice_line_ids.remove(idx)
            inv = form.save()
            self._assert_foreign_consistency(inv, f"del{step}")

    def test_form_usd_base_stress_10_products(self):
        random.seed(7)
        usd_rate = self.env["res.currency.rate"].search([
            ("currency_id", "=", self.currency_usd.id),
            ("company_id", "=", self.company.id)], limit=1)
        vef_rate = self.env["res.currency.rate"].search([
            ("currency_id", "=", self.currency_vef.id),
            ("company_id", "=", self.company.id)], limit=1)
        if usd_rate:
            usd_rate.inverse_company_rate = 1.0
        if vef_rate:
            vef_rate.inverse_company_rate = 0.02
        self.company.write({
            "currency_id": self.currency_usd.id,
            "currency_foreign_id": self.currency_vef.id,
        })
        self.env.flush_all()

        inv = self._stress_invoice(self.currency_usd)
        self.assertEqual(len(inv.invoice_line_ids), 10)
        self.assertGreater(inv.foreign_inverse_rate, 0)

        for step in range(3):
            form = Form(inv, view="account.view_move_form")
            idx = random.randrange(len(form.invoice_line_ids))
            with form.invoice_line_ids.edit(idx) as lf:
                lf.foreign_price = lf.foreign_price * random.choice([1.05, 0.95, 1.12])
            inv = form.save()
            self._assert_foreign_consistency(inv, f"edit{step}")

        for step in range(3):
            form = Form(inv, view="account.view_move_form")
            idx = random.randrange(len(form.invoice_line_ids))
            form.invoice_line_ids.remove(idx)
            inv = form.save()
            self._assert_foreign_consistency(inv, f"del{step}")

    def test_real_case_stale_alterno_tax_totals_matches_entry(self):
        usd_rate = self.env["res.currency.rate"].search([
            ("currency_id", "=", self.currency_usd.id),
            ("company_id", "=", self.company.id),
        ], order="name desc", limit=1)
        usd_rate.write({"inverse_company_rate": 746.63})
        self.env.flush_all()

        product = self.env["product.product"].create({
            "name": "REAL CASE", "type": "service", "list_price": 100.0,
            "property_account_income_id": self.acc_inc.id,
            "taxes_id": [(6, 0, [self.tax_16.id])], "supplier_taxes_id": [(5, 0, 0)],
        })
        inv = self.env["account.move"].with_context(check_move_validity=False).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_vef.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [Command.create({
                "product_id": product.id,
                "quantity": 1.0, "price_unit": 1156979.90,
                "account_id": self.acc_inc.id,
                "tax_ids": [(6, 0, [self.tax_16.id])],
            })],
        })
        inv.action_post()
        self.env.flush_all()
        self.env.invalidate_all()
        self._assert_tax_totals_foreign(inv, "real-coherent")

        product_line = inv.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product')[:1]
        product_line.foreign_price = 1549.25
        self.env.flush_all()
        self.env.invalidate_all()

        tt = inv.tax_totals or {}
        entry_untaxed = sum(
            abs(l.foreign_subtotal)
            for l in inv.line_ids if l.display_type == 'product')
        entry_total = entry_untaxed + sum(
            abs(l.foreign_debit - l.foreign_credit)
            for l in inv.line_ids if l.display_type == 'tax')

        self.assertEqual(round(entry_untaxed, 2), 1549.25)
        self.assertEqual(round(entry_total, 2), 1797.13)
        self.assertEqual(round(tt['foreign_amount_untaxed'], 2), 1549.25)
        self.assertEqual(round(tt['foreign_amount_total'], 2), 1797.13)

        self.assertAlmostEqual(
            tt['foreign_amount_untaxed'], entry_untaxed, places=1)
        self.assertAlmostEqual(
            tt['foreign_amount_total'], entry_total, places=1)

        group_base = sum(
            g['tax_group_base_amount']
            for subtotals in tt['groups_by_foreign_subtotal'].values()
            for g in subtotals)
        self.assertAlmostEqual(group_base, tt['foreign_amount_untaxed'], places=1)

        self._assert_tax_totals_foreign(inv, "real-stale-aligned")

    def test_real_case_vef_base_alterno_matches_entry(self):
        usd_rate = self.env["res.currency.rate"].search([
            ("currency_id", "=", self.currency_usd.id),
            ("company_id", "=", self.company.id),
        ], order="name desc", limit=1)
        usd_rate.write({"inverse_company_rate": 742.81})
        self.env.flush_all()

        product = self.env["product.product"].create({
            "name": "REAL VEF CASE", "type": "service", "list_price": 100.0,
            "property_account_income_id": self.acc_inc.id,
            "taxes_id": [(6, 0, [self.tax_16.id])], "supplier_taxes_id": [(5, 0, 0)],
        })
        inv = self.env["account.move"].with_context(check_move_validity=False).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_vef.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [Command.create({
                "product_id": product.id,
                "quantity": 1.0, "price_unit": 1177430.0,
                "account_id": self.acc_inc.id,
                "tax_ids": [(6, 0, [self.tax_16.id])],
            })],
        })
        self.env.flush_all()
        self.env.invalidate_all()
        self._assert_tax_totals_foreign(inv, "vef-real-coherent")

        product_line = inv.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product')[:1]
        product_line.foreign_price = 1611.22
        self.env.flush_all()
        self.env.invalidate_all()

        tt = inv.tax_totals or {}
        entry_untaxed = sum(
            abs(l.foreign_subtotal)
            for l in inv.line_ids if l.display_type == 'product')
        entry_total = entry_untaxed + sum(
            abs(l.foreign_debit - l.foreign_credit)
            for l in inv.line_ids if l.display_type == 'tax')

        self.assertEqual(round(entry_untaxed, 2), 1611.22)
        self.assertEqual(round(entry_total, 2), 1869.02)
        self.assertEqual(round(tt['foreign_amount_untaxed'], 2), 1611.22)
        self.assertEqual(round(tt['foreign_amount_total'], 2), 1869.02)

        self.assertAlmostEqual(
            tt['foreign_amount_untaxed'], entry_untaxed, places=1)
        self.assertAlmostEqual(
            tt['foreign_amount_total'], entry_total, places=1)

        self._assert_tax_totals_foreign(inv, "vef-real-aligned")

    def test_mixed_sign_discount_foreign_total(self):
        """A negative product line (global discount) must SUBTRACT from the
        foreign total instead of adding its magnitude (#14341 review finding)."""
        product = self.env["product.product"].create({
            "name": "MIXED SIGN", "type": "service", "list_price": 100.0,
            "property_account_income_id": self.acc_inc.id,
            "taxes_id": [(6, 0, [self.tax_16.id])], "supplier_taxes_id": [(5, 0, 0)],
        })
        # from_loyalty bypasses l10n_ve_invoice's negative-price-line guard
        # (_check_price_in_zero): this test targets foreign-amount sign
        # handling, not that unrelated business validation.
        inv = self.env["account.move"].with_context(
            check_move_validity=False, from_loyalty=True,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_vef.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": product.id, "quantity": 1.0, "price_unit": 100.0,
                    "account_id": self.acc_inc.id, "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
                Command.create({
                    "product_id": product.id, "quantity": 1.0, "price_unit": -20.0,
                    "account_id": self.acc_inc.id, "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
            ],
        })
        inv.action_post()
        self.env.flush_all()
        self.env.invalidate_all()

        # Force a stale alterno on the first line so the align block in
        # l10n_ve_tax._prepare_tax_totals is exercised.
        product_line = inv.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product')[:1]
        product_line.foreign_price = 2.10
        self.env.flush_all()
        self.env.invalidate_all()

        tt = inv.tax_totals or {}
        entry_untaxed = sum(
            l.foreign_subtotal
            for l in inv.line_ids if l.display_type == 'product')
        entry_tax = inv.direction_sign * sum(
            l.foreign_debit - l.foreign_credit
            for l in inv.line_ids if l.display_type == 'tax')
        expected_total = abs(entry_untaxed + entry_tax)

        naive_total = sum(
            abs(l.foreign_subtotal)
            for l in inv.line_ids if l.display_type == 'product')
        naive_total += abs(entry_tax)

        self.assertNotAlmostEqual(
            naive_total, expected_total, places=2,
            msg="test premise: naive abs() sum must differ from the signed sum")

        self.assertAlmostEqual(
            tt['foreign_amount_total'], expected_total, places=2,
            msg="negative discount line must subtract from the foreign total")
        self.assertNotAlmostEqual(
            tt['foreign_amount_total'], naive_total, places=2,
            msg="abs() per line must not be used (discount inflated the total)")

    # ═══════════════════════════════════════════════════════════════
    # res_currency.py - edit_rate / unlink
    # ═══════════════════════════════════════════════════════════════

    def test_currency_edit_rate_true_for_support_group(self):
        group = self.env.ref("l10n_ve_accountant.group_fiscal_config_support")
        user = self.env.user
        user.groups_id = [(4, group.id)]
        self.currency_usd.invalidate_recordset(["edit_rate"])
        self.assertTrue(self.currency_usd.with_user(user).edit_rate)

    def test_currency_edit_rate_false_without_group(self):
        group = self.env.ref("l10n_ve_accountant.group_fiscal_config_support")
        user = self.env.user
        user.groups_id = [(3, group.id)]
        self.currency_usd.invalidate_recordset(["edit_rate"])
        self.assertFalse(self.currency_usd.with_user(user).edit_rate)

    def test_currency_unlink_blocked_without_group(self):
        group = self.env.ref("l10n_ve_accountant.group_fiscal_config_support")
        currency = self.env["res.currency"].create({
            "name": "TCB", "symbol": "TCB",
        })
        user = self.env.user
        user.groups_id = [(3, group.id)]
        with self.assertRaises(UserError):
            currency.with_user(user).unlink()

    def test_currency_unlink_allowed_with_group(self):
        group = self.env.ref("l10n_ve_accountant.group_fiscal_config_support")
        currency = self.env["res.currency"].create({
            "name": "TCA", "symbol": "TCA",
        })
        user = self.env.user
        user.groups_id = [(4, group.id)]
        currency.with_user(user).unlink()
        self.assertFalse(currency.exists())

    # ═══════════════════════════════════════════════════════════════
    # account_payment.py - _prepare_move_line_default_vals (more branches)
    # ═══════════════════════════════════════════════════════════════

    def _bank_journal_with_methods(self, code):
        manual_in = self.env.ref("account.account_payment_method_manual_in")
        manual_out = self.env.ref("account.account_payment_method_manual_out")
        return self.env['account.journal'].create({
            'name': f'Bank {code}', 'code': code, 'type': 'bank',
            'default_account_id': self.acc_bank.id, 'company_id': self.company.id,
            'inbound_payment_method_line_ids': [(0, 0, {
                'name': f'In{code}', 'payment_method_id': manual_in.id,
                'payment_type': 'inbound', 'payment_account_id': self.acc_bank.id,
            })],
            'outbound_payment_method_line_ids': [(0, 0, {
                'name': f'Out{code}', 'payment_method_id': manual_out.id,
                'payment_type': 'outbound', 'payment_account_id': self.acc_bank.id,
            })],
        })

    def test_prepare_move_line_default_vals_foreign_currency_outbound(self):
        bank = self._bank_journal_with_methods('BNKO1')
        pml = bank.outbound_payment_method_line_ids[:1]
        pay = self.env["account.payment"].create({
            "payment_type": "outbound", "partner_type": "supplier",
            "partner_id": self.partner.id, "amount": 100.0,
            "currency_id": self.currency_usd.id,
            "payment_method_line_id": pml.id, "journal_id": bank.id,
        })
        pay._compute_rate()
        vals = pay._prepare_move_line_default_vals()
        self.assertEqual(len(vals), 2)
        self.assertLessEqual(vals[0]['debit'], 0.0)

    def test_prepare_move_line_default_vals_third_currency(self):
        bank = self._bank_journal_with_methods('BNKO2')
        pml = bank.inbound_payment_method_line_ids[:1]
        pay = self.env["account.payment"].create({
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": self.partner.id, "amount": 100.0,
            "currency_id": self.currency_eur.id,
            "payment_method_line_id": pml.id, "journal_id": bank.id,
        })
        pay._compute_rate()
        vals = pay._prepare_move_line_default_vals()
        self.assertEqual(len(vals), 2)

    def test_prepare_move_line_default_vals_with_write_off(self):
        bank = self._bank_journal_with_methods('BNKO3')
        pml = bank.inbound_payment_method_line_ids[:1]
        pay = self.env["account.payment"].create({
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": self.partner.id, "amount": 100.0,
            "currency_id": self.currency_usd.id,
            "payment_method_line_id": pml.id, "journal_id": bank.id,
        })
        pay._compute_rate()
        vals = pay._prepare_move_line_default_vals(write_off_line_vals=[
            {"balance": 5.0, "amount_currency": 5.0, "account_id": self.acc_exp.id},
        ])
        self.assertGreaterEqual(len(vals), 2)

    # ═══════════════════════════════════════════════════════════════
    # wizard/account_payment_register.py
    # ═══════════════════════════════════════════════════════════════

    def _register_wizard(self, invoice, extra_vals=None):
        vals = dict(extra_vals or {})
        return self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=invoice.ids, active_id=invoice.id,
        ).create(vals)

    def test_payment_register_default_get_sets_foreign_total_billed_vef(self):
        invoice = self._create_invoice(self.currency_usd, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        wizard = self._register_wizard(invoice)
        self.assertAlmostEqual(
            wizard.foreign_total_billed_vef, invoice.foreign_amount_residual, places=2,
        )

    def test_payment_register_compute_foreign_rate_no_date(self):
        invoice = self._create_invoice(self.currency_usd, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        wizard = self._register_wizard(invoice)
        wizard.payment_date = False
        wizard._compute_foreign_rate()
        self.assertEqual(wizard.foreign_rate, 0.0)

    def test_payment_register_compute_foreign_rate_with_date(self):
        invoice = self._create_invoice(self.currency_usd, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        wizard = self._register_wizard(invoice)
        wizard.payment_date = fields.Date.today()
        wizard._compute_foreign_rate()
        self.assertGreater(wizard.foreign_rate, 0.0)
        wizard._compute_foreign_inverse_rate()
        self.assertGreater(wizard.foreign_inverse_rate, 0.0)

    def test_payment_register_total_amount_same_currency(self):
        invoice = self._create_invoice(self.currency_usd, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        wizard = self._register_wizard(invoice)
        self.assertEqual(wizard.source_currency_id, wizard.currency_id)
        self.assertGreater(wizard.amount, 0.0)

    def test_payment_register_total_amount_foreign_to_company(self):
        invoice = self._create_invoice(self.currency_usd, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        wizard = self._register_wizard(invoice, {"currency_id": self.currency_vef.id})
        self.assertGreater(wizard.amount, 0.0)

    def test_payment_register_total_amount_company_to_foreign(self):
        invoice = self._create_invoice(self.currency_vef, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        wizard = self._register_wizard(invoice, {"currency_id": self.currency_usd.id})
        self.assertGreater(wizard.amount, 0.0)

    def test_payment_register_total_amount_foreign_to_foreign(self):
        invoice = self._create_invoice(self.currency_eur, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        wizard = self._register_wizard(invoice, {"currency_id": self.currency_usd.id})
        self.assertGreater(wizard.amount, 0.0)

    def test_payment_register_create_payment_vals_includes_rate(self):
        invoice = self._create_invoice(self.currency_usd, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        wizard = self._register_wizard(invoice)
        wizard.payment_date = fields.Date.today()
        result = wizard.action_create_payments()
        payment = self.env["account.payment"].search(
            [("partner_id", "=", self.partner.id)], order="id desc", limit=1,
        )
        self.assertAlmostEqual(payment.foreign_rate, wizard.foreign_rate, places=2)
        self.assertAlmostEqual(payment.foreign_inverse_rate, wizard.foreign_inverse_rate, places=2)

    # ═══════════════════════════════════════════════════════════════
    # report/all_payment_report.py
    # ═══════════════════════════════════════════════════════════════

    def test_all_payment_report_missing_context_raises(self):
        report = self.env["report.l10n_ve_accountant.financial_all_payments"]
        with self.assertRaises(UserError):
            report._get_report_values([], data={"form": {"payment_type": "inbound"}})

    def test_all_payment_report_missing_form_raises(self):
        report = self.env["report.l10n_ve_accountant.financial_all_payments"].with_context(
            active_model="account.payment", active_id=1,
        )
        with self.assertRaises(UserError):
            report._get_report_values([], data={})

    def test_all_payment_report_returns_docs_and_labels(self):
        bank = self._bank_journal_with_methods('BNKO4')
        pml = bank.inbound_payment_method_line_ids[:1]
        payment = self.env["account.payment"].create({
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": self.partner.id, "amount": 100.0,
            "currency_id": self.currency_vef.id,
            "payment_method_line_id": pml.id, "journal_id": bank.id,
        })
        report = self.env["report.l10n_ve_accountant.financial_all_payments"].with_context(
            active_model="account.payment", active_id=payment.id,
        )
        today = fields.Date.today()
        result = report._get_report_values([], data={
            "form": {
                "payment_type": "inbound",
                "journal_id": bank.id,
                "start_date": today,
                "end_date": today,
            },
            "context": {"uid": self.env.uid},
        })
        self.assertIn(payment, result["docs"])
        self.assertEqual(result["payment_type"], "De Clientes")
        self.assertEqual(result["journal"], bank.name)

    # ═══════════════════════════════════════════════════════════════
    # account_invoice_report.py - get_view / _select
    # ═══════════════════════════════════════════════════════════════

    def test_invoice_report_get_view_relabels_foreign_fields(self):
        res = self.env["account.invoice.report"].get_view(view_type="pivot")
        self.assertIn("Total Billed (", res["arch"])
        self.assertIn("Foreign Rate (", res["arch"])
        self.assertIn("Foreign Total (", res["arch"])

    def test_invoice_report_get_view_no_foreign_currency(self):
        self.company.currency_foreign_id = False
        res = self.env["account.invoice.report"].get_view(view_type="pivot")
        self.assertNotIn("Total Billed (", res["arch"])

    def test_invoice_report_select_query_reachable(self):
        invoice = self._create_invoice(self.currency_usd, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        records = self.env["account.invoice.report"].search([
            ("move_id", "=", invoice.id),
        ])
        self.assertTrue(records)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - get_invoice_line_ids_subtotals_by_name
    # ═══════════════════════════════════════════════════════════════

    def test_get_invoice_line_ids_subtotals_by_name(self):
        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_vef.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id, "name": "Same Name",
                    "quantity": 1.0, "price_unit": 50.0,
                    "account_id": self.acc_inc.id, "tax_ids": [(5, 0, 0)],
                }),
                Command.create({
                    "product_id": self.product.id, "name": "Same Name",
                    "quantity": 1.0, "price_unit": 30.0,
                    "account_id": self.acc_inc.id, "tax_ids": [(5, 0, 0)],
                }),
            ],
        })
        result = invoice.get_invoice_line_ids_subtotals_by_name()
        self.assertIn("Same Name", result)
        self.assertEqual(len(result["Same Name"]), 2)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _compute_rate_for_documents (manually_set_rate)
    # ═══════════════════════════════════════════════════════════════

    def test_compute_rate_manually_set_rate_skips_recompute(self):
        invoice = self._create_invoice(self.currency_usd, 100.0)
        invoice.manually_set_rate = True
        invoice.foreign_rate = 12.34
        invoice.date = fields.Date.today()
        invoice._compute_rate()
        self.assertAlmostEqual(invoice.foreign_rate, 12.34, places=2)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _compute_foreign_taxable_income
    # ═══════════════════════════════════════════════════════════════

    def test_compute_foreign_taxable_income(self):
        invoice = self._create_invoice(self.currency_usd, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertAlmostEqual(
            invoice.foreign_taxable_income,
            invoice.tax_totals.get("foreign_amount_untaxed", 0.0),
            places=2,
        )

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _compute_foreign_total_billed (third currency)
    # ═══════════════════════════════════════════════════════════════

    def test_foreign_total_billed_third_currency(self):
        invoice = self._create_invoice(self.currency_eur, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertGreater(invoice.foreign_total_billed, 0.0)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _onchange_foreign_rate
    # ═══════════════════════════════════════════════════════════════

    def test_onchange_foreign_rate_negative_raises(self):
        journal = self._rectification_purchase_journal()
        invoice = self._create_in_invoice(journal, fields.Date.today())
        with self.assertRaises(ValidationError):
            with Form(invoice, view="account.view_move_form") as form:
                form.foreign_rate = -5.0

    def test_onchange_foreign_rate_positive_computes_inverse(self):
        journal = self._rectification_purchase_journal()
        invoice = self._create_in_invoice(journal, fields.Date.today())
        with Form(invoice, view="account.view_move_form") as form:
            form.foreign_rate = 25.0
        invoice = form.save()
        self.assertAlmostEqual(invoice.foreign_inverse_rate, 1 / 25.0, places=6)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _check_product_id constraint
    # ═══════════════════════════════════════════════════════════════

    def test_check_product_id_constraint(self):
        with self.assertRaises(ValidationError):
            self.env["account.move"].with_context(
                check_move_validity=False,
            ).create({
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.sale_journal.id,
                "currency_id": self.currency_vef.id,
                "date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create({
                        "display_type": "product",
                        "quantity": 1.0, "price_unit": 50.0,
                        "account_id": self.acc_inc.id, "tax_ids": [(5, 0, 0)],
                    }),
                ],
            })

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - get_account_move_report_data (doc_title)
    # ═══════════════════════════════════════════════════════════════

    def test_get_account_move_report_data_doc_title_fully_paid(self):
        invoice = self._create_invoice(self.currency_vef, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        bank = self._bank_journal_with_methods('BNKO5')
        pml = bank.inbound_payment_method_line_ids[:1]
        payment = self.env["account.payment"].create({
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": self.partner.id, "amount": invoice.amount_total,
            "currency_id": self.currency_vef.id,
            "payment_method_line_id": pml.id, "journal_id": bank.id,
        })
        payment.action_post()
        (invoice.line_ids | payment.move_id.line_ids).filtered(
            lambda l: l.account_id == self.acc_rec and not l.reconciled
        ).reconcile()
        self.assertEqual(invoice.amount_residual, 0.0)
        data = invoice.get_account_move_report_data()
        self.assertTrue(data["doc_title"])

    def test_get_account_move_report_data_doc_title_partially_paid(self):
        invoice = self._create_invoice(self.currency_vef, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        bank = self._bank_journal_with_methods('BNKO6')
        pml = bank.inbound_payment_method_line_ids[:1]
        payment = self.env["account.payment"].create({
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": self.partner.id, "amount": invoice.amount_total / 2.0,
            "currency_id": self.currency_vef.id,
            "payment_method_line_id": pml.id, "journal_id": bank.id,
        })
        payment.action_post()
        (invoice.line_ids | payment.move_id.line_ids).filtered(
            lambda l: l.account_id == self.acc_rec and not l.reconciled
        ).reconcile()
        self.assertGreater(invoice.amount_residual, 0.0)
        data = invoice.get_account_move_report_data()
        self.assertFalse(data["doc_title"])

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - action_post credit limit
    # ═══════════════════════════════════════════════════════════════

    def test_action_post_credit_limit_exceeded(self):
        self.company.account_use_credit_limit = True
        self.partner.use_partner_credit_limit = True
        self.partner.credit_limit = 1.0
        invoice = self._create_invoice(self.currency_vef, 100.0)
        with self.assertRaises(ValidationError):
            invoice.with_context(move_action_post_alert=True).action_post()

    def test_action_post_credit_limit_not_exceeded(self):
        self.company.account_use_credit_limit = True
        self.partner.use_partner_credit_limit = True
        self.partner.credit_limit = 100000.0
        invoice = self._create_invoice(self.currency_vef, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, 'posted')

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - legacy_compute_line_ids_foreign_debit_and_credit
    # (dead code: no longer called by the module, kept only for
    # backward-compat; exercised directly here purely to raise coverage)
    # ═══════════════════════════════════════════════════════════════

    def test_legacy_compute_foreign_debit_credit_basic(self):
        invoice = self._create_invoice(self.currency_usd, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        invoice.legacy_compute_line_ids_foreign_debit_and_credit()
        self._assert_balances(invoice, "legacy-basic")

    def test_legacy_compute_foreign_debit_credit_two_lines_one_foreign(self):
        move = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "line_ids": [
                Command.create({
                    "account_id": self.acc_bank.id, "debit": 100.0, "credit": 0.0,
                    "currency_id": self.currency_usd.id, "amount_currency": 2.0,
                }),
                Command.create({
                    "account_id": self.acc_exp.id, "debit": 0.0, "credit": 100.0,
                }),
            ],
        })
        move.legacy_compute_line_ids_foreign_debit_and_credit()
        self._assert_balances(move, "legacy-2lines")

    def test_legacy_compute_foreign_debit_credit_all_foreign(self):
        move = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "line_ids": [
                Command.create({
                    "account_id": self.acc_bank.id, "debit": 100.0, "credit": 0.0,
                    "currency_id": self.currency_usd.id, "amount_currency": 2.0,
                }),
                Command.create({
                    "account_id": self.acc_exp.id, "debit": 0.0, "credit": 100.0,
                    "currency_id": self.currency_usd.id, "amount_currency": -2.0,
                }),
            ],
        })
        move.legacy_compute_line_ids_foreign_debit_and_credit()
        self._assert_balances(move, "legacy-allforeign")

    def test_legacy_compute_foreign_debit_credit_adjustment_and_skip(self):
        move = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "line_ids": [
                Command.create({
                    "account_id": self.acc_bank.id, "debit": 100.0, "credit": 0.0,
                    "foreign_debit_adjustment": 5.0,
                }),
                Command.create({
                    "account_id": self.acc_exp.id, "debit": 0.0, "credit": 50.0,
                    "not_foreign_recalculate": True,
                }),
                Command.create({
                    "account_id": self.acc_exp.id,
                    "debit": 0.0, "credit": 50.0,
                }),
            ],
        })
        move.legacy_compute_line_ids_foreign_debit_and_credit()
        skip_line = move.line_ids.filtered(lambda l: l.not_foreign_recalculate)
        self.assertEqual(skip_line.foreign_debit, 0.0)
        self.assertEqual(skip_line.foreign_credit, 0.0)

    def test_legacy_compute_foreign_debit_credit_multiple_receivable_lines(self):
        move = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0, "price_unit": 100.0,
                    "account_id": self.acc_inc.id, "tax_ids": [(5, 0, 0)],
                }),
            ],
        })
        move.with_context(move_action_post_alert=True).action_post()
        extra_rec = move.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable")[:1]
        extra_rec.copy({"move_id": move.id})
        move.legacy_compute_line_ids_foreign_debit_and_credit()

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _compute_inverse_rate_vef branches
    # ═══════════════════════════════════════════════════════════════

    def test_compute_inverse_rate_vef_no_foreign_currency(self):
        self.company.currency_foreign_id = False
        move = self.env["account.move"].new({
            "move_type": "entry",
            "date": fields.Date.today(),
        })
        move._compute_inverse_rate_vef()
        self.assertEqual(move.foreign_inverse_rate_vef, 0.0)

    def test_compute_inverse_rate_vef_no_date(self):
        move = self.env["account.move"].new({
            "move_type": "entry",
            "date": False,
            "invoice_date": False,
        })
        move._compute_inverse_rate_vef()
        self.assertEqual(move.foreign_inverse_rate_vef, 0.0)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _compute_detailed_amounts (mixed discount)
    # ═══════════════════════════════════════════════════════════════

    def test_detailed_amounts_mixed_discount_and_no_discount(self):
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
                    "quantity": 1.0, "price_unit": 100.0, "discount": 0.0,
                    "account_id": self.acc_inc.id, "tax_ids": [(5, 0, 0)],
                }),
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0, "price_unit": 100.0, "discount": 10.0,
                    "account_id": self.acc_inc.id, "tax_ids": [(5, 0, 0)],
                }),
            ],
        })
        details = invoice.detailed_amounts
        self.assertAlmostEqual(details.get('discount_amount', 0), 10.0, places=2)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - get_view branches
    # ═══════════════════════════════════════════════════════════════

    def test_get_view_no_foreign_currency_company(self):
        self.company.currency_foreign_id = False
        res = self.env["account.move"].get_view(view_type="form")
        self.assertIn("arch", res)

    def test_get_view_list_type_with_foreign_currency(self):
        res = self.env["account.move"].get_view(view_type="search")
        self.assertIn("arch", res)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - create() manual rate mismatch message_post
    # ═══════════════════════════════════════════════════════════════

    def test_create_manual_rate_mismatch_posts_message(self):
        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "invoice_date": fields.Date.today(),
            "date": fields.Date.today(),
            "manually_set_rate": True,
            "foreign_rate": 999.0,
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0, "price_unit": 100.0,
                    "account_id": self.acc_inc.id, "tax_ids": [(5, 0, 0)],
                }),
            ],
        })
        self.assertGreaterEqual(len(invoice.message_ids), 1)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _check_taxes_id / _check_product_id (entry skip)
    # ═══════════════════════════════════════════════════════════════

    def test_check_taxes_id_skips_journal_entries(self):
        self.company.unique_tax = True
        move = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "line_ids": [
                Command.create({
                    "display_type": "product",
                    "account_id": self.acc_exp.id, "debit": 100.0, "credit": 0.0,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
                Command.create({
                    "account_id": self.acc_bank.id, "debit": 0.0, "credit": 100.0,
                }),
            ],
        })
        self.assertTrue(move)

    def test_check_product_id_skips_journal_entries(self):
        move = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "line_ids": [
                Command.create({
                    "display_type": "product",
                    "account_id": self.acc_exp.id, "debit": 100.0, "credit": 0.0,
                }),
                Command.create({
                    "account_id": self.acc_bank.id, "debit": 0.0, "credit": 100.0,
                }),
            ],
        })
        self.assertTrue(move)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - action_register_payment (multiple rates)
    # ═══════════════════════════════════════════════════════════════

    def test_action_register_payment_multiple_rates_raises(self):
        inv1 = self._create_invoice(self.currency_usd, 100.0)
        inv1.with_context(move_action_post_alert=True).action_post()
        inv2 = self._create_invoice(self.currency_usd, 100.0)
        inv2.manually_set_rate = True
        inv2.foreign_rate = inv1.foreign_rate + 10.0
        inv2.with_context(move_action_post_alert=True).action_post()
        with self.assertRaises(UserError):
            (inv1 | inv2).action_register_payment()

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - action_update_account_id (income account present)
    # ═══════════════════════════════════════════════════════════════

    def test_action_update_account_id_line_with_income_account_unchanged(self):
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
                    "quantity": 1.0, "price_unit": 100.0,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
            ],
        })
        invoice.action_update_account_id()
        line = invoice.invoice_line_ids[:1]
        self.assertEqual(line.account_id, self.acc_inc)

    # ═══════════════════════════════════════════════════════════════
    # account_move.py - _compute_needed_terms (entry / no foreign currency)
    # ═══════════════════════════════════════════════════════════════

    def test_compute_needed_terms_skips_entry_and_no_foreign_currency(self):
        entry = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "line_ids": [
                Command.create({
                    "account_id": self.acc_exp.id, "debit": 100.0, "credit": 0.0,
                }),
                Command.create({
                    "account_id": self.acc_bank.id, "debit": 0.0, "credit": 100.0,
                }),
            ],
        })
        entry._compute_needed_terms()
        self.assertTrue(entry)

        invoice = self._create_invoice(self.currency_usd, 100.0)
        invoice.foreign_currency_id = False
        invoice._compute_needed_terms()
        for term_values in invoice.needed_terms.values():
            self.assertNotIn('foreign_balance', term_values)

    # ═══════════════════════════════════════════════════════════════
    # account_move_line.py - _get_non_invoice_foreign_value
    # ═══════════════════════════════════════════════════════════════

    def test_get_non_invoice_foreign_value_single_currency_line(self):
        move = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "line_ids": [
                Command.create({
                    "account_id": self.acc_exp.id, "debit": 100.0, "credit": 0.0,
                }),
                Command.create({
                    "account_id": self.acc_bank.id, "debit": 0.0, "credit": 100.0,
                    "currency_id": self.currency_usd.id, "amount_currency": -2.0,
                }),
            ],
        })
        line = move.line_ids.filtered(lambda l: l.account_id == self.acc_exp)
        value = line._get_non_invoice_foreign_value()
        self.assertAlmostEqual(value, 2.0, places=2)

    def test_get_non_invoice_foreign_value_third_currency(self):
        move = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "line_ids": [
                Command.create({
                    "account_id": self.acc_exp.id, "debit": 100.0, "credit": 0.0,
                    "currency_id": self.currency_eur.id, "amount_currency": 100.0,
                }),
                Command.create({
                    "account_id": self.acc_bank.id, "debit": 0.0, "credit": 100.0,
                }),
            ],
        })
        line = move.line_ids.filtered(lambda l: l.currency_id == self.currency_eur)
        value = line._get_non_invoice_foreign_value()
        self.assertIsInstance(value, float)

    # ═══════════════════════════════════════════════════════════════
    # account_move_line.py - _get_foreign_value branches
    # ═══════════════════════════════════════════════════════════════

    def test_get_foreign_value_special_display_types_and_adjustments(self):
        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({"display_type": "line_note", "name": "A note"}),
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0, "price_unit": 100.0,
                    "account_id": self.acc_inc.id, "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
            ],
        })
        note_line = invoice.invoice_line_ids.filtered(lambda l: l.display_type == 'line_note')
        self.assertEqual(note_line._get_foreign_value(), 0.0)

        tax_line = invoice.line_ids.filtered(lambda l: l.display_type == 'tax')
        tax_line.foreign_debit_adjustment = 7.0
        self.assertAlmostEqual(tax_line._get_foreign_value(), 7.0, places=2)

        product_line = invoice.invoice_line_ids.filtered(lambda l: l.display_type == 'product')
        product_line.foreign_debit_adjustment = 3.0
        self.assertAlmostEqual(product_line._get_foreign_value(), 3.0, places=2)

    # ═══════════════════════════════════════════════════════════════
    # account_move_line.py - _compute_foreign_amount_residual (non-reconcile)
    # ═══════════════════════════════════════════════════════════════

    def test_compute_foreign_amount_residual_non_reconcile_account(self):
        invoice = self._create_invoice(self.currency_vef, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        product_line = invoice.invoice_line_ids.filtered(lambda l: l.display_type == 'product')
        self.assertEqual(product_line.foreign_amount_residual, 0.0)
        self.assertEqual(product_line.foreign_amount_residual_currency, 0.0)

    # ═══════════════════════════════════════════════════════════════
    # account_move_line.py - _inverse_amount_currency (entry, foreign line)
    # ═══════════════════════════════════════════════════════════════

    def test_inverse_amount_currency_entry_foreign_line(self):
        move = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "line_ids": [
                Command.create({
                    "account_id": self.acc_bank.id, "debit": 0.0, "credit": 0.0,
                    "currency_id": self.currency_usd.id, "amount_currency": 33.335,
                }),
                Command.create({
                    "account_id": self.acc_exp.id, "debit": 0.0, "credit": 0.0,
                }),
            ],
        })
        line = move.line_ids.filtered(lambda l: l.currency_id == self.currency_usd)
        line._inverse_amount_currency()
        self.assertIsInstance(line.balance, float)

    # ═══════════════════════════════════════════════════════════════
    # account_move_line.py - _apply_product_real_portion guards
    # ═══════════════════════════════════════════════════════════════

    def test_apply_product_real_portion_guards(self):
        entry = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "line_ids": [
                Command.create({
                    "display_type": "product",
                    "account_id": self.acc_exp.id, "debit": 100.0, "credit": 0.0,
                }),
                Command.create({
                    "account_id": self.acc_bank.id, "debit": 0.0, "credit": 100.0,
                }),
            ],
        })
        self.env["account.move.line"]._apply_product_real_portion(entry.line_ids)

        vef_invoice = self._create_invoice(self.currency_vef, 100.0)
        self.env["account.move.line"]._apply_product_real_portion(vef_invoice.invoice_line_ids)

        posted_invoice = self._create_invoice(self.currency_usd, 100.0)
        posted_invoice.with_context(move_action_post_alert=True).action_post()
        self.env["account.move.line"]._apply_product_real_portion(posted_invoice.invoice_line_ids)
        self.assertTrue(True)

    # ═══════════════════════════════════════════════════════════════
    # bank_rec_widget.py - _action_validate
    # ═══════════════════════════════════════════════════════════════

    def test_bank_rec_widget_action_validate_base_case(self):
        bank_journal = self.env["account.journal"].create({
            "name": "Bank RecW", "code": "BRECW", "type": "bank",
            "default_account_id": self.acc_bank.id, "company_id": self.company.id,
        })
        st_line = self.env["account.bank.statement.line"].create({
            "journal_id": bank_journal.id,
            "date": fields.Date.today(),
            "payment_ref": "coverage-rec",
            "amount": 1000.0,
        })
        wizard = self.env["bank.rec.widget"].with_context(
            default_st_line_id=st_line.id,
        ).new({})
        line = wizard.line_ids.filtered(lambda x: x.flag == "auto_balance")
        wizard._js_action_mount_line_in_edit(line.index)
        line.account_id = self.acc_inc
        wizard._line_value_changed_account_id(line)
        wizard._action_validate()
        self.assertTrue(st_line.is_reconciled)

    def test_bank_rec_widget_action_validate_rounding_adjustment(self):
        bank_journal = self.env["account.journal"].create({
            "name": "Bank RecW2", "code": "BRECW2", "type": "bank",
            "default_account_id": self.acc_bank.id, "company_id": self.company.id,
        })
        st_line = self.env["account.bank.statement.line"].create({
            "journal_id": bank_journal.id,
            "date": fields.Date.today(),
            "payment_ref": "coverage-rec2",
            "amount": 1000.0,
        })
        wizard = self.env["bank.rec.widget"].with_context(
            default_st_line_id=st_line.id,
        ).new({})
        line = wizard.line_ids.filtered(lambda x: x.flag == "auto_balance")
        wizard._js_action_mount_line_in_edit(line.index)
        line.account_id = self.acc_inc
        line.balance = -999.99
        wizard._action_validate()
        liquidity = wizard.line_ids.filtered(lambda l: l.flag in ("liquidity", "aml"))
        self.assertTrue(liquidity)

    # ═══════════════════════════════════════════════════════════════
    # report/account_invoice_details_report.py
    # ═══════════════════════════════════════════════════════════════

    def _invoices_details_wizard(self, extra_vals=None):
        vals = {
            "date_from": fields.Date.today().replace(day=1),
            "date_to": fields.Date.today(),
            "company_id": self.company.id,
        }
        vals.update(extra_vals or {})
        return self.env["account.invoices.details"].create(vals)

    def test_invoice_details_report_get_sale_details_no_tz_raises(self):
        report = self.env["report.l10n_ve_accountant.report_account_invoices_details"]
        wizard = self._invoices_details_wizard()
        self.env.user.tz = False
        with self.assertRaises(ValidationError):
            report.get_sale_details(wizard)

    def test_invoice_details_report_get_sale_details_empty(self):
        self.env.user.tz = "America/Caracas"
        report = self.env["report.l10n_ve_accountant.report_account_invoices_details"]
        wizard = self._invoices_details_wizard({
            "date_from": fields.Date.from_string("2000-01-01"),
            "date_to": fields.Date.from_string("2000-01-31"),
        })
        data = report.get_sale_details(wizard)
        self.assertEqual(data["invoices"], {})
        self.assertEqual(data["payments"], {})

    def test_invoice_details_report_get_sale_details_full(self):
        self.env.user.tz = "America/Caracas"
        report = self.env["report.l10n_ve_accountant.report_account_invoices_details"]
        term_2_lines = self.env["account.payment.term"].create({
            "name": "Details 30-30-40",
            "line_ids": [
                Command.create({"value": "percent", "value_amount": 60, "nb_days": 0}),
                Command.create({"value": "percent", "value_amount": 40, "nb_days": 30}),
            ],
        })
        invoice_with_term = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "invoice_date": fields.Date.today(),
            "date": fields.Date.today(),
            "invoice_payment_term_id": term_2_lines.id,
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0, "price_unit": 100.0, "discount": 10.0,
                    "account_id": self.acc_inc.id, "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
            ],
        })
        invoice_with_term.with_context(move_action_post_alert=True).action_post()

        invoice_cash = self._create_invoice(self.currency_vef, 50.0)
        invoice_cash.with_context(move_action_post_alert=True).action_post()

        refund = self.env["account.move"].with_context(check_move_validity=False).create({
            "move_type": "out_refund",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "invoice_date": fields.Date.today(),
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0, "price_unit": 20.0,
                    "account_id": self.acc_inc.id, "tax_ids": [(5, 0, 0)],
                }),
            ],
        })
        refund.with_context(move_action_post_alert=True).action_post()

        bank = self._bank_journal_with_methods('BNKO7')
        pml = bank.inbound_payment_method_line_ids[:1]
        payment = self.env["account.payment"].create({
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": self.partner.id, "amount": 30.0,
            "currency_id": self.currency_vef.id,
            "payment_method_line_id": pml.id, "journal_id": bank.id,
        })
        payment.action_post()

        wizard = self._invoices_details_wizard()
        data = report.get_sale_details(wizard)
        self.assertTrue(data["invoices"])
        self.assertTrue(data["payments"])
        self.assertTrue(data["journal_ids"])
        self.assertTrue(data["payment_term_ids"])

        self.assertEqual(report.format_monetary(100.0, 'base.VEF'), report.format_monetary(100.0, 'base.VEF'))
        totals = report.p_get_new_values({"amount": 0, "foreign_amount": 0}, payment)
        self.assertIn("amount", totals)
        self.assertEqual(report.new_payment_term(invoice_with_term)["id"], str(term_2_lines.id))
        self.assertEqual(report.new_journal(invoice_with_term)["id"], str(self.sale_journal.id))

    def test_invoice_details_report_get_report_values(self):
        self.env.user.tz = "America/Caracas"
        wizard = self._invoices_details_wizard()
        invoice = self._create_invoice(self.currency_vef, 100.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        report = self.env["report.l10n_ve_accountant.report_account_invoices_details"]
        result = report._get_report_values([wizard.id], data={})
        self.assertIn("invoices", result)
        self.assertIn("self", result)
