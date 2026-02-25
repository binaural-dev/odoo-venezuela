
import logging
from odoo.tests import TransactionCase, tagged
from odoo import fields, Command

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_accountant_test")
class TestForeignBalance(TransactionCase):
    """
    Suite de pruebas para el Foreign Balance (Débito/Crédito Alterno).

    Compañía: VEF (moneda base), USD (moneda alterna).
    Tasa base en setUp: 1 USD = 40 VEF.

    Convención de asserts:
      - places=2   → exacto a centavos (sin delta).
      - delta=0.02 → máximo 2 centavos de tolerancia (conversiones múltiples).
    Nunca usar delta >= 0.05, ya que el bug principal era de exactamente $0.01.
    """

    # ─────────────────────────────────────────────────────────────────
    # Setup
    # ─────────────────────────────────────────────────────────────────

    def setUp(self):
        super().setUp()

        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.currency_eur = self.env.ref("base.EUR")
        self.currency_eur.active = True
        self.company = self.env.ref("base.main_company")
        self.country_ve = self.env.ref("base.ve")

        # Compañía: base VEF, alterna USD, país Venezuela
        self.company.write(
            {
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
                "account_fiscal_country_id": self.country_ve.id,
                "country_id": self.country_ve.id,
            }
        )

        # Tasas base para todos los tests (algunas se sobreescriben en el test específico)
        #   VEF = 1.0  (base)
        #   USD = 40.0 VEF por 1 USD
        #   EUR = 44.0 VEF por 1 EUR
        self.env["res.currency.rate"].create(
            {
                "name": fields.Date.today(),
                "currency_id": self.currency_vef.id,
                "inverse_company_rate": 1.0,
                "company_id": self.company.id,
            }
        )
        self.rate_usd = self.env["res.currency.rate"].create(
            {
                "name": fields.Date.today(),
                "currency_id": self.currency_usd.id,
                "inverse_company_rate": 40.0,  # 1 USD = 40 VEF
                "company_id": self.company.id,
            }
        )
        self.env["res.currency.rate"].create(
            {
                "name": fields.Date.today(),
                "currency_id": self.currency_eur.id,
                "inverse_company_rate": 44.0,  # 1 EUR = 44 VEF
                "company_id": self.company.id,
            }
        )

        self.account_receivable = self.env["account.account"].search(
            [("code", "=", "120000"), ("company_ids", "in", self.company.id)], limit=1
        )
        if not self.account_receivable:
            self.account_receivable = self.env["account.account"].create(
                {
                    "name": "Receivable",
                    "code": "120000",
                    "account_type": "asset_receivable",
                    "company_ids": [(6, 0, [self.company.id])],
                    "reconcile": True,
                }
            )

        self.account_income = self.env["account.account"].search(
            [("code", "=", "400000"), ("company_ids", "in", self.company.id)], limit=1
        )
        if not self.account_income:
            self.account_income = self.env["account.account"].create(
                {
                    "name": "Income",
                    "code": "400000",
                    "account_type": "income",
                    "company_ids": [(6, 0, [self.company.id])],
                }
            )

        self.test_tax_group = self.env["account.tax.group"].create(
            {
                "name": "Test Tax Group",
                "company_id": self.company.id,
                "country_id": self.country_ve.id,
            }
        )

        self.account_tax_account = self.env["account.account"].search(
            [("code", "=", "200000"), ("company_ids", "in", self.company.id)], limit=1
        )
        if not self.account_tax_account:
            self.account_tax_account = self.env["account.account"].create(
                {
                    "name": "Tax Paid",
                    "code": "200000",
                    "account_type": "liability_current",
                    "company_ids": [(6, 0, [self.company.id])],
                }
            )

        self.test_tax = self.env["account.tax"].create(
            {
                "name": "Test Tax 16%",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": self.company.id,
                "tax_group_id": self.test_tax_group.id,
            }
        )

        self.sale_journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].sudo().create(
            {
                "name": "Sales Test",
                "code": "SLTST",
                "type": "sale",
                "company_id": self.company.id,
                "default_account_id": self.account_income.id,
            }
        )

        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "country_id": self.country_ve.id,
                "property_account_receivable_id": self.account_receivable.id,
            }
        )

        # Producto con IVA 16%
        self.product = self.env["product.product"].create(
            {
                "name": "Product Test",
                "type": "service",
                "list_price": 100.0,
                "taxes_id": [(6, 0, [self.test_tax.id])],
            }
        )

    # ─────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────

    def _log_lines(self, lines, label=""):
        """Imprime todas las líneas de un asiento en el log de tests."""
        _logger.info("── %s ──", label or "Lines")
        for line in lines:
            _logger.info(
                "  %-30s | deb=%10.2f | cre=%10.2f | f_deb=%10.2f | f_cre=%10.2f",
                (line.name or "")[:30],
                line.debit,
                line.credit,
                line.foreign_debit,
                line.foreign_credit,
            )

    def _assert_foreign_balance_squares(self, lines, label=""):
        """
        Verifica que:
        1. Σ foreign_debit == Σ foreign_credit  (cuadre del asiento)
        2. Para cada línea: foreign_balance == foreign_debit - foreign_credit
           (consistencia interna — detecta saldos stale o inconsistentes)

        Ambas verificaciones usan places=2 (exacto a centavos).
        Nunca usar delta >= 0.05 en este módulo — el bug principal era $0.01.
        """
        fd = sum(lines.mapped("foreign_debit"))
        fc = sum(lines.mapped("foreign_credit"))
        self._log_lines(lines, label)
        _logger.info(
            "  Σ foreign_debit=%.4f  Σ foreign_credit=%.4f  diff=%.4f",
            fd, fc, abs(fd - fc),
        )

        # 1. Cuadre del asiento
        self.assertAlmostEqual(
            fd, fc, places=2,
            msg=(
                f"[{label}] Foreign balance no cuadra: "
                f"debit={fd:.4f} credit={fc:.4f} diff={abs(fd - fc):.4f}"
            ),
        )

        # 2. Consistencia interna: foreign_balance debe ser siempre foreign_debit - foreign_credit
        for line in lines:
            expected_balance = line.foreign_debit - line.foreign_credit
            self.assertAlmostEqual(
                line.foreign_balance, expected_balance, places=2,
                msg=(
                    f"[{label}] Línea {line.name!r} (type={line.display_type}): "
                    f"foreign_balance={line.foreign_balance:.4f} != "
                    f"foreign_debit({line.foreign_debit:.4f}) - "
                    f"foreign_credit({line.foreign_credit:.4f}) = {expected_balance:.4f}"
                ),
            )

        return fd, fc


    def _assert_non_payment_term_lines_convert(self, lines, date, label=""):
        """
        Para las líneas que NO son payment_term, verifica que foreign_debit/credit
        coincida con la conversión directa VEF→USD (places=2).
        Las líneas payment_term usan residuo, por lo que se omiten aquí.
        """
        for line in lines:
            if line.display_type == "payment_term":
                continue  # payment_term usa residuo, no conversión directa
            if line.debit > 0:
                expected = self.currency_vef._convert(
                    line.debit, self.currency_usd, self.company, date
                )
                self.assertAlmostEqual(
                    line.foreign_debit, expected, places=2,
                    msg=f"[{label}] {line.name!r} foreign_debit={line.foreign_debit:.2f} != expected={expected:.2f}",
                )
            if line.credit > 0:
                expected = self.currency_vef._convert(
                    line.credit, self.currency_usd, self.company, date
                )
                self.assertAlmostEqual(
                    line.foreign_credit, expected, places=2,
                    msg=f"[{label}] {line.name!r} foreign_credit={line.foreign_credit:.2f} != expected={expected:.2f}",
                )

    def _set_usd_rate(self, vef_per_usd):
        """Sobreescribe la tasa USD para el test actual."""
        self.rate_usd.write({"inverse_company_rate": vef_per_usd})

    # ─────────────────────────────────────────────────────────────────
    # Tests de Facturas
    # ─────────────────────────────────────────────────────────────────

    def test_invoice_foreign_balance_simple(self):
        """
        Factura en USD (moneda alterna). Tasa 1 USD = 40 VEF.
        Producto: 100 USD + IVA 16% = 116 USD.
        La línea CxC (payment_term) usa residuo → debe cuadrar exactamente.
        """
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.sale_journal.id,
                "currency_id": self.currency_usd.id,
                "date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 100.0,  # 100 USD
                            "account_id": self.account_income.id,
                        }
                    )
                ],
            }
        )
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, "posted", "La factura no se publicó")

        fd, fc = self._assert_foreign_balance_squares(
            invoice.line_ids, "invoice_simple_usd"
        )

        # Total: 100 USD base + 16 USD IVA = 116 USD exactos
        self.assertAlmostEqual(fd, 116.0, places=2, msg="Total USD debe ser 116.00")
        self.assertGreater(fd, 0)

    def test_invoice_foreign_balance_company_currency(self):
        """
        Factura en VEF (moneda base). Tasa 1 USD = 40 VEF.
        Producto: 4.000 VEF + IVA 16% = 4.640 VEF → 116 USD.
        Verifica cuadre exacto y conversión línea por línea.
        """
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.sale_journal.id,
                "currency_id": self.currency_vef.id,
                "date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 4000.0,  # 4.000 VEF
                            "account_id": self.account_income.id,
                        }
                    )
                ],
            }
        )
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, "posted")

        fd, fc = self._assert_foreign_balance_squares(
            invoice.line_ids, "invoice_company_currency_vef"
        )

        # 4.000 VEF + 16% = 4.640 VEF / 40 = 116.00 USD exacto
        self.assertAlmostEqual(fd, 116.0, places=2, msg="Total USD debe ser 116.00")

        # Verificar líneas individuales (excepto payment_term)
        self._assert_non_payment_term_lines_convert(
            invoice.line_ids, invoice.date, "invoice_company_currency_vef"
        )

    def test_invoice_pricelist_eur(self):
        """
        Factura en EUR (tercera moneda). Tasas: 1 EUR = 44 VEF, 1 USD = 40 VEF.
        Producto: 100 EUR + IVA 16%.
          100 EUR → 4.400 VEF (base)
          IVA 16% → 704 VEF
          Total  → 5.104 VEF / 40 = 127.60 USD
        Verifica cuadre exacto.
        """
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.sale_journal.id,
                "currency_id": self.currency_eur.id,
                "date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 100.0,  # 100 EUR
                            "account_id": self.account_income.id,
                        }
                    )
                ],
            }
        )
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, "posted", "La factura no se publicó")

        fd, fc = self._assert_foreign_balance_squares(
            invoice.line_ids, "invoice_eur"
        )

        # 5.104 VEF / 40 = 127.60 USD
        self.assertGreater(fd, 0)
        self.assertAlmostEqual(fd, 127.6, delta=0.02, msg="Total USD debe ser ≈ 127.60")

    def test_invoice_pricelist_vef_two_products(self):
        """
        CASO REAL DEL BUG: Factura en VEF con tasa 402,3343 VEF/USD.
          Producto 1: 23.200,00 VEF + IVA 16% (3.712,00 VEF)
          Producto 2: 56.200,00 VEF EXENTO
          Total:      83.112,00 VEF → ≈ 206,57 USD

        Antes del fix, la línea CxC convertía 83.112 / 402,3343 = 206,58 (redondeo),
        mientras los créditos sumaban 206,57 → descuadre de $0,01.
        Con el fix (residuo), la CxC toma exactamente la suma de los créditos.
        """
        RATE = 402.3343
        self._set_usd_rate(RATE)

        product_exempt = self.env["product.product"].create(
            {
                "name": "Producto Exento",
                "type": "service",
                "list_price": 56200.0,
                "taxes_id": [(5, 0, 0)],
            }
        )

        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.sale_journal.id,
                "currency_id": self.currency_vef.id,
                "date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 23200.0,
                            "account_id": self.account_income.id,
                            "tax_ids": [(6, 0, [self.test_tax.id])],
                        }
                    ),
                    Command.create(
                        {
                            "product_id": product_exempt.id,
                            "quantity": 1.0,
                            "price_unit": 56200.0,
                            "account_id": self.account_income.id,
                            "tax_ids": [(5, 0, 0)],
                        }
                    ),
                ],
            }
        )
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, "posted", "La factura no se publicó")

        # Total VEF: 23.200 + 56.200 + 3.712 (IVA) = 83.112,00
        self.assertAlmostEqual(
            invoice.amount_total, 83112.0, places=2,
            msg="Total factura VEF debe ser 83.112,00",
        )

        # Cuadre exacto (este assert detecta el bug de $0,01)
        fd, fc = self._assert_foreign_balance_squares(
            invoice.line_ids, "invoice_two_products_rate_402"
        )

        # Total USD esperado: 83.112 / 402,3343 ≈ 206,57
        expected_usd = 83112.0 / RATE
        self.assertAlmostEqual(
            fd, expected_usd, delta=0.02,
            msg=f"Total USD debe ser ≈ {expected_usd:.2f}",
        )

        # Las líneas producto/tax deben convertir correctamente (no payment_term)
        self._assert_non_payment_term_lines_convert(
            invoice.line_ids, invoice.date, "invoice_two_products_per_line"
        )

    # ─────────────────────────────────────────────────────────────────
    # Tests de Pagos
    # ─────────────────────────────────────────────────────────────────

    def _get_or_create_bank_journal(self, currency):
        journal = self.env["account.journal"].search(
            [
                ("type", "=", "bank"),
                ("currency_id", "=", currency.id),
                ("company_id", "=", self.company.id),
            ],
            limit=1,
        )
        if not journal:
            journal = self.env["account.journal"].sudo().create(
                {
                    "name": f"Bank {currency.name}",
                    "type": "bank",
                    "code": f"BNK{currency.name}",
                    "currency_id": currency.id,
                    "company_id": self.company.id,
                }
            )
        return journal

    def _create_usd_invoice(self, price_unit=100.0):
        """Crea y publica una factura en USD con el producto test (IVA 16%)."""
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.sale_journal.id,
                "currency_id": self.currency_usd.id,
                "date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": price_unit,
                            "account_id": self.account_income.id,
                        }
                    )
                ],
            }
        )
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, "posted", "La factura no se publicó")
        return invoice

    def test_payment_foreign_balance_usd(self):
        """
        Pago en USD de una factura en USD. Tasa 1 USD = 40 VEF.
        Producto: 100 USD + 16% IVA = 116 USD.
        Verifica:
          - foreign_debit == foreign_credit (cuadre exacto)
          - Total USD = 116.00
          - Conversión línea por línea (VEF → USD)
        """
        bank_journal = self._get_or_create_bank_journal(self.currency_usd)
        invoice = self._create_usd_invoice(100.0)

        self.assertAlmostEqual(
            invoice.amount_total, 116.0, places=2,
            msg="Total factura USD debe ser 116.00",
        )

        payment_register = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create(
                {
                    "journal_id": bank_journal.id,
                    "amount": 116.0,
                    "currency_id": self.currency_usd.id,
                    "payment_date": fields.Date.today(),
                }
            )
        )
        payment = payment_register._create_payments()
        self.assertIn(payment.state, ["posted", "paid"], "Pago no publicado")

        move = payment.move_id
        fd, fc = self._assert_foreign_balance_squares(
            move.line_ids, "payment_usd"
        )
        self.assertGreater(fd, 0)
        self.assertAlmostEqual(fd, 116.0, places=2, msg="Total USD pago debe ser 116.00")

        # Conversión línea por línea para asientos que no son factura
        for line in move.line_ids:
            if line.debit > 0:
                expected = self.currency_vef._convert(
                    line.debit, self.currency_usd, self.company, payment.date
                )
                self.assertAlmostEqual(
                    line.foreign_debit, expected, delta=0.02,
                    msg=f"payment_usd {line.name!r} foreign_debit",
                )
            if line.credit > 0:
                expected = self.currency_vef._convert(
                    line.credit, self.currency_usd, self.company, payment.date
                )
                self.assertAlmostEqual(
                    line.foreign_credit, expected, delta=0.02,
                    msg=f"payment_usd {line.name!r} foreign_credit",
                )

    def test_payment_foreign_balance_vef(self):
        """
        Pago en VEF de una factura en USD. Tasa 1 USD = 40 VEF.
        Factura: 116 USD → pago 4.640 VEF.
        Verifica cuadre exacto y que el total en USD sea ≈ 116.
        """
        bank_journal = self._get_or_create_bank_journal(self.currency_vef)
        invoice = self._create_usd_invoice(100.0)

        # 116 USD × 40 = 4.640 VEF
        amount_vef = self.currency_usd._convert(
            116.0, self.currency_vef, self.company, fields.Date.today()
        )
        self.assertAlmostEqual(amount_vef, 4640.0, places=2, msg="4.640 VEF esperados")

        payment_register = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create(
                {
                    "journal_id": bank_journal.id,
                    "amount": amount_vef,
                    "currency_id": self.currency_vef.id,
                    "payment_date": fields.Date.today(),
                }
            )
        )
        payment = payment_register._create_payments()
        self.assertIn(payment.state, ["posted", "paid"], "Pago no publicado")

        move = payment.move_id
        fd, fc = self._assert_foreign_balance_squares(
            move.line_ids, "payment_vef"
        )
        # 4.640 VEF / 40 = 116 USD
        self.assertAlmostEqual(fd, 116.0, places=2, msg="Total USD pago debe ser 116.00")

        # Conversión línea por línea
        for line in move.line_ids:
            if line.debit > 0:
                expected = self.currency_vef._convert(
                    line.debit, self.currency_usd, self.company, payment.date
                )
                self.assertAlmostEqual(
                    line.foreign_debit, expected, delta=0.02,
                    msg=f"payment_vef {line.name!r} foreign_debit",
                )
            if line.credit > 0:
                expected = self.currency_vef._convert(
                    line.credit, self.currency_usd, self.company, payment.date
                )
                self.assertAlmostEqual(
                    line.foreign_credit, expected, delta=0.02,
                    msg=f"payment_vef {line.name!r} foreign_credit",
                )

    def test_payment_foreign_balance_eur(self):
        """
        Pago en EUR de una factura en USD.
        Tasas: 1 USD = 40 VEF, 1 EUR = 44 VEF.
        Factura: 116 USD → pago en EUR equivalente.
        Verifica cuadre exacto (debit == credit) y total ≈ 116 USD.
        """
        bank_journal = self._get_or_create_bank_journal(self.currency_eur)
        invoice = self._create_usd_invoice(100.0)

        amount_eur = self.currency_usd._convert(
            116.0, self.currency_eur, self.company, fields.Date.today()
        )

        payment_register = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create(
                {
                    "journal_id": bank_journal.id,
                    "amount": amount_eur,
                    "currency_id": self.currency_eur.id,
                    "payment_date": fields.Date.today(),
                }
            )
        )
        payment = payment_register._create_payments()
        self.assertIn(
            payment.state, ["posted", "paid", "in_process"], "Pago no publicado"
        )

        move = payment.move_id
        fd, fc = self._assert_foreign_balance_squares(
            move.line_ids, "payment_eur"
        )
        self.assertAlmostEqual(fd, 116.0, delta=0.02, msg="Total USD pago debe ser ≈ 116.00")

        # Conversión línea por línea
        for line in move.line_ids:
            if line.debit > 0:
                expected = self.currency_vef._convert(
                    line.debit, self.currency_usd, self.company, payment.date
                )
                self.assertAlmostEqual(
                    line.foreign_debit, expected, delta=0.02,
                    msg=f"payment_eur {line.name!r} foreign_debit",
                )
            if line.credit > 0:
                expected = self.currency_vef._convert(
                    line.credit, self.currency_usd, self.company, payment.date
                )
                self.assertAlmostEqual(
                    line.foreign_credit, expected, delta=0.02,
                    msg=f"payment_eur {line.name!r} foreign_credit",
                )

    def test_invoice_pricelist_vef_exempt_zero_tax(self):
        """
        Caso real: producto exento representado con un IMPUESTO del 0%
        (en lugar de sin impuestos). Tasa: 1 USD = 402,3343 VEF.

        Diferencia clave vs test_invoice_pricelist_vef_two_products:
          - El producto exento lleva un tax 0%, por lo que Odoo crea una
            línea `display_type=tax` con debit=0 y credit=0.
          - Esa línea tax no aporta monto, pero sí es procesada por
            _compute_foreign_debit_credit (Caso 1b). Debe producir
            foreign_debit=0 y foreign_credit=0.
          - El residuo del payment_term debe seguir cuadrando.

        Montos:
          Producto 1: 23.200,00 VEF + IVA 16%  → tax 3.712,00 VEF
          Producto 2: 56.200,00 VEF exento 0%  → tax 0,00 VEF
          Total VEF:  83.112,00 → ≈ 206,57 USD
        """
        RATE = 402.3343
        self._set_usd_rate(RATE)

        # Impuesto 0% para exentos
        tax_zero = self.env["account.tax"].create(
            {
                "name": "Exento 0%",
                "amount": 0.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": self.company.id,
                "tax_group_id": self.test_tax_group.id,
            }
        )

        product_exempt = self.env["product.product"].create(
            {
                "name": "Producto Exento 0%",
                "type": "service",
                "list_price": 56200.0,
                "taxes_id": [(6, 0, [tax_zero.id])],
            }
        )

        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.sale_journal.id,
                "currency_id": self.currency_vef.id,
                "date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 23200.0,
                            "account_id": self.account_income.id,
                            "tax_ids": [(6, 0, [self.test_tax.id])],
                        }
                    ),
                    Command.create(
                        {
                            "product_id": product_exempt.id,
                            "quantity": 1.0,
                            "price_unit": 56200.0,
                            "account_id": self.account_income.id,
                            "tax_ids": [(6, 0, [tax_zero.id])],
                        }
                    ),
                ],
            }
        )
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, "posted", "La factura no se publicó")

        # Total VEF = 23.200 + 56.200 + 3.712 (IVA 16%) + 0,00 (IVA 0%) = 83.112
        self.assertAlmostEqual(
            invoice.amount_total, 83112.0, places=2,
            msg="Total factura VEF debe ser 83.112,00",
        )

        # Verificar que la línea tax del impuesto 0% tiene foreign_debit=0 y foreign_credit=0
        tax_zero_lines = invoice.line_ids.filtered(
            lambda l: l.display_type == "tax" and l.tax_line_id == tax_zero
        )
        for tl in tax_zero_lines:
            self.assertAlmostEqual(
                tl.foreign_debit, 0.0, places=2,
                msg=f"Línea tax 0% debe tener foreign_debit=0, tiene {tl.foreign_debit}",
            )
            self.assertAlmostEqual(
                tl.foreign_credit, 0.0, places=2,
                msg=f"Línea tax 0% debe tener foreign_credit=0, tiene {tl.foreign_credit}",
            )

        # Cuadre exacto + consistencia interna (detecta bug $0.01 y stale foreign_balance)
        fd, fc = self._assert_foreign_balance_squares(
            invoice.line_ids, "invoice_exempt_zero_tax"
        )

        # Total USD ≈ 83.112 / 402,3343
        expected_usd = 83112.0 / RATE
        self.assertAlmostEqual(
            fd, expected_usd, delta=0.02,
            msg=f"Total USD debe ser ≈ {expected_usd:.2f}",
        )

        # Conversión línea por línea (excepto payment_term)
        self._assert_non_payment_term_lines_convert(
            invoice.line_ids, invoice.date, "invoice_exempt_zero_tax_per_line"
        )


    # ─────────────────────────────────────────────────────────────────
    # Tests de custom_rate en líneas de impuesto (tax display_type)
    # Cubre: custom_rate = foreign_inverse_rate if is_purchase_document else None
    # Ref: account_move_line.py L186
    # ─────────────────────────────────────────────────────────────────

    def _create_purchase_setup(self):
        """
        Crea journal, cuentas y tax de COMPRA para vendor bill tests.
        Retorna (purchase_journal, account_expense, purchase_tax, vendor_partner).
        """
        account_payable = self.env["account.account"].search(
            [("code", "=", "220000"), ("company_ids", "in", self.company.id)], limit=1
        )
        if not account_payable:
            account_payable = self.env["account.account"].create({
                "name": "Payable Test",
                "code": "220000",
                "account_type": "liability_payable",
                "company_ids": [(6, 0, [self.company.id])],
                "reconcile": True,
            })

        account_expense = self.env["account.account"].search(
            [("code", "=", "600000"), ("company_ids", "in", self.company.id)], limit=1
        )
        if not account_expense:
            account_expense = self.env["account.account"].create({
                "name": "Expense Test",
                "code": "600000",
                "account_type": "expense",
                "company_ids": [(6, 0, [self.company.id])],
            })

        purchase_journal = self.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].sudo().create({
            "name": "Purchases Test",
            "code": "PURTST",
            "type": "purchase",
            "company_id": self.company.id,
            "default_account_id": account_expense.id,
        })

        purchase_tax = self.env["account.tax"].create({
            "name": "IVA Compra 16%",
            "amount": 16,
            "amount_type": "percent",
            "type_tax_use": "purchase",
            "company_id": self.company.id,
            "tax_group_id": self.test_tax_group.id,
        })

        vendor = self.env["res.partner"].create({
            "name": "Vendor Test",
            "country_id": self.country_ve.id,
            "property_account_payable_id": account_payable.id,
        })

        return purchase_journal, account_expense, purchase_tax, vendor



    def test_credit_note_foreign_balance_squares(self):
        """
        NOTA DE CRÉDITO (out_refund): direction_sign invertido.
        Verifica que el cuadre se mantenga con tasa 402,3343 VEF/USD.
        """
        RATE = 402.3343
        self._set_usd_rate(RATE)

        product_exempt = self.env["product.product"].create({
            "name": "Producto Exento Refund",
            "type": "service",
            "list_price": 56200.0,
            "taxes_id": [(5, 0, 0)],
        })

        refund = self.env["account.move"].create({
            "move_type": "out_refund",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_vef.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0,
                    "price_unit": 23200.0,
                    "account_id": self.account_income.id,
                    "tax_ids": [(6, 0, [self.test_tax.id])],
                }),
                Command.create({
                    "product_id": product_exempt.id,
                    "quantity": 1.0,
                    "price_unit": 56200.0,
                    "account_id": self.account_income.id,
                    "tax_ids": [(5, 0, 0)],
                }),
            ],
        })
        refund.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(refund.state, "posted", "La nota de crédito no se publicó")

        self.assertAlmostEqual(refund.amount_total, 83112.0, places=2)

        fd, fc = self._assert_foreign_balance_squares(
            refund.line_ids, "credit_note_rate_402"
        )
        expected_usd = 83112.0 / RATE
        self.assertAlmostEqual(fd, expected_usd, delta=0.02,
            msg=f"Total USD nota crédito debe ser ≈ {expected_usd:.2f}")

    def test_vendor_bill_foreign_balance_squares_problematic_rate(self):
        """
        FACTURA DE PROVEEDOR (in_invoice) en VEF con tasa 402,3343 VEF/USD.
        Mismo escenario del bug original pero en contexto de compras.
        """
        RATE = 402.3343
        self._set_usd_rate(RATE)

        purchase_journal, account_expense, purchase_tax, vendor = (
            self._create_purchase_setup()
        )

        product_exempt = self.env["product.product"].create({
            "name": "Gasto Exento",
            "type": "service",
            "taxes_id": [(5, 0, 0)],
        })
        expense_product = self.env["product.product"].create({
            "name": "Gasto con IVA",
            "type": "service",
            "supplier_taxes_id": [(6, 0, [purchase_tax.id])],
        })

        bill = self.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": vendor.id,
            "journal_id": purchase_journal.id,
            "currency_id": self.currency_vef.id,
            "date": fields.Date.today(),
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": expense_product.id,
                    "quantity": 1.0,
                    "price_unit": 23200.0,
                    "account_id": account_expense.id,
                    "tax_ids": [(6, 0, [purchase_tax.id])],
                }),
                Command.create({
                    "product_id": product_exempt.id,
                    "quantity": 1.0,
                    "price_unit": 56200.0,
                    "account_id": account_expense.id,
                    "tax_ids": [(5, 0, 0)],
                }),
            ],
        })
        bill.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(bill.state, "posted", "La factura proveedor no se publicó")

        self.assertAlmostEqual(bill.amount_total, 83112.0, places=2)

        fd, fc = self._assert_foreign_balance_squares(
            bill.line_ids, "vendor_bill_rate_402"
        )
        expected_usd = 83112.0 / RATE
        self.assertAlmostEqual(fd, expected_usd, delta=0.02,
            msg=f"Total USD factura proveedor ≈ {expected_usd:.2f}")

    def test_invoice_multi_installment_payment_term(self):
        """
        PAYMENT TERM MULTI-CUOTA: genera múltiples líneas display_type=payment_term.
        Verifica que el residuo no se duplique y que la suma de cuotas iguale
        el total de créditos de las demás líneas.
        """
        RATE = 402.3343
        self._set_usd_rate(RATE)

        payment_term = self.env["account.payment.term"].create({
            "name": "50/50 Test",
            "company_id": self.company.id,
            "line_ids": [
                Command.create({
                    "value": "percent",
                    "value_amount": 50.0,
                    "nb_days": 0,
                }),
                Command.create({
                    "value": "percent",   # En Odoo 17+ 'balance' ya no existe
                    "value_amount": 50.0,
                    "nb_days": 30,
                }),
            ],
        })


        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_vef.id,
            "invoice_payment_term_id": payment_term.id,
            "date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id,
                    "quantity": 1.0,
                    "price_unit": 23200.0,
                    "account_id": self.account_income.id,
                    "tax_ids": [(6, 0, [self.test_tax.id])],
                }),
            ],
        })
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, "posted")

        pt_lines = invoice.line_ids.filtered(
            lambda l: l.display_type == "payment_term"
        )
        self.assertGreater(len(pt_lines), 1,
            "Se esperan múltiples líneas payment_term para el término 50/50")

        # Cuadre exacto — detecta si el residuo se acumuló incorrectamente
        fd, fc = self._assert_foreign_balance_squares(
            invoice.line_ids, "multi_installment_rate_402"
        )

        expected_usd = 26912.0 / RATE  # 23200 + 16% = 26912 VEF
        self.assertAlmostEqual(fd, expected_usd, delta=0.02,
            msg=f"Total USD multi-cuota ≈ {expected_usd:.2f}")

        # La suma de foreign_debit de TODAS las cuotas debe igualar exactamente
        # el total de créditos (la última cuota toma el residuo exacto).
        pt_foreign_debit = sum(pt_lines.mapped("foreign_debit"))
        other_foreign_credit = sum(
            invoice.line_ids.filtered(
                lambda l: l.display_type not in ("payment_term", "line_section", "line_note")
            ).mapped("foreign_credit")
        )
        self.assertAlmostEqual(
            pt_foreign_debit, other_foreign_credit, places=2,
            msg=(
                f"Suma foreign_debit cuotas ({pt_foreign_debit:.4f}) "
                f"!= total créditos ({other_foreign_credit:.4f})"
            ),
        )

