"""Ticket 16410: a bank line in Bs must follow its counterpart when it moves to $.

A statement line in Bs is created with the suspense account as counterpart (the
bank line takes its $ at the rate of the day). Reconciling it against an account
in $ rewrites the counterpart to USD 1,700 for 1,700,000 Bs (the bank's rate).
The bank line has to be recomputed, otherwise the entry is balanced in Bs and
not in $.
"""
from datetime import timedelta

from odoo import fields
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install", "bank_statement_foreign_balance")
class TestBankStatementForeignBalance(TransactionCase):
    def setUp(self):
        super().setUp()
        # The journal items tab requires account.group_account_readonly
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
        # Rate of the day 886.2 Bs/USD; the bank used 1000.
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
        # No currency on the journal, like the real ones: it accepts lines in USD.
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
        """The entry of the statement line, edited so its counterpart is USD 1,700."""
        move = self._statement_line().move_id
        # On creation the bank line takes the $ at the rate of the day: 1,700,000 / 886.2
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
        """USD 1,700 with a balance forced to 1,700,000 Bs is set back to the rate of the day.

        The edit dialog lets the user type both fields, and the core stored them as they
        came (implicit rate 1000 against 886.2 of the day). The amount in USD wins, the
        balance is USD 1,700 x 886.2 and the difference stays in the suspense account.
        """
        st_line = self._statement_line()
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
        # Only the balance changed, so the USD amount follows it: 1,700,000 / 886.2.
        self.assertAlmostEqual(counterpart.balance, 1700000.0, places=2)
        self.assertAlmostEqual(counterpart.amount_currency, 1700000.0 / 886.2, places=2)
        self.assertAlmostEqual(self._foreign_imbalance(move), 0.0, places=2)

    def test_08_reconcile_usd_line_without_editing(self):
        """Without editing anything the widget already follows the rate of the date."""
        st_line = self._statement_line()
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

    def _foreign_statement_line(self, **extra):
        vals = {
            "journal_id": self.bank.id, "date": self.today,
            "payment_ref": "pago en $", "foreign_currency_id": self.usd.id,
            "amount_currency": 10.82,
        }
        vals.update(extra)
        return self.env["account.bank.statement.line"].create(vals)

    def test_09_statement_line_only_in_foreign_currency_gets_its_amount(self):
        """A statement line with only the amount in $ does not stay at 0 Bs.

        The core does not compute `amount` from `amount_currency`: the line stayed at 0 Bs
        and the payment reconciled against it sent its Bs to the exchange difference.
        """
        st_line = self._foreign_statement_line()
        self.assertAlmostEqual(st_line.amount, 10.82 * 886.2, places=2)
        bank_line = st_line.move_id.line_ids.filtered(
            lambda l: l.account_id == self.bank.default_account_id)
        self.assertAlmostEqual(bank_line.balance, 10.82 * 886.2, places=2)
        self.assertAlmostEqual(self._foreign_imbalance(st_line.move_id), 0.0, places=2)

    def test_10_statement_line_with_explicit_amount_is_not_touched(self):
        """An explicit amount in Bs is respected even if it does not follow the rate."""
        st_line = self._foreign_statement_line(amount=10000.0)
        self.assertEqual(st_line.amount, 10000.0)
        self.assertEqual(st_line.amount_currency, 10.82)

    def test_11_statement_line_with_the_form_gets_its_amount(self):
        """The same happens with the line form (default journal)."""
        form = Form(self.env["account.bank.statement.line"].with_context(
            default_journal_id=self.bank.id))
        form.payment_ref = "pago en $ (form)"
        form.foreign_currency_id = self.usd
        form.amount_currency = 10.82
        # The onchange fills the Bs before saving
        self.assertAlmostEqual(form.amount, 10.82 * 886.2, places=2)
        st_line = form.save()
        self.assertAlmostEqual(st_line.amount, 10.82 * 886.2, places=2)

    def test_12_statement_line_in_the_company_currency_is_not_touched(self):
        """Without a foreign currency `amount` is not completed."""
        st_line = self.env["account.bank.statement.line"].create({
            "journal_id": self.bank.id, "date": self.today,
            "payment_ref": "pago en Bs", "amount": 0.0,
        })
        self.assertEqual(st_line.amount, 0.0)

    def test_13_form_last_edited_field_wins(self):
        """In the form the last edited field wins and the other follows the rate of the date."""
        form = Form(self.env["account.bank.statement.line"].with_context(
            default_journal_id=self.bank.id))
        form.payment_ref = "pago en $ (onchange)"
        form.foreign_currency_id = self.usd
        form.amount_currency = 10.82
        self.assertAlmostEqual(form.amount, 10.82 * 886.2, places=2)
        # A different amount in Bs is typed: the amount in $ follows it
        form.amount = 10000.0
        self.assertAlmostEqual(form.amount_currency, 10000.0 / 886.2, places=2)
        # The onchange of the amount in $ does not rewrite the Bs the user has just typed
        self.assertEqual(form.amount, 10000.0)
        # The amount in $ is edited again: the Bs follows it
        form.amount_currency = 20.0
        self.assertAlmostEqual(form.amount, 20.0 * 886.2, places=2)
        st_line = form.save()
        self.assertAlmostEqual(st_line.amount, 20.0 * 886.2, places=2)
        self.assertEqual(st_line.amount_currency, 20.0)
        # A Bs amount that does not give an exact $ amount is respected as it is
        form = Form(self.env["account.bank.statement.line"].with_context(
            default_journal_id=self.bank.id))
        form.payment_ref = "pago en $ (redondeo)"
        form.foreign_currency_id = self.usd
        form.amount_currency = 10.82
        form.amount = 20000.0
        self.assertEqual(form.amount, 20000.0)
        self.assertAlmostEqual(form.amount_currency, 20000.0 / 886.2, places=2)
        self.assertAlmostEqual(self._foreign_imbalance(st_line.move_id), 0.0, places=2)

    def test_14_form_without_foreign_currency_is_not_touched(self):
        """Without a foreign currency the Bs stays as typed."""
        form = Form(self.env["account.bank.statement.line"].with_context(
            default_journal_id=self.bank.id))
        form.payment_ref = "pago en Bs (onchange)"
        form.amount = 12345.67
        self.assertEqual(form.amount, 12345.67)
        self.assertEqual(form.save().amount, 12345.67)

    def test_15_form_date_change_recomputes_the_amount_in_currency(self):
        """Changing the date keeps the Bs amount (what the bank moved) and recomputes the $ amount."""
        past = self.today - timedelta(days=3)
        self.env["res.currency.rate"].create([
            {"name": past, "currency_id": self.vef.id,
             "inverse_company_rate": 1.0, "company_id": self.company.id},
            {"name": past, "currency_id": self.usd.id,
             "inverse_company_rate": 900.0, "company_id": self.company.id},
        ])
        form = Form(self.env["account.bank.statement.line"].with_context(
            default_journal_id=self.bank.id))
        form.payment_ref = "pago en $ (fecha)"
        form.foreign_currency_id = self.usd
        form.amount_currency = 10.82
        bs = 10.82 * 886.2
        self.assertAlmostEqual(form.amount, bs, places=2)
        form.date = past
        self.assertAlmostEqual(form.amount, bs, places=2)
        self.assertAlmostEqual(form.amount_currency, bs / 900.0, places=2)
        form.date = self.today
        self.assertAlmostEqual(form.amount, bs, places=2)
        self.assertAlmostEqual(form.amount_currency, bs / 886.2, places=2)
        st_line = form.save()
        self.assertAlmostEqual(st_line.amount, bs, places=2)
        self.assertAlmostEqual(self._foreign_imbalance(st_line.move_id), 0.0, places=2)

    def test_16_manual_alternate_amounts_survive_a_change_in_a_sibling_line(self):
        """A manual adjustment or a frozen line is not overwritten when a sibling line changes."""
        move = self.env["account.move"].create({
            "move_type": "entry", "journal_id": self.bank.id, "date": self.today,
            "line_ids": [
                (0, 0, {"account_id": self.bank.default_account_id.id, "credit": 886200.0}),
                (0, 0, {"account_id": self.counterpart.id, "currency_id": self.usd.id,
                        "amount_currency": 1000.0}),
            ]})
        bank = move.line_ids.filtered(lambda l: l.account_id == self.bank.default_account_id)
        usd_line = move.line_ids - bank
        self.assertAlmostEqual(bank.foreign_credit, 1000.0, places=2)
        bank.foreign_credit_adjustment = 1200.0
        self.assertAlmostEqual(bank.foreign_credit, 1200.0, places=2)
        # The counterpart changes: the manual adjustment wins over the rule of the sibling lines
        move.write({"line_ids": [
            (1, usd_line.id, {"amount_currency": 1100.0}),
            (1, bank.id, {"credit": 974820.0}),
        ]})
        self.assertAlmostEqual(bank.foreign_credit, 1200.0, places=2)
        # A line excluded from the recalculation keeps its value too
        bank.write({"foreign_credit_adjustment": 0.0, "not_foreign_recalculate": True, "foreign_credit": 900.0})
        move.write({"line_ids": [
            (1, usd_line.id, {"amount_currency": 1000.0}),
            (1, bank.id, {"credit": 886200.0}),
        ]})
        self.assertAlmostEqual(bank.foreign_credit, 900.0, places=2)
