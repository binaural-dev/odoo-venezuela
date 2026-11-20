"""Cash paid in a foreign currency goes to the cash journal of that currency.

Odoo 19 had a cash method per currency, each with its journal. Odoo 20 has one
cash method per register (ADR-023): the ``cross_journal`` of the settings of a
currency, when it is a cash journal in that currency or in the company one,
receives the cash paid in that currency (task 87725), and that cash does not
cross at the closing.

The company of the fixture is in USD and its alternate currency is VEF: the
register of these tests is in the company currency and takes VEF as the
foreign one.
"""

from odoo import Command
from odoo.tests import tagged

from .test_pos_session_accounting_common import TestPosSessionAccountingBase


@tagged("post_install", "-at_install")
class TestPosForeignCashJournal(TestPosSessionAccountingBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._create_rate_of_day(40.0)
        Account = cls.env["account.account"]
        Journal = cls.env["account.journal"]
        cls.main_cash_account = Account.create({
            "name": "FCJ Main Cash",
            "code": "100200F",
            "account_type": "asset_cash",
            "company_ids": [Command.set(cls.company.ids)],
        })
        cls.foreign_cash_account = Account.create({
            "name": "FCJ Foreign Cash",
            "code": "100201F",
            "account_type": "asset_cash",
            "company_ids": [Command.set(cls.company.ids)],
        })
        cls.company_cash_account = Account.create({
            "name": "FCJ Company Cash",
            "code": "100202F",
            "account_type": "asset_cash",
            "company_ids": [Command.set(cls.company.ids)],
        })
        cls.main_cash_journal = Journal.create({
            "name": "FCJ Main Cash",
            "type": "cash",
            "code": "FCJM",
            "company_id": cls.company.id,
            "default_account_id": cls.main_cash_account.id,
            "profit_account_id": cls.account_exchange_gain.id,
            "loss_account_id": cls.account_exchange_loss.id,
        })
        cls.foreign_cash_journal = Journal.create({
            "name": "FCJ Foreign Cash",
            "type": "cash",
            "code": "FCJF",
            "company_id": cls.company.id,
            "currency_id": cls.foreign_currency.id,
            "default_account_id": cls.foreign_cash_account.id,
        })
        cls.company_cash_journal = Journal.create({
            "name": "FCJ Company Cash",
            "type": "cash",
            "code": "FCJC",
            "company_id": cls.company.id,
            "default_account_id": cls.company_cash_account.id,
        })
        cls.cross_journal = Journal.create({
            "name": "FCJ Cross",
            "type": "general",
            "code": "FCJX",
            "company_id": cls.company.id,
        })
        cls.method = cls.env["pos.payment.method"].create({
            "name": "FCJ Cash",
            "type": "cash",
            "company_id": cls.company.id,
            "journal_id": cls.main_cash_journal.id,
            "currency_ids": [Command.set(cls.foreign_currency.ids)],
        })
        cls.setting = cls.env["pos.payment.method.currency"].create({
            "payment_method_id": cls.method.id,
            "currency_id": cls.foreign_currency.id,
            "cross_journal": cls.foreign_cash_journal.id,
            "cross_account_journal": cls.cross_journal.id,
        })
        cls.company_config = cls.env["pos.config"].create({
            "name": "FCJ Config",
            "company_id": cls.company.id,
            "default_partner_id": cls.company.partner_id.id,
            "closing_journal_id": Journal.create({
                "name": "FCJ Closing", "type": "sale", "code": "FCJS", "company_id": cls.company.id,
            }).id,
            "journal_id": Journal.create({
                "name": "FCJ Invoices", "type": "sale", "code": "FCJI", "company_id": cls.company.id,
            }).id,
            "payment_method_ids": [Command.set(cls.method.ids)],
        })

    def _session(self):
        session = self.env["pos.session"].create({
            "config_id": self.company_config.id,
            "user_id": self.env.ref("base.user_admin").id,
        }).with_company(self.company)
        session.set_opening_control(0, "")
        return session

    def test_the_cash_cross_journal_of_a_currency_receives_its_cash(self):
        self.assertEqual(
            self.method._get_foreign_cash_journal(self.foreign_currency), self.foreign_cash_journal
        )
        self.setting.cross_journal = self.company_cash_journal
        self.assertEqual(
            self.method._get_foreign_cash_journal(self.foreign_currency), self.company_cash_journal
        )

    def test_a_bank_cross_journal_keeps_the_cross_of_the_closing(self):
        self.setting.cross_journal = self.bank_journal
        self.assertFalse(self.method._get_foreign_cash_journal(self.foreign_currency))

    def test_a_cash_journal_in_a_third_currency_is_not_used(self):
        eur = self.env.ref("base.EUR")
        eur.active = True
        self.foreign_cash_journal.currency_id = eur
        self.assertFalse(self.method._get_foreign_cash_journal(self.foreign_currency))

    def test_cash_in_the_journal_of_its_currency_keeps_the_exact_company_amount(self):
        session = self._session()
        partner = self.company.partner_id
        # 4700 VEF for 116 USD: not the rate of the day (40), the one the
        # register charged.
        lines = self.method.with_company(self.company)._create_cash_payment_line(
            session, 116.0, self.account_receivable, "FCJ sale", partner,
            self.foreign_currency.id, 4700.0,
        )
        statement_line = lines.move_id.statement_line_id
        self.assertEqual(statement_line.journal_id, self.foreign_cash_journal)
        self.assertNotIn(statement_line, session.bank_statement_line_ids)
        self.assertEqual(statement_line.pos_session_id, session)
        self.assertAlmostEqual(statement_line.amount, 4700.0, places=2)
        self.assertAlmostEqual(statement_line.pos_company_amount, 116.0, places=2)
        liquidity = lines.move_id.line_ids.filtered(
            lambda line: line.account_id == self.foreign_cash_account
        )
        self.assertEqual(liquidity.currency_id, self.foreign_currency)
        self.assertAlmostEqual(liquidity.amount_currency, 4700.0, places=2)
        self.assertAlmostEqual(liquidity.debit, 116.0, places=2)
        self.assertEqual(lines.account_id, self.account_receivable)
        self.assertEqual(lines.partner_id, partner)
        self.assertAlmostEqual(lines.credit, 116.0, places=2)
        self.assertAlmostEqual(lines.amount_currency, -4700.0, places=2)

    def test_cash_in_a_company_currency_journal_is_booked_in_that_currency(self):
        self.setting.cross_journal = self.company_cash_journal
        session = self._session()
        lines = self.method.with_company(self.company)._create_cash_payment_line(
            session, 116.0, self.account_receivable, "FCJ sale", self.company.partner_id,
            self.foreign_currency.id, 4700.0,
        )
        statement_line = lines.move_id.statement_line_id
        self.assertEqual(statement_line.journal_id, self.company_cash_journal)
        self.assertFalse(statement_line.foreign_currency_id)
        self.assertAlmostEqual(statement_line.amount, 116.0, places=2)
        self.assertEqual(lines.currency_id, self.company.currency_id)
        self.assertAlmostEqual(lines.credit, 116.0, places=2)

    def test_refund_goes_out_of_the_journal_of_its_currency(self):
        session = self._session()
        lines = self.method.with_company(self.company)._create_cash_payment_line(
            session, -116.0, self.account_receivable, "FCJ refund", self.company.partner_id,
            self.foreign_currency.id, 4700.0,
        )
        statement_line = lines.move_id.statement_line_id
        self.assertAlmostEqual(statement_line.amount, -4700.0, places=2)
        self.assertAlmostEqual(statement_line.pos_company_amount, -116.0, places=2)
        self.assertAlmostEqual(lines.debit, 116.0, places=2)

    def test_cash_in_the_company_currency_stays_in_the_journal_of_the_method(self):
        session = self._session()
        lines = self.method.with_company(self.company)._create_cash_payment_line(
            session, 50.0, self.account_receivable, "FCJ sale", self.company.partner_id,
        )
        self.assertEqual(lines.move_id.statement_line_id.journal_id, self.main_cash_journal)
        self.assertIn(lines.move_id.statement_line_id, session.bank_statement_line_ids)

    def test_cash_booked_in_its_journal_does_not_cross(self):
        session = self._session()
        self.assertFalse(session._is_cross_move_eligible(self.method, self.foreign_currency))
        self.assertFalse(
            session._is_cross_move_eligible(self.method, self.foreign_currency, use_suspense=True)
        )

    def test_a_register_in_another_currency_keeps_the_journal_of_the_method(self):
        self.env["pos.payment.method.currency"].create({
            "payment_method_id": self.combined_cash_method.id,
            "currency_id": self.payment_currency.id,
            "cross_journal": self.company_cash_journal.id,
            "cross_account_journal": self.cross_journal.id,
        })
        session = self.env["pos.session"].new({"config_id": self.config.id})
        self.assertFalse(session.is_in_company_currency)
        self.assertFalse(
            session._get_foreign_cash_journal(self.combined_cash_method, self.payment_currency)
        )

    def test_a_changed_amount_or_journal_drops_the_exact_company_amount(self):
        session = self._session()
        lines = self.method.with_company(self.company)._create_cash_payment_line(
            session, 116.0, self.account_receivable, "FCJ sale", self.company.partner_id,
            self.foreign_currency.id, 4700.0,
        )
        statement_line = lines.move_id.statement_line_id
        invalidates = statement_line._invalidates_company_amount
        self.assertFalse(invalidates(statement_line, {"amount": 4700.0}))
        self.assertTrue(invalidates(statement_line, {"amount": 4000.0}))
        self.assertTrue(invalidates(statement_line, {"journal_id": self.main_cash_journal.id}))
        self.assertFalse(invalidates(statement_line, {"payment_ref": "renamed"}))
