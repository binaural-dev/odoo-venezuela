from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged("post_install", "-at_install", "l10n_ve_sale")
class TestSaleOrderVat(TransactionCase):

    def setUp(self):
        super().setUp()
        # Sin tasa del día la orden no se crea (compute_rate lanza UserError)
        company = self.env.company
        currency = company.foreign_currency_id or self.env.ref("base.VEF")
        if not self.env["res.currency.rate"].search_count([
            ("currency_id", "=", currency.id),
            ("company_id", "=", company.id),
            ("name", "=", fields.Date.today()),
        ]):
            self.env["res.currency.rate"].create({
                "currency_id": currency.id,
                "company_id": company.id,
                "name": fields.Date.today(),
                "inverse_company_rate": 50.0,
            })
        self.partner_no_vat = self.env["res.partner"].create({
            "name": "Partner Sin VAT",
        })
        self.partner_with_vat = self.env["res.partner"].create({
            "name": "Partner Con VAT",
            "vat": "123456789",
            "prefix_vat": False,
        })
        self.partner_with_prefix_vat = self.env["res.partner"].create({
            "name": "Partner Con Prefix VAT",
            "prefix_vat": "J",
            "vat": "123456789",
        })

    def test_vat_empty_when_partner_has_no_vat(self):
        so = self.env["sale.order"].create({
            "partner_id": self.partner_no_vat.id,
        })
        self.assertEqual(so.vat, "")

    def test_vat_computed_from_partner_without_prefix(self):
        so = self.env["sale.order"].create({
            "partner_id": self.partner_with_vat.id,
        })
        self.assertEqual(so.vat, "123456789")

    def test_vat_computed_from_partner_with_prefix(self):
        so = self.env["sale.order"].create({
            "partner_id": self.partner_with_prefix_vat.id,
        })
        self.assertEqual(so.vat, "J123456789")
