from odoo.tests import tagged
from odoo.tests.common import new_test_user

from .test_partial_payment_common import PartialPaymentTestCommon


@tagged("post_install", "-at_install", "l10n_ve_partial_payment")
class TestPartialPaymentPermissions(PartialPaymentTestCommon):
    """Covers the double server-side gate in
    ``account_move._can_apply_partial_payment``/``can_apply_partial_payment``:
    both the company flag (``partial_pay_from_outstanding``) AND the
    ``group_partial_payment_apply`` group membership must hold for the gate
    to return ``True``. Also covers the ``implied_ids`` grant to
    ``account.group_account_manager`` declared in ``security/res_groups.xml``.
    """

    def setUp(self):
        super().setUp()
        self.invoice = self._create_invoice_vef(100.00)
        self.invoice.with_context(move_action_post_alert=True).action_post()

    def test_flag_off_blocks_even_with_group(self):
        """Company flag defaults to ``False`` (section 6.1): even a user with
        the group must NOT be able to apply a partial amount while the flag
        is off."""
        self.company.partial_pay_from_outstanding = False
        gate = self.invoice.with_user(self.user_with_group).can_apply_partial_payment()
        self.assertFalse(gate)

    def test_flag_on_without_group_blocks(self):
        """Flag on but the acting user lacks ``group_partial_payment_apply``:
        the gate must stay closed (falls back to unmodified ``l10n_ve_igtf``
        behavior instead of an error, per the method's docstring)."""
        self.company.partial_pay_from_outstanding = True
        gate = self.invoice.with_user(
            self.user_without_group
        ).can_apply_partial_payment()
        self.assertFalse(gate)

    def test_flag_on_with_group_allows(self):
        """Both gates satisfied: the "Add" popover may open with an amount
        input and the server will honor a genuinely partial amount."""
        self.company.partial_pay_from_outstanding = True
        gate = self.invoice.with_user(self.user_with_group).can_apply_partial_payment()
        self.assertTrue(gate)

    def test_account_manager_group_gets_partial_payment_group_by_implied_ids(self):
        """``security/res_groups.xml`` appends ``group_partial_payment_apply``
        to ``account.group_account_manager``'s ``implied_ids`` -- a fresh
        Accounting Administrator must already have it without any explicit
        assignment."""
        manager = new_test_user(
            self.env, login="partial_manager", groups="account.group_account_manager"
        )
        self.assertTrue(
            manager.has_group("l10n_ve_partial_payment.group_partial_payment_apply"),
            "Accounting Administrators must inherit the partial-payment group "
            "via implied_ids.",
        )
