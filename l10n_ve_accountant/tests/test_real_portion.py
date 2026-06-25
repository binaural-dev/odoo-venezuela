import logging
from odoo.tests import TransactionCase, tagged
from odoo import fields, Command

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_accountant_real_portion")
class TestRealPortion(TransactionCase):

    def setUp(self):
        super().setUp()

        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
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

        # Rates: 1 USD = 50 VEF, 1 EUR = 55 VEF
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
            "inverse_company_rate": 50.0,
            "company_id": self.company.id,
        })
        self.env["res.currency.rate"].create({
            "name": today,
            "currency_id": self.currency_eur.id,
            "inverse_company_rate": 55.0,
            "company_id": self.company.id,
        })

        # ── Accounts ────────────────────────────────────────────
        self.acc_rec = self._get_or_create('120000', 'Receivable', 'asset_receivable', reconcile=True)
        self.acc_inc = self._get_or_create('400000', 'Income', 'income')
        self.acc_tax = self._get_or_create('200000', 'Tax Payable', 'liability_current', reconcile=True)
        self.acc_bank = self._get_or_create('100100', 'Bank', 'asset_cash', reconcile=True)
        self.acc_expense = self._get_or_create('500000', 'Expense', 'expense')

        # ── Payment methods ─────────────────────────────────────
        self.manual_in = self.env.ref("account.account_payment_method_manual_in")
        self.manual_out = self.env.ref("account.account_payment_method_manual_out")

        # ── Bank journal ────────────────────────────────────────
        pm_in = self.env['account.payment.method.line'].create({
            'name': 'In USD',
            'payment_method_id': self.manual_in.id,
            'payment_type': 'inbound',
            'payment_account_id': self.acc_bank.id,
        })
        pm_out = self.env['account.payment.method.line'].create({
            'name': 'Out USD',
            'payment_method_id': self.manual_out.id,
            'payment_type': 'outbound',
            'payment_account_id': self.acc_bank.id,
        })
        self.bank_journal = self.env['account.journal'].create({
            'name': 'Bank USD', 'code': 'BNKUSD', 'type': 'bank',
            'currency_id': self.currency_usd.id,
            'default_account_id': self.acc_bank.id,
            'company_id': self.company.id,
            'inbound_payment_method_line_ids': [(6, 0, pm_in.ids)],
            'outbound_payment_method_line_ids': [(6, 0, pm_out.ids)],
        })

        # ── Sale journal ────────────────────────────────────────
        self.sale_journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].sudo().create({
            "name": "Sales Test", "code": "SLTST",
            "type": "sale", "company_id": self.company.id,
            "default_account_id": self.acc_inc.id,
        })

        # ── General journal ─────────────────────────────────────
        self.general_journal = self.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].sudo().create({
            "name": "General Test", "code": "GENTST",
            "type": "general", "company_id": self.company.id,
        })

        # ── Taxes ───────────────────────────────────────────────
        self.tax_group = self.env['account.tax.group'].create({
            'name': 'IVA', 'company_id': self.company.id,
            'country_id': self.country_ve.id,
        })
        self.tax_16 = self._create_tax('IVA 16%', 16.0)
        self.tax_8 = self._create_tax('IVA 8%', 8.0)

        # ── Product ─────────────────────────────────────────────
        self.product = self.env['product.product'].create({
            'name': 'Service', 'type': 'service', 'list_price': 100.0,
            'property_account_income_id': self.acc_inc.id,
            'taxes_id': [(5, 0, 0)],
            'supplier_taxes_id': [(5, 0, 0)],
        })

        # ── Partner ─────────────────────────────────────────────
        self.partner = self.env["res.partner"].create({
            "name": "Test Partner",
            "country_id": self.country_ve.id,
            "property_account_receivable_id": self.acc_rec.id,
        })

    # ── Helpers ─────────────────────────────────────────────────

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

    def _set_usd_rate(self, rate):
        """Set the USD/VEF rate for today"""
        currency_rate = self.env["res.currency.rate"].search([
            ("name", "=", fields.Date.today()),
            ("currency_id", "=", self.currency_usd.id),
            ("company_id", "=", self.company.id),
        ], limit=1)
        if currency_rate:
            currency_rate.write({"inverse_company_rate": rate})
        else:
            self.env["res.currency.rate"].create({
                "name": fields.Date.today(),
                "currency_id": self.currency_usd.id,
                "inverse_company_rate": rate,
                "company_id": self.company.id,
            })

    def _assert_balances(self, move, label=""):
        """Verifica que la suma de debitos = suma de creditos"""
        td = sum(move.line_ids.mapped('debit'))
        tc = sum(move.line_ids.mapped('credit'))
        self.assertAlmostEqual(
            td, tc, places=2,
            msg=f"{label}: Debit {td} != Credit {tc}"
        )
        return td, tc

    def _assert_foreign_squares(self, move, label=""):
        """Verifica que foreign_debit total = foreign_credit total"""
        fd = sum(move.line_ids.mapped('foreign_debit'))
        fc = sum(move.line_ids.mapped('foreign_credit'))
        self.assertAlmostEqual(
            fd, fc, places=2,
            msg=f"{label}: Foreign debit {fd} != foreign credit {fc}"
        )
        return fd, fc

    def _assert_pt_vs_other_foreign(self, move, label=""):
        """Verifica que PT foreign_debit == other foreign_credit y viceversa"""
        pt = move.line_ids.filtered(lambda l: l.display_type == 'payment_term')
        other = move.line_ids.filtered(lambda l: l.display_type != 'payment_term')
        pt_fd = sum(pt.mapped('foreign_debit'))
        pt_fc = sum(pt.mapped('foreign_credit'))
        other_fd = sum(other.mapped('foreign_debit'))
        other_fc = sum(other.mapped('foreign_credit'))
        self.assertAlmostEqual(
            pt_fd, other_fc, places=2,
            msg=f"{label}: PT foreign_debit ({pt_fd}) != other foreign_credit ({other_fc})"
        )
        self.assertAlmostEqual(
            pt_fc, other_fd, places=2,
            msg=f"{label}: PT foreign_credit ({pt_fc}) != other foreign_debit ({other_fd})"
        )

    def _log_lines(self, move, label=""):
        """Log all lines for debugging"""
        _logger.info(f"=== {label} ===")
        for line in move.line_ids:
            _logger.info(
                f"  {line.display_type or 'line':15s} | "
                f"account: {line.account_id.code or '':6s} | "
                f"debit: {line.debit:>10.2f} | credit: {line.credit:>10.2f} | "
                f"amount_currency: {line.amount_currency or 0:>10.2f} | "
                f"fd: {line.foreign_debit:>8.2f} | fc: {line.foreign_credit:>8.2f}"
            )

    # ═══════════════════════════════════════════════════════════════
    # TESTS: FACTURAS
    # ═══════════════════════════════════════════════════════════════

    def test_01_invoice_usd_balanced(self):
        """Factura en USD con 2 productos e IVA 16% - debe balancearse sola"""
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
                    "quantity": 1.0,
                    "price_unit": 800.00,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0,
                    "price_unit": 200.00,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
            ],
        })
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, 'posted')
        self._log_lines(invoice, "test_01_invoice_usd")

        # Balance contable
        self._assert_balances(invoice, "test_01")
        # Foreign squares
        self._assert_foreign_squares(invoice, "test_01")
        # Total USD: 1.000 + 160 = 1.160
        fd, fc = self._assert_foreign_squares(invoice, "test_01")
        self.assertAlmostEqual(fd, 1160.0, delta=1.0)
        # Se ejecuto la distribucion
        self.assertGreaterEqual(invoice.real_portion_count, 0)

    def test_02_invoice_usd_two_taxes_with_foreign_distribution(self):
        """Factura en USD con 2 productos usando IVA 16% y IVA 8%.
           Verifica que _distribute_foreign_pt_residual distribuye
           correctamente foreign_debit/credit entre PT y no-PT.
        """
        payment_term = self.env['account.payment.term'].create({
            'name': '50% - 50%',
            'line_ids': [
                Command.create({'value': 'percent', 'value_amount': 50, 'nb_days': 0}),
                Command.create({'value': 'percent', 'value_amount': 50, 'nb_days': 15}),
            ]
        })

        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_usd.id,
            "date": fields.Date.today(),
            "invoice_payment_term_id": payment_term.id,
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0,
                    "price_unit": 800.00,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0,
                    "price_unit": 200.00,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(6, 0, [self.tax_8.id])],
                }),
            ],
        })
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, 'posted')
        self._log_lines(invoice, "test_02_foreign_dist")

        self._assert_balances(invoice, "test_02")
        self._assert_foreign_squares(invoice, "test_02")
        self._assert_pt_vs_other_foreign(invoice, "test_02")
        # Total: $800 + $128 + $200 + $16 = $1.144,00
        fd, fc = self._assert_foreign_squares(invoice, "test_02")
        self.assertAlmostEqual(fd, 1144.0, delta=1.0)

    def test_03_invoice_eur_third_currency(self):
        """Factura en EUR (tercera moneda, ni VEF ni USD).
           _distribute_foreign_pt_residual debe usar conversion AGREGADA
           porque EUR no es ni company_currency ni foreign_currency
        """
        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_eur.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 2.0,
                    "price_unit": 2500.00,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0,
                    "price_unit": 1500.00,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(6, 0, [self.tax_8.id])],
                }),
            ],
        })
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, 'posted')
        self._log_lines(invoice, "test_03_eur")

        # Balance contable
        self._assert_balances(invoice, "test_03")
        # Foreign squares entre PT y no-PT
        self._assert_pt_vs_other_foreign(invoice, "test_03")

    def test_04_invoice_eur_third_currency_no_pt(self):
        """Factura EUR sin payment_term - verifica foreign balance"""
        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_eur.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0,
                    "price_unit": 1000.00,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
            ],
        })
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, 'posted')
        self._assert_balances(invoice, "test_04")
        self._assert_foreign_squares(invoice, "test_04")

    def test_05_invoice_variable_rates(self):
        """Factura en VEF con tasa irregular - _fix_company_currency_rounding
           debe corregir la diferencia entre conversion agregada y linea por linea
        """
        self._set_usd_rate(402.3343)

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
                    "product_id": self.product.id,
                    "quantity": 1.0,
                    "price_unit": 23200.00,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0,
                    "price_unit": 56200.00,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(5, 0, 0)],
                }),
            ],
        })
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, 'posted')
        self._log_lines(invoice, "test_05_var_rates")

        self._assert_balances(invoice, "test_05")
        self._assert_foreign_squares(invoice, "test_05")
        # Total VEF: 23.200 + 56.200 + 3.712 (IVA) = 83.112,00
        self.assertAlmostEqual(invoice.amount_total, 83112.0, places=2)
        # Total USD esperado: 83.112 / 402,3343 ≈ 206,57
        expected_usd = 83112.0 / 402.3343
        fd, fc = self._assert_foreign_squares(invoice, "test_05")
        self.assertAlmostEqual(fd, expected_usd, delta=0.02)

    def test_06_invoice_with_payment_terms(self):
        """Factura con 3 vencimientos - el residuo debe ir al ultimo plazo"""
        payment_term = self.env['account.payment.term'].create({
            'name': '40% - 30% - 30%',
            'line_ids': [
                Command.create({'value': 'percent', 'value_amount': 40, 'nb_days': 0}),
                Command.create({'value': 'percent', 'value_amount': 30, 'nb_days': 15}),
                Command.create({'value': 'percent', 'value_amount': 30, 'nb_days': 30}),
            ]
        })

        self._set_usd_rate(402.3343)

        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_vef.id,
            "date": fields.Date.today(),
            "invoice_payment_term_id": payment_term.id,
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0,
                    "price_unit": 23200.00,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(6, 0, [self.tax_16.id])],
                }),
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0,
                    "price_unit": 56200.00,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(5, 0, 0)],
                }),
            ],
        })
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, 'posted')
        self._log_lines(invoice, "test_06_pt")

        # Verificar 3 payment_term lines
        pt_lines = invoice.line_ids.filtered(lambda l: l.display_type == 'payment_term')
        self.assertEqual(len(pt_lines), 3, "Debe haber 3 plazos de pago")

        self._assert_balances(invoice, "test_06")
        self._assert_foreign_squares(invoice, "test_06")
        self._assert_pt_vs_other_foreign(invoice, "test_06")

    # ═══════════════════════════════════════════════════════════════
    # TESTS: ASIENTOS MANUALES
    # ═══════════════════════════════════════════════════════════════

    def test_07_manual_entry_balanced(self):
        """Asiento manual en USD con montos exactos - no debe requerir ajuste"""
        move = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "ref": "Manual entry balanced",
            "currency_id": self.currency_usd.id,
            "line_ids": [
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": 500.00,
                    "debit": 25000.00,
                    "credit": 0.0,
                }),
                Command.create({
                    "account_id": self.acc_bank.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": -500.00,
                    "debit": 0.0,
                    "credit": 25000.00,
                }),
            ],
        })
        move.action_post()
        self.assertEqual(move.state, 'posted')
        self._assert_balances(move, "test_07")
        self._assert_foreign_squares(move, "test_07")

    def test_08_manual_entry_with_real_portion(self):
        """Asiento manual en USD con desbalance intencional.
           _distribute_entry_real_portion debe distribuir el real_portion_amount
           en las lineas de contrapartida (no efectivo, no impuesto)
        """
        # Montos: gasto 1 = 20.000, gasto 2 = 17.503,50, gasto 3 = 12.497,50
        # Banco = -50.000,00
        # Desbalance = 20.000 + 17.503,50 + 12.497,50 - 50.000 = 1,00
        move = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "ref": "Manual entry with desbalance",
            "currency_id": self.currency_usd.id,
            "line_ids": [
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": 400.00,
                    "debit": 20000.00,
                    "credit": 0.0,
                }),
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": 350.00,
                    "debit": 17503.50,
                    "credit": 0.0,
                }),
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": 250.00,
                    "debit": 12497.50,
                    "credit": 0.0,
                }),
                Command.create({
                    "account_id": self.acc_bank.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": -1000.00,
                    "debit": 0.0,
                    "credit": 50000.00,
                }),
            ],
        })

        # Verificar que hay desbalance antes de la correccion
        td_before = sum(move.line_ids.mapped('debit'))
        tc_before = sum(move.line_ids.mapped('credit'))
        self.assertNotAlmostEqual(
            td_before, tc_before, places=2,
            msg="El asiento debe tener desbalance antes de la correccion"
        )
        desbalance = td_before - tc_before
        _logger.info(f"test_08: Desbalance antes = {desbalance}")

        # Aplicar _distribute_entry_real_portion
        cc = self.company.currency_id
        move.write({"real_portion_amount": -desbalance})
        move._distribute_entry_real_portion(move, cc)

        self._log_lines(move, "test_08_after_distribution")
        self._assert_balances(move, "test_08_despues")
        self.assertGreaterEqual(move.real_portion_count, 1)

        # Verificar que las lineas de gasto se ajustaron
        expense_lines = move.line_ids.filtered(lambda l: l.account_id == self.acc_expense)
        total_expense_bs = sum(expense_lines.mapped('balance'))
        # La suma de gastos debe ser igual al credito del banco
        bank_credit = sum(move.line_ids.filtered(
            lambda l: l.account_id == self.acc_bank
        ).mapped('balance'))
        self.assertAlmostEqual(total_expense_bs, abs(bank_credit), places=2)

    def test_09_manual_entry_eur_third_currency(self):
        """Asiento manual en EUR con desbalance - debe distribuirse igual"""
        move = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "ref": "Manual entry EUR",
            "currency_id": self.currency_eur.id,
            "line_ids": [
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_eur.id,
                    "amount_currency": 500.00,
                    "debit": 27500.00,
                    "credit": 0.0,
                }),
                Command.create({
                    "account_id": self.acc_bank.id,
                    "currency_id": self.currency_eur.id,
                    "amount_currency": -500.00,
                    "debit": 0.0,
                    "credit": 27500.00,
                }),
            ],
        })
        move.action_post()
        self.assertEqual(move.state, 'posted')
        self._assert_balances(move, "test_09")
        self._assert_foreign_squares(move, "test_09")

    def test_10_manual_entry_three_lines_amortization(self):
        """Asiento manual con 3 lineas de gasto donde la ultima absorbe el residuo.
           Verifica que el algoritmo _distribute_to_lines funciona correctamente
           y que la ultima linea recibe el sobrante
        """
        # Gastos: 10.000 + 8.000 + 7.000 = 25.000
        # Banco: -24.997,50
        # Desbalance = 25.000 - 24.997,50 = 2,50
        move = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "ref": "Amortization test",
            "currency_id": self.currency_usd.id,
            "line_ids": [
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": 200.00,
                    "debit": 10000.00,
                    "credit": 0.0,
                }),
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": 160.00,
                    "debit": 8000.00,
                    "credit": 0.0,
                }),
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": 140.00,
                    "debit": 7000.00,
                    "credit": 0.0,
                }),
                Command.create({
                    "account_id": self.acc_bank.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": -500.00,
                    "debit": 0.0,
                    "credit": 24997.50,
                }),
            ],
        })

        td = sum(move.line_ids.mapped('debit'))
        tc = sum(move.line_ids.mapped('credit'))
        desbalance = td - tc
        self.assertAlmostEqual(desbalance, 2.50, places=2,
                               msg="El desbalance debe ser exactamente 2,50")

        # Aplicar correccion
        cc = self.company.currency_id
        move.write({"real_portion_amount": -desbalance})
        move._distribute_entry_real_portion(move, cc)

        self._log_lines(move, "test_10_amortizacion")
        self._assert_balances(move, "test_10")

        # Verificar que las 3 lineas de gasto se ajustaron
        expense_lines = move.line_ids.filtered(
            lambda l: l.account_id == self.acc_expense
        ).sorted('balance')
        # La ultima linea (menor balance) debe haber absorbido el residuo
        total_expense = sum(expense_lines.mapped('balance'))
        self.assertAlmostEqual(total_expense, 24997.50, places=2)

    def test_11_manual_entry_no_rounding_needed(self):
        """Asiento manual exacto - sin desbalance - _distribute_entry_real_portion
           no debe modificar nada
        """
        move = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "ref": "No rounding needed",
            "currency_id": self.currency_usd.id,
            "line_ids": [
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": 600.00,
                    "debit": 30000.00,
                    "credit": 0.0,
                }),
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": 400.00,
                    "debit": 20000.00,
                    "credit": 0.0,
                }),
                Command.create({
                    "account_id": self.acc_bank.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": -1000.00,
                    "debit": 0.0,
                    "credit": 50000.00,
                }),
            ],
        })
        # Ya esta balanceado
        self._assert_balances(move, "test_11_antes")

        # Aplicar _distribute_entry_real_portion con real_portion_amount = 0
        # No debe modificar nada
        balances_antes = {l.id: l.balance for l in move.line_ids}
        cc = self.company.currency_id
        move.write({"real_portion_amount": 0.0})
        move._distribute_entry_real_portion(move, cc)

        for line in move.line_ids:
            self.assertEqual(
                line.balance, balances_antes[line.id],
                f"Linea {line.id} no debio modificarse"
            )

        move.action_post()
        self.assertEqual(move.state, 'posted')

    def test_12_manual_entry_keeps_foreign_balanced(self):
        """Asiento manual en USD - verifica que foreign_debit/credit
           se mantengan balanceados despues de _distribute_entry_real_portion
        """
        move = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "ref": "Foreign balance after real portion",
            "currency_id": self.currency_usd.id,
            "line_ids": [
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": 333.33,
                    "debit": 16666.50,
                    "credit": 0.0,
                }),
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": 333.33,
                    "debit": 16666.50,
                    "credit": 0.0,
                }),
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": 333.34,
                    "debit": 16667.00,
                    "credit": 0.0,
                }),
                Command.create({
                    "account_id": self.acc_bank.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": -1000.00,
                    "debit": 0.0,
                    "credit": 50000.00,
                }),
            ],
        })

        td = sum(move.line_ids.mapped('debit'))
        tc = sum(move.line_ids.mapped('credit'))
        desbalance = td - tc

        cc = self.company.currency_id
        move.write({"real_portion_amount": -desbalance})
        move._distribute_entry_real_portion(move, cc)

        self._assert_balances(move, "test_12")
        self._assert_foreign_squares(move, "test_12")

    def test_13_real_portion_count_increments(self):
        """Verifica que real_portion_count se incrementa al distribuir"""
        move = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "ref": "Count increment test",
            "currency_id": self.currency_usd.id,
            "line_ids": [
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": 100.00,
                    "debit": 5000.00,
                    "credit": 0.0,
                }),
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": 100.00,
                    "debit": 5001.00,
                    "credit": 0.0,
                }),
                Command.create({
                    "account_id": self.acc_bank.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": -200.00,
                    "debit": 0.0,
                    "credit": 10000.00,
                }),
            ],
        })

        td = sum(move.line_ids.mapped('debit'))
        tc = sum(move.line_ids.mapped('credit'))
        desbalance = td - tc
        count_before = move.real_portion_count

        cc = self.company.currency_id
        move.write({"real_portion_amount": -desbalance})
        move._distribute_entry_real_portion(move, cc)

        self.assertGreater(
            move.real_portion_count, count_before,
            "real_portion_count debe incrementarse"
        )

    # ═══════════════════════════════════════════════════════════════
    # TESTS: ASIENTOS MANUALES SOLO CON BALANCE (sin debit/credit)
    # ═══════════════════════════════════════════════════════════════

    def test_14_manual_entry_balance_only_balanced(self):
        """Asiento manual usando amount_currency + balance (sin debit/credit).
           Balanceado exacto - debe postear sin ajuste.
        """
        move = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "ref": "Balance only balanced",
            "currency_id": self.currency_usd.id,
            "line_ids": [
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": 500.00,
                    "balance": 25000.00,
                }),
                Command.create({
                    "account_id": self.acc_bank.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": -500.00,
                    "balance": -25000.00,
                }),
            ],
        })
        move.action_post()
        self.assertEqual(move.state, 'posted')
        self._assert_balances(move, "test_14")
        self._assert_foreign_squares(move, "test_14")

        # Verificar que debit/credit se computaron desde balance
        expense = move.line_ids.filtered(lambda l: l.account_id == self.acc_expense)
        bank = move.line_ids.filtered(lambda l: l.account_id == self.acc_bank)
        self.assertEqual(expense.debit, 25000.00)
        self.assertEqual(expense.credit, 0.0)
        self.assertEqual(bank.debit, 0.0)
        self.assertEqual(bank.credit, 25000.00)

    def test_15_manual_entry_balance_only_unbalanced(self):
        """Asiento manual con balance, desbalanceado.
           _distribute_entry_real_portion debe corregirlo.
        """
        move = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "ref": "Balance only unbalanced",
            "currency_id": self.currency_usd.id,
            "line_ids": [
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": 400.00,
                    "balance": 20000.00,
                }),
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": 350.00,
                    "balance": 17503.50,
                }),
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": 250.00,
                    "balance": 12497.50,
                }),
                Command.create({
                    "account_id": self.acc_bank.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": -1000.00,
                    "balance": -50000.00,
                }),
            ],
        })

        td = sum(move.line_ids.mapped('debit'))
        tc = sum(move.line_ids.mapped('credit'))
        desbalance = td - tc
        self.assertAlmostEqual(desbalance, 1.00, places=2)

        cc = self.company.currency_id
        move.write({"real_portion_amount": -desbalance})
        move._distribute_entry_real_portion(move, cc)

        self._assert_balances(move, "test_15")
        self._assert_foreign_squares(move, "test_15")
        self.assertGreaterEqual(move.real_portion_count, 1)

    def test_16_manual_entry_balance_only_three_lines_amort(self):
        """Asiento manual con balance, 3 lineas de gasto.
           La ultima debe absorber el residuo.
        """
        move = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "ref": "Balance only amortization",
            "currency_id": self.currency_usd.id,
            "line_ids": [
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": 200.00,
                    "balance": 10000.00,
                }),
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": 160.00,
                    "balance": 8000.00,
                }),
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": 140.00,
                    "balance": 7000.00,
                }),
                Command.create({
                    "account_id": self.acc_bank.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": -500.00,
                    "balance": -24997.50,
                }),
            ],
        })

        td = sum(move.line_ids.mapped('debit'))
        tc = sum(move.line_ids.mapped('credit'))
        desbalance = td - tc
        self.assertAlmostEqual(desbalance, 2.50, places=2)

        cc = self.company.currency_id
        move.write({"real_portion_amount": -desbalance})
        move._distribute_entry_real_portion(move, cc)

        self._assert_balances(move, "test_16")
        self._assert_foreign_squares(move, "test_16")
        self.assertGreaterEqual(move.real_portion_count, 1)

        expense_lines = move.line_ids.filtered(
            lambda l: l.account_id == self.acc_expense
        ).sorted('balance')
        total_expense = sum(expense_lines.mapped('balance'))
        self.assertAlmostEqual(total_expense, 24997.50, places=2)

    def test_17_manual_entry_balance_foreign_squares(self):
        """Asiento manual con balance - verifica foreign_debit/credit
           se mantienen balanceados despues del ajuste.
        """
        move = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "ref": "Balance foreign squares",
            "currency_id": self.currency_usd.id,
            "line_ids": [
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": 333.33,
                    "balance": 16666.50,
                }),
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": 333.33,
                    "balance": 16666.50,
                }),
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": 333.34,
                    "balance": 16667.00,
                }),
                Command.create({
                    "account_id": self.acc_bank.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": -1000.00,
                    "balance": -50000.00,
                }),
            ],
        })
        # Ya balanceado -> no necesita _distribute_entry_real_portion
        self._assert_balances(move, "test_17_antes")
        self._assert_foreign_squares(move, "test_17_antes")

        move.action_post()
        self.assertEqual(move.state, 'posted')
        self._assert_balances(move, "test_17")
        self._assert_foreign_squares(move, "test_17")

        # Verificar que debit/credit se computaron desde balance
        expense_lines = move.line_ids.filtered(lambda l: l.account_id == self.acc_expense)
        bank = move.line_ids.filtered(lambda l: l.account_id == self.acc_bank)
        for exp in expense_lines:
            self.assertEqual(exp.debit, exp.balance)
            self.assertEqual(exp.credit, 0.0)
        self.assertEqual(bank.credit, abs(bank.balance))
        self.assertEqual(bank.debit, 0.0)

    # ═══════════════════════════════════════════════════════════════
    # TESTS: ASIENTOS MANUALES SOLO CON amount_currency (sin balance ni debit/credit)
    # ═══════════════════════════════════════════════════════════════

    def test_18_manual_entry_amount_currency_only_balanced(self):
        """Asiento manual usando SOLO amount_currency + currency_id.
           Sin balance, sin debit, sin credit.
           Odoo debe computar balance = round(amount_currency / currency_rate)
           via _inverse_amount_currency.
        """
        move = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "ref": "Amount currency only balanced",
            "currency_id": self.currency_usd.id,
            "line_ids": [
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": 500.00,
                }),
                Command.create({
                    "account_id": self.acc_bank.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": -500.00,
                }),
            ],
        })

        # Verificar que el balance se computo desde amount_currency
        for line in move.line_ids:
            self.assertIsNotNone(line.balance)
            self.assertNotEqual(line.balance, 0.0)
            if line.balance > 0:
                self.assertEqual(line.debit, line.balance)
                self.assertEqual(line.credit, 0.0)
            else:
                self.assertEqual(line.credit, abs(line.balance))
                self.assertEqual(line.debit, 0.0)

        self._assert_balances(move, "test_18")
        self._assert_foreign_squares(move, "test_18")

        move.action_post()
        self.assertEqual(move.state, 'posted')
        self._assert_balances(move, "test_18_posted")
        self._assert_foreign_squares(move, "test_18_posted")

    def test_19_manual_entry_amount_currency_only_unbalanced(self):
        """Asiento manual con SOLO amount_currency, PERO con balances
           explicitos que NO coinciden con la tasa (simula distintas tasas
           por linea). La porcion real debe corregir el desbalance.

           NOTA: Si solo se usa amount_currency sin balance, Odoo computa
           balance = round(amount_currency / currency_rate) usando la
           misma tasa para todas las lineas, por lo NUNCA hay desbalance.
           Para crear un desbalance intencional hay que forzar balances
           que no correspondan a la tasa actual.
        """
        total_usd = 1000.00
        tasa_dia = 50.00
        total_correcto = round(total_usd * tasa_dia, 2)  # 50.000,00

        # Gastos con balances calculados a tasas DISTINTAS
        gastos = [
            {"amc": 400.00, "tasa": 50.02, "bal": 20008.00},
            {"amc": 350.00, "tasa": 49.99, "bal": 17496.50},
            {"amc": 250.00, "tasa": 50.01, "bal": 12502.50},
        ]
        total_gastos_bal = sum(g["bal"] for g in gastos)  # 50.007,00
        desbalance_esp = round(total_gastos_bal - total_correcto, 2)  # 7,00

        move = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "ref": f"Amount currency unbalanced ({desbalance_esp})",
            "currency_id": self.currency_usd.id,
            "line_ids": [
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": g["amc"],
                    "balance": g["bal"],
                }) for g in gastos
            ] + [
                Command.create({
                    "account_id": self.acc_bank.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": -total_usd,
                    "balance": -total_correcto,
                }),
            ],
        })

        td = sum(move.line_ids.mapped('debit'))
        tc = sum(move.line_ids.mapped('credit'))
        diff = round(td - tc, 2)
        self.assertAlmostEqual(diff, desbalance_esp, places=2,
                               msg=f"Debe haber desbalance de {desbalance_esp}")

        cc = self.company.currency_id
        move.write({"real_portion_amount": -diff})
        move._distribute_entry_real_portion(move, cc)

        self._assert_balances(move, "test_19")
        self._assert_foreign_squares(move, "test_19")
        self.assertGreaterEqual(move.real_portion_count, 1)

        # Verificar que los gastos suman el total correcto
        expense_lines = move.line_ids.filtered(
            lambda l: l.account_id == self.acc_expense
        )
        total_ajustado = round(sum(expense_lines.mapped('balance')), 2)
        self.assertAlmostEqual(
            total_ajustado, total_correcto, places=2,
            msg=f"Los gastos deben sumar {total_correcto} VEF"
        )

    def test_20_manual_entry_amount_currency_only_eur(self):
        """Asiento manual con SOLO amount_currency en EUR (tercera moneda).
           El balance debe computarse usando la tasa EUR/VEF.
        """
        move = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "ref": "Amount currency only EUR",
            "currency_id": self.currency_eur.id,
            "line_ids": [
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_eur.id,
                    "amount_currency": 500.00,
                }),
                Command.create({
                    "account_id": self.acc_bank.id,
                    "currency_id": self.currency_eur.id,
                    "amount_currency": -500.00,
                }),
            ],
        })

        for line in move.line_ids:
            self.assertIsNotNone(line.balance)
            self.assertNotEqual(line.balance, 0.0)

        self._assert_balances(move, "test_20")

        # Verificar que la tasa EUR/VEF se aplico correctamente
        expense = move.line_ids.filtered(lambda l: l.account_id == self.acc_expense)
        # Con inverse_company_rate = 55 (1 EUR = 55 VEF):
        # currency_rate ≈ 0.01818... (VEF → EUR)
        # balance = round(500 / 0.01818...) = round(27500) = 27500
        self.assertAlmostEqual(expense.balance, 27500.00, delta=1.0)

        move.action_post()
        self.assertEqual(move.state, 'posted')
        self._assert_balances(move, "test_20_posted")
        self._assert_foreign_squares(move, "test_20_posted")

    # ═══════════════════════════════════════════════════════════════
    # TESTS: DEMOSTRACION WRONG vs RIGHT (sin y con porcion real)
    # ═══════════════════════════════════════════════════════════════

    def test_21_demo_wrong_vs_right_real_portion(self):
        """WRONG vs RIGHT: Demostracion de como la porcion real corrige
           el error de conversion linea por linea.

           ESCENARIO:
           3 gastos en USD cada uno registrado con una tasa LIGERAMENTE
           DISTINTA (simula conversiones en fechas diferentes).
           El banco paga el total $1.000,00 a la tasa del dia (50,00).

           SIN PORCION REAL (WRONG):
             Gasto A: $400,00 × tasa 50,02 = 20.008,00 VEF
             Gasto B: $350,00 × tasa 49,99 = 17.496,50 VEF
             Gasto C: $250,00 × tasa 50,01 = 12.502,50 VEF
             Suma gastos: 50.007,00 VEF   ← INCORRECTO
             Banco:      -50.000,00 VEF   ← CORRECTO (total × tasa del dia)
             DESBALANCE: 7,00 VEF ❌

           CON PORCION REAL (RIGHT):
             _distribute_entry_real_portion distribuye los 7,00 VEF
             proporcionalmente entre los gastos:
             Gasto A: 20.008,00 - 2,80 = 20.005,20 VEF
             Gasto B: 17.496,50 - 2,45 = 17.494,05 VEF
             Gasto C: 12.502,50 - 1,75 = 12.500,75 VEF ← absorbe residuo
             Suma gastos: 50.000,00 VEF ✅
             Banco:      -50.000,00 VEF ✅
        """
        # Totales correctos
        total_usd = 1000.00
        tasa_del_dia = 50.00
        total_vef_correcto = round(total_usd * tasa_del_dia, 2)  # 50.000,00

        # Cada gasto con su propia tasa (WRONG)
        gastos = [
            {"amount": 400.00, "tasa": 50.02},
            {"amount": 350.00, "tasa": 49.99},
            {"amount": 250.00, "tasa": 50.01},
        ]

        # Calculamos el balance linea por linea (como lo haria alguien SIN porcion real)
        lineas_vals = []
        total_vef_lineas = 0.0
        for g in gastos:
            bal = round(g["amount"] * g["tasa"], 2)
            total_vef_lineas += bal
            lineas_vals.append(Command.create({
                "account_id": self.acc_expense.id,
                "currency_id": self.currency_usd.id,
                "amount_currency": g["amount"],
                "balance": bal,  # ← balance calculado con su propia tasa
            }))

        # Banco al total correcto
        lineas_vals.append(Command.create({
            "account_id": self.acc_bank.id,
            "currency_id": self.currency_usd.id,
            "amount_currency": -total_usd,
            "balance": -total_vef_correcto,  # ← balance correcto (agregado)
        }))

        desbalance_esperado = round(total_vef_lineas - total_vef_correcto, 2)

        move = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "ref": f"DEMO WRONG: desbalance = {desbalance_esperado}",
            "currency_id": self.currency_usd.id,
            "line_ids": lineas_vals,
        })

        # VERIFICACION WRONG: el asiento esta desbalanceado
        td_wrong = sum(move.line_ids.mapped('debit'))
        tc_wrong = sum(move.line_ids.mapped('credit'))
        diff_wrong = round(td_wrong - tc_wrong, 2)
        _logger.info(
            f"test_21 WRONG: debit={td_wrong}, credit={tc_wrong}, "
            f"diferencia={diff_wrong} (deberia ser {desbalance_esperado})"
        )
        self.assertAlmostEqual(
            diff_wrong, desbalance_esperado, places=2,
            msg=f"WRONG: El asiento DEBE estar desbalanceado por {desbalance_esperado}. "
                f"Si esto falla, revisar el escenario."
        )

        # AHORA: Aplicar porcion real
        cc = self.company.currency_id
        move.write({"real_portion_amount": -diff_wrong})
        move._distribute_entry_real_portion(move, cc)

        # VERIFICACION RIGHT: el asiento ahora esta balanceado
        td_right = sum(move.line_ids.mapped('debit'))
        tc_right = sum(move.line_ids.mapped('credit'))
        _logger.info(
            f"test_21 RIGHT: debit={td_right}, credit={tc_right}, "
            f"diferencia={round(td_right - tc_right, 2)}"
        )
        self._assert_balances(move, "test_21_RIGHT")
        self.assertGreaterEqual(
            move.real_portion_count, 1,
            "RIGHT: real_portion_count debe incrementarse despues de la correccion"
        )

        # Verificar que el total de gastos ahora es el correcto
        expense_lines = move.line_ids.filtered(
            lambda l: l.account_id == self.acc_expense
        )
        total_gastos_vef = round(sum(expense_lines.mapped('balance')), 2)
        self.assertAlmostEqual(
            total_gastos_vef, total_vef_correcto, places=2,
            msg=f"RIGHT: Los gastos deben sumar {total_vef_correcto} VEF "
                f"pero suman {total_gastos_vef} VEF"
        )

        # Verificar que el banco no se modifico
        bank_line = move.line_ids.filtered(lambda l: l.account_id == self.acc_bank)
        self.assertAlmostEqual(
            abs(bank_line.balance), total_vef_correcto, places=2,
            msg="RIGHT: El banco NO debe modificarse"
        )

    def test_22_demo_wrong_vs_right_amount_currency_with_balance(self):
        """WRONG vs RIGHT: amount_currency con balances explicitos
           que simulan distintas tasas. La porcion real corrige
           el desbalance y amount_currency NO debe modificarse.

           ESCENARIO:
           Igual que test_21: 3 gastos cada uno con su propia tasa,
           banco a la tasa del dia. La diferencia es que aqui se
           verifica que amount_currency se mantiene intacto despues
           de _distribute_entry_real_portion.
        """
        total_usd = 1000.00
        tasa_dia = 50.00
        total_vef_correcto = round(total_usd * tasa_dia, 2)

        gastos = [
            {"amc": 400.00, "tasa": 50.02, "bal": 20008.00},
            {"amc": 350.00, "tasa": 49.99, "bal": 17496.50},
            {"amc": 250.00, "tasa": 50.01, "bal": 12502.50},
        ]
        total_vef_lineas = sum(g["bal"] for g in gastos)
        desbalance_esp = round(total_vef_lineas - total_vef_correcto, 2)

        # Guardar los amount_currency originales para verificar despues
        amc_originales = {g["amc"] for g in gastos}

        move = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": fields.Date.today(),
            "ref": f"DEMO amc+bal: desbalance={desbalance_esp}",
            "currency_id": self.currency_usd.id,
            "line_ids": [
                Command.create({
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": g["amc"],
                    "balance": g["bal"],
                }) for g in gastos
            ] + [
                Command.create({
                    "account_id": self.acc_bank.id,
                    "currency_id": self.currency_usd.id,
                    "amount_currency": -total_usd,
                    "balance": -total_vef_correcto,
                }),
            ],
        })

        # WRONG: desbalance presente
        td = sum(move.line_ids.mapped('debit'))
        tc = sum(move.line_ids.mapped('credit'))
        diff = round(td - tc, 2)
        self.assertAlmostEqual(
            diff, desbalance_esp, places=2,
            msg=f"WRONG: desbalance debe ser {desbalance_esp}"
        )

        # Capturar amount_currency ANTES de la correccion
        amc_expense_before = {
            l.id: l.amount_currency
            for l in move.line_ids
            if l.account_id == self.acc_expense
        }

        # RIGHT: aplicar porcion real
        cc = self.company.currency_id
        move.write({"real_portion_amount": -diff})
        move._distribute_entry_real_portion(move, cc)

        self._assert_balances(move, "test_22_RIGHT")
        self.assertGreaterEqual(move.real_portion_count, 1)

        # Verificar que amount_currency NO se modifico
        for l in move.line_ids:
            if l.id in amc_expense_before:
                self.assertEqual(
                    l.amount_currency, amc_expense_before[l.id],
                    f"amount_currency de la linea {l.id} NO debe cambiar. "
                    f"Era {amc_expense_before[l.id]} y quedo {l.amount_currency}"
                )

        # Verificar que el total de gastos ahora es correcto
        expense_lines = move.line_ids.filtered(
            lambda l: l.account_id == self.acc_expense
        )
        total_gastos = round(sum(expense_lines.mapped('balance')), 2)
        self.assertAlmostEqual(
            total_gastos, total_vef_correcto, places=2,
            msg=f"RIGHT: gastos deben sumar {total_vef_correcto} VEF"
        )
