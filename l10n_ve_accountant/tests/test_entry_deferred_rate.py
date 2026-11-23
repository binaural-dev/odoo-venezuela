"""Tasa diferida de los asientos manuales.

Facturas, notas, recibos y pagos exigen la tasa exacta de su fecha desde que se crean.
Un asiento manual se puede crear en borrador con fecha futura o sin tasa (queda con
foreign_rate = 0) y AL PUBLICAR se recalcula la tasa exacta de `date` (UserError si no
existe). Las cuotas de depreciacion (tasa manual) no se recalculan.
"""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from .common_rates import set_rate

THURSDAY = date(2026, 3, 5)
FRIDAY = date(2026, 3, 6)
SATURDAY = date(2026, 3, 7)
SUNDAY = date(2026, 3, 8)
MONDAY = date(2026, 3, 9)
FUTURE = date(2099, 1, 1)
RATE_THURSDAY = 38.0
RATE_FRIDAY = 40.0
NO_RATE = "There is no rate assigned"


@tagged("post_install", "-at_install", "l10n_ve_accountant_entry_deferred_rate")
class TestEntryDeferredRate(TransactionCase):
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

        self.partner = self.env["res.partner"].create({"name": "Deferred Rate Partner"})
        self.account_a = self._account("EDR-A", "100971", "asset_current", self.company)
        self.account_b = self._account("EDR-B", "100972", "liability_current", self.company)
        self.journal = self.env["account.journal"].create(
            {"name": "EDR General", "code": "EDRG", "type": "general", "company_id": self.company.id}
        )
        self.sale_journal = self.env["account.journal"].create(
            {
                "name": "EDR Sale",
                "code": "EDRS",
                "type": "sale",
                "company_id": self.company.id,
                "default_account_id": self._account(
                    "EDR-I", "400971", "income", self.company
                ).id,
            }
        )
        self.purchase_journal = self.env["account.journal"].create(
            {
                "name": "EDR Purchase",
                "code": "EDRP",
                "type": "purchase",
                "company_id": self.company.id,
                "default_account_id": self._account(
                    "EDR-E", "500971", "expense", self.company
                ).id,
            }
        )
        self.bank_account = self._account("EDR-BANK", "100973", "asset_cash", self.company)
        self.bank_journal = self.env["account.journal"].create(
            {
                "name": "EDR Bank",
                "code": "EDRB",
                "type": "bank",
                "company_id": self.company.id,
                "default_account_id": self.bank_account.id,
            }
        )
        for line in (
            self.bank_journal.inbound_payment_method_line_ids
            | self.bank_journal.outbound_payment_method_line_ids
        ).filtered(lambda l: not l.payment_account_id):
            line.payment_account_id = self.bank_account

    # ---- helpers

    def _account(self, name, code, account_type, company):
        return self.env["account.account"].create(
            {
                "name": name,
                "code": code,
                "account_type": account_type,
                "company_ids": [(6, 0, [company.id])],
            }
        )

    def _entry(self, day, **extra):
        vals = {
            "move_type": "entry",
            "journal_id": self.journal.id,
            "date": day,
            "line_ids": [
                (0, 0, {"account_id": self.account_a.id, "debit": 1000.0}),
                (0, 0, {"account_id": self.account_b.id, "credit": 1000.0}),
            ],
        }
        vals.update(extra)
        return self.env["account.move"].create(vals)

    def _invoice_vals(self, move_type, day, **extra):
        vals = {
            "move_type": move_type,
            "partner_id": self.partner.id,
            "journal_id": (
                self.purchase_journal
                if move_type in ("in_invoice", "in_refund", "in_receipt")
                else self.sale_journal
            ).id,
            "invoice_date": day,
            # explicito: por defecto es "hoy" y l10n_ve_invoice exige que no pase de `date`
            "invoice_date_display": day,
            "date": day,
        }
        vals.update(extra)
        return vals

    def _payment(self, day):
        return self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner.id,
                "amount": 100.0,
                "journal_id": self.bank_journal.id,
                "date": day,
            }
        )

    def _patch_cron(self):
        """El cron hace commit/rollback reales, prohibidos dentro de un test."""
        self.patch(
            self.registry["ir.cron"], "_commit_progress", lambda *a, **k: 1
        )
        self.patch(self.env.cr, "rollback", lambda: None)

    # ---- (a), (b), (c): ciclo basico

    def test_future_manual_entry_is_created_in_draft_without_rate(self):
        move = self._entry(FUTURE)

        self.assertEqual(move.state, "draft")
        self.assertEqual(move.foreign_rate, 0)
        self.assertEqual(move.foreign_inverse_rate, 0)

    def test_post_without_rate_on_its_date_raises(self):
        move = self._entry(SATURDAY)
        self.assertEqual(move.foreign_rate, 0)

        with self.assertRaisesRegex(UserError, NO_RATE):
            move.action_post()

        self.assertEqual(move.state, "draft")

    def test_post_with_rate_loaded_uses_exact_rate_in_header_and_lines(self):
        move = self._entry(SATURDAY)
        self.assertEqual(move.foreign_rate, 0)
        set_rate(self.env, self.usd, SATURDAY, self.company, 45.0)

        move.action_post()

        self.assertEqual(move.state, "posted")
        self.assertAlmostEqual(move.foreign_rate, 45.0, places=4)
        self.assertAlmostEqual(move.foreign_inverse_rate, 1 / 45.0, places=8)
        for line in move.line_ids:
            with self.subTest(account=line.account_id.code):
                self.assertAlmostEqual(abs(line.foreign_balance), 1000.0 / 45.0, places=2)
        self.assertEqual(sum(move.line_ids.mapped("foreign_debit")), sum(move.line_ids.mapped("foreign_credit")))

    # ---- (d), (e): tasa manual

    def test_manual_rate_is_not_recalculated_on_post(self):
        """Como una cuota de depreciacion: la tasa manual cargada se respeta."""
        set_rate(self.env, self.usd, SATURDAY, self.company, 99.0)
        move = self._entry(
            SATURDAY,
            manually_set_rate=True,
            foreign_rate=45.0,
            foreign_inverse_rate=1 / 45.0,
        )

        move.action_post()

        self.assertEqual(move.state, "posted")
        self.assertAlmostEqual(move.foreign_rate, 45.0, places=4)

    def test_manual_flag_without_rate_is_recalculated_on_post(self):
        """Como un duplicado/copia recurrente: manually_set_rate=True pero tasa 0."""
        move = self._entry(SATURDAY, manually_set_rate=True)
        self.assertEqual(move.foreign_rate, 0)
        set_rate(self.env, self.usd, SATURDAY, self.company, 50.0)

        move.action_post()

        self.assertAlmostEqual(move.foreign_rate, 50.0, places=4)

    # ---- (f): documentos que exigen tasa exacta al crearse

    def test_invoice_credit_note_and_receipt_require_exact_rate_on_create(self):
        for move_type in ("out_invoice", "in_invoice", "out_refund", "out_receipt"):
            with self.subTest(move_type=move_type), self.assertRaisesRegex(UserError, NO_RATE):
                self.env["account.move"].create(self._invoice_vals(move_type, SATURDAY))

    def test_invoice_with_manual_rate_on_date_without_rate_raises_on_create(self):
        with self.assertRaisesRegex(UserError, NO_RATE):
            self.env["account.move"].create(
                self._invoice_vals(
                    "out_invoice",
                    SATURDAY,
                    manually_set_rate=True,
                    foreign_rate=45.0,
                    foreign_inverse_rate=1 / 45.0,
                )
            )

    def test_payment_entry_requires_exact_rate_on_create(self):
        payment = self._payment(FRIDAY)
        ok = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": self.journal.id,
                "date": FRIDAY,
                "origin_payment_id": payment.id,
            }
        )
        self.assertFalse(ok._is_rate_deferrable())
        # el que falla va al final: un create abortado deja computos pendientes en el cache
        with self.assertRaisesRegex(UserError, NO_RATE):
            self.env["account.move"].create(
                {
                    "move_type": "entry",
                    "journal_id": self.journal.id,
                    "date": SATURDAY,
                    "origin_payment_id": payment.id,
                }
            )

    def test_hook_values(self):
        Move = self.env["account.move"]
        self.assertTrue(Move.create({"move_type": "entry", "journal_id": self.journal.id, "date": FRIDAY})._is_rate_deferrable())
        self.assertFalse(Move.create(self._invoice_vals("out_invoice", FRIDAY))._is_rate_deferrable())
        diff = Move.create(
            {
                "move_type": "entry",
                "journal_id": self.journal.id,
                "date": FRIDAY,
                "l10n_ve_exchange_foreign_diff_entry": True,
            }
        )
        self.assertFalse(diff._is_rate_deferrable())
        self.assertFalse(
            Move.with_context(is_statement_line=True)
            .new({"move_type": "entry", "journal_id": self.journal.id, "date": FRIDAY})
            ._is_rate_deferrable()
        )

    # ---- (g): extracto e inventario

    def test_bank_statement_line_requires_exact_rate_on_create(self):
        StLine = self.env["account.bank.statement.line"]
        ok = StLine.create(
            {
                "date": FRIDAY,
                "payment_ref": "EDR ok",
                "amount": 100.0,
                "journal_id": self.bank_journal.id,
            }
        )
        self.assertFalse(ok.move_id._is_rate_deferrable())
        # el que falla va al final: un create abortado deja computos pendientes en el cache
        with self.assertRaisesRegex(UserError, NO_RATE):
            StLine.create(
                {
                    "date": SATURDAY,
                    "payment_ref": "EDR no rate",
                    "amount": 100.0,
                    "journal_id": self.bank_journal.id,
                }
            )

    def test_stock_entry_is_not_deferrable(self):
        if "stock_move_ids" not in self.env["account.move"]._fields:
            self.skipTest("stock_account is not installed")
        product = self.env["product.product"].create({"name": "EDR Product"})
        stock_move = self.env["stock.move"].create(
            {
                "product_id": product.id,
                "product_uom_qty": 1.0,
                "location_id": self.env.ref("stock.stock_location_suppliers").id,
                "location_dest_id": self.env.ref("stock.stock_location_stock").id,
            }
        )
        move = self._entry(FRIDAY)
        self.assertTrue(move._is_rate_deferrable())
        stock_move.account_move_id = move.id
        self.assertFalse(move._is_rate_deferrable())
        # el core crea el asiento de inventario y lo vincula DESPUES: sin tasa en su
        # fecha, publicarlo ya vinculado debe fallar y no quedar con tasa 0
        late = self._entry(SATURDAY)
        stock_move.account_move_id = late.id
        with self.assertRaisesRegex(UserError, "cannot be posted without an exchange rate"):
            late._post()

    # ---- (h): publicacion programada

    def test_soft_post_of_future_entry_only_schedules_it(self):
        move = self._entry(FUTURE)

        move._post(soft=True)

        self.assertEqual(move.state, "draft")
        self.assertEqual(move.auto_post, "at_date")
        self.assertEqual(move.foreign_rate, 0)

    # ---- (i): periodo bloqueado

    def test_lock_date_moving_the_date_does_not_leave_a_posted_entry_without_rate(self):
        self.company.sudo().fiscalyear_lock_date = FRIDAY
        move = self._entry(THURSDAY)
        self.assertAlmostEqual(move.foreign_rate, RATE_THURSDAY, places=4)

        with self.assertRaises(UserError):
            move.action_post()

        self.assertEqual(move.state, "draft")

    # ---- (j): cron

    def test_cron_leaves_entry_without_rate_in_draft_and_posts_the_rest(self):
        self._patch_cron()
        bad = self._entry(SATURDAY, auto_post="at_date")
        good = self._entry(FRIDAY, auto_post="at_date")

        self.env["account.move"]._autopost_draft_entries()

        self.assertEqual(good.state, "posted")
        self.assertAlmostEqual(good.foreign_rate, RATE_FRIDAY, places=4)
        self.assertEqual(bad.state, "draft")
        self.assertEqual(bad.auto_post, "no")

    # ---- (k): reverso

    def test_reversal_of_posted_entry_inherits_original_rate(self):
        move = self._entry(FRIDAY)
        move.action_post()
        set_rate(self.env, self.usd, MONDAY, self.company, 50.0)

        for day in (SUNDAY, MONDAY):
            with self.subTest(reversal_date=day):
                reverse = move._reverse_moves([{"date": day}])
                self.assertEqual(reverse.reversed_entry_id, move)
                self.assertAlmostEqual(reverse.foreign_rate, RATE_FRIDAY, places=4)
                self.assertAlmostEqual(
                    reverse.foreign_inverse_rate, move.foreign_inverse_rate, places=8
                )

    # ---- (l): compania sin moneda alterna

    def test_company_without_alternate_currency_is_not_affected(self):
        other = self.env["res.company"].create(
            {"name": "EDR No Alternate", "currency_id": self.vef.id}
        )
        self.assertFalse(other.foreign_currency_id)
        self.env.user.company_ids = [(4, other.id)]
        account_a = self._account("EDR-OA", "100974", "asset_current", other)
        account_b = self._account("EDR-OB", "100975", "liability_current", other)
        journal = self.env["account.journal"].create(
            {"name": "EDR Other", "code": "EDRO", "type": "general", "company_id": other.id}
        )
        env = self.env(
            context=dict(self.env.context, allowed_company_ids=[other.id, self.company.id])
        )
        self.assertEqual(env.company, other)

        move = env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": journal.id,
                "company_id": other.id,
                "date": SATURDAY,
                "line_ids": [
                    (0, 0, {"account_id": account_a.id, "debit": 1000.0}),
                    (0, 0, {"account_id": account_b.id, "credit": 1000.0}),
                ],
            }
        )
        self.assertFalse(move.foreign_currency_id)

        move.action_post()

        self.assertEqual(move.state, "posted")

    # ---- onchange de fecha

    def test_date_onchange_warns_only_when_rate_is_missing(self):
        move = self.env["account.move"].new(
            {"move_type": "entry", "journal_id": self.journal.id, "date": SATURDAY}
        )
        result = move._onchange_date_rate_warning()
        self.assertIn("warning", result)

        move.date = FRIDAY
        self.assertIsNone(move._onchange_date_rate_warning())
