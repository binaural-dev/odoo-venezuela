from lxml import etree

from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPosPaymentReportView(TransactionCase):
    def test_payment_report_form_opens(self):
        """The Payment Report wizard form must open and render the POS list.

        Odoo 19 removed the 'tree' view type. A field declared with
        mode="tree" makes the web client look for a default 'tree' view and
        the wizard fails with "No default view of type 'tree' could be found".
        """
        view = self.env.ref("l10n_ve_pos.pos_payment_report")
        arch = etree.fromstring(
            self.env["pos.payment.report"].get_view(view.id, "form")["arch"]
        )
        modes = [
            mode
            for node in arch.iter("field")
            for mode in (node.get("mode") or "").split(",")
            if mode
        ]
        self.assertNotIn("tree", modes)

        pos_config = self.env["pos.config"].create({"name": "Test POS"})
        with Form(self.env["pos.payment.report"], view=view) as wizard:
            wizard.pos_config_ids.add(pos_config)
        self.assertIn(pos_config, wizard.record.pos_config_ids)
