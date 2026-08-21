from odoo.tests import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestAccountMoveActionsMerge(TransactionCase):
    """`l10n_ve_accountant` overrides the `context` of the native credit-note
    actions to add `no_upload: True` (hides the OCR "Upload" button) and
    `l10n_ve_invoice` re-declares the same `ir.actions.act_window` records in
    full. Since `l10n_ve_invoice` depends on `l10n_ve_accountant` and loads
    after it, any field it re-declares wins outright over what the earlier
    module set for that same field - so both modules must agree on the final
    value of `context` (and, for the vendor/customer credit-note actions,
    `view_id`) or the override silently disappears the moment only
    `l10n_ve_invoice` is installed (which is every real VE deployment)."""

    def test_out_refund_action_keeps_no_upload_and_no_create(self):
        action = self.env.ref("account.action_move_out_refund_type")
        context = safe_eval(action.context or "{}")
        self.assertTrue(
            context.get("no_upload"),
            "l10n_ve_invoice overwrote 'no_upload' from account.action_move_out_refund_type's context",
        )
        self.assertFalse(
            context.get("create", True),
            "l10n_ve_invoice overwrote 'create' from account.action_move_out_refund_type's context",
        )
        self.assertEqual(
            action.view_id.id,
            self.env.ref("l10n_ve_accountant.view_out_credit_note_tree_no_create_l10n_ve").id,
            "account.action_move_out_refund_type is not using the no-create list view",
        )

    def test_in_refund_action_keeps_no_upload_and_no_create(self):
        action = self.env.ref("account.action_move_in_refund_type")
        context = safe_eval(action.context or "{}")
        self.assertTrue(
            context.get("no_upload"),
            "l10n_ve_invoice overwrote 'no_upload' from account.action_move_in_refund_type's context",
        )
        self.assertFalse(
            context.get("create", True),
            "l10n_ve_invoice overwrote 'create' from account.action_move_in_refund_type's context",
        )
        self.assertEqual(
            action.view_id.id,
            self.env.ref("l10n_ve_accountant.view_in_invoice_refund_tree_no_create_l10n_ve").id,
            "account.action_move_in_refund_type is not using the no-create list view",
        )
