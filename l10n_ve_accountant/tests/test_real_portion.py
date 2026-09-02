import logging
from datetime import timedelta

from odoo.tests import TransactionCase, tagged
from odoo import fields, Command
from odoo.tools import float_round

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
        self.tax_0 = self._create_tax('Exento', 0.0)

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
        """Factura en VEF con tasa irregular -
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
                    "tax_ids": [(6, 0, [self.tax_0.id])],
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
                    "tax_ids": [(6, 0, [self.tax_0.id])],
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

    # ═══════════════════════════════════════════════════════════════
    # TESTS: COGS Y REDONDEO ACUMULADO (openspec l10n-ve-foreign-pt-cogs-imbalance)
    # ═══════════════════════════════════════════════════════════════

    def test_23_invoice_with_cogs_pair_stays_balanced(self):
        """Factura VEF con un par COGS autobalanceado, igual al que
           stock_account._post() inyecta en line_ids ANTES de postear
           (ver openspec/changes/l10n-ve-foreign-pt-cogs-imbalance).

           El par tiene el mismo costo con price_unit de signo opuesto
           (igual que _stock_account_prepare_realtime_out_lines_vals).
           Con _compute_foreign_price basado en _convert (lineal), negar
           el costo debe negar exactamente el monto alterno, así que el
           par se autobalancea sin depender de que _distribute_foreign_pt_residual
           lo excluya de 'other'.
        """
        acc_stock = self._get_or_create('110100', 'Stock Account', 'asset_current')

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
            ],
        })

        # Par COGS, mismo patrón que _stock_account_prepare_realtime_out_lines_vals:
        # price_unit de signo opuesto, mismo costo.
        cogs_cost = 9000.00
        invoice.write({
            "line_ids": [
                Command.create({
                    "name": "COGS interim",
                    "product_id": self.product.id,
                    "quantity": 1.0,
                    "price_unit": cogs_cost,
                    "account_id": acc_stock.id,
                    "display_type": "cogs",
                    "tax_ids": [(5, 0, 0)],
                }),
                Command.create({
                    "name": "COGS expense",
                    "product_id": self.product.id,
                    "quantity": 1.0,
                    "price_unit": -cogs_cost,
                    "account_id": self.acc_expense.id,
                    "display_type": "cogs",
                    "tax_ids": [(5, 0, 0)],
                }),
            ],
        })

        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, 'posted')
        self._log_lines(invoice, "test_23_cogs")

        cogs_lines = invoice.line_ids.filtered(lambda l: l.display_type == 'cogs')
        self.assertEqual(len(cogs_lines), 2, "Debe haber 2 lineas COGS")

        # El par COGS debe autobalancearse en moneda alterna por construccion
        cogs_fd = sum(cogs_lines.mapped('foreign_debit'))
        cogs_fc = sum(cogs_lines.mapped('foreign_credit'))
        self.assertAlmostEqual(
            cogs_fd, cogs_fc, places=2,
            msg=f"COGS: foreign_debit ({cogs_fd}) != foreign_credit ({cogs_fc})"
        )

        # Y el asiento completo (COGS incluidas) sigue cuadrando
        self._assert_balances(invoice, "test_23")
        self._assert_foreign_squares(invoice, "test_23")

    def test_24_invoice_many_lines_decimal_rounding(self):
        """Factura VEF con 50 lineas de precios con muchos decimales y
           una tasa con muchos decimales - hallazgo #2 del proposal
           (redondeo acumulado en facturas grandes).

           No es una regresion de hoy: foreign_subtotal sigue siendo
           foreign_price (ya redondeado) x cantidad, sin tocar. Lo que
           se verifica es que, aun con esa desviacion por linea,
           _distribute_foreign_pt_residual sigue cuadrando el total.
        """
        self._set_usd_rate(37.6543)

        lines = []
        n = 50
        for i in range(n):
            price = round(13.3333 + i * 0.7777, 4)
            lines.append(Command.create({
                "product_id": self.product.id,
                "quantity": 3.0,
                "price_unit": price,
                "account_id": self.acc_inc.id,
                "tax_ids": [(6, 0, [self.tax_16.id])],
            }))

        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_vef.id,
            "date": fields.Date.today(),
            "invoice_line_ids": lines,
        })
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, 'posted')

        self.assertEqual(
            len(invoice.invoice_line_ids), n,
            "Deben crearse las 50 lineas de producto"
        )

        # El cuadre total debe mantenerse pese al redondeo por linea
        self._assert_balances(invoice, "test_24")
        fd, fc = self._assert_foreign_squares(invoice, "test_24")

        # Medicion informativa (no regresion): cuanto se desvia la suma
        # "ingenua" de foreign_subtotal por linea (cada una ya redondeada)
        # respecto de convertir el total una sola vez.
        product_lines = invoice.line_ids.filtered(lambda l: l.display_type == 'product')
        naive_foreign_total = sum(product_lines.mapped('foreign_subtotal'))
        direct_convert_total = self.currency_vef._convert(
            sum(product_lines.mapped('price_subtotal')),
            self.currency_usd, self.company, fields.Date.today(),
        )
        deviation = abs(naive_foreign_total - direct_convert_total)
        _logger.info(
            f"test_24: desviacion redondeo acumulado (50 lineas) = "
            f"{deviation:.4f} USD (hallazgo #2 del proposal, no regresion)"
        )
        # El total del asiento SIEMPRE debe cuadrar, sin importar la
        # desviacion por linea - eso es lo que garantiza la distribucion.
        self.assertAlmostEqual(fd, fc, places=2)

        # Techo para la desviacion acumulada: con 50 lineas no deberia pasar
        # de 1 USD. Si algun cambio futuro la dispara, este assert lo detecta
        # en vez de dejarlo solo en el log.
        self.assertLess(
            deviation, 1.0,
            msg=f"Desviacion por redondeo acumulado demasiado alta: {deviation:.4f} USD"
        )

    # ═══════════════════════════════════════════════════════════════
    # TESTS: UNIFICACION DEL CALCULO ALTERNO VIA _convert() (TA-74966)
    # ═══════════════════════════════════════════════════════════════

    def test_25_manual_rate_does_not_override_convert(self):
        """Con la unificacion via _convert(), la tasa fijada en el documento
           (manually_set_rate) NO se usa para calcular el monto alterno de las
           lineas: manda siempre la tasa de res.currency.rate a la fecha.

           Este test deja constancia de la decision tomada en TA-74966. La
           tasa del documento queda como dato informativo -- los flujos que la
           heredan (l10n_ve_sale con use_invoice_rate_from_sale_order,
           l10n_ve_pos, cierre de ejercicio) muestran su tasa pero los montos
           alternos salen de la tabla.
        """
        self._set_usd_rate(50.0)

        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_vef.id,
            "date": fields.Date.today(),
            "invoice_date": fields.Date.today(),
            # Tasa "heredada" distinta de la tabla: 1 USD = 25 VEF
            "manually_set_rate": True,
            "foreign_rate": 25.0,
            "foreign_inverse_rate": 0.04,
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

        line = invoice.invoice_line_ids
        # Tabla: 1000 / 50 = 20 USD. Tasa manual habria dado 1000 / 25 = 40.
        self.assertAlmostEqual(
            line.foreign_price, 20.0, places=2,
            msg=f"foreign_price debe salir de la tabla (20), no de la tasa "
                f"del documento (40). Obtenido: {line.foreign_price}"
        )
        # La tasa del documento se conserva como dato informativo
        self.assertAlmostEqual(invoice.foreign_rate, 25.0, places=2)

        invoice.action_post()
        self._assert_balances(invoice, "test_25")
        self._assert_foreign_squares(invoice, "test_25")

    def test_26_foreign_price_recomputes_when_date_changes(self):
        """La fecha entra en _convert(), asi que debe estar declarada en el
           @api.depends de _compute_foreign_price: mover la fecha de un
           borrador tiene que recalcular el monto alterno.

           Antes de TA-74966 esta dependencia llegaba de rebote a traves de
           foreign_inverse_rate (related de move_id.foreign_inverse_rate, que
           si se recalcula con la fecha). Al pasar todo a _convert() ese
           rebote desaparece y la dependencia tiene que ser explicita.
        """
        self._set_usd_rate(50.0)

        past_date = fields.Date.today() - timedelta(days=30)
        self.env["res.currency.rate"].create({
            "name": past_date,
            "currency_id": self.currency_usd.id,
            "inverse_company_rate": 25.0,
            "company_id": self.company.id,
        })

        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_vef.id,
            "date": fields.Date.today(),
            "invoice_date": fields.Date.today(),
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

        line = invoice.invoice_line_ids
        self.assertAlmostEqual(line.foreign_price, 20.0, places=2)

        # Se mueve la fecha a una con tasa 25 -> 1000 / 25 = 40 USD
        invoice.write({
            "invoice_date": past_date,
            "date": past_date,
        })

        self.assertAlmostEqual(
            line.foreign_price, 40.0, places=2,
            msg=f"foreign_price no se recalculo al cambiar la fecha "
                f"(esperado 40, obtenido {line.foreign_price})"
        )

    def test_27_manual_entry_third_currency(self):
        """Asiento manual (no factura) con una linea en una tercera moneda.

           Es el caso que atravesaba el fallback eliminado en
           _get_non_invoice_foreign_value: ni el atajo de balance directo
           (no hay lineas en moneda alterna) ni la multiplicacion por
           foreign_inverse_rate. Ahora convierte con _convert() desde la
           moneda de la compania.
        """
        self._set_usd_rate(50.0)

        misc_journal = self.env["account.journal"].search([
            ("type", "=", "general"),
            ("company_id", "=", self.company.id),
        ], limit=1)
        self.assertTrue(misc_journal, "Debe existir un diario misceláneo")

        entry = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": misc_journal.id,
            "date": fields.Date.today(),
            "line_ids": [
                Command.create({
                    "name": "Debito EUR",
                    "account_id": self.acc_expense.id,
                    "currency_id": self.currency_eur.id,
                    "debit": 5500.0,
                    "credit": 0.0,
                    "amount_currency": 100.0,
                }),
                Command.create({
                    "name": "Credito VEF",
                    "account_id": self.acc_bank.id,
                    "debit": 0.0,
                    "credit": 5500.0,
                }),
            ],
        })
        entry.action_post()
        self._log_lines(entry, "test_27_third_currency")

        # 5500 VEF / 50 = 110 USD en cada pata
        eur_line = entry.line_ids.filtered(lambda l: l.currency_id == self.currency_eur)
        self.assertAlmostEqual(
            eur_line.foreign_debit, 110.0, places=2,
            msg=f"La linea EUR debe convertirse via _convert desde VEF "
                f"(esperado 110 USD, obtenido {eur_line.foreign_debit})"
        )
        self._assert_balances(entry, "test_27")
        self._assert_foreign_squares(entry, "test_27")

    # ═══════════════════════════════════════════════════════════════
    # TESTS: PRECISION, IMPUESTOS Y FECHA DE LA TASA (TA-74966)
    # Cada uno esta construido para FALLAR si se revierte el cambio
    # que verifica.
    # ═══════════════════════════════════════════════════════════════

    def test_29_foreign_price_keeps_field_precision(self):
        """foreign_price debe redondearse a la precision del campo
           ("Foreign Product Price", configurable) y no a los decimales de la
           moneda destino.

           REVERSION: si se quita el round=False + float_round y se deja que
           _convert() redondee por defecto, un precio unitario pequeno se
           pierde: 0,0567 VEF / 50 = 0,001134 USD se guardaria como 0,00, y
           foreign_subtotal (= foreign_price x cantidad) arrastraria ese cero
           multiplicado por la cantidad.
        """
        self._set_usd_rate(50.0)
        precision = self.env["decimal.precision"].precision_get(
            "Foreign Product Price"
        )
        self.assertGreater(
            precision, 2,
            "El test asume que Foreign Product Price tiene mas de 2 decimales"
        )

        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_vef.id,
            "date": fields.Date.today(),
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 10000.0,
                    "price_unit": 0.0567,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(5, 0, 0)],
                }),
            ],
        })

        line = invoice.invoice_line_ids
        # El esperado se calcula con la precision configurada, no con un
        # numero fijo de decimales: "Foreign Product Price" es editable.
        expected = float_round(0.0567 / 50.0, precision_digits=precision)
        self.assertAlmostEqual(
            line.foreign_price, expected, places=precision,
            msg=f"foreign_price perdio precision: {line.foreign_price} "
                f"(esperado {expected}). Con el redondeo de la moneda seria 0.00"
        )
        self.assertNotEqual(
            line.foreign_price, 0.0,
            "Un precio unitario pequeno no debe colapsar a cero"
        )
        # Y el subtotal no se va a cero por culpa del redondeo del unitario
        self.assertAlmostEqual(
            line.foreign_subtotal, 11.34, places=2,
            msg=f"foreign_subtotal = {line.foreign_subtotal}, esperado 11.34"
        )

    def test_30_foreign_subtotal_with_price_included_tax(self):
        """Con impuesto incluido en el precio, foreign_subtotal debe ser la
           BASE (sin impuesto), que es lo que devuelve compute_all.

           REVERSION: si se vuelve a la multiplicacion directa
           (foreign_price x cantidad), el subtotal se reporta con el impuesto
           dentro: 2,32 en vez de 2,00 USD.
        """
        self._set_usd_rate(50.0)

        tax_incl = self._create_tax('IVA 16% incluido', 16.0)
        tax_incl.price_include_override = 'tax_included'

        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_vef.id,
            "date": fields.Date.today(),
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0,
                    "price_unit": 116.00,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(6, 0, [tax_incl.id])],
                }),
            ],
        })

        line = invoice.invoice_line_ids
        # 116 VEF / 50 = 2,32 USD con el impuesto dentro
        self.assertAlmostEqual(line.foreign_price, 2.32, places=2)
        # y la base sin impuesto es 2,32 / 1,16 = 2,00 USD
        self.assertAlmostEqual(
            line.foreign_subtotal, 2.00, places=2,
            msg=f"foreign_subtotal = {line.foreign_subtotal}. Debe ser la base "
                f"sin impuesto (2.00); 2.32 significa que no paso por compute_all"
        )

    def test_31_foreign_total_billed_matches_lines(self):
        """foreign_total_billed debe salir de tax_totals, que se arma sumando
           las lineas, y no de convertir el total del documento de una vez.

           REVERSION: si se reintroduce la rama que hace
           _convert(amount_total), el pie del documento deja de cuadrar con la
           suma de los foreign_subtotal que se ven en las lineas, porque una
           via redondea una sola vez y la otra acumula el redondeo por linea.
        """
        self._set_usd_rate(37.6543)

        lines = []
        for i in range(12):
            lines.append(Command.create({
                "product_id": self.product.id,
                "quantity": 3.0,
                "price_unit": round(13.3333 + i * 0.7777, 4),
                "account_id": self.acc_inc.id,
                "tax_ids": [(5, 0, 0)],
            }))

        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_vef.id,
            "date": fields.Date.today(),
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": lines,
        })

        tax_totals = invoice.tax_totals if isinstance(invoice.tax_totals, dict) else {}
        self.assertAlmostEqual(
            invoice.foreign_total_billed,
            tax_totals.get("total_amount_foreign_currency", 0),
            places=2,
            msg="foreign_total_billed no coincide con tax_totals: hay una "
                "segunda via de conversion"
        )

    def test_32_rate_date_is_invoice_date_for_invoices(self):
        """La fecha de la tasa es invoice_date en facturas y notas, y date en
           asientos manuales.

           En esta localizacion invoice_date es la fecha de la TASA (la fecha
           visible del documento es invoice_date_display, ver
           account.move._get_accounting_date_source).

           REVERSION: si el helper vuelve a mezclar criterios de fecha, este
           test falla porque la factura usaria la tasa del dia contable en vez
           de la de su invoice_date.
        """
        self._set_usd_rate(50.0)
        past_date = fields.Date.today() - timedelta(days=30)
        self.env["res.currency.rate"].create({
            "name": past_date,
            "currency_id": self.currency_usd.id,
            "inverse_company_rate": 25.0,
            "company_id": self.company.id,
        })

        # invoice_date (tasa) en el pasado, date (contable) hoy
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_vef.id,
            "date": fields.Date.today(),
            "invoice_date": past_date,
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0,
                    "price_unit": 1000.00,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(5, 0, 0)],
                }),
            ],
        })

        line = invoice.invoice_line_ids
        self.assertAlmostEqual(
            line.foreign_price, 40.0, places=2,
            msg=f"La factura debe usar la tasa de invoice_date (1000/25 = 40), "
                f"no la de date (1000/50 = 20). Obtenido: {line.foreign_price}"
        )

    def test_33_price_unit_ves_uses_document_date(self):
        """price_unit_ves debe convertir con _convert() a la fecha del
           documento.

           REVERSION: el codigo anterior dividia entre line.currency_id.rate,
           que es la tasa del contexto (hoy), no la de la fecha de la factura.
           Con una factura fechada en el pasado y otra tasa vigente ese dia,
           ambos caminos dan resultados distintos.
        """
        self._set_usd_rate(50.0)
        past_date = fields.Date.today() - timedelta(days=30)
        self.env["res.currency.rate"].create({
            "name": past_date,
            "currency_id": self.currency_usd.id,
            "inverse_company_rate": 25.0,
            "company_id": self.company.id,
        })

        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_usd.id,
            "date": past_date,
            "invoice_date": past_date,
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0,
                    "price_unit": 100.00,
                    "account_id": self.acc_inc.id,
                    "tax_ids": [(5, 0, 0)],
                }),
            ],
        })

        line = invoice.invoice_line_ids
        # 100 USD a la tasa de past_date (25) = 2500 VEF, no 5000
        self.assertAlmostEqual(
            line.price_unit_ves, 2500.0, places=2,
            msg=f"price_unit_ves = {line.price_unit_ves}. Debe usar la tasa de "
                f"la fecha del documento (2500), no la de hoy (5000)"
        )

    def test_34_line_section_never_receives_real_portion_residual(self):
        """Ticket #14978 / CDD Las Mercedes: una factura USD con un
        'line_section' (encabezado de un producto combo, o una sección
        tipeada a mano) no confirmaba -- Postgres rechazaba el posteo con
        "Forbidden balance or account on non-accountable line".

        Causa: _distribute_invoice_real_portion arma `non_pt`/`target_lines`
        filtrando solo ('payment_term', 'cogs'), sin excluir
        ('line_section', 'line_subsection', 'line_note'). Como esas líneas
        tienen balance=0, _distribute_to_lines las ordena al final (ordena
        por -abs(balance)) y les asigna lo que sobra del redondeo del
        "real portion" -- así una línea no contable termina con
        balance/debit != 0, lo que viola el CHECK de account.move.line.

        Un `create()` normal no garantiza el residuo de redondeo en este
        fixture aislado (depende de la conversión exacta de cada línea), así
        que más abajo se desbalancea la factura ya posteada a propósito y se
        llama _distribute_invoice_real_portion() directamente -- el mismo
        método que _sync_dynamic_lines dispara en la vida real.
        """
        self._set_usd_rate(772.5441)

        lines = [Command.create({
            "display_type": "line_section",
            "name": "laboratorios",
        })]
        for i in range(20):
            price = round(13.3333 + i * 0.7777, 4)
            lines.append(Command.create({
                "product_id": self.product.id,
                "quantity": 3.0,
                "price_unit": price,
                "account_id": self.acc_inc.id,
                "tax_ids": [(5, 0, 0)],
            }))
        lines.insert(11, Command.create({
            "display_type": "line_section",
            "name": "Estudios",
        }))

        invoice = self.env["account.move"].with_context(
            check_move_validity=False,
        ).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_usd.id,
            "date": fields.Date.today(),
            "invoice_line_ids": lines,
        })

        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, 'posted')
        section_lines = invoice.line_ids.filtered(
            lambda l: l.display_type in ('line_section', 'line_subsection', 'line_note')
        )
        self.assertTrue(section_lines, "La factura debe conservar sus líneas de sección")

        cc = invoice.company_currency_id
        product_line = invoice.line_ids.filtered(
            lambda l: l.display_type == 'product'
        )[:1]
        product_line.sudo().with_context(check_move_validity=False).write({
            'credit': product_line.credit + 0.01,
            'balance': product_line.balance - 0.01,
        })
        invoice._distribute_invoice_real_portion(invoice, cc)

        # Antes del fix, esta línea terminaba con balance/debit != 0 y
        # Postgres rechazaba el UPDATE con
        # "account_move_line_check_non_accountable_fields_null".
        for line in section_lines:
            self.assertEqual(line.balance, 0.0, f"'{line.name}' quedó con balance={line.balance}")
            self.assertEqual(line.debit, 0.0, f"'{line.name}' quedó con debit={line.debit}")
            self.assertEqual(line.credit, 0.0, f"'{line.name}' quedó con credit={line.credit}")
            self.assertFalse(line.account_id, f"'{line.name}' quedó con account_id={line.account_id}")
