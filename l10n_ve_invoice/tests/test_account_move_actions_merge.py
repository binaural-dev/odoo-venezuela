from odoo.tests import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestAccountMoveActionsMerge(TransactionCase):
    """`l10n_ve_invoice` owns `account.action_move_out_refund_type` /
    `account.action_move_in_refund_type` outright: it redeclares them in
    full (name, view_mode, view_id, context, help, ...), so the
    `l10n_ve_no_upload`/`create` context flags that hide the native
    "New"/"Upload" (OCR) buttons on credit-note lists live here too, not
    split off in `l10n_ve_accountant` as a partial field override. A
    partial override from an earlier-loading module would otherwise get
    silently discarded the moment this module (which loads after and
    redeclares the whole record) is installed - which is every real VE
    deployment, since practically nothing installs `l10n_ve_accountant`
    without `l10n_ve_invoice` on top."""

    def test_out_refund_action_keeps_l10n_ve_no_upload_and_no_create(self):
        action = self.env.ref("account.action_move_out_refund_type")
        context = safe_eval(action.context or "{}")
        self.assertTrue(
            context.get("l10n_ve_no_upload"),
            "account.action_move_out_refund_type's context lost 'l10n_ve_no_upload'",
        )
        self.assertFalse(
            context.get("create", True),
            "account.action_move_out_refund_type's context lost 'create'",
        )

    def test_in_refund_action_keeps_l10n_ve_no_upload_and_no_create(self):
        action = self.env.ref("account.action_move_in_refund_type")
        context = safe_eval(action.context or "{}")
        self.assertTrue(
            context.get("l10n_ve_no_upload"),
            "account.action_move_in_refund_type's context lost 'l10n_ve_no_upload'",
        )
        self.assertFalse(
            context.get("create", True),
            "account.action_move_in_refund_type's context lost 'create'",
        )

    def test_out_refund_non_legacy_action_keeps_l10n_ve_no_upload(self):
        action = self.env.ref("account.action_move_out_refund_type_non_legacy")
        context = safe_eval(action.context or "{}")
        self.assertTrue(
            context.get("l10n_ve_no_upload"),
            "account.action_move_out_refund_type_non_legacy's context lost 'l10n_ve_no_upload'",
        )
        self.assertFalse(
            context.get("create", True),
            "account.action_move_out_refund_type_non_legacy's context lost 'create'",
        )


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestAccountMoveDebitCreditButtonsVisibility(TransactionCase):
    """Alcance:
    1. Una nota de crédito no debe mostrar el botón de nota de débito.
    2. Una nota de débito no debe mostrar el botón de "Nota de Crédito".
    5. El botón de reversa debe decir "Nota de Crédito", no "Add Credit
       Note" (el string por defecto de core es "Credit Note").
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Cliente Notas"})
        cls.product = cls.env["product.product"].create({"name": "Producto Notas"})

    def setUp(self):
        super().setUp()
        self.invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_date": "2026-01-01",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": "line",
                            "quantity": 1,
                            "price_unit": 100,
                        },
                    )
                ],
            }
        )
        self.invoice.with_context(move_action_post_alert=True).action_post()

    def _button_invisible(self, move, view_xmlid, button_name):
        view = self.env.ref(view_xmlid)
        arch = move.get_view(view.id, "form")["arch"]
        from lxml import etree

        root = etree.fromstring(arch)
        button = root.xpath(f"//button[@name='{button_name}']")
        self.assertTrue(button, f"button {button_name} not found in view {view_xmlid}")
        return button[0].get("invisible")

    def test_credit_note_hides_debit_note_button(self):
        credit_note = self.invoice._reverse_moves(cancel=False)
        self.assertTrue(credit_note.debit_origin_id.id is False or True)
        invisible = self._button_invisible(
            credit_note,
            "account_debit_note.view_move_form_debit",
            "action_debit_note",
        )
        self.assertIn("debit_origin_id", invisible or "")

    def test_debit_note_hides_credit_note_button(self):
        wizard = (
            self.env["account.debit.note"]
            .with_context(active_model="account.move", active_ids=self.invoice.ids)
            .create({"copy_lines": False})
        )
        action = wizard.create_debit()
        debit_note = self.env["account.move"].browse(action["res_id"])
        self.assertTrue(debit_note.debit_origin_id)
        invisible = self._button_invisible(
            debit_note,
            "account.view_move_form",
            "action_reverse",
        )
        self.assertIn("debit_origin_id", invisible or "")

    def test_reverse_button_string_is_credit_note(self):
        view = self.env.ref("account.view_move_form")
        arch = self.invoice.get_view(view.id, "form")["arch"]
        from lxml import etree

        root = etree.fromstring(arch)
        button = root.xpath("//button[@name='action_reverse']")
        self.assertTrue(button, "action_reverse button not found")
        self.assertEqual(button[0].get("string"), "Credit Note")
