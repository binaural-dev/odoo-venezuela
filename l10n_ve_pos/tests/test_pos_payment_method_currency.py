"""Settings of a payment method by currency (ADR-023).

Odoo 20 admits one cash payment method per register, which takes several
currencies (``currency_ids``). What Odoo 19 kept on one method per currency
(``is_foreign_currency``, ``cross_journal``, ``cross_account_journal``) hangs
from ``pos.payment.method.currency``, and the payment says which currency it
was made in through the native ``foreign_currency_id``.
"""

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .test_pos_session_accounting_common import TestPosSessionAccountingBase


@tagged("post_install", "-at_install", "l10n_ve_pos", "pos_method_currency")
class TestPosPaymentMethodCurrency(TestPosSessionAccountingBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.eur = cls.env.ref("base.EUR")
        cls.eur.active = True
        cls.cross_journal = cls.env["account.journal"].create(
            {
                "name": "C Cross Journal",
                "type": "general",
                "code": "CRSM",
                "company_id": cls.company.id,
            }
        )
        cls.method = cls.combined_cash_method

    def _setting(self, currency, method=None):
        return self.env["pos.payment.method.currency"].create(
            {
                "payment_method_id": (method or self.method).id,
                "currency_id": currency.id,
                "cross_account_journal": self.cross_journal.id,
            }
        )

    def test_setting_is_found_by_currency(self):
        self.method.write(
            {"currency_ids": [Command.set((self.payment_currency | self.eur).ids)]}
        )
        usd_setting = self._setting(self.payment_currency)
        self.assertEqual(self.method._get_currency_settings(self.payment_currency), usd_setting)
        self.assertFalse(self.method._get_currency_settings(self.eur))

    def test_one_setting_per_method_and_currency(self):
        self._setting(self.payment_currency)
        with self.assertRaises(Exception), mute_logger("odoo.sql_db"), self.env.cr.savepoint():
            self._setting(self.payment_currency)

    def test_currency_must_be_one_of_the_method(self):
        with self.assertRaises(ValidationError):
            self._setting(self.eur)

    def test_removing_a_currency_removes_its_settings(self):
        self.method.write(
            {"currency_ids": [Command.set((self.payment_currency | self.eur).ids)]}
        )
        usd_setting = self._setting(self.payment_currency)
        eur_setting = self._setting(self.eur)
        self.method.write({"currency_ids": [Command.unlink(self.eur.id)]})
        self.assertFalse(eur_setting.exists())
        self.assertTrue(usd_setting.exists())

    def test_payment_currency_of_a_payment(self):
        session = self.env["pos.session"].create(
            {"config_id": self.config.id, "user_id": self.env.ref("base.user_admin").id}
        ).with_company(self.company)
        order = self._create_paid_order(
            session, method=self.combined_bank_method, name="OL/CUR/1"
        )
        foreign = order.payment_ids
        self.assertEqual(foreign.foreign_currency_id, self.payment_currency)
        self.assertTrue(foreign.is_foreign_currency)
        self.assertEqual(foreign.payment_currency_id, self.payment_currency)

        foreign.foreign_currency_id = order.currency_id
        self.assertFalse(foreign.is_foreign_currency)
        self.assertEqual(foreign.payment_currency_id, order.currency_id)

        foreign.foreign_currency_id = False
        self.assertFalse(foreign.is_foreign_currency)
        self.assertEqual(foreign.payment_currency_id, order.currency_id)

    def test_payment_reads_the_settings_of_its_currency(self):
        self.combined_bank_method.write(
            {"currency_ids": [Command.set((self.payment_currency | self.eur).ids)]}
        )
        usd_setting = self._setting(self.payment_currency, self.combined_bank_method)
        session = self.env["pos.session"].create(
            {"config_id": self.config.id, "user_id": self.env.ref("base.user_admin").id}
        ).with_company(self.company)
        order = self._create_paid_order(
            session, method=self.combined_bank_method, name="OL/CUR/2"
        )
        self.assertEqual(order.payment_ids._get_currency_settings(), usd_setting)

    def test_identify_customer_is_required_by_the_payment_wizard(self):
        method = self.split_bank_method
        session = self.env["pos.session"].create(
            {"config_id": self.config.id, "user_id": self.env.ref("base.user_admin").id}
        ).with_company(self.company)
        order = self._create_paid_order(
            session, method=method, name="OL/CUR/3", partner_id=False
        )
        self.env.cr.execute("UPDATE pos_order SET state = 'draft' WHERE id = %s", (order.id,))
        order.invalidate_recordset(["state"])
        wizard = (
            self.env["pos.make.payment"]
            .with_context(active_id=order.id)
            .create({"payment_method_id": method.id, "amount": 1.0})
        )
        with self.assertRaises(UserError):
            wizard.check()

    def test_identify_customer_is_not_required_without_the_flag(self):
        method = self.combined_bank_method
        session = self.env["pos.session"].create(
            {"config_id": self.config.id, "user_id": self.env.ref("base.user_admin").id}
        ).with_company(self.company)
        order = self._create_paid_order(
            session, method=method, name="OL/CUR/4", partner_id=False
        )
        self.env.cr.execute("UPDATE pos_order SET state = 'draft' WHERE id = %s", (order.id,))
        order.invalidate_recordset(["state"])
        wizard = (
            self.env["pos.make.payment"]
            .with_context(active_id=order.id)
            .create({"payment_method_id": method.id, "amount": 1.0})
        )
        try:
            wizard.check()
        except UserError as error:
            self.assertNotIn("Customer is required", str(error))
