from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestNoForeignCurrencyPageSaleOrder(TransactionCase):
    """La página "Foreign currency" y su grupo de visibilidad fueron eliminados."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        other = cls.env["res.currency"].with_context(active_test=False).search(
            [("id", "!=", company.currency_id.id), ("name", "in", ["USD", "VEF", "VES", "EUR"])],
            limit=1,
        )
        other.active = True
        company.foreign_currency_id = other

    def test_group_does_not_exist(self):
        self.assertFalse(
            self.env.ref("l10n_ve_sale.group_foreign_currency_view_sales", raise_if_not_found=False),
            "El grupo l10n_ve_sale.group_foreign_currency_view_sales ya no debe existir",
        )
        self.assertFalse(
            self.env["ir.model.data"].search_count(
                [("module", "=", "l10n_ve_sale"), ("name", "=", "group_foreign_currency_view_sales")]
            )
        )

    def test_form_has_no_foreign_currency_page(self):
        doc = etree.fromstring(self.env["sale.order"].get_view(view_type="form")["arch"])
        self.assertFalse(
            doc.xpath("//page[@name='foreign_currency']"),
            "La página foreign_currency no debe aparecer en el formulario de sale.order",
        )
        self.assertFalse(
            doc.xpath("//field[@widget='account-tax-foreign-totals-field']"),
            "El widget account-tax-foreign-totals-field no debe aparecer en el formulario de sale.order",
        )

    def test_no_view_defines_foreign_currency_page(self):
        """`get_view` oculta las páginas con `groups` al usuario actual, así que
        también se revisa el arch crudo de todas las vistas del modelo."""
        views = self.env["ir.ui.view"].with_context(active_test=False).search(
            [("model", "=", "sale.order"), ("type", "=", "form")]
        )
        self.assertTrue(views)
        for view in views:
            self.assertNotIn(
                'name="foreign_currency"', view.arch_db, f"{view.xml_id or view.name} define la página"
            )
            self.assertNotIn(
                "account-tax-foreign-totals-field", view.arch_db, f"{view.xml_id or view.name} usa el widget"
            )
