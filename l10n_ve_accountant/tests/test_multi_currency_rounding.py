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
