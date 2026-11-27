"""Access rights on the settings of a payment method by currency.

``security/ir.access.csv`` gives ``pos.payment.method.currency`` read access to
the PoS users, full access to the PoS managers and a multi-company rule, as core
does for ``pos.payment.method``.
"""

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install", "l10n_ve_pos", "pos_method_currency_access")
class TestPosPaymentMethodCurrencyAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        cls.usd = cls.env.ref("base.USD")
        cls.eur = cls.env.ref("base.EUR")
        (cls.usd | cls.eur).write({"active": True})
        journal = cls.env["account.journal"].create(
            {"name": "Cash access", "code": "PMCA", "type": "cash", "company_id": cls.company.id}
        )
        cls.method = cls.env["pos.payment.method"].create(
            {
                "name": "Cash access",
                "type": "cash",
                "company_id": cls.company.id,
                "journal_id": journal.id,
                "currency_ids": [Command.set((cls.usd | cls.eur).ids)],
            }
        )
        cls.setting = cls.env["pos.payment.method.currency"].create(
            {"payment_method_id": cls.method.id, "currency_id": cls.usd.id}
        )
        cls.pos_user = new_test_user(
            cls.env,
            login="pmc_pos_user",
            groups="point_of_sale.group_pos_user",
            company_id=cls.company.id,
            company_ids=[Command.set(cls.company.ids)],
        )
        cls.pos_manager = new_test_user(
            cls.env,
            login="pmc_pos_manager",
            groups="point_of_sale.group_pos_manager",
            company_id=cls.company.id,
            company_ids=[Command.set(cls.company.ids)],
        )
        cls.other_company = cls.env["res.company"].create(
            {
                "name": "PMC Other Company",
                "currency_id": cls.usd.id,
                "country_id": cls.env.ref("base.ve").id,
            }
        )
        cls.other_user = new_test_user(
            cls.env,
            login="pmc_other_company",
            groups="point_of_sale.group_pos_user",
            company_id=cls.other_company.id,
            company_ids=[Command.set(cls.other_company.ids)],
        )

    def _settings_as(self, user):
        """The model as ``user``, limited to the companies the user has."""
        return (
            self.env["pos.payment.method.currency"]
            .with_user(user)
            .with_context(allowed_company_ids=user.company_ids.ids)
        )

    def test_pos_user_reads_the_settings(self):
        settings = self._settings_as(self.pos_user)
        found = settings.search([("payment_method_id", "=", self.method.id)])
        self.assertEqual(found, self.setting)
        values = settings.browse(self.setting.id).read(["currency_id"])
        self.assertEqual(values[0]["currency_id"][0], self.usd.id)

    def test_pos_user_cannot_create_a_setting(self):
        with self.assertRaises(AccessError):
            self._settings_as(self.pos_user).create(
                {"payment_method_id": self.method.id, "currency_id": self.eur.id}
            )

    def test_pos_user_cannot_modify_a_setting(self):
        with self.assertRaises(AccessError):
            self._settings_as(self.pos_user).browse(self.setting.id).write(
                {"cross_account_journal": False}
            )

    def test_pos_user_cannot_delete_a_setting(self):
        with self.assertRaises(AccessError):
            self._settings_as(self.pos_user).browse(self.setting.id).unlink()
        self.assertTrue(self.setting.exists())

    def test_pos_manager_manages_the_settings(self):
        settings = self._settings_as(self.pos_manager)
        eur_setting = settings.create(
            {"payment_method_id": self.method.id, "currency_id": self.eur.id}
        )
        eur_setting.write({"cross_account_journal": False})
        eur_setting.unlink()
        self.assertFalse(eur_setting.exists())

    def test_user_of_another_company_does_not_see_the_settings(self):
        settings = self._settings_as(self.other_user)
        self.assertFalse(settings.search([("id", "=", self.setting.id)]))
        with self.assertRaises(AccessError):
            settings.browse(self.setting.id).read(["currency_id"])
