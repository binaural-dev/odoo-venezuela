"""Un asiento sin tasa exacta (fin de semana, feriado, fecha futura) toma la ultima
tasa anterior a su fecha; facturas, notas, recibos y asientos de pago siguen exigiendo
la tasa exacta. La tasa queda fija desde que se guarda.
"""

from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from .common_rates import set_rate

THURSDAY = date(2026, 3, 5)
FRIDAY = date(2026, 3, 6)
SATURDAY = date(2026, 3, 7)
SUNDAY = date(2026, 3, 8)
FUTURE = date(2099, 1, 1)
# 1 USD = 38 / 40 VEF
RATE_THURSDAY = 38.0
RATE_FRIDAY = 40.0


@tagged("post_install", "-at_install", "l10n_ve_accountant_entry_last_rate")
class TestEntryLastRate(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.vef = self.env.ref("base.VEF")
        self.usd = self.env.ref("base.USD")
        self.vef.active = True
        self.usd.active = True
        self.company.write(
            {"currency_id": self.vef.id, "foreign_currency_id": self.usd.id}
        )
        self.env.user.write(
            {"company_ids": [(4, self.company.id)], "company_id": self.company.id}
        )
        self.Rate = self.env["res.currency.rate"].sudo()
        self.Rate.search(
            [("currency_id", "=", self.usd.id), ("company_id", "=", self.company.id)]
        ).unlink()
        set_rate(self.env, self.usd, THURSDAY, self.company, RATE_THURSDAY)
        set_rate(self.env, self.usd, FRIDAY, self.company, RATE_FRIDAY)

        self.partner = self.env["res.partner"].create({"name": "Entry Last Rate Partner"})
        self.account_a = self._account("ELR-A", "100981", "asset_current", self.company)
        self.account_b = self._account("ELR-B", "100982", "liability_current", self.company)
        self.journal = self.env["account.journal"].create(
            {"name": "ELR General", "code": "ELRG", "type": "general", "company_id": self.company.id}
        )
        self.sale_journal = self.env["account.journal"].create(
            {
                "name": "ELR Sale",
                "code": "ELRS",
                "type": "sale",
                "company_id": self.company.id,
                "default_account_id": self._account(
                    "ELR-I", "400981", "income", self.company
                ).id,
            }
        )
        self.purchase_journal = self.env["account.journal"].create(
            {
                "name": "ELR Purchase",
                "code": "ELRP",
                "type": "purchase",
                "company_id": self.company.id,
                "default_account_id": self._account(
                    "ELR-E", "600981", "expense", self.company
                ).id,
            }
        )

    def _account(self, name, code, account_type, company):
        return self.env["account.account"].create(
            {
                "name": name,
                "code": code,
                "account_type": account_type,
                "company_ids": [(6, 0, [company.id])],
            }
        )

    def _entry_vals(self, day, **extra):
        vals = {"move_type": "entry", "journal_id": self.journal.id, "date": day}
        vals.update(extra)
        return vals

    def _entry_with_lines(self, day, **extra):
        return self.env["account.move"].create(
            self._entry_vals(
                day,
                line_ids=[
                    (0, 0, {"account_id": self.account_a.id, "debit": 1000.0}),
                    (0, 0, {"account_id": self.account_b.id, "credit": 1000.0}),
                ],
                **extra,
            )
        )

    def _invoice_vals(self, move_type, day, **extra):
        journal = (
            self.purchase_journal if move_type.startswith("in_") else self.sale_journal
        )
        vals = {
            "move_type": move_type,
            "partner_id": self.partner.id,
            "journal_id": journal.id,
            "invoice_date": day,
            # explicito: por defecto es "hoy" y l10n_ve_invoice exige que no pase de `date`
            "invoice_date_display": day,
            "date": day,
        }
        vals.update(extra)
        return vals

    def _updated_messages(self, move):
        return move.message_ids.filtered(lambda m: "The rate has been updated" in (m.body or ""))

    # ---- asientos: ultima tasa anterior

    def test_entry_on_weekend_uses_last_previous_rate(self):
        for day in (SATURDAY, SUNDAY):
            with self.subTest(day=day):
                move = self.env["account.move"].create(self._entry_vals(day))
                self.assertAlmostEqual(move.foreign_rate, RATE_FRIDAY, places=4)
                self.assertAlmostEqual(move.foreign_inverse_rate, 1 / RATE_FRIDAY, places=8)

    def test_entry_on_future_date_uses_last_existing_rate(self):
        move = self.env["account.move"].create(self._entry_vals(FUTURE))

        self.assertAlmostEqual(move.foreign_rate, RATE_FRIDAY, places=4)

    def test_entry_on_holiday_between_rates_uses_earlier_rate(self):
        """Un feriado entre dos dias con tasa: se usa la del dia habil anterior."""
        set_rate(self.env, self.usd, date(2026, 3, 10), self.company, 50.0)
        move = self.env["account.move"].create(self._entry_vals(date(2026, 3, 9)))

        self.assertAlmostEqual(move.foreign_rate, RATE_FRIDAY, places=4)

    def test_entry_rate_stays_fixed_when_a_rate_is_added_later(self):
        move = self.env["account.move"].create(self._entry_vals(SATURDAY))
        set_rate(self.env, self.usd, SATURDAY, self.company, 99.0)

        self.assertAlmostEqual(move.foreign_rate, RATE_FRIDAY, places=4)

    def test_entry_without_any_previous_rate_still_raises(self):
        with self.assertRaisesRegex(UserError, "There is no rate assigned"):
            self.env["account.move"].create(self._entry_vals(date(2026, 3, 1)))

    def test_exchange_diff_entry_uses_last_previous_rate(self):
        move = self.env["account.move"].create(
            self._entry_vals(SATURDAY, l10n_ve_exchange_foreign_diff_entry=True)
        )

        self.assertAlmostEqual(move.foreign_rate, RATE_FRIDAY, places=4)

    def test_entry_lines_are_consistent_with_the_rate_used(self):
        """El USD de cada linea sale de la tasa de la fecha usada (la del viernes)."""
        move = self._entry_with_lines(SATURDAY)

        for line in move.line_ids:
            with self.subTest(account=line.account_id.code):
                ratio = abs(line.foreign_balance / line.balance)
                self.assertAlmostEqual(ratio, 1 / move.foreign_rate, places=6)
                self.assertAlmostEqual(abs(line.foreign_balance), 1000.0 / RATE_FRIDAY, places=2)

    def test_reverse_of_weekend_entry(self):
        move = self._entry_with_lines(SATURDAY)
        move.action_post()

        reverse = move._reverse_moves([{"date": SUNDAY}])

        self.assertEqual(reverse.reversed_entry_id, move)
        self.assertAlmostEqual(reverse.foreign_rate, RATE_FRIDAY, places=4)
        for line in reverse.line_ids:
            self.assertAlmostEqual(abs(line.foreign_balance), 1000.0 / RATE_FRIDAY, places=2)

    # ---- documentos que siguen exigiendo tasa exacta

    def test_invoices_and_notes_still_require_exact_rate(self):
        for move_type in ("out_invoice", "in_invoice", "out_refund", "in_refund"):
            with self.subTest(move_type=move_type), self.assertRaisesRegex(
                UserError, "There is no rate assigned"
            ):
                self.env["account.move"].create(self._invoice_vals(move_type, SATURDAY))

    def test_invoice_with_exact_rate_is_created(self):
        move = self.env["account.move"].create(self._invoice_vals("out_invoice", FRIDAY))

        self.assertAlmostEqual(move.foreign_rate, RATE_FRIDAY, places=4)

    def test_receipts_still_require_exact_rate(self):
        for move_type in ("out_receipt", "in_receipt"):
            with self.subTest(move_type=move_type), self.assertRaisesRegex(
                UserError, "There is no rate assigned"
            ):
                self.env["account.move"].create(self._invoice_vals(move_type, SATURDAY))

    def test_payment_entry_still_requires_exact_rate(self):
        """Un asiento con `origin_payment_id` (asiento de pago) exige tasa exacta."""
        bank = self._account("ELR-BANK", "100983", "asset_cash", self.company)
        bank_journal = self.env["account.journal"].create(
            {
                "name": "ELR Bank",
                "code": "ELRB",
                "type": "bank",
                "company_id": self.company.id,
                "default_account_id": bank.id,
            }
        )
        for line in (
            bank_journal.inbound_payment_method_line_ids
            | bank_journal.outbound_payment_method_line_ids
        ).filtered(lambda l: not l.payment_account_id):
            line.payment_account_id = bank
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner.id,
                "amount": 100.0,
                "journal_id": bank_journal.id,
                "date": FRIDAY,
            }
        )
        ok = self.env["account.move"].create(
            self._entry_vals(FRIDAY, origin_payment_id=payment.id)
        )
        self.assertTrue(ok._is_exact_rate_required())
        # el que falla va al final: un create abortado deja computos pendientes en el cache
        with self.assertRaisesRegex(UserError, "There is no rate assigned"):
            self.env["account.move"].create(
                self._entry_vals(SATURDAY, origin_payment_id=payment.id)
            )

    def test_hook_values(self):
        Move = self.env["account.move"]
        self.assertFalse(Move.create(self._entry_vals(FRIDAY))._is_exact_rate_required())
        self.assertTrue(
            Move.create(self._invoice_vals("out_invoice", FRIDAY))._is_exact_rate_required()
        )
        diff = Move.create(self._entry_vals(FRIDAY, l10n_ve_exchange_foreign_diff_entry=True))
        self.assertFalse(diff._is_exact_rate_required())

    # ---- multicompania

    def test_rate_is_looked_up_in_the_company_of_the_move(self):
        other = self.env["res.company"].create(
            {
                "name": "ELR Other Company",
                "currency_id": self.vef.id,
                "foreign_currency_id": self.usd.id,
            }
        )
        self.env.user.company_ids = [(4, other.id)]
        set_rate(self.env, self.usd, FRIDAY, other, 70.0)
        journal = self.env["account.journal"].create(
            {"name": "ELR Other General", "code": "ELRO", "type": "general", "company_id": other.id}
        )
        env = self.env(
            context=dict(self.env.context, allowed_company_ids=[self.company.id, other.id])
        )
        self.assertEqual(env.company, self.company)

        move = env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": journal.id,
                "company_id": other.id,
                "date": SATURDAY,
            }
        )

        self.assertAlmostEqual(move.foreign_rate, 70.0, places=4)

    # ---- tasa manual

    def test_entry_with_manual_rate_without_exact_rate_does_not_fail(self):
        move = self.env["account.move"].create(
            self._entry_vals(
                SATURDAY,
                manually_set_rate=True,
                foreign_rate=45.0,
                foreign_inverse_rate=1 / 45.0,
            )
        )

        self.assertAlmostEqual(move.foreign_rate, 45.0, places=4)
        message = self._updated_messages(move)
        self.assertEqual(len(message), 1)
        self.assertIn("from 40.0 to 45.0", message.body)

    def test_entry_with_manual_rate_and_no_previous_rate_does_not_post_message(self):
        move = self.env["account.move"].create(
            self._entry_vals(
                date(2026, 3, 1),
                manually_set_rate=True,
                foreign_rate=45.0,
                foreign_inverse_rate=1 / 45.0,
            )
        )

        self.assertAlmostEqual(move.foreign_rate, 45.0, places=4)
        self.assertFalse(self._updated_messages(move))

    def test_invoice_with_manual_rate_on_date_without_rate_no_longer_fails(self):
        """Nuevo comportamiento: antes `create()` lanzaba aunque la tasa del dia no se usara."""
        move = self.env["account.move"].create(
            self._invoice_vals(
                "out_invoice",
                SATURDAY,
                manually_set_rate=True,
                foreign_rate=45.0,
                foreign_inverse_rate=1 / 45.0,
            )
        )

        self.assertAlmostEqual(move.foreign_rate, 45.0, places=4)
        self.assertFalse(self._updated_messages(move))

    # ---- onchange (registro virtual)

    def test_virtual_entry_on_weekend_does_not_raise(self):
        move = self.env["account.move"].new(
            {"move_type": "entry", "journal_id": self.journal.id, "date": SATURDAY}
        )

        self.assertAlmostEqual(move.foreign_rate, RATE_FRIDAY, places=4)

    def test_virtual_invoice_on_weekend_raises(self):
        move = self.env["account.move"].new(self._invoice_vals("out_invoice", SATURDAY))

        with self.assertRaisesRegex(UserError, "There is no rate assigned"):
            move.foreign_rate  # noqa: B018
