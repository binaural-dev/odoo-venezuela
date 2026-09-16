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
