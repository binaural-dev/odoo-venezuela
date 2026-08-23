from odoo.tests import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestAccountMoveActionsMerge(TransactionCase):
    """`l10n_ve_invoice` owns `account.action_move_out_refund_type` /
    `account.action_move_in_refund_type` outright: it redeclares them in
    full (name, view_mode, view_id, context, help, ...), so the "no create"
    list views and the `no_upload`/`create` context flags that hide the
    native "New"/"Upload" (OCR) buttons on credit-note lists live here too,
    not split off in `l10n_ve_accountant` as a partial field override. A
    partial override from an earlier-loading module would otherwise get
    silently discarded the moment this module (which loads after and
    redeclares the whole record) is installed - which is every real VE
    deployment, since practically nothing installs `l10n_ve_accountant`
    without `l10n_ve_invoice` on top."""

    def test_out_refund_action_keeps_no_upload_and_no_create(self):
        action = self.env.ref("account.action_move_out_refund_type")
        context = safe_eval(action.context or "{}")
        self.assertTrue(
            context.get("no_upload"),
            "account.action_move_out_refund_type's context lost 'no_upload'",
        )
        self.assertFalse(
            context.get("create", True),
            "account.action_move_out_refund_type's context lost 'create'",
        )
        self.assertEqual(
            action.view_id.id,
            self.env.ref("l10n_ve_invoice.view_out_credit_note_tree_no_create_l10n_ve").id,
            "account.action_move_out_refund_type is not using the no-create list view",
        )

    def test_in_refund_action_keeps_no_upload_and_no_create(self):
        action = self.env.ref("account.action_move_in_refund_type")
        context = safe_eval(action.context or "{}")
        self.assertTrue(
            context.get("no_upload"),
            "account.action_move_in_refund_type's context lost 'no_upload'",
        )
        self.assertFalse(
            context.get("create", True),
            "account.action_move_in_refund_type's context lost 'create'",
        )
        self.assertEqual(
            action.view_id.id,
            self.env.ref("l10n_ve_invoice.view_in_invoice_refund_tree_no_create_l10n_ve").id,
            "account.action_move_in_refund_type is not using the no-create list view",
        )

    def test_out_refund_non_legacy_action_keeps_no_upload(self):
        action = self.env.ref("account.action_move_out_refund_type_non_legacy")
        context = safe_eval(action.context or "{}")
        self.assertTrue(
            context.get("no_upload"),
            "account.action_move_out_refund_type_non_legacy's context lost 'no_upload'",
        )
        self.assertFalse(
            context.get("create", True),
            "account.action_move_out_refund_type_non_legacy's context lost 'create'",
        )
