from lxml import etree

from odoo.tests import TransactionCase, tagged

VAT_FIELD_JS = "l10n_ve_contact/static/src/fields/vat_field/vat_field.js"
VAT_FIELD_XML = "l10n_ve_contact/static/src/fields/vat_field/vat_field.xml"


@tagged("res_partner", "bin", "-at_install", "post_install")
class TestVatFieldWidget(TransactionCase):
    """The CI/RIF of the contact form only takes digits while typing (ticket 16093).

    The filtering itself is covered by the Hoot tests in
    static/tests/unit/vat_field.test.js; these tests guard what the browser
    needs to run it: the widget on the field and the widget in every bundle
    that renders the contact form.
    """

    def _vat_widgets(self, view_id=False):
        arch = self.env["res.partner"].get_views([(view_id, "form")])["views"]["form"]["arch"]
        return [node.get("widget") for node in etree.fromstring(arch).xpath("//field[@name='vat']")]

    def _bundle_paths(self, bundle):
        # Each item is a tuple whose first element is the file path.
        return [asset[0] for asset in self.env["ir.asset"]._get_asset_paths(bundle, {})]

    def test_contact_form_vat_uses_digits_widget(self):
        widgets = self._vat_widgets()
        self.assertTrue(widgets, "The contact form must show the CI/RIF field")
        self.assertEqual(set(widgets), {"l10n_ve_vat"})

    def test_forms_built_on_the_contact_form_keep_the_widget(self):
        # The PoS contact form (l10n_ve_pos.view_partner_form_pos) is one of
        # them: a primary view built on base.view_partner_form.
        views = self.env["ir.ui.view"].search(
            [
                ("model", "=", "res.partner"),
                ("type", "=", "form"),
                ("mode", "=", "primary"),
                ("inherit_id", "=", self.env.ref("base.view_partner_form").id),
            ]
        )
        checked = 0
        for view in views:
            widgets = self._vat_widgets(view.id)
            if widgets:
                self.assertEqual(set(widgets), {"l10n_ve_vat"}, view.xml_id or view.name)
                checked += 1
        if not checked:
            self.skipTest("No primary contact form with a CI/RIF (e.g. l10n_ve_pos is not installed)")

    def test_partner_autocomplete_does_not_replace_the_widget(self):
        # partner_autocomplete is auto_install: when it is there, its
        # _get_view puts its own widget on vat, and ours must win. The arch
        # is simulated so the test does not depend on it being installed;
        # _get_view is called directly because get_views is cached.
        self.patch(
            type(self.env["ir.ui.view"]),
            "_get_combined_arch",
            lambda view: etree.fromstring(
                '<form><field name="name"/><field name="vat" widget="field_partner_autocomplete"/></form>'
            ),
        )
        view = self.env.ref("base.view_partner_form")
        arch, _view = self.env["res.partner"]._get_view(view.id, "form")
        self.assertEqual(arch.xpath("//field[@name='vat']/@widget"), ["l10n_ve_vat"])

    def test_digits_widget_in_backend_bundle(self):
        paths = self._bundle_paths("web.assets_backend")
        for asset in (VAT_FIELD_JS, VAT_FIELD_XML):
            self.assertTrue(any(path.endswith(asset) for path in paths), asset)

    def test_digits_widget_in_pos_bundle(self):
        # The PoS renders the backend contact form in a dialog: without the
        # widget in its bundle the CI/RIF falls back to the plain char field.
        paths = self._bundle_paths("point_of_sale._assets_pos")
        for asset in (VAT_FIELD_JS, VAT_FIELD_XML):
            self.assertTrue(any(path.endswith(asset) for path in paths), asset)
