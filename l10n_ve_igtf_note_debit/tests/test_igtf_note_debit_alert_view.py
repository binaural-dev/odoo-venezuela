from lxml import etree

from odoo.tests import TransactionCase, tagged

FOREIGN_ALERT_TEXT = "FOREIGN_MODULE_ALERT"


@tagged("igtf_note_debit_alert_view", "-at_install", "post_install")
class TestIgtfNoteDebitAlertView(TransactionCase):
    """El aviso "notas de IGTF pendientes" va justo después de la alerta de pendientes de la nota de
    crédito de cliente, aunque otro módulo agregue un `alert-info` antes (antes se ubicaba con el
    índice posicional `[3]`, que ese aviso ajeno corría)."""

    def setUp(self):
        super().setUp()
        self.env["ir.ui.view"].create({
            "name": "test.alert.before.core.alerts",
            "model": "account.move",
            "type": "form",
            "inherit_id": self.env.ref("l10n_ve_accountant.view_account_move_form_l10n_ve_accountant").id,
            "arch": (
                "<data><xpath expr=\"//header\" position=\"after\">"
                "<div class=\"alert alert-info mb-0\" role=\"alert\" invisible=\"not id\">%s</div>"
                "</xpath></data>" % FOREIGN_ALERT_TEXT
            ),
        })
        arch = self.env["account.move"].get_view(view_type="form")["arch"]
        self.tree = etree.fromstring(arch)

    def test_pending_igtf_alert_after_customer_credit_note_alert(self):
        warnings = self.tree.xpath("//div[contains(@invisible, 'has_pending_igtf_debit_note')]")
        self.assertEqual(len(warnings), 1)
        previous = warnings[0].getprevious()
        while previous is not None and previous.tag == "field":
            previous = previous.getprevious()
        self.assertIsNotNone(previous)
        self.assertIn("alert-info", previous.get("class", ""))
        self.assertIn("move_type != 'out_refund'", previous.get("invisible", ""))
        self.assertIn("invoice_has_outstanding", previous.get("invisible", ""))
