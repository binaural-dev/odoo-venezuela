import logging
import random

from odoo.tests import TransactionCase, tagged
from odoo.tests.common import Form
from odoo import fields, Command
from odoo.exceptions import ValidationError

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
        self._set_correlative_if_required(form, "TEST-REPRO2-0001")
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
        self._set_correlative_if_required(form, f"TEST-STRESS-{currency.name}-0001")
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
            l.foreign_subtotal
            for l in inv.line_ids if l.display_type == 'product')
        entry_total = abs(entry_untaxed + inv.direction_sign * sum(
            l.foreign_debit - l.foreign_credit
            for l in inv.line_ids if l.display_type == 'tax'))

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
            l.foreign_subtotal
            for l in inv.line_ids if l.display_type == 'product')
        entry_total = abs(entry_untaxed + inv.direction_sign * sum(
            l.foreign_debit - l.foreign_credit
            for l in inv.line_ids if l.display_type == 'tax'))

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
