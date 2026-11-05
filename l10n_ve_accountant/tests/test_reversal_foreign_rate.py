from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_accountant_reversal_rate")
class TestReversalForeignRate(TransactionCase):
    """Ticket #15114: el reverso del asiento de un pago debe valorar la moneda
    alterna a la tasa de la fecha del pago ORIGINAL, no a la del dia del reverso.
    """

    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.env.user.write(
            {"company_ids": [(4, self.company.id)], "company_id": self.company.id}
        )
        self.currency_vef = self.env.ref("base.VEF")
        self.currency_usd = self.env.ref("base.USD")

        # Compañia: moneda VEF, moneda alterna USD.
        self.company.write(
            {
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
            }
        )

        self.Rate = self.env["res.currency.rate"]
        self.today = fields.Date.today()
        self.day1 = self.today - timedelta(days=10)
        self.day2 = self.today

        # Dos tasas en dos fechas distintas:
        #   Dia 1 -> 1 USD = 40 VEF ; Dia 2 -> 1 USD = 50 VEF
        self._set_usd_rate(self.day1, 40.0)
        self._set_usd_rate(self.day2, 50.0)

        self.partner = self.env["res.partner"].create({"name": "Partner Reverso"})

        self.account_bank = self.env["account.account"].create(
            {
                "name": "BANK ACCOUNT",
                "code": "100199",
                "account_type": "asset_cash",
                "company_ids": [(6, 0, [self.company.id])],
                "reconcile": True,
            }
        )

        self.manual_in = self.env.ref("account.account_payment_method_manual_in")
        self.manual_out = self.env.ref("account.account_payment_method_manual_out")
        self.pm_line_in = self.env["account.payment.method.line"].create(
            {
                "name": "Manual Inbound",
                "payment_method_id": self.manual_in.id,
                "payment_type": "inbound",
                "payment_account_id": self.account_bank.id,
            }
        )
        self.pm_line_out = self.env["account.payment.method.line"].create(
            {
                "name": "Manual Outbound",
                "payment_method_id": self.manual_out.id,
                "payment_type": "outbound",
                "payment_account_id": self.account_bank.id,
            }
        )

        # El diario bancario debe definir AMBOS métodos (inbound y outbound) con
        # cuenta asignada: l10n_ve_accountant exige cuenta en los métodos de
        # pago bancarios, y si se omite el outbound Odoo crea uno por defecto
        # sin cuenta y la constraint falla.
        self.bank_journal = self.env["account.journal"].create(
            {
                "name": "Bank Reverso",
                "type": "bank",
                "code": "BNKRV",
                "currency_id": self.currency_vef.id,
                "default_account_id": self.account_bank.id,
                "inbound_payment_method_line_ids": [(6, 0, self.pm_line_in.ids)],
                "outbound_payment_method_line_ids": [(6, 0, self.pm_line_out.ids)],
            }
        )

    def _set_usd_rate(self, date, vef_per_usd):
        """Crea o actualiza la tasa USD (VEF por USD) para una fecha."""
        rate = self.Rate.search(
            [
                ("name", "=", date),
                ("currency_id", "=", self.currency_usd.id),
                ("company_id", "=", self.company.id),
            ],
            limit=1,
        )
        vals = {
            "company_rate": 1.0 / vef_per_usd,
            "inverse_company_rate": vef_per_usd,
        }
        if rate:
            rate.write(vals)
            return rate
        return self.Rate.create(
            dict(
                vals,
                name=date,
                currency_id=self.currency_usd.id,
                company_id=self.company.id,
            )
        )

    def _create_posted_payment(self, amount, date):
        payment = (
            self.env["account.payment"]
            .with_company(self.company)
            .create(
                {
                    "amount": amount,
                    "date": date,
                    "currency_id": self.currency_vef.id,
                    "payment_type": "inbound",
                    "partner_type": "customer",
                    "partner_id": self.partner.id,
                    "journal_id": self.bank_journal.id,
                    "payment_method_line_id": self.pm_line_in.id,
                }
            )
        )
        payment.action_post()
        return payment

    def test_payment_reversal_inherits_original_rate(self):
        """El reverso hereda la tasa del pago original (Dia 1), no la del reverso."""
        amount = 200.0  # 200 VEF -> $5 @40 (Dia 1) ; seria $4 @50 (Dia 2)

        payment = self._create_posted_payment(amount, self.day1)
        move = payment.move_id
        self.assertEqual(move.move_type, "entry")

        orig_debit = sum(move.line_ids.mapped("foreign_debit"))
        orig_credit = sum(move.line_ids.mapped("foreign_credit"))
        # Sanity: el pago original quedo valorado a la tasa del Dia 1 (40).
        self.assertAlmostEqual(orig_debit, 5.0, places=2)
        self.assertAlmostEqual(orig_credit, 5.0, places=2)

        # Reverso del asiento del pago con fecha del Dia 2 (tasa 50).
        reversal = move._reverse_moves([{"date": self.day2}])
        self.assertEqual(reversal.reversed_entry_id, move)

        rev_debit = sum(reversal.line_ids.mapped("foreign_debit"))
        rev_credit = sum(reversal.line_ids.mapped("foreign_credit"))

        # El reverso DEBE valorar a la tasa del Dia 1 ($5), revirtiendo exacto
        # el monto en moneda alterna del pago original...
        self.assertAlmostEqual(
            rev_debit,
            orig_debit,
            places=2,
            msg="El debito alterno del reverso debe heredar la tasa del pago original",
        )
        self.assertAlmostEqual(
            rev_credit,
            orig_credit,
            places=2,
            msg="El credito alterno del reverso debe heredar la tasa del pago original",
        )
        # ...y NO a la tasa del dia del reverso ($4), que es el bug del ticket.
        self.assertNotAlmostEqual(
            rev_debit,
            4.0,
            places=2,
            msg="El reverso no debe recalcular la moneda alterna a la tasa del dia del reverso",
        )
        # El reverso cuadra en moneda alterna.
        self.assertAlmostEqual(rev_debit, rev_credit, places=2)

    def test_same_day_reversal_unaffected(self):
        """Reverso el mismo dia del pago: sin diferencia de tasa (no regresion)."""
        amount = 200.0
        payment = self._create_posted_payment(amount, self.day2)  # Dia 2 (tasa 50)
        move = payment.move_id

        reversal = move._reverse_moves([{"date": self.day2}])

        rev_debit = sum(reversal.line_ids.mapped("foreign_debit"))
        # 200 VEF @50 = $4, mismo dia => coincide con el original.
        self.assertAlmostEqual(rev_debit, 4.0, places=2)
        self.assertAlmostEqual(
            rev_debit, sum(move.line_ids.mapped("foreign_debit")), places=2
        )
