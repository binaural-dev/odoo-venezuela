from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_invoice", "l10n_ve_invoice_free_form_description")
class TestFreeFormLineDescription(TransactionCase):
    """The free-form invoice prints the description of a line as Odoo 19 did."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        company.currency_id = cls.env.ref("base.VEF")
        company.foreign_currency_id = cls.env.ref("base.USD")
        company.external_report_layout_id = cls.env.ref("web.external_layout_standard")
        today = fields.Date.today()
        Rate = cls.env["res.currency.rate"]
        for currency, rate in ((cls.env.ref("base.VEF"), 1.0), (cls.env.ref("base.USD"), 40.0)):
            if not Rate.search([("name", "=", today), ("currency_id", "=", currency.id), ("company_id", "=", company.id)]):
                Rate.create({"name": today, "currency_id": currency.id, "inverse_company_rate": rate, "company_id": company.id})
        receivable = cls.env["account.account"].create({
            "name": "Free Form Receivable", "code": "1111190", "account_type": "asset_receivable", "reconcile": True,
        })
        revenue = cls.env["account.account"].create({
            "name": "Free Form Revenue", "code": "4444490", "account_type": "income",
        })
        cls.partner = cls.env["res.partner"].create({
            "name": "Free Form Partner", "property_account_receivable_id": receivable.id,
        })
        cls.journal = cls.env["account.journal"].create({
            "name": "Free Form Sales", "type": "sale", "code": "FFS1", "default_account_id": revenue.id,
        })
        Product = cls.env["product.product"]
        common = {"type": "service", "property_account_income_id": revenue.id, "taxes_id": [Command.clear()]}
        cls.plain_product = Product.create({"name": "Plain Product", **common})
        cls.described_product = Product.create({
            "name": "Described Product", "description_sale": "Its sale description", **common,
        })

    def _invoice(self, lines):
        return self.env["account.move"].with_context(check_move_validity=False).create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [Command.create({"quantity": 1, "price_unit": 100.0, **line}) for line in lines],
        })

    def test_line_without_text_prints_the_product(self):
        line = self._invoice([{"product_id": self.plain_product.id}]).invoice_line_ids
        self.assertEqual(line._get_free_form_description(), "Plain Product")

    def test_line_with_the_product_description_prints_product_and_description(self):
        line = self._invoice([{"product_id": self.described_product.id}]).invoice_line_ids
        self.assertEqual(line._get_free_form_description(), "Described Product\nIts sale description")

    def test_line_with_its_own_text_prints_only_that_text(self):
        line = self._invoice([{"product_id": self.plain_product.id, "name": "Text written on the line"}]).invoice_line_ids
        self.assertEqual(line._get_free_form_description(), "Text written on the line")

    def test_free_form_prints_the_description_of_every_line(self):
        invoice = self._invoice([
            {"product_id": self.plain_product.id},
            {"product_id": self.described_product.id},
            {"product_id": self.plain_product.id, "name": "Text written on the line"},
        ])
        invoice.with_context(move_action_post_alert=True).action_post()
        html = self.env["ir.actions.report"]._render_qweb_html(
            "l10n_ve_invoice.action_invoice_free_form_l10n_ve_invoice", invoice.ids
        )[0]
        html = html.decode() if isinstance(html, bytes) else str(html)
        for expected in ("Plain Product", "Described Product", "Its sale description", "Text written on the line"):
            self.assertIn(expected, html)
