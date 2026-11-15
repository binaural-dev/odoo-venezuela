"""Ticket 16195: el asiento de ajuste de monedas no realizadas solo mueve los VEF.

El asistente nativo (`account_reports`, "Ganancias/pérdidas de moneda no
realizadas") ajusta `debit`/`credit` y crea las líneas con `amount_currency = 0`.
En moneda alterna no hay diferencia: 100 USD siguen siendo 100 USD, solo cambia lo
que valen en bolívares. La localización les asignaba, sin embargo, un importe
alterno (los bolívares del ajuste convertidos a dólares), de modo que los reportes
en USD mostraban cuentas por cobrar y ganancias en dólares que no existen.
"""

import json
from datetime import date

from odoo.tests import TransactionCase, freeze_time, tagged


# `create_entries` crea la reversión con la fecha de hoy antes de asignarle la de
# reversión, y busca la tasa exacta de ese día: se congela el "hoy" para que las
# pruebas no dependan de la fecha en que se corren. Mediodía para que la zona
# horaria del usuario no mueva `context_today` al día anterior.
@freeze_time("2026-11-09 12:00:00")
@tagged("post_install", "-at_install", "l10n_ve_accountant_multicurrency_revaluation")
class TestMulticurrencyRevaluation(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.env.user.write(
            {"company_ids": [(4, self.company.id)], "company_id": self.company.id}
        )
        self.currency_vef = self.env.ref("base.VEF")
        self.currency_usd = self.env.ref("base.USD")
        (self.currency_vef | self.currency_usd).write({"active": True})
        self.company.write(
            {
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
            }
        )

        # Factura del 5-oct a 300 Bs/USD; cierre del 31-oct a 330; pago del 5-nov a
        # 345; reversión del 15-nov a 360 (tasas distintas a propósito). El 9-nov es
        # el "hoy" congelado: la reversión nace con esa fecha antes de moverse.
        for day, vef_per_usd in (
            ("2026-10-05", 300.0),
            ("2026-10-31", 330.0),
            ("2026-11-01", 340.0),
            ("2026-11-05", 345.0),
            ("2026-11-09", 345.0),
            ("2026-11-15", 360.0),
        ):
            self.env["res.currency.rate"].create(
                {
                    "name": day,
                    "currency_id": self.currency_usd.id,
                    "company_id": self.company.id,
                    "company_rate": 1.0 / vef_per_usd,
                    "inverse_company_rate": vef_per_usd,
                }
            )

        self.partner = self.env["res.partner"].create({"name": "Cliente Reval"})
        self.income = self.env["account.account"].search(
            [("account_type", "=", "income")], limit=1
        )
        self.provision_income = self.env["account.account"].create(
            {
                "name": "GANANCIA CAMBIARIA NO REALIZADA",
                "code": "711199",
                "account_type": "income_other",
                "company_ids": [(6, 0, [self.company.id])],
            }
        )
        self.provision_expense = self.env["account.account"].create(
            {
                "name": "PERDIDA CAMBIARIA NO REALIZADA",
                "code": "721199",
                "account_type": "expense",
                "company_ids": [(6, 0, [self.company.id])],
            }
        )
        self.journal = self.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", self.company.id)], limit=1
        )
        self.company.write(
            {
                "account_revaluation_journal_id": self.journal.id,
                "account_revaluation_income_provision_account_id": self.provision_income.id,
                "account_revaluation_expense_provision_account_id": self.provision_expense.id,
            }
        )
        self.product = self.env["product.product"].create(
            {"name": "Producto Reval", "type": "service"}
        )
        self.report = self.env.ref("account_reports.multicurrency_revaluation_report")

        # Diario de banco con métodos de pago con cuenta (la localización lo exige).
        account_bank = self.env["account.account"].create(
            {
                "name": "BANCO REVAL",
                "code": "100188",
                "account_type": "asset_cash",
                "company_ids": [(6, 0, [self.company.id])],
                "reconcile": True,
            }
        )
        pm_in = self.env["account.payment.method.line"].create(
            {
                "name": "Manual Inbound",
                "payment_method_id": self.env.ref("account.account_payment_method_manual_in").id,
                "payment_type": "inbound",
                "payment_account_id": account_bank.id,
            }
        )
        pm_out = self.env["account.payment.method.line"].create(
            {
                "name": "Manual Outbound",
                "payment_method_id": self.env.ref("account.account_payment_method_manual_out").id,
                "payment_type": "outbound",
                "payment_account_id": account_bank.id,
            }
        )
        self.bank_journal = self.env["account.journal"].create(
            {
                "name": "Bank Reval",
                "type": "bank",
                "code": "BNKRV2",
                "default_account_id": account_bank.id,
                "inbound_payment_method_line_ids": [(6, 0, pm_in.ids)],
                "outbound_payment_method_line_ids": [(6, 0, pm_out.ids)],
            }
        )

    # ------------------------------------------------------------------ helpers
    def _post_usd_invoice(self, move_type="out_invoice", amount=100.0):
        invoice = self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": self.partner.id,
                "invoice_date": "2026-10-05",
                "invoice_date_display": "2026-10-05",
                "date": "2026-10-05",
                "currency_id": self.currency_usd.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Servicio",
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": amount,
                            "account_id": self.income.id,
                            "tax_ids": [(5,)],
                        },
                    )
                ],
            }
        )
        invoice.with_context(move_action_post_alert=True).action_post()
        return invoice

    def _revaluation_wizard(self, reversal_date=None):
        self.env.flush_all()
        options = self.report.get_options(
            {
                "date": {
                    "mode": "single",
                    "filter": "custom",
                    "date_from": "2026-10-31",
                    "date_to": "2026-10-31",
                }
            }
        )
        values = {"reversal_date": reversal_date} if reversal_date else {}
        return self.env["account.multicurrency.revaluation.wizard"].with_context(
            multicurrency_revaluation_report_options=options
        ).create(values)

    def _create_entries(self, reversal_date=None):
        wizard = self._revaluation_wizard(reversal_date)
        move = self.env["account.move"].browse(wizard.create_entries()["res_id"])
        reversal = self.env["account.move"].search([("reversed_entry_id", "=", move.id)])
        return move, reversal

    def _foreign_by_account(self, move):
        """{account: (foreign_debit, foreign_credit)} del asiento."""
        return {
            line.account_id: (line.foreign_debit, line.foreign_credit)
            for line in move.line_ids
        }

    def _receivable_balances(self, account, up_to):
        lines = self.env["account.move.line"].search(
            [("account_id", "=", account.id), ("parent_state", "=", "posted"), ("date", "<=", up_to)]
        )
        return sum(lines.mapped("balance")), sum(lines.mapped("foreign_balance"))

    # -------------------------------------------------------------------- tests
    def test_adjustment_entry_has_zero_alternate_amounts(self):
        """Los 3.000 Bs del ajuste quedan en VEF y las líneas en 0 de alterno."""
        self._post_usd_invoice()
        move, reversal = self._create_entries()

        self.assertEqual(len(move.line_ids), 2)
        receivable = move.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )
        self.assertAlmostEqual(receivable.debit, 3000.0, places=2)
        for line in move.line_ids:
            self.assertEqual(line.foreign_debit, 0.0)
            self.assertEqual(line.foreign_credit, 0.0)
            self.assertEqual(line.foreign_balance, 0.0)
        self.assertEqual(move.foreign_balance, 0.0)

    def test_reversal_has_zero_alternate_amounts(self):
        """La reversión (también en bolívares) queda con 0 en la moneda alterna."""
        self._post_usd_invoice()
        move, reversal = self._create_entries()

        self.assertTrue(reversal)
        self.assertEqual(reversal.state, "posted")
        for line in reversal.line_ids:
            self.assertEqual(line.foreign_debit, 0.0)
            self.assertEqual(line.foreign_credit, 0.0)
        # En bolívares sí se anulan exactamente, también la cuenta por cobrar.
        self.assertAlmostEqual(
            sum(move.line_ids.mapped("balance")) + sum(reversal.line_ids.mapped("balance")),
            0.0,
            places=2,
        )
        receivable = (move | reversal).line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )
        self.assertAlmostEqual(sum(receivable.mapped("balance")), 0.0, places=2)

    def test_receivable_alternate_balance_does_not_change(self):
        """El saldo de la CxC en USD es 100 antes, durante y después del ajuste."""
        invoice = self._post_usd_invoice()
        receivable_account = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        ).account_id
        move, reversal = self._create_entries(reversal_date="2026-11-15")

        # Cierre: en bolívares sube 3.000, en dólares nada.
        bs, usd = self._receivable_balances(receivable_account, date(2026, 10, 31))
        self.assertAlmostEqual(bs, 33000.0, places=2)
        self.assertAlmostEqual(usd, 100.0, places=2)
        # Entre el cierre y la reversión la fecha de reversión se movió al 15-nov.
        bs, usd = self._receivable_balances(receivable_account, date(2026, 11, 10))
        self.assertAlmostEqual(bs, 33000.0, places=2)
        self.assertAlmostEqual(usd, 100.0, places=2)
        # Tras la reversión vuelve a 30.000 Bs y los dólares siguen igual.
        bs, usd = self._receivable_balances(receivable_account, date(2026, 11, 15))
        self.assertAlmostEqual(bs, 30000.0, places=2)
        self.assertAlmostEqual(usd, 100.0, places=2)

    def test_payment_between_adjustment_and_reversal_leaves_no_alternate_residue(self):
        """Pagada la factura entre el cierre y la reversión, no queda USD fantasma."""
        invoice = self._post_usd_invoice()
        receivable_account = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        ).account_id
        self._create_entries(reversal_date="2026-11-15")

        self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=invoice.ids
        ).create(
            {
                "payment_date": date(2026, 11, 5),
                "amount": 100.0,
                "currency_id": self.currency_usd.id,
                "journal_id": self.bank_journal.id,
            }
        )._create_payments()
        self.assertEqual(invoice.payment_state, "paid")

        # El ajuste de 3.000 Bs sigue vivo hasta la reversión, pero en USD es 0.
        bs, usd = self._receivable_balances(receivable_account, date(2026, 11, 10))
        self.assertAlmostEqual(bs, 3000.0, places=2)
        self.assertAlmostEqual(usd, 0.0, places=2)
        bs, usd = self._receivable_balances(receivable_account, date(2026, 11, 15))
        self.assertAlmostEqual(bs, 0.0, places=2)
        self.assertAlmostEqual(usd, 0.0, places=2)

    def test_payable_adjustment_is_also_zero_alternate(self):
        """Una factura de proveedor en USD (pérdida cambiaria) también queda en 0."""
        bill = self._post_usd_invoice(move_type="in_invoice")
        self.assertEqual(bill.state, "posted")
        move, reversal = self._create_entries()

        self.assertTrue(move.line_ids)
        for entry in (move, reversal):
            for line in entry.line_ids:
                self.assertEqual(line.foreign_debit, 0.0)
                self.assertEqual(line.foreign_credit, 0.0)

    def test_only_revaluation_lines_are_flagged(self):
        """La marca es de las líneas del asistente: un asiento manual en el mismo
        diario sigue calculando su valor en moneda alterna con la tasa de su fecha.
        """
        self._post_usd_invoice()
        move, reversal = self._create_entries()
        self.assertTrue(all(move.line_ids.mapped("not_foreign_recalculate")))
        self.assertTrue(all(reversal.line_ids.mapped("not_foreign_recalculate")))

        manual = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": self.journal.id,
                "date": "2026-10-31",
                "line_ids": [
                    (0, 0, {"account_id": self.provision_expense.id, "debit": 3300.0, "credit": 0.0}),
                    (0, 0, {"account_id": self.provision_income.id, "debit": 0.0, "credit": 3300.0}),
                ],
            }
        )
        manual.action_post()
        self.assertFalse(any(manual.line_ids.mapped("not_foreign_recalculate")))
        # 3.300 Bs / 330 = 10 USD: el cálculo normal sigue intacto.
        self.assertAlmostEqual(sum(manual.line_ids.mapped("foreign_debit")), 10.0, places=2)

    def test_preview_data_is_still_computed(self):
        """La vista previa del cuadro "Crear asiento de ajuste" no se rompe."""
        self._post_usd_invoice()
        wizard = self._revaluation_wizard()
        preview = json.loads(wizard.preview_data)
        self.assertEqual(
            [col["field"] for col in preview["options"]["columns"]],
            ["account_id", "name", "debit", "credit"],
        )
        self.assertTrue(preview["groups_vals"])
        # Los 3.000 Bs del ajuste siguen saliendo en débito y crédito.
        amounts = sorted(
            (cmd[2]["debit"], cmd[2]["credit"])
            for cmd in wizard._get_move_vals()["line_ids"]
        )
        self.assertEqual(amounts, [(0.0, 3000.0), (3000.0, 0.0)])
