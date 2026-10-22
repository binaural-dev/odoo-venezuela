from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestResCurrencyGroupRestriction(TransactionCase):
    """Eliminar una moneda y gestionar sus tasas de cambio solo debe
    estar permitido a los usuarios de group_fiscal_config_support."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_support = cls.env.ref("l10n_ve_accountant.group_fiscal_config_support")
        # group_account_manager es quien tiene el permiso ACL base de borrar
        # res.currency (account/security/ir.model.access.csv); sin él, el
        # unlink() de este test fallaría por AccessError antes de llegar
        # siquiera a la regla de negocio de group_fiscal_config_support.
        cls.group_account_manager = cls.env.ref("account.group_account_manager")
        cls.support_user = cls.env["res.users"].create({
            "name": "Fiscal Support User",
            "login": "fiscal_support_user_test",
            "email": "fiscal_support_user_test@example.com",
            "group_ids": [(4, cls.group_support.id), (4, cls.group_account_manager.id)],
        })
        cls.plain_user = cls.env["res.users"].create({
            "name": "Plain User",
            "login": "plain_user_test",
            "email": "plain_user_test@example.com",
        })

    def _create_currency(self, name):
        return self.env["res.currency"].create({
            "name": name,
            "symbol": name,
        })

    def test_edit_rate_true_for_support_group(self):
        currency = self._create_currency("TS1")
        self.assertTrue(
            currency.with_user(self.support_user).edit_rate,
            "Un usuario de group_fiscal_config_support debe poder editar la tasa",
        )

    def test_edit_rate_false_for_plain_user(self):
        currency = self._create_currency("TS2")
        self.assertFalse(
            currency.with_user(self.plain_user).edit_rate,
            "Un usuario sin group_fiscal_config_support no debe poder editar la tasa",
        )

    def test_unlink_raises_for_plain_user(self):
        currency = self._create_currency("TS3")
        with self.assertRaises(UserError):
            currency.with_user(self.plain_user).unlink()
        self.assertTrue(currency.exists())

    def test_unlink_allowed_for_support_group(self):
        currency = self._create_currency("TS4")
        currency.with_user(self.support_user).unlink()
        self.assertFalse(currency.exists())
