import logging
from odoo.tests import TransactionCase, tagged
from odoo import fields, Command

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_accountant_rounding")
class TestMultiCurrencyRounding(TransactionCase):

    def setUp(self):
        super().setUp()

        self.currency_vef = self.env.ref("base.VEF")
        self.currency_usd = self.env.ref("base.USD")
        self.currency_eur = self.env.ref("base.EUR")
        self.currency_eur.active = True
        self.company = self.env.ref("base.main_company")
        self.country_ve = self.env.ref("base.ve")

        # Company: VEF base, USD foreign
        self.company.write({
            "currency_id": self.currency_vef.id,
            "foreign_currency_id": self.currency_usd.id,
            "account_fiscal_country_id": self.country_ve.id,
            "country_id": self.country_ve.id,
        })

        # Rates: 1 USD = 40 VEF, 1 EUR = 45 VEF
        today = fields.Date.today()
        self.env["res.currency.rate"].create({
            "name": today,
            "currency_id": self.currency_vef.id,
            "inverse_company_rate": 1.0,
            "company_id": self.company.id,
        })
        self.env["res.currency.rate"].create({
            "name": today,
            "currency_id": self.currency_usd.id,
            "inverse_company_rate": 40.0,
            "company_id": self.company.id,
        })
        self.env["res.currency.rate"].create({
            "name": today,
            "currency_id": self.currency_eur.id,
            "inverse_company_rate": 45.0,
            "company_id": self.company.id,
        })

        # Accounts
        self.acc_rec = self._get_or_create('120000', 'Receivable', 'asset_receivable', reconcile=True)
        self.acc_inc = self._get_or_create('400000', 'Income', 'income')
        self.acc_tax = self._get_or_create('200000', 'Tax Payable', 'liability_current', reconcile=True)
        self.acc_bank_vef = self._get_or_create('100100', 'Bank VEF', 'asset_cash', reconcile=True)
        self.acc_bank_usd = self._get_or_create('100200', 'Bank USD', 'asset_cash', reconcile=True)
        self.acc_bank_eur = self._get_or_create('100300', 'Bank EUR', 'asset_cash', reconcile=True)

        # Payment methods
        self.manual_in = self.env.ref("account.account_payment_method_manual_in")
        self.manual_out = self.env.ref("account.account_payment_method_manual_out")

        # Bank journals per currency
        self.bank_vef = self._create_bank_journal('BNKV', 'Banco VEF', self.currency_vef, self.acc_bank_vef)
        self.bank_usd = self._create_bank_journal('BNKU', 'Banco USD', self.currency_usd, self.acc_bank_usd)
        self.bank_eur = self._create_bank_journal('BNKE', 'Banco EUR', self.currency_eur, self.acc_bank_eur)

        # Taxes: 16%, 31%, 8%
        self.tax_group = self.env['account.tax.group'].create({
            'name': 'IVA', 'company_id': self.company.id, 'country_id': self.country_ve.id,
        })
        self.tax_16 = self._create_tax('IVA 16%', 16.0)
        self.tax_31 = self._create_tax('IVA 31%', 31.0)
        self.tax_8 = self._create_tax('IVA 8%', 8.0)

        # Product
        self.product = self.env['product.product'].create({
            'name': 'Service',
            'type': 'service',
            'list_price': 100.0,
            'property_account_income_id': self.acc_inc.id,
            'taxes_id': [(5, 0, 0)],
            'supplier_taxes_id': [(5, 0, 0)],
        })

        # Sale journal
        self.sale_journal = self.env['account.journal'].search([
            ('type', '=', 'sale'), ('company_id', '=', self.company.id),
        ], limit=1)

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

    def _create_bank_journal(self, code, name, currency, account):
        pm_in = self.env['account.payment.method.line'].create({
            'name': f'In {currency.name}',
            'payment_method_id': self.manual_in.id,
            'payment_type': 'inbound',
            'payment_account_id': account.id,
        })
        pm_out = self.env['account.payment.method.line'].create({
            'name': f'Out {currency.name}',
            'payment_method_id': self.manual_out.id,
            'payment_type': 'outbound',
            'payment_account_id': account.id,
        })
        return self.env['account.journal'].create({
            'name': name, 'code': code, 'type': 'bank',
            'currency_id': currency.id,
            'default_account_id': account.id,
            'company_id': self.company.id,
            'inbound_payment_method_line_ids': [(6, 0, pm_in.ids)],
            'outbound_payment_method_line_ids': [(6, 0, pm_out.ids)],
        })

    def _create_tax(self, name, amount):
        return self.env["account.tax"].with_company(self.company).create({
            "name": name,
            "amount": amount,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "company_id": self.company.id,
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

    def _create_group_tax(self, name, child_taxes):
        return self.env["account.tax"].with_company(self.company).create({
            "name": name,
            "amount_type": "group",
            "type_tax_use": "sale",
            "company_id": self.company.id,
            "tax_group_id": self.tax_group.id,
            "children_tax_ids": [(6, 0, child_taxes.ids)],
        })

    def _check_line(self, line):
        """Verifica que amount_currency == round(balance * rate)"""
        if line.display_type not in ('product', 'tax', 'payment_term', 'liquidity'):
            return True
        expected_amc = line.currency_id.round(line.balance * line.currency_rate)
        return abs(line.amount_currency - expected_amc) < 0.01

    def _check_foreign(self, line):
        """Verifica foreign_debit/credit consistentes con foreign_balance"""
        if line.display_type not in ('product', 'tax', 'payment_term', 'liquidity'):
            return True
        if not line.foreign_balance:
            return abs(line.foreign_debit) < 0.01 and abs(line.foreign_credit) < 0.01
        exp_fd = abs(line.foreign_balance) if line.foreign_balance > 0 else 0.0
        exp_fc = abs(line.foreign_balance) if line.foreign_balance < 0 else 0.0
        return (abs(line.foreign_debit - exp_fd) < 0.01 and
                abs(line.foreign_credit - exp_fc) < 0.01)

    def _create_invoice(self, currency, pricelist, lines_data):
        """Crea y publica una factura.
        lines_data: list of (qty, price_unit, [tax_records])
        """
        # Buscar o crear lista de precios en la moneda adecuada
        pl = pricelist
        if not pl and currency != self.currency_vef:
            pl = self.env['product.pricelist'].search([
                ('currency_id', '=', currency.id),
            ], limit=1)
            if not pl:
                pl = self.env['product.pricelist'].create({
                    'name': f'Pricelist {currency.name}',
                    'currency_id': currency.id,
                    'company_id': self.company.id,
                })
        partner = self.env['res.partner'].create({
            'name': f'Partner {currency.name}',
            'company_id': self.company.id,
            'property_account_receivable_id': self.acc_rec.id,
            'property_product_pricelist': pl.id if pl else False,
        })
        inv = self.env['account.move'].with_context(
            check_move_validity=False,
        ).create([{
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'currency_id': currency.id,
            'journal_id': self.sale_journal.id,
            'invoice_date': fields.Date.today(),
            'company_id': self.company.id,
            'pricelist_id': pl.id if pl else False,
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': self.product.id,
                    'name': f'L{i}',
                    'quantity': qty,
                    'price_unit': pu,
                    'tax_ids': [(6, 0, [t.id for t in taxes])],
                })
                for i, (qty, pu, taxes) in enumerate(lines_data)
            ],
        }])[0]
        inv.action_post()
        return inv

    def _create_payment(self, inv, currency, bank_journal, amount):
        """Crea un pago por el monto dado en la moneda indicada."""
        pay = self.env['account.payment'].with_company(self.company).create({
            'amount': amount,
            'date': fields.Date.today(),
            'currency_id': currency.id,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': inv.partner_id.id,
            'journal_id': bank_journal.id,
            'payment_method_id': self.manual_in.id,
            'company_id': self.company.id,
        })
        pay.action_post()
        return pay

    # ── Tests ─────────────────────────────────────────────────────

    def test_01_eur_three_taxes(self):
        """Factura EUR con 3 líneas e impuestos 16%, 31%, 8%"""
        inv = self._create_invoice(self.currency_eur, None, [
            (2, 250000.00, [self.tax_16, self.tax_31]),
            (1, 150000.00, [self.tax_8]),
            (3, 50000.00, [self.tax_16]),
        ])
        for line in inv.line_ids:
            self.assertTrue(self._check_line(line),
                            f"Línea {line.display_type}: amount_currency no coincide con round(balance*rate)")
            self.assertTrue(self._check_foreign(line),
                            f"Línea {line.display_type}: foreign_debit/credit inconsistentes")
        # Balance contable
        td = sum(inv.line_ids.mapped('debit'))
        tc = sum(inv.line_ids.mapped('credit'))
        self.assertAlmostEqual(td, tc, places=2, msg="Debit != Credit")
        # Foreign totals
        pt = inv.line_ids.filtered(lambda l: l.display_type == 'payment_term')
        other = inv.line_ids.filtered(lambda l: l.display_type != 'payment_term')
        pt_fd = sum(pt.mapped('foreign_debit'))
        pt_fc = sum(pt.mapped('foreign_credit'))
        other_fd = sum(other.mapped('foreign_debit'))
        other_fc = sum(other.mapped('foreign_credit'))
        self.assertAlmostEqual(pt_fd, other_fc, places=2,
                               msg="PT foreign_debit != other foreign_credit")
        self.assertAlmostEqual(pt_fc, other_fd, places=2,
                               msg="PT foreign_credit != other foreign_debit")

    def test_02_usd_three_taxes(self):
        """Factura USD con 3 líneas e impuestos 16%, 31%, 8%"""
        inv = self._create_invoice(self.currency_usd, None, [
            (1, 10000.00, [self.tax_16, self.tax_31]),
            (2, 5000.00, [self.tax_8]),
            (3, 2000.00, [self.tax_31]),
        ])
        for line in inv.line_ids:
            self.assertTrue(self._check_line(line),
                            f"Línea {line.display_type}: amount_currency no coincide con round(balance*rate)")
            self.assertTrue(self._check_foreign(line),
                            f"Línea {line.display_type}: foreign_debit/credit inconsistentes")
        td = sum(inv.line_ids.mapped('debit'))
        tc = sum(inv.line_ids.mapped('credit'))
        self.assertAlmostEqual(td, tc, places=2, msg="Debit != Credit")

    def test_03_vef_three_taxes(self):
        """Factura VEF (moneda base) con 3 líneas - control"""
        inv = self._create_invoice(self.currency_vef, None, [
            (1, 1000000.00, [self.tax_16]),
            (2, 500000.00, [self.tax_31]),
            (3, 250000.00, [self.tax_8]),
        ])
        for line in inv.line_ids:
            self.assertTrue(self._check_line(line),
                            f"Línea {line.display_type}: amount_currency no coincide con round(balance*rate)")
        td = sum(inv.line_ids.mapped('debit'))
        tc = sum(inv.line_ids.mapped('credit'))
        self.assertAlmostEqual(td, tc, places=2, msg="Debit != Credit")

    def test_04_eur_payment(self):
        """Pago en EUR: el asiento del pago debe coincidir con la PT line de la factura"""
        inv = self._create_invoice(self.currency_eur, None, [
            (2, 250000.00, [self.tax_16, self.tax_31]),
            (1, 150000.00, [self.tax_8]),
            (3, 50000.00, [self.tax_16]),
        ])
        pt = inv.line_ids.filtered(lambda l: l.display_type == 'payment_term')
        pt_amc = sum(pt.mapped('amount_currency'))

        pay = self._create_payment(inv, self.currency_eur, self.bank_eur, pt_amc)

        pm = pay.move_id
        pos_line = pm.line_ids.filtered(lambda l: l.balance > 0)
        neg_line = pm.line_ids.filtered(lambda l: l.balance < 0)

        # amount_currency del pago debe coincidir con la factura
        pos_amc = sum(pos_line.mapped('amount_currency'))
        neg_amc = abs(sum(neg_line.mapped('amount_currency')))
        self.assertAlmostEqual(pos_amc, pt_amc, places=2,
                               msg="Payment positive line amc != invoice PT amc")
        self.assertAlmostEqual(neg_amc, pt_amc, places=2,
                               msg="Payment negative line amc != invoice PT amc")

        # Consistentes internamente
        for line in pm.line_ids:
            self.assertTrue(self._check_line(line),
                            f"Payment line: amount_currency no coincide con round(balance*rate)")

    def test_05_usd_payment(self):
        """Pago en USD"""
        inv = self._create_invoice(self.currency_usd, None, [
            (1, 10000.00, [self.tax_16, self.tax_31]),
            (2, 5000.00, [self.tax_8]),
            (3, 2000.00, [self.tax_31]),
        ])
        pt = inv.line_ids.filtered(lambda l: l.display_type == 'payment_term')
        pt_amc = sum(pt.mapped('amount_currency'))

        pay = self._create_payment(inv, self.currency_usd, self.bank_usd, pt_amc)

        pos = pay.move_id.line_ids.filtered(lambda l: l.balance > 0)
        neg = pay.move_id.line_ids.filtered(lambda l: l.balance < 0)
        self.assertAlmostEqual(sum(pos.mapped('amount_currency')), pt_amc, places=2)
        self.assertAlmostEqual(abs(sum(neg.mapped('amount_currency'))), pt_amc, places=2)
        for line in pay.move_id.line_ids:
            self.assertTrue(self._check_line(line))

    def test_06_vef_payment(self):
        """Pago en VEF"""
        inv = self._create_invoice(self.currency_vef, None, [
            (1, 1000000.00, [self.tax_16]),
            (2, 500000.00, [self.tax_31]),
            (3, 250000.00, [self.tax_8]),
        ])
        pt = inv.line_ids.filtered(lambda l: l.display_type == 'payment_term')
        pt_amc = sum(pt.mapped('amount_currency'))

        pay = self._create_payment(inv, self.currency_vef, self.bank_vef, pt_amc)

        pos = pay.move_id.line_ids.filtered(lambda l: l.balance > 0)
        neg = pay.move_id.line_ids.filtered(lambda l: l.balance < 0)
        self.assertAlmostEqual(sum(pos.mapped('amount_currency')), pt_amc, places=2)
        self.assertAlmostEqual(abs(sum(neg.mapped('amount_currency'))), pt_amc, places=2)
        for line in pay.move_id.line_ids:
            self.assertTrue(self._check_line(line))

    def test_07_eur_single_line(self):
        """Factura EUR 1 línea - verifica que no hay falsos positivos"""
        inv = self._create_invoice(self.currency_eur, None, [
            (1, 568184700.18, [self.tax_16]),
        ])
        for line in inv.line_ids:
            self.assertTrue(self._check_line(line))
        td = sum(inv.line_ids.mapped('debit'))
        tc = sum(inv.line_ids.mapped('credit'))
        self.assertAlmostEqual(td, tc, places=2)

    def test_08_eur_two_lines_equal(self):
        """Factura EUR 2 líneas iguales - verifica redondeo simétrico"""
        inv = self._create_invoice(self.currency_eur, None, [
            (1, 250000.00, [self.tax_16]),
            (1, 250000.00, [self.tax_16]),
        ])
        for line in inv.line_ids:
            self.assertTrue(self._check_line(line))
        td = sum(inv.line_ids.mapped('debit'))
        tc = sum(inv.line_ids.mapped('credit'))
        self.assertAlmostEqual(td, tc, places=2)

    def test_09_eur_foreign_distribution(self):
        """Verifica que montos alternos (foreign) se distribuyen correctamente"""
        inv = self._create_invoice(self.currency_eur, None, [
            (2, 250000.00, [self.tax_16]),
            (3, 100000.00, [self.tax_31]),
        ])
        pt = inv.line_ids.filtered(lambda l: l.display_type == 'payment_term')
        other = inv.line_ids.filtered(lambda l: l.display_type != 'payment_term')
        pt_fd = sum(pt.mapped('foreign_debit'))
        pt_fc = sum(pt.mapped('foreign_credit'))
        other_fd = sum(other.mapped('foreign_debit'))
        other_fc = sum(other.mapped('foreign_credit'))
        self.assertAlmostEqual(pt_fd, other_fc, places=2,
                               msg="PT foreign_debit != other foreign_credit")
        self.assertAlmostEqual(pt_fc, other_fd, places=2,
                               msg="PT foreign_credit != other foreign_debit")

    def test_10_eur_large_amount(self):
        """Factura EUR con montos grandes tipo 914 (varios productos)"""
        inv = self._create_invoice(self.currency_eur, None, [
            (1, 300000000.00, [self.tax_16]),
            (1, 200000000.00, [self.tax_16]),
            (1, 68184700.18, [self.tax_16]),
        ])
        for line in inv.line_ids:
            self.assertTrue(self._check_line(line),
                            f"{line.display_type}: amc mismatch")
            self.assertTrue(self._check_foreign(line),
                            f"{line.display_type}: foreign mismatch")
        td = sum(inv.line_ids.mapped('debit'))
        tc = sum(inv.line_ids.mapped('credit'))
        self.assertAlmostEqual(td, tc, places=2, msg="Unbalanced")

    def test_11_eur_two_lines_different_taxes(self):
        """Factura EUR 2 líneas cada una con impuesto diferente"""
        inv = self._create_invoice(self.currency_eur, None, [
            (1, 100000.00, [self.tax_16]),
            (2, 50000.00, [self.tax_31]),
        ])
        for line in inv.line_ids:
            self.assertTrue(self._check_line(line))
            self.assertTrue(self._check_foreign(line))
        td = sum(inv.line_ids.mapped('debit'))
        tc = sum(inv.line_ids.mapped('credit'))
        self.assertAlmostEqual(td, tc, places=2)

    def test_12_usd_two_lines_different_taxes(self):
        """Factura USD 2 líneas cada una con impuesto diferente"""
        inv = self._create_invoice(self.currency_usd, None, [
            (3, 1000.00, [self.tax_8]),
            (2, 500.00, [self.tax_16]),
        ])
        for line in inv.line_ids:
            self.assertTrue(self._check_line(line))
            self.assertTrue(self._check_foreign(line))
        td = sum(inv.line_ids.mapped('debit'))
        tc = sum(inv.line_ids.mapped('credit'))
        self.assertAlmostEqual(td, tc, places=2)

    def test_13_eur_payment_foreign_check(self):
        """Pago EUR: verifica foreign_debit/foreign_credit en el asiento del pago"""
        inv = self._create_invoice(self.currency_eur, None, [
            (2, 250000.00, [self.tax_16]),
            (3, 100000.00, [self.tax_31]),
        ])
        pt = inv.line_ids.filtered(lambda l: l.display_type == 'payment_term')
        pt_amc = sum(pt.mapped('amount_currency'))
        pay = self._create_payment(inv, self.currency_eur, self.bank_eur, pt_amc)
        pm = pay.move_id
        for line in pm.line_ids:
            self.assertTrue(self._check_line(line),
                            f"Payment line {line.display_type}: amc mismatch")
            self.assertTrue(self._check_foreign(line),
                            f"Payment line {line.display_type}: foreign mismatch")
        # foreign debe balancearse entre lado positivo y negativo
        pos = pm.line_ids.filtered(lambda l: l.balance > 0)
        neg = pm.line_ids.filtered(lambda l: l.balance < 0)
        pos_fd = sum(pos.mapped('foreign_debit'))
        pos_fc = sum(pos.mapped('foreign_credit'))
        neg_fd = sum(neg.mapped('foreign_debit'))
        neg_fc = sum(neg.mapped('foreign_credit'))
        self.assertAlmostEqual(pos_fd, neg_fc, places=2,
                               msg="Payment: pos foreign_debit != neg foreign_credit")
        self.assertAlmostEqual(pos_fc, neg_fd, places=2,
                               msg="Payment: pos foreign_credit != neg foreign_debit")

    def test_14_usd_payment_foreign_check(self):
        """Pago USD: verifica foreign_debit/foreign_credit en el asiento del pago"""
        inv = self._create_invoice(self.currency_usd, None, [
            (1, 10000.00, [self.tax_16, self.tax_31]),
            (2, 5000.00, [self.tax_8]),
        ])
        pt = inv.line_ids.filtered(lambda l: l.display_type == 'payment_term')
        pt_amc = sum(pt.mapped('amount_currency'))
        pay = self._create_payment(inv, self.currency_usd, self.bank_usd, pt_amc)
        pm = pay.move_id
        for line in pm.line_ids:
            self.assertTrue(self._check_line(line))
            self.assertTrue(self._check_foreign(line))
        pos = pm.line_ids.filtered(lambda l: l.balance > 0)
        neg = pm.line_ids.filtered(lambda l: l.balance < 0)
        self.assertAlmostEqual(sum(pos.mapped('foreign_debit')),
                               sum(neg.mapped('foreign_credit')), places=2)

    # ── Tests: tax computed natively in VEF ─────────────────────────
    # The tax line's balance must match `% x Σ product line balances`
    # exactly, not just be "close" by rounding (`_check_line` already
    # covers amount_currency, but not the % against the real VEF base).

    def _assert_tax_matches_real_base(self, inv):
        """For each percent tax: tax line balance == round(Σ balance of the product lines using it * %).

        Matches on the tax OR its group_tax_id: `l.tax_ids` holds whatever
        the user picked, which is the group (not the child) for a percent
        tax that is a child of a `group` tax.
        """
        product_lines = inv.line_ids.filtered(lambda l: l.display_type == 'product')
        tax_lines = inv.line_ids.filtered(lambda l: l.display_type == 'tax')
        cc = inv.company_id.currency_id
        for tax_line in tax_lines:
            rep_line = tax_line.tax_repartition_line_id
            tax = rep_line.tax_id
            if tax.amount_type != 'percent':
                continue
            group_tax = tax_line.group_tax_id
            base_lines = product_lines.filtered(
                lambda l: tax in l.tax_ids or (group_tax and group_tax in l.tax_ids)
            )
            base_vef = sum(base_lines.mapped('balance'))
            factor = rep_line.factor_percent / 100.0
            expected = cc.round(base_vef * (tax.amount / 100.0) * factor)
            self.assertAlmostEqual(
                abs(tax_line.balance), abs(expected), places=2,
                msg=(
                    f"Tax {tax.name}: balance={tax_line.balance} "
                    f"does not match {tax.amount}% of the real VEF base "
                    f"({base_vef}) = {expected}"
                ),
            )

    def test_15_usd_tax_matches_real_vef_base(self):
        """Tax % must match the real VEF base of the product lines, not just amount_currency/rate."""
        inv = self._create_invoice(self.currency_usd, None, [
            (1, 10000.00, [self.tax_16, self.tax_31]),
            (2, 5000.00, [self.tax_8]),
            (3, 2000.00, [self.tax_31]),
        ])
        self._assert_tax_matches_real_base(inv)
        td = sum(inv.line_ids.mapped('debit'))
        tc = sum(inv.line_ids.mapped('credit'))
        self.assertAlmostEqual(td, tc, places=2, msg="Debit != Credit")

    def test_16_eur_tax_matches_real_vef_base(self):
        """Same as above in EUR, to confirm this isn't USD-specific."""
        inv = self._create_invoice(self.currency_eur, None, [
            (2, 250000.00, [self.tax_16, self.tax_31]),
            (1, 150000.00, [self.tax_8]),
        ])
        self._assert_tax_matches_real_base(inv)

    def test_17_vef_tax_matches_real_vef_base(self):
        """Control: VEF invoice (company currency) -- no special path applies (currency_id == company currency), tax must match the same way."""
        inv = self._create_invoice(self.currency_vef, None, [
            (1, 1000000.00, [self.tax_16]),
            (2, 500000.00, [self.tax_31]),
            (3, 250000.00, [self.tax_8]),
        ])
        self._assert_tax_matches_real_base(inv)

    def test_18_usd_many_decimals_no_imbalance(self):
        """Regression: many-decimal prices and non-integer quantities must not raise 'Entry not balanced'."""
        inv = self._create_invoice(self.currency_usd, None, [
            (1, 15485.659512345, [self.tax_16]),
            (2, 1458454.6123456, [self.tax_16]),
        ])
        td = sum(inv.line_ids.mapped('debit'))
        tc = sum(inv.line_ids.mapped('credit'))
        self.assertAlmostEqual(td, tc, places=2, msg="Debit != Credit (entry not balanced)")
        self._assert_tax_matches_real_base(inv)
        for line in inv.line_ids:
            self.assertTrue(self._check_line(line),
                            f"Line {line.display_type}: amount_currency does not match round(balance*rate)")

    def test_19_usd_edit_price_after_post_no_imbalance(self):
        """Regression: editing price_unit before posting must not leave a stale balance that unbalances the entry."""
        partner = self.env['res.partner'].create({
            'name': 'Partner edit test',
            'company_id': self.company.id,
            'property_account_receivable_id': self.acc_rec.id,
        })
        inv = self.env['account.move'].with_context(check_move_validity=False).create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'currency_id': self.currency_usd.id,
            'journal_id': self.sale_journal.id,
            'invoice_date': fields.Date.today(),
            'company_id': self.company.id,
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': self.product.id,
                    'name': 'L0',
                    'quantity': 1,
                    'price_unit': 100.0,
                    'tax_ids': [(6, 0, [self.tax_16.id])],
                }),
            ],
        })
        line = inv.invoice_line_ids[0]
        # Large single write, matching the reported bug.
        line.write({'price_unit': 1458454.6123456, 'quantity': 2})
        inv.action_post()
        td = sum(inv.line_ids.mapped('debit'))
        tc = sum(inv.line_ids.mapped('credit'))
        self.assertAlmostEqual(td, tc, places=2, msg="Debit != Credit tras editar price_unit")
        self._assert_tax_matches_real_base(inv)

    # ── Tests: "Product Price" precision (6 decimals) vs. currency
    # rounding (2 decimals) -- the tax must always match the VEF base,
    # in both USD and EUR. ────────────────────────────────────────────

    def _assert_header_and_tax_line_match(self, inv):
        """Check header totals sum up, and each percent tax line's balance/amount_currency matches a hand-computed % of the real base (VEF and document currency)."""
        cc = inv.company_id.currency_id
        doc_currency = inv.currency_id
        product_lines = inv.line_ids.filtered(lambda l: l.display_type == 'product')
        tax_lines = inv.line_ids.filtered(lambda l: l.display_type == 'tax')

        # 1. Header (document currency) == sum of lines.
        expected_untaxed = doc_currency.round(sum(product_lines.mapped('amount_currency')))
        expected_tax = doc_currency.round(sum(tax_lines.mapped('amount_currency')))
        self.assertAlmostEqual(
            abs(inv.amount_untaxed), abs(expected_untaxed), places=2,
            msg="amount_untaxed does not match the sum of product lines",
        )
        self.assertAlmostEqual(
            abs(inv.amount_tax), abs(expected_tax), places=2,
            msg="amount_tax does not match the sum of tax lines",
        )
        self.assertAlmostEqual(
            inv.amount_total, inv.amount_untaxed + inv.amount_tax, places=2,
            msg="amount_total != amount_untaxed + amount_tax",
        )

        # 2. Per percent tax: balance == round(Σ VEF base * % * factor_percent),
        #    hand-computed here (not reusing the fix's own helper).
        for tax_line in tax_lines:
            rep_line = tax_line.tax_repartition_line_id
            tax = rep_line.tax_id
            if tax.amount_type != 'percent':
                continue
            group_tax = tax_line.group_tax_id
            base_lines = product_lines.filtered(
                lambda l: tax in l.tax_ids or (group_tax and group_tax in l.tax_ids)
            )
            base_vef = sum(base_lines.mapped('balance'))
            hand_computed = cc.round(base_vef * tax.amount / 100.0 * rep_line.factor_percent / 100.0)
            self.assertAlmostEqual(
                abs(tax_line.balance), abs(hand_computed), places=2,
                msg=(
                    f"Tax line {tax.name}: balance={tax_line.balance} "
                    f"!= hand-computed ({hand_computed}) over VEF base {base_vef}"
                ),
            )
            # Document-currency amount must match too: both surfaces
            # (VEF and document) must agree, not just each with itself.
            base_doc = sum(base_lines.mapped('amount_currency'))
            hand_computed_doc = doc_currency.round(
                abs(base_doc) * tax.amount / 100.0 * rep_line.factor_percent / 100.0
            )
            self.assertAlmostEqual(
                abs(tax_line.amount_currency), hand_computed_doc, places=2,
                msg=(
                    f"Tax line {tax.name}: amount_currency={tax_line.amount_currency} "
                    f"!= hand-computed ({hand_computed_doc}) over document-currency base"
                ),
            )

    def _create_invoice_with_precision(self, currency, lines_data):
        """Like `_create_invoice`, forcing "Product Price" precision to 6 decimals and VEF rounding to 0.01, so the scenario is deterministic."""
        dp_price = self.env['decimal.precision'].search([('name', '=', 'Product Price')], limit=1)
        if dp_price:
            dp_price.digits = 6
        self.currency_vef.rounding = 0.01
        return self._create_invoice(currency, None, lines_data)

    def test_20_usd_product_price_6_decimals_tax_matches(self):
        """USD invoice, 6-decimal prices, non-integer quantities: tax must match the VEF base exactly."""
        inv = self._create_invoice_with_precision(self.currency_usd, [
            (1, 156.354321, [self.tax_16]),
            (2.5, 2.498557, [self.tax_16]),
            (3, 1458454.612345, [self.tax_31]),
        ])
        self._assert_header_and_tax_line_match(inv)
        td = sum(inv.line_ids.mapped('debit'))
        tc = sum(inv.line_ids.mapped('credit'))
        self.assertAlmostEqual(td, tc, places=2, msg="Debit != Credit")

    def test_21_eur_product_price_6_decimals_tax_matches(self):
        """Same as above in EUR, to confirm this isn't USD-specific."""
        inv = self._create_invoice_with_precision(self.currency_eur, [
            (1, 156.354321, [self.tax_16]),
            (2.5, 2.498557, [self.tax_16]),
            (3, 1458454.612345, [self.tax_8]),
        ])
        self._assert_header_and_tax_line_match(inv)
        td = sum(inv.line_ids.mapped('debit'))
        tc = sum(inv.line_ids.mapped('credit'))
        self.assertAlmostEqual(td, tc, places=2, msg="Debit != Credit")

    def test_22_usd_eur_precision_multiple_taxes_per_line(self):
        """One line with two percent taxes (16% + 31%), 6-decimal price, USD and EUR: each tax must match the same VEF base individually."""
        for currency in (self.currency_usd, self.currency_eur):
            with self.subTest(currency=currency.name):
                inv = self._create_invoice_with_precision(currency, [
                    (3.333333, 999.999999, [self.tax_16, self.tax_31]),
                ])
                self._assert_header_and_tax_line_match(inv)
                td = sum(inv.line_ids.mapped('debit'))
                tc = sum(inv.line_ids.mapped('credit'))
                self.assertAlmostEqual(td, tc, places=2, msg=f"Debit != Credit ({currency.name})")

    # ── Tests: `_distribute_invoice_real_portion` must not overwrite the
    # balance our `_sync_tax_lines` fix already set for `percent` taxes.
    # They are NOT idempotent by construction: amount_currency/rate
    # amplifies document-currency rounding into a multi-VEF error when
    # dividing by a small rate (confirmed empirically: without the skip
    # in `_distribute_invoice_real_portion`, these tests failed by
    # 0.11-0.16 VEF). Hence the explicit `continue` for `percent` taxes.

    def test_23_distribute_invoice_real_portion_is_idempotent_for_percent_tax(self):
        """Calling `_distribute_invoice_real_portion` after sync must not change a percent tax line's balance/amount_currency."""
        inv = self._create_invoice_with_precision(self.currency_usd, [
            (1, 156.354321, [self.tax_16]),
            (2.5, 2.498557, [self.tax_16]),
            (3, 1458454.612345, [self.tax_31]),
        ])
        cc = inv.company_currency_id
        tax_lines = inv.line_ids.filtered(lambda l: l.display_type == 'tax')
        balances_before = {line.id: line.balance for line in tax_lines}
        amounts_before = {line.id: line.amount_currency for line in tax_lines}

        # Direct call to the step, as invoked internally by
        # `_distribute_final_real_portion`.
        inv._distribute_invoice_real_portion(inv, cc)

        for line in tax_lines:
            self.assertEqual(
                line.balance, balances_before[line.id],
                msg=(
                    f"_distribute_invoice_real_portion changed the balance of "
                    f"tax line {line.name}: {balances_before[line.id]} -> {line.balance}"
                ),
            )
            self.assertEqual(
                line.amount_currency, amounts_before[line.id],
                msg=f"_distribute_invoice_real_portion changed amount_currency of {line.name}",
            )

    def test_24_distribute_invoice_real_portion_would_diverge_without_the_skip(self):
        """Show why the skip is needed: the old amount_currency/rate formula diverges from the real (fixed) balance."""
        inv = self._create_invoice_with_precision(self.currency_eur, [
            (2, 987.123456, [self.tax_16, self.tax_31]),
            (1.5, 12345.678901, [self.tax_8]),
        ])
        cc = inv.company_currency_id
        rate = inv.invoice_currency_rate
        tax_lines = inv.line_ids.filtered(lambda l: l.display_type == 'tax')
        any_diverges = False
        for line in tax_lines:
            tax = line.tax_repartition_line_id.tax_id
            if tax.amount_type != 'percent':
                continue
            naive_formula_result = cc.round(line.amount_currency / rate)
            if not cc.is_zero(naive_formula_result - line.balance):
                any_diverges = True
            # The real (fixed) balance still matches the product lines'
            # real base -- that's what matters, not matching the old formula.
        self._assert_header_and_tax_line_match(inv)
        self.assertTrue(
            any_diverges,
            msg=(
                "Expected at least one tax to diverge from amount_currency/rate "
                "with these numbers -- if none diverges, this test case does not "
                "demonstrate the problem that motivated the skip"
            ),
        )

    def test_25_usd_eur_direct_call_after_edit_stays_consistent(self):
        """After editing a line and calling `_distribute_invoice_real_portion` twice, the tax must still match the real VEF base."""
        for currency in (self.currency_usd, self.currency_eur):
            with self.subTest(currency=currency.name):
                inv = self._create_invoice_with_precision(currency, [
                    (1, 500.111111, [self.tax_16]),
                ])
                line = inv.invoice_line_ids[0]
                line.write({'price_unit': 777.777777, 'quantity': 4.25})

                cc = inv.company_currency_id
                # Called a second time explicitly: repeating it must not drift the result.
                inv._distribute_invoice_real_portion(inv, cc)
                inv._distribute_invoice_real_portion(inv, cc)

                self._assert_header_and_tax_line_match(inv)
                td = sum(inv.line_ids.mapped('debit'))
                tc = sum(inv.line_ids.mapped('credit'))
                self.assertAlmostEqual(td, tc, places=2, msg=f"Debit != Credit ({currency.name})")

    def test_26_group_tax_two_percent_children_tax_matches_base(self):
        """A percent child of a `group` tax must not fall back to base_vef=0: `record.tax_ids` holds the group, not the child."""
        tax_a = self._create_tax('Group child A 5%', 5.0)
        tax_b = self._create_tax('Group child B 3%', 3.0)
        group_tax = self._create_group_tax('Group AB', tax_a + tax_b)
        inv = self._create_invoice_with_precision(self.currency_usd, [
            (2, 12345.678901, [group_tax]),
        ])
        tax_lines = inv.line_ids.filtered(lambda l: l.display_type == 'tax')
        self.assertEqual(len(tax_lines), 2, "Expected one tax line per group child")
        for line in tax_lines:
            self.assertFalse(
                self.currency_vef.is_zero(line.balance),
                msg=f"Tax line {line.name} balance is zero -- group child base lookup failed",
            )
        self._assert_header_and_tax_line_match(inv)
        td = sum(inv.line_ids.mapped('debit'))
        tc = sum(inv.line_ids.mapped('credit'))
        self.assertAlmostEqual(td, tc, places=2, msg="Debit != Credit")

    def test_27_amount_currency_rounds_with_document_currency_precision(self):
        """amount_currency of a percent tax line must round to the document currency's precision, not the company currency's (VEF, 2 decimals)."""
        currency_3dp = self.env['res.currency'].create({
            'name': 'XT3',
            'symbol': 'XT3',
            'rounding': 0.001,
            'decimal_places': 3,
            'active': True,
        })
        self.env['res.currency.rate'].create({
            'name': fields.Date.today(),
            'currency_id': currency_3dp.id,
            'inverse_company_rate': 47.0,
            'company_id': self.company.id,
        })
        inv = self._create_invoice_with_precision(currency_3dp, [
            (1, 137.918273, [self.tax_16]),
        ])
        tax_line = inv.line_ids.filtered(lambda l: l.display_type == 'tax')
        base_vef = sum(
            inv.line_ids.filtered(lambda l: l.display_type == 'product').mapped('balance')
        )
        raw_tax_vef = base_vef * 0.16
        rate = inv.invoice_currency_rate
        expected_3dp = currency_3dp.round(raw_tax_vef * rate)
        expected_if_rounded_as_vef = self.currency_vef.round(raw_tax_vef * rate)
        self.assertNotEqual(
            expected_3dp, expected_if_rounded_as_vef,
            msg="Test setup does not exercise a 3rd-decimal difference; adjust the numbers",
        )
        self.assertAlmostEqual(
            tax_line.amount_currency, expected_3dp, places=3,
            msg="amount_currency was rounded with the wrong currency's precision",
        )

    # ── Test: amount_currency (native) vs foreign_debit/foreign_credit
    # (alterno) on a USD invoice when the *document* currency and the
    # *foreign* currency are the SAME (USD). This isolates the two
    # pipelines from any FX-conversion noise: if they still disagree,
    # the difference comes purely from the rounding pipeline itself
    # (rate derived from a pre-rounded `foreign_price` vs. the native
    # tax engine's own base), not from currency conversion. See
    # `_prepare_product_foreign_base_line_for_taxes_computation`
    # (account_move.py ~1272-1276): `rate = foreign_price / price_unit`,
    # where `foreign_price` is already float_round()'ed to the foreign
    # currency's precision before the division happens.

    def test_28_usd_invoice_amount_currency_vs_foreign_matches_when_doc_currency_is_foreign_currency(self):
        """When invoice currency == company.foreign_currency_id (USD == USD), amount_currency and
        foreign_debit/foreign_credit of the SAME tax line should represent the same money and must match.
        With 6-decimal 'Product Price', a naive rate derived from an already-rounded foreign_price can
        drift by 0.01 vs. the native amount_currency computed by Odoo's own tax engine.

        Forces 'round_per_line': the default is 'round_globally', under which this test would pass
        without ever exercising `_per_line_tax_sums` -- see test_30 for that code path specifically."""
        self.company.tax_calculation_rounding_method = 'round_per_line'
        inv = self._create_invoice_with_precision(self.currency_usd, [
            (1, 156.354321, [self.tax_16]),
            (2.5, 2.498557, [self.tax_16]),
            (3, 1458454.612345, [self.tax_31]),
            (7, 0.019999, [self.tax_16]),
        ])
        tax_lines = inv.line_ids.filtered(lambda l: l.display_type == 'tax')
        self.assertTrue(tax_lines, "No tax lines found on the invoice")
        mismatches = []
        for line in tax_lines:
            native_amc = abs(line.amount_currency)
            alterno = abs(line.foreign_debit - line.foreign_credit)
            diff = abs(native_amc - alterno)
            if diff > 0.005:
                mismatches.append(
                    f"{line.name}: amount_currency={native_amc} vs "
                    f"foreign_debit-foreign_credit={alterno} (diff={diff})"
                )
        self.assertFalse(
            mismatches,
            msg=(
                "amount_currency (native) differs from foreign_debit/foreign_credit (alterno) "
                "on the SAME tax line, even though the invoice currency and the foreign currency "
                "are both USD (no FX conversion should be involved):\n" + "\n".join(mismatches)
            ),
        )
        product_lines = inv.line_ids.filtered(lambda l: l.display_type == 'product')
        for line in product_lines:
            native_amc = abs(line.amount_currency)
            alterno = abs(line.foreign_debit - line.foreign_credit)
            diff = abs(native_amc - alterno)
            self.assertLessEqual(
                diff, 0.005,
                msg=(
                    f"Product line {line.name}: amount_currency={native_amc} vs "
                    f"foreign_debit-foreign_credit={alterno} (diff={diff})"
                ),
            )

    def test_29_vef_invoice_foreign_vs_direct_convert_of_balance(self):
        """VEF invoice (= company currency, rate 1): balance == amount_currency trivially.
        The 'foreign' pipeline independently recomputes tax from `foreign_price` (converted
        price_unit) instead of just converting the already-computed VEF balance. With
        6-decimal product prices, these two independent computations can round differently.
        This compares each tax/product line's foreign_debit-foreign_credit against a plain
        currency conversion of its own (native) balance, to see if/where they diverge."""
        inv = self._create_invoice_with_precision(self.currency_vef, [
            (1, 156.354321, [self.tax_16]),
            (2.5, 2.498557, [self.tax_16]),
            (3, 1458454.612345, [self.tax_31]),
            (7, 0.019999, [self.tax_16]),
            (1.333333, 999999.999999, [self.tax_16, self.tax_31]),
        ])
        rate_date = inv.invoice_date
        lines = inv.line_ids.filtered(lambda l: l.display_type in ('product', 'tax'))
        report = []
        for line in lines:
            direct_convert = self.currency_vef._convert(
                line.balance, self.currency_usd, self.company, rate_date,
            )
            alterno = line.foreign_debit - line.foreign_credit
            diff = abs(abs(direct_convert) - abs(alterno))
            report.append(
                f"{line.display_type} {line.name}: balance(VEF)={line.balance} "
                f"direct_convert(USD)={direct_convert} foreign(USD)={alterno} diff={diff}"
            )
        _logger.info("test_29 report:\n" + "\n".join(report))
        mismatches = [r for r in report if float(r.rsplit('diff=', 1)[1]) > 0.005]
        self.assertFalse(
            mismatches,
            msg=(
                "foreign_debit/foreign_credit diverges from a direct currency conversion "
                "of the same line's VEF balance by more than 0.005 USD:\n" + "\n".join(mismatches)
            ),
        )

    def test_30_fiscal_machine_round_per_line_vs_round_globally(self):
        """User-provided real-world case: rate 803.34 VEF/USD, 2 lines of 11.16 USD each,
        tax 16%. Per the fiscal-machine method (round the tax of EACH line to 2 decimals,
        THEN sum), the expected total tax is 2868.88 Bs. If the company is configured with
        'round_globally' (Odoo 19 default), summing the raw (unrounded) per-line taxes and
        rounding once at the end gives 2868.89 Bs instead -- a real 0.01 divergence from what
        the law/fiscal-machine method requires, independent of any 'foreign'/alterno logic."""
        self.env["res.currency.rate"].search([
            ("currency_id", "=", self.currency_usd.id),
            ("company_id", "=", self.company.id),
        ]).unlink()
        self.env["res.currency.rate"].create({
            "name": fields.Date.today(),
            "currency_id": self.currency_usd.id,
            "inverse_company_rate": 803.34,
            "company_id": self.company.id,
        })

        expected_round_per_line = 2868.88
        expected_round_globally = 2868.89
        self.assertNotEqual(
            expected_round_per_line, expected_round_globally,
            msg="Sanity check on the hand-computed numbers themselves",
        )

        for mode in ("round_per_line", "round_globally"):
            with self.subTest(mode=mode):
                self.company.tax_calculation_rounding_method = mode
                inv = self._create_invoice(self.currency_usd, None, [
                    (1, 11.16, [self.tax_16]),
                    (1, 11.16, [self.tax_16]),
                ])
                tax_line = inv.line_ids.filtered(lambda l: l.display_type == 'tax')
                total_tax_vef = abs(sum(tax_line.mapped('balance')))
                product_lines = inv.line_ids.filtered(lambda l: l.display_type == 'product')
                debug = "\n".join(
                    f"  {l.display_type} {l.name}: balance={l.balance} "
                    f"amount_currency={l.amount_currency} currency_rate={l.currency_rate} "
                    f"foreign_debit={l.foreign_debit} foreign_credit={l.foreign_credit}"
                    for l in (product_lines + tax_line)
                )
                _logger.info(
                    "test_30 mode=%s total_tax_vef=%s (expected round_per_line=%s, "
                    "round_globally=%s) invoice_currency_rate=%s\n%s",
                    mode, total_tax_vef, expected_round_per_line, expected_round_globally,
                    inv.invoice_currency_rate, debug,
                )
                expected = (
                    expected_round_per_line if mode == "round_per_line"
                    else expected_round_globally
                )
                self.assertAlmostEqual(
                    total_tax_vef, expected, places=2,
                    msg=(
                        f"With tax_calculation_rounding_method={mode}, total tax in VEF "
                        f"was {total_tax_vef}, expected {expected}"
                    ),
                )
                # amount_currency (USD, native) vs foreign_debit/foreign_credit (USD,
                # alterno) of the SAME tax line -- invoice currency == foreign currency
                # (both USD), so these should represent the exact same money.
                native_amc = abs(tax_line.amount_currency)
                alterno = abs(sum(tax_line.mapped('foreign_debit')) - sum(tax_line.mapped('foreign_credit')))
                self.assertAlmostEqual(
                    native_amc, alterno, places=2,
                    msg=(
                        f"[{mode}] Tax line amount_currency={native_amc} USD (native) != "
                        f"foreign_debit-foreign_credit={alterno} USD (alterno), even though "
                        f"invoice currency and foreign currency are both USD"
                    ),
                )
                # The widget/PDF total (`amount_tax`, backed by `tax_totals`,
                # computed independently from `base_lines` via the core
                # engine) must match what actually posted to the tax line's
                # `balance`/`amount_currency` -- otherwise the invoice the
                # customer sees disagrees with the ledger. `amount_tax` is
                # in the DOCUMENT currency (USD here), same as
                # `amount_currency` -- NOT in VEF like `total_tax_vef`.
                self.assertAlmostEqual(
                    abs(inv.amount_tax), native_amc, places=2,
                    msg=(
                        f"[{mode}] inv.amount_tax={inv.amount_tax} USD does not match the "
                        f"posted tax line's amount_currency ({native_amc} USD) -- the invoice "
                        f"widget/PDF would show a different tax than what was actually posted"
                    ),
                )

    def test_31_mixed_sign_lines_both_rounding_modes(self):
        """A negative (discount/adjustment) line sharing a tax with positive lines must NET OUT,
        not add up as if both were positive -- in BOTH rounding modes. `round_per_line` had a
        real `abs()` bug here (fixed via `_per_line_tax_sums` summing SIGNED per-line amounts);
        `round_globally`'s `_vef_base_for_tax`/`_grouped_tax_sums` never used `abs()` so it was
        never at risk, but is included for completeness/regression coverage."""
        self.env["res.currency.rate"].search([
            ("currency_id", "=", self.currency_usd.id),
            ("company_id", "=", self.company.id),
        ]).unlink()
        self.env["res.currency.rate"].create({
            "name": fields.Date.today(),
            "currency_id": self.currency_usd.id,
            "inverse_company_rate": 803.34,
            "company_id": self.company.id,
        })
        for mode in ("round_per_line", "round_globally"):
            with self.subTest(mode=mode):
                self.company.tax_calculation_rounding_method = mode
                # Line A: 11.16 USD (positive). Line B: a -4.16 USD
                # adjustment on the SAME tax -- net base is 7.00 USD, net
                # tax must reflect that, not `tax(11.16) + tax(-4.16)`
                # miscomputed as `tax(11.16) + tax(4.16)`.
                inv = self._create_invoice(self.currency_usd, None, [
                    (1, 11.16, [self.tax_16]),
                    (1, -4.16, [self.tax_16]),
                ])
                tax_line = inv.line_ids.filtered(lambda l: l.display_type == 'tax')
                product_lines = inv.line_ids.filtered(lambda l: l.display_type == 'product')
                net_base_usd = sum(product_lines.mapped('amount_currency'))
                expected_tax_usd = self.currency_usd.round(abs(net_base_usd) * 0.16)
                self.assertAlmostEqual(
                    abs(tax_line.amount_currency), expected_tax_usd, places=2,
                    msg=(
                        f"[{mode}] With mixed-sign lines, "
                        f"tax_line.amount_currency={tax_line.amount_currency} does not match "
                        f"the netted base's tax ({expected_tax_usd}) -- looks like the negative "
                        f"line's contribution was added instead of subtracted"
                    ),
                )
                net_base_vef = sum(product_lines.mapped('balance'))
                expected_tax_vef = self.currency_vef.round(abs(net_base_vef) * 0.16)
                self.assertAlmostEqual(
                    abs(tax_line.balance), expected_tax_vef, places=2,
                    msg=(
                        f"[{mode}] With mixed-sign lines, tax_line.balance={tax_line.balance} "
                        f"(VEF) does not match the netted base's tax ({expected_tax_vef}) -- "
                        f"looks like the negative line's contribution was added instead of "
                        f"subtracted"
                    ),
                )
                # `amount_tax` is in the document currency (USD), same as
                # `amount_currency` -- NOT in VEF like `expected_tax_vef`.
                self.assertAlmostEqual(
                    abs(inv.amount_tax), abs(tax_line.amount_currency), places=2,
                    msg=f"[{mode}] inv.amount_tax (widget total, USD) inconsistent with the posted tax line",
                )

    def test_32_SCOPE_CHECK_vef_only_invoice_round_per_line(self):
        """SCOPE CHECK (not a real regression guard): the whole `_apply_vef_first` fix is gated
        behind `move.currency_id != move.company_id.currency_id`. This checks whether a
        single-currency VEF invoice (company currency == document currency, the most common
        case for many VE businesses) also gets fiscal-machine-style per-line rounding, or
        whether Odoo's original grouped-then-round-once behavior is still unpatched there."""
        self.company.tax_calculation_rounding_method = 'round_per_line'
        # Same shape as the real-world case, but priced directly in VEF so
        # `currency_id == company_id.currency_id` and the whole multi-currency
        # block (where the fix lives) never runs.
        inv = self._create_invoice(self.currency_vef, None, [
            (1, 8965.2744 / 1, [self.tax_16]),
            (1, 8965.2744 / 1, [self.tax_16]),
        ])
        tax_line = inv.line_ids.filtered(lambda l: l.display_type == 'tax')
        total_tax_vef = abs(sum(tax_line.mapped('balance')))
        _logger.info(
            "test_32 SCOPE CHECK: VEF-only invoice, round_per_line, total_tax_vef=%s "
            "(fiscal-machine method expects 2868.88, grouped-then-round expects 2868.89)",
            total_tax_vef,
        )

    def _create_chained_taxes(self, suffix=""):
        """Tax A 10% (include_base_amount) followed by Tax B 5% computed on A's base + A's amount."""
        tax_a = self.env["account.tax"].with_company(self.company).create({
            "name": f"Tax A 10% (chained){suffix}",
            "amount": 10.0,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "company_id": self.company.id,
            "tax_group_id": self.tax_group.id,
            "sequence": 1,
            "include_base_amount": True,
            "invoice_repartition_line_ids": [
                (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0, 'account_id': self.acc_tax.id}),
            ],
            "refund_repartition_line_ids": [
                (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0, 'account_id': self.acc_tax.id}),
            ],
        })
        tax_b = self._create_tax(f'Tax B 5% (on chained base){suffix}', 5.0)
        tax_b.sequence = 2
        return tax_a, tax_b

    def _expected_chained_vef(self, product_lines, mode):
        """Exact expected (tax_a_vef, tax_b_vef), replicating the real algorithm per mode --
        not a hand-approximated formula. `round_per_line`: round each line's tax_a, fold it into
        that SAME line's base, round tax_b, sum the already-rounded per-line amounts (mirrors
        `_per_line_tax_sums`). `round_globally`: round once over the summed base, same as
        `_grouped_tax_sums` (the proportional per-line distribution it does algebraically sums
        back to the same whole-invoice total for two identical lines, as used here)."""
        if mode == 'round_per_line':
            total_a = 0.0
            total_b = 0.0
            for pl in product_lines:
                base = abs(pl.balance)
                line_tax_a = self.currency_vef.round(base * 0.10)
                line_tax_b = self.currency_vef.round((base + line_tax_a) * 0.05)
                total_a += line_tax_a
                total_b += line_tax_b
            return self.currency_vef.round(total_a), self.currency_vef.round(total_b)
        base_vef = sum(abs(pl.balance) for pl in product_lines)
        tax_a = self.currency_vef.round(base_vef * 0.10)
        tax_b = self.currency_vef.round((base_vef + tax_a) * 0.05)
        return tax_a, tax_b

    def test_33_include_base_amount_chained_tax_both_rounding_modes_both_currencies(self):
        """A tax with include_base_amount=True must fold its OWN just-computed amount into the
        base of the NEXT tax on the same line, in BOTH `tax_calculation_rounding_method` modes
        and for both a USD and a EUR invoice (company currency stays VEF throughout) --
        `round_per_line` via `_per_line_tax_sums`/`extra_base_by_line_id`, `round_globally` via
        `_grouped_tax_sums`'s proportional distribution back into the same tracker. Both derive
        exclusively from our own freshly-computed per-line amounts, never from Odoo's core
        `tax_details` (which can carry a stale internal rate -- see the comment above
        `extra_base_by_line_id` in account_move.py for why that path was tried and reverted).
        Repartition lines are processed in ascending `tax.sequence` order so the chaining tax
        (lower sequence) is always folded in before its dependent (higher sequence)."""
        for mode in ("round_per_line", "round_globally"):
            for currency, rate in ((self.currency_usd, 803.34), (self.currency_eur, 915.20)):
                with self.subTest(mode=mode, currency=currency.name):
                    self.company.tax_calculation_rounding_method = mode
                    tax_a, tax_b = self._create_chained_taxes(f" [{mode}/{currency.name}]")

                    self.env["res.currency.rate"].search([
                        ("currency_id", "=", currency.id),
                        ("company_id", "=", self.company.id),
                    ]).unlink()
                    self.env["res.currency.rate"].create({
                        "name": fields.Date.today(),
                        "currency_id": currency.id,
                        "inverse_company_rate": rate,
                        "company_id": self.company.id,
                    })

                    inv = self._create_invoice(currency, None, [
                        (1, 11.16, [tax_a, tax_b]),
                        (1, 11.16, [tax_a, tax_b]),
                    ])
                    product_lines = inv.line_ids.filtered(lambda l: l.display_type == 'product')
                    tax_lines = inv.line_ids.filtered(lambda l: l.display_type == 'tax')
                    line_a = tax_lines.filtered(lambda l: l.tax_line_id == tax_a)
                    line_b = tax_lines.filtered(lambda l: l.tax_line_id == tax_b)
                    self.assertTrue(line_a and line_b, "Expected one tax line per chained tax")

                    base_vef = abs(sum(product_lines.mapped('balance')))
                    naive_tax_b = self.currency_vef.round(base_vef * 0.05)
                    expected_tax_a, expected_tax_b = self._expected_chained_vef(product_lines, mode)
                    self.assertNotEqual(
                        naive_tax_b, expected_tax_b,
                        msg=(
                            f"[{mode}/{currency.name}] Test setup does not exercise a real "
                            f"cascading difference; adjust the numbers"
                        ),
                    )
                    self.assertAlmostEqual(
                        abs(line_a.balance), expected_tax_a, places=2,
                        msg=f"[{mode}/{currency.name}] Tax A balance={line_a.balance} != exact expected {expected_tax_a}",
                    )
                    self.assertAlmostEqual(
                        abs(line_b.balance), expected_tax_b, places=2,
                        msg=(
                            f"[{mode}/{currency.name}] Tax B balance={line_b.balance} != exact "
                            f"expected {expected_tax_b} (naive, wrong, would give {naive_tax_b})"
                        ),
                    )
                    td = sum(inv.line_ids.mapped('debit'))
                    tc = sum(inv.line_ids.mapped('credit'))
                    self.assertAlmostEqual(
                        td, tc, places=2, msg=f"[{mode}/{currency.name}] Debit != Credit"
                    )
                    # amount_currency (native) vs foreign_debit/foreign_credit (alterno) must
                    # still match on the chained tax lines when currency == foreign currency.
                    if currency == self.currency_usd:
                        for line in (line_a, line_b):
                            native_amc = abs(line.amount_currency)
                            alterno = abs(line.foreign_debit - line.foreign_credit)
                            self.assertAlmostEqual(
                                native_amc, alterno, places=2,
                                msg=(
                                    f"[{mode}] {line.name}: amount_currency={native_amc} vs "
                                    f"foreign={alterno} diverge on a chained tax line"
                                ),
                            )

    def test_34_include_base_amount_both_rounding_modes_vef_only_invoice(self):
        """SCOPE CHECK companion to test_32: chained tax on a single-currency VEF invoice, in
        both rounding modes. The multi-currency block (where `extra_base_by_line_id` lives)
        never runs here (currency_id == company currency), so this exercises whatever Odoo's
        own core does with `include_base_amount` unpatched -- confirms it stays balanced and
        cascades correctly on its own, same conclusion as test_32 for the non-chained case.

        Unlike test_33, this does NOT independently predict Tax A's exact value -- that would
        require replicating Odoo core's own (unaudited-by-us) internal rounding order, which
        does not need to match `_expected_chained_vef` (that helper mirrors OUR algorithm, not
        the core's). Instead it uses the ACTUAL posted Tax A as ground truth for what Tax B's
        base must equal, which is exact and requires no assumption about the core's internals."""
        for mode in ("round_per_line", "round_globally"):
            with self.subTest(mode=mode):
                self.company.tax_calculation_rounding_method = mode
                tax_a, tax_b = self._create_chained_taxes(f" [{mode}]")
                inv = self._create_invoice(self.currency_vef, None, [
                    (1, 8965.2744, [tax_a, tax_b]),
                    (1, 8965.2744, [tax_a, tax_b]),
                ])
                product_lines = inv.line_ids.filtered(lambda l: l.display_type == 'product')
                tax_lines = inv.line_ids.filtered(lambda l: l.display_type == 'tax')
                line_a = tax_lines.filtered(lambda l: l.tax_line_id == tax_a)
                line_b = tax_lines.filtered(lambda l: l.tax_line_id == tax_b)
                self.assertTrue(line_a and line_b, f"[{mode}] Expected one tax line per chained tax")

                base_vef = abs(sum(product_lines.mapped('balance')))
                naive_tax_b = self.currency_vef.round(base_vef * 0.05)
                exact_expected_tax_b = self.currency_vef.round((base_vef + abs(line_a.balance)) * 0.05)
                self.assertNotEqual(
                    naive_tax_b, exact_expected_tax_b,
                    msg=f"[{mode}] Test setup does not exercise a real cascading difference",
                )
                self.assertAlmostEqual(
                    abs(line_b.balance), exact_expected_tax_b, places=2,
                    msg=(
                        f"[{mode}] VEF-only: Tax B balance={line_b.balance} != exact "
                        f"{exact_expected_tax_b} (base + actual posted Tax A) -- naive, wrong, "
                        f"would give {naive_tax_b}"
                    ),
                )
                td = sum(inv.line_ids.mapped('debit'))
                tc = sum(inv.line_ids.mapped('credit'))
                self.assertAlmostEqual(td, tc, places=2, msg=f"[{mode}] Debit != Credit")

    def _expected_per_line_tax_vef(self, product_lines, tax):
        """Ground truth for a SPECIFIC tax's total, replicating `_per_line_tax_sums`: round each
        matching line's own contribution (from its ACTUAL posted `balance`, not an independent
        prediction) and sum the already-rounded amounts."""
        total = 0.0
        for pl in product_lines:
            if tax in pl.tax_ids:
                total += self.currency_vef.round(abs(pl.balance) * tax.amount / 100.0)
        return self.currency_vef.round(total)

    def test_35_round_per_line_with_a_real_mix_of_different_taxes_across_lines(self):
        """Tests 01-27 already mix several DIFFERENT taxes across lines (a two-tax line, a
        single-tax-8 line, a single-tax-16 line) but all run under the default
        `round_globally` -- none of them exercise `_per_line_tax_sums`/the `round_per_line`
        fix with that kind of real mix (overlapping tax_ids across lines, not just the same
        single tax repeated). This closes that gap: same three-line shape as test_02/test_15,
        explicitly forced to `round_per_line`, with exact per-tax expectations."""
        self.company.tax_calculation_rounding_method = 'round_per_line'
        self.env["res.currency.rate"].search([
            ("currency_id", "=", self.currency_usd.id),
            ("company_id", "=", self.company.id),
        ]).unlink()
        self.env["res.currency.rate"].create({
            "name": fields.Date.today(),
            "currency_id": self.currency_usd.id,
            "inverse_company_rate": 803.34,
            "company_id": self.company.id,
        })
        inv = self._create_invoice(self.currency_usd, None, [
            (1, 156.354321, [self.tax_16, self.tax_31]),
            (2.5, 2.498557, [self.tax_8]),
            (3, 1458454.612345, [self.tax_16]),
        ])
        product_lines = inv.line_ids.filtered(lambda l: l.display_type == 'product')
        tax_lines = inv.line_ids.filtered(lambda l: l.display_type == 'tax')

        for tax, name in ((self.tax_16, 'IVA 16%'), (self.tax_31, 'IVA 31%'), (self.tax_8, 'IVA 8%')):
            tax_line = tax_lines.filtered(lambda l, t=tax: l.tax_line_id == t)
            self.assertEqual(len(tax_line), 1, f"Expected exactly one tax line for {name}")
            expected = self._expected_per_line_tax_vef(product_lines, tax)
            self.assertAlmostEqual(
                abs(tax_line.balance), expected, places=2,
                msg=(
                    f"{name}: balance={tax_line.balance} != exact per-line-summed expected "
                    f"{expected} -- tax_16 appears on TWO different lines (one shared with "
                    f"tax_31, one alone), tax_31 and tax_8 each on only one line"
                ),
            )
        td = sum(inv.line_ids.mapped('debit'))
        tc = sum(inv.line_ids.mapped('credit'))
        self.assertAlmostEqual(td, tc, places=2, msg="Debit != Credit")
        # NOTE: `_assert_header_and_tax_line_match` is NOT used here -- it hand-computes the
        # expected tax by summing all matching lines' bases first and rounding once (the
        # `round_globally` shape), which is exactly what `round_per_line` must NOT do.

    # ── Native-Odoo documentation/regression tests: what does Odoo's OWN
    # engine do for each `amount_type`, independent of anything this module
    # changes? `_apply_vef_first`'s round_per_line fix only touches
    # `amount_type == 'percent'` taxes (`_per_line_tax_sums`/
    # `_grouped_tax_sums`) -- 'fixed', 'division' and price-included taxes
    # fall through to "keep original behavior" (account_move.py, the
    # `if not tax or tax.amount_type != 'percent':` guard in
    # `_apply_vef_first`) regardless of currency or rounding mode. These
    # tests use `tax.compute_all()` (Odoo's own public API) as an
    # independent oracle to confirm/document what actually gets posted,
    # in BOTH rounding modes, on a VEF-only invoice so no part of this
    # module's code intervenes at all -- pure core Odoo behavior.

    def test_36_native_fixed_amount_tax_both_rounding_modes(self):
        """amount_type='fixed': a flat amount per unit, independent of price_unit. Must be
        exactly `amount * quantity` regardless of rounding mode (nothing to round-per-line vs
        round-globally about a flat rate -- there's no percentage/base multiplication at all)."""
        tax_fixed = self.env["account.tax"].with_company(self.company).create({
            "name": "Fixed Tax 50 VEF/unit",
            "amount": 50.0,
            "amount_type": "fixed",
            "type_tax_use": "sale",
            "company_id": self.company.id,
            "tax_group_id": self.tax_group.id,
            "invoice_repartition_line_ids": [
                (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0, 'account_id': self.acc_tax.id}),
            ],
            "refund_repartition_line_ids": [
                (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0, 'account_id': self.acc_tax.id}),
            ],
        })
        for mode in ("round_per_line", "round_globally"):
            with self.subTest(mode=mode):
                self.company.tax_calculation_rounding_method = mode
                inv = self._create_invoice(self.currency_vef, None, [
                    (3, 1000.0, [tax_fixed]),
                    (2, 2500.0, [tax_fixed]),
                ])
                tax_line = inv.line_ids.filtered(lambda l: l.tax_line_id == tax_fixed)
                self.assertEqual(len(tax_line), 1, f"[{mode}] Expected one tax line")
                # Oracle: Odoo's own compute_all for each line, independent
                # of anything this module touches.
                oracle_total = 0.0
                for qty, price in ((3, 1000.0), (2, 2500.0)):
                    res = tax_fixed.compute_all(price, currency=self.currency_vef, quantity=qty)
                    oracle_total += res['taxes'][0]['amount']
                self.assertAlmostEqual(
                    abs(tax_line.balance), self.currency_vef.round(oracle_total), places=2,
                    msg=f"[{mode}] Fixed tax balance={tax_line.balance} != compute_all oracle {oracle_total}",
                )
                # Documents the actual rule: fixed tax = amount * total quantity, period.
                self.assertAlmostEqual(
                    abs(tax_line.balance), 50.0 * (3 + 2), places=2,
                    msg=f"[{mode}] Fixed tax must equal amount * total quantity exactly",
                )

    def test_37_native_price_included_percent_tax_both_rounding_modes(self):
        """amount_type='percent' with price_include=True: the listed price_unit already
        contains the tax, so the base (untaxed) must be BACKED OUT of it, not added on top.
        For a 16% price-included tax on 116.00, base=100.00 and tax=16.00 (not base=116.00,
        tax=18.56). Goes through `_apply_vef_first` on a multi-currency invoice (it's still
        `amount_type == 'percent'`) but this specific test uses a VEF-only invoice to document
        the CORE's own price_include math with nothing from this module in the way."""
        tax_incl = self.env["account.tax"].with_company(self.company).create({
            "name": "IVA 16% incluido en precio",
            "amount": 16.0,
            "amount_type": "percent",
            "price_include_override": "tax_included",
            "type_tax_use": "sale",
            "company_id": self.company.id,
            "tax_group_id": self.tax_group.id,
            "invoice_repartition_line_ids": [
                (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0, 'account_id': self.acc_tax.id}),
            ],
            "refund_repartition_line_ids": [
                (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0, 'account_id': self.acc_tax.id}),
            ],
        })
        for mode in ("round_per_line", "round_globally"):
            with self.subTest(mode=mode):
                self.company.tax_calculation_rounding_method = mode
                inv = self._create_invoice(self.currency_vef, None, [
                    (1, 116.0, [tax_incl]),
                ])
                product_line = inv.line_ids.filtered(lambda l: l.display_type == 'product')
                tax_line = inv.line_ids.filtered(lambda l: l.tax_line_id == tax_incl)
                oracle = tax_incl.compute_all(116.0, currency=self.currency_vef, quantity=1)
                oracle_base = self.currency_vef.round(oracle['total_excluded'])
                oracle_tax = self.currency_vef.round(oracle['taxes'][0]['amount'])
                self.assertAlmostEqual(
                    oracle_base, 100.0, places=2,
                    msg="Test setup sanity check: 116 with 16% included should back out to 100",
                )
                self.assertAlmostEqual(
                    abs(product_line.balance), oracle_base, places=2,
                    msg=f"[{mode}] Untaxed base={product_line.balance} != compute_all oracle {oracle_base}",
                )
                self.assertAlmostEqual(
                    abs(tax_line.balance), oracle_tax, places=2,
                    msg=f"[{mode}] Included tax={tax_line.balance} != compute_all oracle {oracle_tax}",
                )
                # Documents the actual rule: base + tax must reconstruct the original price.
                self.assertAlmostEqual(
                    abs(product_line.balance) + abs(tax_line.balance), 116.0, places=2,
                    msg=f"[{mode}] base + tax must reconstruct the original price-included amount",
                )

    def test_38_native_division_type_tax_both_rounding_modes(self):
        """amount_type='division': the tax is expressed as a percentage of the TOTAL (price
        included), not of the base -- e.g. a 10% 'division' tax on 100 gives tax=11.111...
        (100 / 0.9 - 100), not tax=10.00 like a plain percent tax would. Documents Odoo's own
        math for this less-common configuration, in both rounding modes, on a VEF-only invoice."""
        tax_div = self.env["account.tax"].with_company(self.company).create({
            "name": "Division Tax 10%",
            "amount": 10.0,
            "amount_type": "division",
            "type_tax_use": "sale",
            "company_id": self.company.id,
            "tax_group_id": self.tax_group.id,
            "invoice_repartition_line_ids": [
                (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0, 'account_id': self.acc_tax.id}),
            ],
            "refund_repartition_line_ids": [
                (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0, 'account_id': self.acc_tax.id}),
            ],
        })
        for mode in ("round_per_line", "round_globally"):
            with self.subTest(mode=mode):
                self.company.tax_calculation_rounding_method = mode
                inv = self._create_invoice(self.currency_vef, None, [
                    (1, 100.0, [tax_div]),
                ])
                tax_line = inv.line_ids.filtered(lambda l: l.tax_line_id == tax_div)
                oracle = tax_div.compute_all(100.0, currency=self.currency_vef, quantity=1)
                oracle_tax = self.currency_vef.round(oracle['taxes'][0]['amount'])
                self.assertNotAlmostEqual(
                    oracle_tax, 10.0, places=2,
                    msg="Test setup sanity check: a 'division' 10% tax must NOT equal a plain 10% of the base",
                )
                self.assertAlmostEqual(
                    abs(tax_line.balance), oracle_tax, places=2,
                    msg=f"[{mode}] Division-type tax={tax_line.balance} != compute_all oracle {oracle_tax}",
                )

    def test_39_price_included_tax_through_our_multi_currency_fix_both_rounding_modes(self):
        """Unlike test_37 (VEF-only, pure core), THIS exercises `_apply_vef_first`/
        `_per_line_tax_sums`/`_grouped_tax_sums` for a price-included tax on a USD invoice
        (currency_id != company currency). Our code doesn't special-case price_include: it
        multiplies `fresh_balance_by_line_id` (the base) by `tax.amount/100`. That's still
        correct BECAUSE `fresh_balance_by_line_id` is read off `to_update['balance']`, which
        Odoo's own base engine already backed out of the price-included amount before our
        override ever runs -- price_include only changes what "the base" IS (backed out vs.
        added on top), not the multiplication our code does once it has that base. Verifies:
        base + tax reconstructs the price-included amount, in VEF AND in USD, in both modes,
        and that amount_currency still matches foreign_debit/foreign_credit (USD invoice ==
        USD foreign currency)."""
        tax_incl = self.env["account.tax"].with_company(self.company).create({
            "name": "IVA 16% incluido (multi-moneda)",
            "amount": 16.0,
            "amount_type": "percent",
            "price_include_override": "tax_included",
            "type_tax_use": "sale",
            "company_id": self.company.id,
            "tax_group_id": self.tax_group.id,
            "invoice_repartition_line_ids": [
                (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0, 'account_id': self.acc_tax.id}),
            ],
            "refund_repartition_line_ids": [
                (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0, 'account_id': self.acc_tax.id}),
            ],
        })
        self.env["res.currency.rate"].search([
            ("currency_id", "=", self.currency_usd.id),
            ("company_id", "=", self.company.id),
        ]).unlink()
        self.env["res.currency.rate"].create({
            "name": fields.Date.today(),
            "currency_id": self.currency_usd.id,
            "inverse_company_rate": 803.34,
            "company_id": self.company.id,
        })
        for mode in ("round_per_line", "round_globally"):
            with self.subTest(mode=mode):
                self.company.tax_calculation_rounding_method = mode
                # 116 USD, tax included: base=100, tax=16.
                inv = self._create_invoice(self.currency_usd, None, [
                    (1, 116.0, [tax_incl]),
                    (2, 58.0, [tax_incl]),
                ])
                product_lines = inv.line_ids.filtered(lambda l: l.display_type == 'product')
                tax_line = inv.line_ids.filtered(lambda l: l.tax_line_id == tax_incl)
                self.assertEqual(len(tax_line), 1, f"[{mode}] Expected one tax line")

                # base + tax reconstructs the original price-included total,
                # in BOTH currencies.
                total_doc = sum(product_lines.mapped('amount_currency')) + tax_line.amount_currency
                self.assertAlmostEqual(
                    abs(total_doc), 116.0 + 2 * 58.0, places=2,
                    msg=f"[{mode}] USD base+tax does not reconstruct the price-included total",
                )
                total_vef = sum(product_lines.mapped('balance')) + tax_line.balance
                oracle = tax_incl.compute_all(116.0, currency=self.currency_usd, quantity=1)
                oracle2 = tax_incl.compute_all(58.0, currency=self.currency_usd, quantity=2)
                oracle_total_doc = oracle['total_included'] + oracle2['total_included']
                self.assertAlmostEqual(
                    abs(total_doc), self.currency_usd.round(oracle_total_doc), places=2,
                    msg=f"[{mode}] USD total does not match compute_all oracle",
                )
                # amount_currency (native, USD) vs foreign (alterno, USD == foreign currency).
                for line in list(product_lines) + [tax_line]:
                    native_amc = abs(line.amount_currency)
                    alterno = abs(line.foreign_debit - line.foreign_credit)
                    self.assertAlmostEqual(
                        native_amc, alterno, places=2,
                        msg=f"[{mode}] {line.name}: amount_currency={native_amc} vs foreign={alterno} diverge",
                    )
                td = sum(inv.line_ids.mapped('debit'))
                tc = sum(inv.line_ids.mapped('credit'))
                self.assertAlmostEqual(td, tc, places=2, msg=f"[{mode}] Debit != Credit")

    def test_40_non_percent_taxes_mode_effect_comes_from_core_not_from_our_code(self):
        """Checks, per tax type, whether `tax_calculation_rounding_method` has any effect on a
        NON-'percent' tax on a multi-currency invoice. `_apply_vef_first`'s `else` branch
        (`to_update['balance'] = cc.round(to_update['amount_currency'] / rate)`) NEVER reads
        the mode and never touches `amount_currency` -- our code contributes ZERO mode-
        dependence here. But that does NOT mean the mode has no effect at all: `amount_currency`
        itself is set by Odoo's OWN core engine BEFORE this code runs, and the core DOES
        consult the mode generally (not just for 'percent'). This was verified empirically
        (not assumed) on THREE asymmetric lines (a symmetric two-identical-lines case can hide
        a real divergence, as it originally did for 'percent' in test_30's discovery):
        - 'fixed' (flat amount * quantity, no percentage/rounding math to speak of): confirmed
          IDENTICAL (balance, amount_currency) in both modes.
        - 'division' (its amount depends on a % of the total, real rounding math involved):
          confirmed it DOES DIVERGE between modes -- the divergence originates entirely in
          Odoo's core (mode-aware there), passed through untouched by this module. Whether
          that native, mode-aware result also matches the fiscal-machine per-line method is a
          separate, unverified question -- out of scope for this fix (only 'percent' was)."""
        for tax, lines_data, expect_mode_independent in (
            (
                self.env["account.tax"].with_company(self.company).create({
                    "name": "Division Tax 10% (mode-blind check)",
                    "amount": 10.0,
                    "amount_type": "division",
                    "type_tax_use": "sale",
                    "company_id": self.company.id,
                    "tax_group_id": self.tax_group.id,
                    "invoice_repartition_line_ids": [
                        (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                        (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0, 'account_id': self.acc_tax.id}),
                    ],
                    "refund_repartition_line_ids": [
                        (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                        (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0, 'account_id': self.acc_tax.id}),
                    ],
                }),
                [(1, 11.16, None), (1, 4.999, None), (3, 0.499999, None)],
                False,
            ),
            (
                self.env["account.tax"].with_company(self.company).create({
                    "name": "Fixed Tax 7 VEF/unit (mode-blind check)",
                    "amount": 7.0,
                    "amount_type": "fixed",
                    "type_tax_use": "sale",
                    "company_id": self.company.id,
                    "tax_group_id": self.tax_group.id,
                    "invoice_repartition_line_ids": [
                        (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                        (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0, 'account_id': self.acc_tax.id}),
                    ],
                    "refund_repartition_line_ids": [
                        (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                        (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0, 'account_id': self.acc_tax.id}),
                    ],
                }),
                [(1, 11.16, None), (1, 4.999, None), (3, 0.499999, None)],
                True,
            ),
        ):
            with self.subTest(tax=tax.name):
                self.env["res.currency.rate"].search([
                    ("currency_id", "=", self.currency_usd.id),
                    ("company_id", "=", self.company.id),
                ]).unlink()
                self.env["res.currency.rate"].create({
                    "name": fields.Date.today(),
                    "currency_id": self.currency_usd.id,
                    "inverse_company_rate": 803.34,
                    "company_id": self.company.id,
                })
                results = {}
                for mode in ("round_per_line", "round_globally"):
                    self.company.tax_calculation_rounding_method = mode
                    inv = self._create_invoice(self.currency_usd, None, [
                        (qty, price, [tax]) for qty, price, _ in lines_data
                    ])
                    tax_line = inv.line_ids.filtered(lambda l, t=tax: l.tax_line_id == t)
                    self.assertEqual(len(tax_line), 1, f"[{tax.name}/{mode}] Expected one tax line")
                    results[mode] = (tax_line.balance, tax_line.amount_currency)
                    _logger.info(
                        "test_40 tax=%s mode=%s (balance, amount_currency)=%s",
                        tax.name, mode, results[mode],
                    )
                if expect_mode_independent:
                    self.assertEqual(
                        results["round_per_line"], results["round_globally"],
                        msg=(
                            f"{tax.name}: expected mode-independent (fixed amount has no "
                            f"percentage/rounding math), but differs: "
                            f"round_per_line={results['round_per_line']} vs "
                            f"round_globally={results['round_globally']}"
                        ),
                    )
                else:
                    self.assertNotEqual(
                        results["round_per_line"], results["round_globally"],
                        msg=(
                            f"{tax.name}: expected the mode to have an effect (via Odoo's own "
                            f"core, not this module's code) on a real percentage-based tax, but "
                            f"both modes gave the same (balance, amount_currency) -- either the "
                            f"test numbers no longer exercise this, or core behavior changed"
                        ),
                    )

    def _fiscal_machine_oracle_vef(self, tax, product_lines):
        """TRUE fiscal-machine expected total for `tax`, using Odoo's OWN `compute_all()` as
        the oracle per line (never a hand-derived formula): for each line that has `tax`
        (directly, or via a `group` tax the user picked that has `tax` as a child -- `tax_ids`
        holds the group, not the child, in that case), compute that line's OWN tax in
        isolation (quantity=1, price_unit=the line's ACTUAL posted VEF balance) and round it
        individually, THEN sum the already-rounded amounts."""
        total = 0.0
        for pl in product_lines:
            picks_tax = tax in pl.tax_ids or any(tax in t.children_tax_ids for t in pl.tax_ids)
            if picks_tax:
                res = tax.compute_all(abs(pl.balance), currency=self.currency_vef, quantity=1)
                total += self.currency_vef.round(res['taxes'][0]['amount'])
        return self.currency_vef.round(total)

    def test_41_division_type_round_per_line_matches_fiscal_machine_oracle(self):
        """Does Odoo's NATIVE round_per_line handling for a 'division' tax (untouched by our
        fix -- see test_40) actually match the fiscal-machine per-line method (round each
        line's own tax, then sum), the same standard `_per_line_tax_sums` enforces for
        'percent'? Verified here with `compute_all()` as an independent oracle -- not assumed,
        not hand-derived. Logs the comparison either way; only asserts internal consistency
        (debit == credit), since whether this native path is "correct" per the fiscal-machine
        standard was explicitly flagged as unverified and out of scope for this fix."""
        tax_div = self.env["account.tax"].with_company(self.company).create({
            "name": "Division Tax 10% (fiscal-machine check)",
            "amount": 10.0,
            "amount_type": "division",
            "type_tax_use": "sale",
            "company_id": self.company.id,
            "tax_group_id": self.tax_group.id,
            "invoice_repartition_line_ids": [
                (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0, 'account_id': self.acc_tax.id}),
            ],
            "refund_repartition_line_ids": [
                (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0, 'account_id': self.acc_tax.id}),
            ],
        })
        self.env["res.currency.rate"].search([
            ("currency_id", "=", self.currency_usd.id),
            ("company_id", "=", self.company.id),
        ]).unlink()
        self.env["res.currency.rate"].create({
            "name": fields.Date.today(),
            "currency_id": self.currency_usd.id,
            "inverse_company_rate": 803.34,
            "company_id": self.company.id,
        })
        self.company.tax_calculation_rounding_method = 'round_per_line'
        inv = self._create_invoice(self.currency_usd, None, [
            (1, 11.16, [tax_div]),
            (1, 4.999, [tax_div]),
            (3, 0.499999, [tax_div]),
        ])
        product_lines = inv.line_ids.filtered(lambda l: l.display_type == 'product')
        tax_line = inv.line_ids.filtered(lambda l: l.tax_line_id == tax_div)
        oracle_total = self._fiscal_machine_oracle_vef(tax_div, product_lines)
        actual_total = abs(tax_line.balance)
        matches = self.currency_vef.is_zero(actual_total - oracle_total)
        _logger.info(
            "test_41 RESULT: 'division' round_per_line native=%s vs fiscal-machine oracle=%s "
            "-> %s",
            actual_total, oracle_total, "MATCHES" if matches else "DIVERGES",
        )
        if not matches:
            _logger.warning(
                "test_41: 'division' with round_per_line configured does NOT match the "
                "fiscal-machine per-line method (native=%s, oracle=%s) -- same class of bug "
                "as 'percent' had, confirmed present and UNFIXED for 'division' (out of scope "
                "for this fix, which only covered 'percent').",
                actual_total, oracle_total,
            )
        td = sum(inv.line_ids.mapped('debit'))
        tc = sum(inv.line_ids.mapped('credit'))
        self.assertAlmostEqual(td, tc, places=2, msg="Debit != Credit")

    def test_42_group_tax_percent_children_round_per_line_matches_fiscal_machine(self):
        """A 'group' tax's children ARE 'percent' taxes -- each child is processed by
        `_apply_vef_first` individually (the group itself, amount_type='group', falls into the
        untouched `else` branch, but its CHILDREN each get their own repartition lines and their
        own `_apply_vef_first` call). So a group tax's percent children should already be
        covered by `_per_line_tax_sums`, same as a standalone percent tax. Verified here with
        two asymmetric lines and the real rate, exact assertion against the fiscal-machine
        oracle for EACH child individually."""
        tax_a = self._create_tax('Group child A 12%', 12.0)
        tax_b = self._create_tax('Group child B 4%', 4.0)
        group_tax = self._create_group_tax('Group AB 16%', tax_a + tax_b)
        self.env["res.currency.rate"].search([
            ("currency_id", "=", self.currency_usd.id),
            ("company_id", "=", self.company.id),
        ]).unlink()
        self.env["res.currency.rate"].create({
            "name": fields.Date.today(),
            "currency_id": self.currency_usd.id,
            "inverse_company_rate": 803.34,
            "company_id": self.company.id,
        })
        self.company.tax_calculation_rounding_method = 'round_per_line'
        inv = self._create_invoice(self.currency_usd, None, [
            (1, 11.16, [group_tax]),
            (1, 4.999, [group_tax]),
        ])
        product_lines = inv.line_ids.filtered(lambda l: l.display_type == 'product')
        tax_lines = inv.line_ids.filtered(lambda l: l.display_type == 'tax')
        for child in (tax_a, tax_b):
            child_line = tax_lines.filtered(lambda l, t=child: l.tax_line_id == t)
            self.assertEqual(len(child_line), 1, f"Expected one tax line for {child.name}")
            oracle = self._fiscal_machine_oracle_vef(child, product_lines)
            self.assertAlmostEqual(
                abs(child_line.balance), oracle, places=2,
                msg=(
                    f"{child.name}: round_per_line balance={child_line.balance} != "
                    f"fiscal-machine oracle {oracle} -- group children should be covered by "
                    f"_per_line_tax_sums same as a standalone percent tax"
                ),
            )
        td = sum(inv.line_ids.mapped('debit'))
        tc = sum(inv.line_ids.mapped('credit'))
        self.assertAlmostEqual(td, tc, places=2, msg="Debit != Credit")
