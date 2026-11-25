"""Ticket 16410: a bank line in Bs must follow its counterpart when it moves to $.

A statement line in Bs is created with the suspense account as counterpart (the
bank line takes its $ at the rate of the day). Reconciling it against an account
in $ rewrites the counterpart to USD 1.700 for 1.700.000 Bs (the bank's rate).
The bank line has to be recomputed, otherwise the entry is balanced in Bs and
not in $.
"""
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

    def test_03_statement_reconciled_through_the_enterprise_code(self):
        """Same case through `edit_reconcile_line`, what the bank reconciliation widget calls."""
        st_line = self._statement_line()
        if not hasattr(st_line, "edit_reconcile_line"):
            self.skipTest("account_accountant (enterprise) is not installed")
        _liquidity, suspense, _other = st_line._seek_for_lines()
        st_line.edit_reconcile_line(suspense.id, {
            "account_id": self.counterpart.id,
            "currency_id": self.usd.id,
            "amount_currency": 1700.0,
            "balance": 1700000.0,
        })
        move = st_line.move_id
        counterpart = move.line_ids.filtered(lambda l: l.account_id == self.counterpart)
        bank = move.line_ids - counterpart
        self.assertEqual(counterpart.amount_currency, 1700.0)
        self.assertAlmostEqual(counterpart.balance, 1700000.0, places=2)
        self.assertAlmostEqual(bank.foreign_credit, 1700.0, places=2)
        self.assertAlmostEqual(self._foreign_imbalance(move), 0.0, places=2)
