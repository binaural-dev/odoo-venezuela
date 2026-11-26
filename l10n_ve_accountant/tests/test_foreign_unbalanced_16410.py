"""Ticket 16410: a bank line in Bs must follow its counterpart when it moves to $.

A statement line in Bs is created with the suspense account as counterpart (the
bank line takes its $ at the rate of the day). Reconciling it against an account
in $ rewrites the counterpart to USD 1.700 for 1.700.000 Bs (the bank's rate).
The bank line has to be recomputed, otherwise the entry is balanced in Bs and
not in $.
"""
from datetime import timedelta

from odoo import fields
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install", "foreign_unbalanced_16410")
class TestForeignUnbalanced16410(TransactionCase):
    def setUp(self):
        super().setUp()
        # La pestana de apuntes exige account.group_account_readonly
        self.env.user.write({"group_ids": [
            (4, self.env.ref("account.group_account_readonly").id),
            (4, self.env.ref("account.group_account_user").id),
            (4, self.env.ref("account.group_account_manager").id),
        ]})
        self.usd = self.env.ref("base.USD")
        self.vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")
        self.company.write({
            "currency_id": self.vef.id,
            "foreign_currency_id": self.usd.id,
            "account_fiscal_country_id": self.env.ref("base.ve").id,
            "country_id": self.env.ref("base.ve").id,
        })
        today = fields.Date.today()
        Rate = self.env["res.currency.rate"]
        Rate.create({"name": today, "currency_id": self.vef.id,
                     "inverse_company_rate": 1.0, "company_id": self.company.id})
        # Tasa del dia 886,2 Bs/USD (como en produccion); el banco uso 1000.
        Rate.create({"name": today, "currency_id": self.usd.id,
                     "inverse_company_rate": 886.2, "company_id": self.company.id})
        self.today = today
        acc_bank = self.env["account.account"].create({
            "name": "BANCO BS", "code": "100200", "account_type": "asset_cash",
            "company_ids": [(6, 0, [self.company.id])], "reconcile": True,
        })
        pm_in = self.env["account.payment.method.line"].create({
            "name": "In", "payment_type": "inbound", "payment_account_id": acc_bank.id,
            "payment_method_id": self.env.ref("account.account_payment_method_manual_in").id,
        })
        pm_out = self.env["account.payment.method.line"].create({
            "name": "Out", "payment_type": "outbound", "payment_account_id": acc_bank.id,
            "payment_method_id": self.env.ref("account.account_payment_method_manual_out").id,
        })
        # Sin moneda en el diario, como los de produccion: acepta lineas en USD.
        self.bank = self.env["account.journal"].create({
            "name": "Banco Bs", "type": "bank", "code": "BBS",
            "default_account_id": acc_bank.id,
            "inbound_payment_method_line_ids": [(6, 0, pm_in.ids)],
            "outbound_payment_method_line_ids": [(6, 0, pm_out.ids)],
        })
        self.counterpart = self.env["account.account"].create({
            "name": "Contrapartida USD", "code": "999991",
            "account_type": "asset_current",
            "company_ids": [(6, 0, [self.company.id])],
        })

    def _foreign_imbalance(self, move):
        return sum(move.line_ids.mapped("foreign_debit")) - sum(move.line_ids.mapped("foreign_credit"))

    def _statement_line(self):
        return self.env["account.bank.statement.line"].create({
            "journal_id": self.bank.id, "date": self.today,
            "payment_ref": "pago en Bs", "amount": -1700000.0,
        })

    def test_01_control_entry_created_in_one_shot(self):
        """Control: both lines exist when the entry is created."""
        with Form(self.env["account.move"].with_context(
                default_move_type="entry", default_journal_id=self.bank.id)) as f:
            f.date = self.today
            with f.line_ids.new() as line:
                line.account_id = self.bank.default_account_id
                line.credit = 1700000.0
            with f.line_ids.new() as line:
                line.account_id = self.counterpart
                line.currency_id = self.usd
                line.amount_currency = 1700.0
                line.debit = 1700000.0
        move = f.save()
        move.action_post()
        self.assertAlmostEqual(self._foreign_imbalance(move), 0.0, places=2)

    def test_02_statement_counterpart_moved_to_usd_with_form(self):
        """The entry of the statement line, edited so its counterpart is USD 1.700."""
        move = self._statement_line().move_id
        # Al crearse, el banco toma el $ a la tasa del dia: 1.700.000 / 886,2
        bank_line = move.line_ids.filtered(lambda l: l.account_id == self.bank.default_account_id)
        self.assertAlmostEqual(bank_line.foreign_credit, 1700000.0 / 886.2, places=2)
        move.button_draft()
        suspense = move.line_ids - bank_line
        with Form(move) as f:
            with f.line_ids.edit(list(move.line_ids).index(suspense)) as line:
                line.account_id = self.counterpart
                line.currency_id = self.usd
                line.amount_currency = 1700.0
                line.debit = 1700000.0
        move.action_post()
        self.assertAlmostEqual(bank_line.foreign_credit, 1700.0, places=2)
        self.assertAlmostEqual(self._foreign_imbalance(move), 0.0, places=2)

    def _edit_suspense(self, st_line, values):
        """What the bank reconciliation widget does when a line is edited."""
        _liquidity, suspense, _other = st_line._seek_for_lines()
        st_line.edit_reconcile_line(suspense.id, values)
        move = st_line.move_id
        counterpart = move.line_ids.filtered(lambda l: l.account_id == self.counterpart)
        remainder = move.line_ids - counterpart - move.line_ids.filtered(
            lambda l: l.account_id == self.bank.default_account_id)
        return move, counterpart, remainder

    def test_03_edit_with_forced_balance_follows_the_rate_of_the_date(self):
        """USD 1.700 with a balance forced to 1.700.000 Bs is set back to the rate of the day.

        The edit dialog lets the user type both fields, and the core stored them as they
        came (implicit rate 1000 against 886,2 of the day). The amount in USD wins, the
        balance is USD 1.700 x 886,2 and the difference stays in the suspense account.
        """
        st_line = self._statement_line()
        if not hasattr(st_line, "edit_reconcile_line"):
            self.skipTest("account_accountant (enterprise) is not installed")
        move, counterpart, remainder = self._edit_suspense(st_line, {
            "account_id": self.counterpart.id,
            "currency_id": self.usd.id,
            "amount_currency": 1700.0,
            "balance": 1700000.0,
        })
        self.assertEqual(counterpart.amount_currency, 1700.0)
        self.assertAlmostEqual(counterpart.balance, 1700.0 * 886.2, places=2)
        self.assertAlmostEqual(remainder.balance, 1700000.0 - 1700.0 * 886.2, places=2)
        bank = move.line_ids.filtered(lambda l: l.account_id == self.bank.default_account_id)
        self.assertAlmostEqual(bank.foreign_credit, 1700000.0 / 886.2, places=2)
        self.assertAlmostEqual(self._foreign_imbalance(move), 0.0, places=2)

    def test_04_edit_only_the_balance_recomputes_the_amount_in_currency(self):
        """Only the balance (and the currency) changes: the USD amount follows the rate."""
        st_line = self._statement_line()
        if not hasattr(st_line, "edit_reconcile_line"):
            self.skipTest("account_accountant (enterprise) is not installed")
        move, counterpart, remainder = self._edit_suspense(st_line, {
            "account_id": self.counterpart.id,
            "currency_id": self.usd.id,
            "balance": 1700000.0,
        })
        self.assertAlmostEqual(counterpart.balance, 1700000.0, places=2)
        self.assertAlmostEqual(counterpart.amount_currency, 1700000.0 / 886.2, places=2)
        self.assertFalse(remainder)
        self.assertAlmostEqual(self._foreign_imbalance(move), 0.0, places=2)

    def test_05_edit_only_the_amount_recomputes_the_balance(self):
        """Only the USD amount changes: the balance follows the rate, the rest is suspense."""
        st_line = self._statement_line()
        if not hasattr(st_line, "edit_reconcile_line"):
            self.skipTest("account_accountant (enterprise) is not installed")
        move, counterpart, remainder = self._edit_suspense(st_line, {
            "account_id": self.counterpart.id,
            "currency_id": self.usd.id,
            "amount_currency": 1700.0,
        })
        self.assertAlmostEqual(counterpart.balance, 1700.0 * 886.2, places=2)
        self.assertAlmostEqual(remainder.balance, 1700000.0 - 1700.0 * 886.2, places=2)
        self.assertAlmostEqual(self._foreign_imbalance(move), 0.0, places=2)

    def test_06_edit_in_company_currency_is_not_touched(self):
        """A line in the currency of the company keeps what the user sent."""
        st_line = self._statement_line()
        if not hasattr(st_line, "edit_reconcile_line"):
            self.skipTest("account_accountant (enterprise) is not installed")
        move, counterpart, remainder = self._edit_suspense(st_line, {
            "account_id": self.counterpart.id,
        })
        self.assertEqual(counterpart.currency_id, self.vef)
        self.assertAlmostEqual(counterpart.balance, 1700000.0, places=2)
        self.assertFalse(remainder)
        self.assertAlmostEqual(self._foreign_imbalance(move), 0.0, places=2)

    def test_07_edit_dialog_with_the_real_form(self):
        """The dialog: USD + amount gives the balance by onchange, forcing it is set back."""
        st_line = self._statement_line()
        if not hasattr(st_line, "edit_reconcile_line"):
            self.skipTest("account_accountant (enterprise) is not installed")
        fields_to_send = ("account_id", "currency_id", "amount_currency", "balance")

        def open_dialog(line, edit):
            """Like the dialog: the Form is not saved, only the changed fields are sent."""
            before = {"account_id": line.account_id.id, "currency_id": line.currency_id.id,
                      "amount_currency": line.amount_currency, "balance": line.balance}
            form = Form(line, view="account_accountant.view_bank_rec_edit_line")
            edit(form)
            after = {
                "account_id": form.account_id.id, "currency_id": form.currency_id.id,
                "amount_currency": form.amount_currency, "balance": form.balance,
            }
            return {key: after[key] for key in fields_to_send if after[key] != before[key]}

        _liquidity, suspense, _other = st_line._seek_for_lines()

        def set_usd(form):
            form.account_id = self.counterpart
            form.currency_id = self.usd
            form.amount_currency = 1700.0
            # The onchange of the core already gives the balance of the date.
            self.assertAlmostEqual(form.balance, 1700.0 * 886.2, places=2)

        st_line.edit_reconcile_line(suspense.id, open_dialog(suspense, set_usd))
        move = st_line.move_id
        counterpart = move.line_ids.filtered(lambda l: l.account_id == self.counterpart)
        self.assertAlmostEqual(counterpart.balance, 1700.0 * 886.2, places=2)
        self.assertAlmostEqual(self._foreign_imbalance(move), 0.0, places=2)

        # The user types the balance of the statement by hand over the line.
        def force_balance(form):
            form.balance = 1700000.0

        changes = open_dialog(counterpart, force_balance)
        self.assertEqual(set(changes), {"balance"})
        st_line.edit_reconcile_line(counterpart.id, changes)
        move = st_line.move_id
        counterpart = move.line_ids.filtered(lambda l: l.account_id == self.counterpart)
        # Only the balance changed, so the USD amount follows it: 1.700.000 / 886,2.
        self.assertAlmostEqual(counterpart.balance, 1700000.0, places=2)
        self.assertAlmostEqual(counterpart.amount_currency, 1700000.0 / 886.2, places=2)
        self.assertAlmostEqual(self._foreign_imbalance(move), 0.0, places=2)

    def test_08_reconcile_usd_line_without_editing(self):
        """Without editing anything the widget already follows the rate of the date."""
        st_line = self._statement_line()
        if not hasattr(st_line, "set_line_bank_statement_line"):
            self.skipTest("account_accountant (enterprise) is not installed")
        past = self.today - timedelta(days=10)
        self.env["res.currency.rate"].create([
            {"name": past, "currency_id": self.vef.id,
             "inverse_company_rate": 1.0, "company_id": self.company.id},
            {"name": past, "currency_id": self.usd.id,
             "inverse_company_rate": 900.0, "company_id": self.company.id},
        ])
        misc = self.env["account.journal"].create(
            {"name": "Varios", "type": "general", "code": "VAR"})
        expense = self.env["account.account"].create({
            "name": "Gasto", "code": "999992", "account_type": "expense",
            "company_ids": [(6, 0, [self.company.id])],
        })
        self.counterpart.write({"reconcile": True, "account_type": "liability_current"})
        old = self.env["account.move"].create({
            "move_type": "entry", "journal_id": misc.id, "date": past,
            "line_ids": [
                (0, 0, {"account_id": expense.id, "debit": 1530000.0,
                        "currency_id": self.usd.id, "amount_currency": 1700.0}),
                (0, 0, {"account_id": self.counterpart.id, "credit": 1530000.0,
                        "currency_id": self.usd.id, "amount_currency": -1700.0}),
            ]})
        old.action_post()
        st_line.set_line_bank_statement_line(
            old.line_ids.filtered(lambda l: l.account_id == self.counterpart).ids)
        move = st_line.move_id
        counterpart = move.line_ids.filtered(lambda l: l.account_id == self.counterpart)
        self.assertEqual(counterpart.amount_currency, 1700.0)
        self.assertAlmostEqual(counterpart.balance, 1700.0 * 886.2, places=2)
        self.assertAlmostEqual(self._foreign_imbalance(move), 0.0, places=2)
