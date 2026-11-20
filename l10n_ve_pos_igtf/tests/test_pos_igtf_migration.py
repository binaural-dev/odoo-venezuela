"""Tests for l10n_ve_pos_igtf: fields, data the PoS loads and the session guard.

Validates:
- Module loads and POS models expose IGTF fields.
- The IGTF flag lives in the currency settings of the payment method (ADR-023),
  one per method and currency, and the PoS loads it.
- A session of a register that applies IGTF does not open without the IGTF
  account of the company.
"""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.l10n_ve_pos.tests.test_pos_session_accounting_common import (
    TestPosSessionAccountingBase,
)


@tagged("post_install", "-at_install", "l10n_ve_pos_igtf")
class TestPosIgtfFields(TransactionCase):
    """Verify IGTF fields are available on POS models after module install."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.ref("base.main_company")

    def test_pos_payment_has_igtf_fields(self):
        """pos.payment exposes include_igtf, igtf_amount, foreign_igtf_amount."""
        Payment = self.env["pos.payment"]
        self.assertIn("include_igtf", Payment._fields)
        self.assertIn("igtf_amount", Payment._fields)
        self.assertIn("foreign_igtf_amount", Payment._fields)

    def test_pos_order_has_igtf_fields(self):
        """pos.order exposes igtf_amount and bi_igtf."""
        Order = self.env["pos.order"]
        self.assertIn("igtf_amount", Order._fields)
        self.assertIn("bi_igtf", Order._fields)

    def test_apply_igtf_is_a_currency_setting(self):
        """apply_igtf is set per payment method and currency, not on the method."""
        Setting = self.env["pos.payment.method.currency"]
        self.assertEqual(Setting._fields["apply_igtf"].type, "boolean")
        self.assertNotIn("apply_igtf", self.env["pos.payment.method"]._fields)

    def test_pos_loads_apply_igtf_of_the_settings(self):
        """The PoS reads apply_igtf of the currency settings it already loads."""
        config = self.env["pos.config"].new({"company_id": self.company.id})
        fields = self.env["pos.payment.method.currency"]._load_pos_data_fields(config)
        self.assertIn("apply_igtf", fields)
        self.assertIn("currency_id", fields)
        self.assertNotIn(
            "apply_igtf", self.env["pos.payment.method"]._load_pos_data_fields(config)
        )

    def test_pos_config_has_igtf_percentage(self):
        """pos.config exposes igtf_percentage via related field."""
        Config = self.env["pos.config"]
        self.assertIn("igtf_percentage", Config._fields)

    def test_module_loads_without_errors(self):
        """Module is installed and all models are available."""
        modules = self.env["ir.module.module"].search(
            [("name", "=", "l10n_ve_pos_igtf"), ("state", "=", "installed")]
        )
        self.assertTrue(modules, "l10n_ve_pos_igtf should be installed")


@tagged("post_install", "-at_install", "l10n_ve_pos_igtf")
class TestPosIgtfSessionGuard(TestPosSessionAccountingBase):
    def _flag_igtf(self, method, apply_igtf=True):
        setting = method.currency_setting_ids.filtered(
            lambda s: s.currency_id == self.payment_currency
        ) or self.env["pos.payment.method.currency"].create(
            {"payment_method_id": method.id, "currency_id": self.payment_currency.id}
        )
        setting.apply_igtf = apply_igtf

    def test_session_does_not_open_without_igtf_account(self):
        self._flag_igtf(self.combined_bank_method)
        self.company.customer_account_igtf_id = False
        with self.assertRaises(ValidationError):
            self.config._check_igtf_account()

    def test_session_opens_with_igtf_account(self):
        self._flag_igtf(self.combined_bank_method)
        self.company.customer_account_igtf_id = self.env["account.account"].create(
            {
                "name": "C IGTF guard",
                "code": "210001C",
                "account_type": "liability_current",
                "company_ids": [(6, 0, [self.company.id])],
            }
        )
        self.config._check_igtf_account()

    def test_session_guard_ignores_registers_without_igtf(self):
        self.company.customer_account_igtf_id = False
        self.assertFalse(
            any(self.config.payment_method_ids.currency_setting_ids.mapped("apply_igtf"))
        )
        self.config._check_igtf_account()

    def test_guard_runs_before_a_session_is_created(self):
        self._flag_igtf(self.combined_bank_method)
        self.company.customer_account_igtf_id = False
        with self.assertRaises(ValidationError):
            self.config._check_before_creating_new_session()
