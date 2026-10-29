from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_accountant_core")
class TestTotalsFooterAssets(TransactionCase):
    """The amount due must not be drawn on top of its label when the totals column is narrow."""

    def test_ves_box_has_the_totals_class(self):
        doc = etree.fromstring(self.env["account.move"].get_view(view_type="form")["arch"])
        boxes = doc.xpath("//group[hasclass('o_ve_invoice_totals')]")
        self.assertEqual(len(boxes), 1)
        self.assertTrue(boxes[0].xpath(".//field[@name='amount_residual_company']"))

    def test_standard_totals_block_keeps_the_class_the_style_relies_on(self):
        doc = etree.fromstring(self.env["account.move"].get_view(view_type="form")["arch"])
        self.assertTrue(doc.xpath("//group[hasclass('oe_invoice_lines_tab')]//field[@name='amount_residual']"))

    def test_backend_bundle_compiles_with_the_container_rules(self):
        bundle = self.env["ir.qweb"]._get_asset_bundle("web.assets_web", assets_params={})
        css = b"".join(attachment.raw for attachment in bundle.css()).decode()
        self.assertIn("container-name: o_ve_invoice_totals", css)
        self.assertIn("@container o_ve_invoice_totals (max-width: 360px)", css)
        self.assertIn(".o_form_view .oe_invoice_lines_tab > .o_group", css)
        # The nowrap must stay on the amount cell: the payments widget shares the group and has to wrap
        self.assertIn(".o_cell.o_wrap_input .o_field_widget{white-space: nowrap;}", css.replace("\n", ""))
