# Ticket #15729: foreign_balance (and foreign_debit / foreign_credit) ended up NULL.
from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_foreign_balance_null")
class TestForeignBalanceNull(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vef = cls.env.ref("base.VEF")
        cls.usd = cls.env.ref("base.USD")
        cls.company = cls.env.ref("base.main_company")
        cls.company.write({"currency_id": cls.vef.id, "currency_foreign_id": cls.usd.id})
        cls.env["res.currency.rate"].create({
            "name": fields.Date.today(), "currency_id": cls.usd.id,
            "inverse_company_rate": 50.0, "company_id": cls.company.id,
        })
        cls.acc_a = cls._acc("2991", "Null A", "asset_current")
        cls.acc_b = cls._acc("2992", "Null B", "liability_current")
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", cls.company.id)], limit=1
        ) or cls.env["account.journal"].create({
            "name": "General Null", "code": "GNUL", "type": "general", "company_id": cls.company.id,
        })

    @classmethod
    def _acc(cls, code, name, atype):
        return cls.env["account.account"].search([
            ("code", "=", code), ("company_id", "=", cls.company.id)], limit=1
        ) or cls.env["account.account"].create({
            "code": code, "name": name, "account_type": atype, "company_id": cls.company.id,
        })

    def _entry(self, amount=100.0, journal=None, **line_extra):
        return self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": (journal or self.journal).id,
            "date": fields.Date.today(),
            "line_ids": [
                Command.create(dict({"account_id": self.acc_a.id, "debit": amount, "credit": 0.0}, **line_extra)),
                Command.create(dict({"account_id": self.acc_b.id, "debit": 0.0, "credit": amount}, **line_extra)),
            ],
        })

    def _null_lines(self, move):
        self.env.flush_all()
        self.env.cr.execute(
            """SELECT id FROM account_move_line WHERE move_id = %s AND (
                   foreign_debit IS NULL OR foreign_credit IS NULL OR foreign_balance IS NULL)""",
            [move.id],
        )
        return [r[0] for r in self.env.cr.fetchall()]

    def test_regular_entry_has_no_null(self):
        move = self._entry()
        move.action_post()
        self.assertEqual(self._null_lines(move), [])
        self.assertAlmostEqual(sum(move.line_ids.mapped("foreign_balance")), 0.0, places=2)

    def test_not_foreign_recalculate_lines_have_no_null(self):
        """A line created with not_foreign_recalculate (skipped by the compute) must
        still store 0.0, not NULL, in foreign_debit/foreign_credit/foreign_balance."""
        move = self._entry(not_foreign_recalculate=True)
        self.assertEqual(self._null_lines(move), [])
        move.action_post()
        self.assertEqual(self._null_lines(move), [])

    def test_exchange_journal_lines_have_no_null(self):
        """Lines of the exchange-difference journal are skipped by the compute too."""
        exchange = self.env["account.journal"].create({
            "name": "Exchange Null", "code": "XNUL", "type": "general", "company_id": self.company.id,
        })
        self.company.currency_exchange_journal_id = exchange
        # Created straight in the exchange journal: the compute only skips the line
        # when it is evaluated for the first time with that journal.
        move = self._entry(journal=exchange)
        self.assertEqual(move.journal_id, exchange)
        self.assertEqual(self._null_lines(move), [])

    def test_foreign_balance_without_foreign_values(self):
        """foreign_balance is computed from foreign_debit/foreign_credit even if one
        of them is falsy."""
        move = self._entry()
        line = move.line_ids[0]
        line.not_foreign_recalculate = True
        line.foreign_debit = 0.0
        line.foreign_credit = 0.0
        self.env.flush_all()
        self.assertEqual(line.foreign_balance, 0.0)
        self.assertEqual(self._null_lines(move), [])

    def test_write_foreign_balance_sets_debit_credit(self):
        move = self._entry()
        line = move.line_ids[0]
        line.not_foreign_recalculate = True
        line.foreign_balance = -7.5
        self.env.flush_all()
        self.assertAlmostEqual(line.foreign_credit, 7.5, places=2)
        self.assertEqual(line.foreign_debit, 0.0)
        self.assertEqual(self._null_lines(move), [])
