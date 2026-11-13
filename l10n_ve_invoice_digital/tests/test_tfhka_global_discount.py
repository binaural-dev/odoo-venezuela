from odoo import Command, fields
from odoo.tests import TransactionCase, tagged

from ..services.tfhka_service_base import TfhkaDataError


@tagged("post_install", "-at_install", "l10n_ve_invoice_digital")
class TestTfhkaGlobalDiscount(TransactionCase):
    """The global discount of `l10n_ve_sale` (optional) in the TFHKA document:
    over the subtotal the totals go out net and nothing is discounted twice;
    over the total the document would not add up, so it is refused."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "discount_mode" not in cls.env["account.move"]._fields:
            cls.has_discounts = False
            return
        cls.has_discounts = True
        cls.company = cls.env.company
        cur = cls.env.ref("base.USD") if cls.company.currency_id != cls.env.ref("base.USD") else cls.env.ref("base.VEF")
        cur.active = True
        cls.company.foreign_currency_id = cur
        if not cls.env["res.currency.rate"].search_count(
            [("currency_id", "=", cur.id), ("company_id", "=", cls.company.id), ("name", "=", fields.Date.today())]
        ):
            cls.env["res.currency.rate"].create(
                {
                    "currency_id": cur.id,
                    "company_id": cls.company.id,
                    "name": fields.Date.today(),
                    "inverse_company_rate": 50.0,
                }
            )
        cls.company.global_discount_account_id = cls.env["account.account"].create(
            {"code": "TFD001", "name": "Global discounts", "account_type": "income"}
        )
        group = cls.env["account.tax.group"].create(
            {"name": "IVA 16%", "country_id": cls.company.country_id.id}
        )
        cls.tax = cls.env["account.tax"].create(
            {
                "name": "IVA 16% tfhka discount",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "tax_group_id": group.id,
            }
        )
        cls.partner = cls.env["res.partner"].create({"name": "Cliente TFHKA descuento"})
        cls.product = cls.env["product.product"].create({"name": "Producto TFHKA", "type": "service"})

    def setUp(self):
        super().setUp()
        if not self.has_discounts:
            self.skipTest("l10n_ve_sale is not installed")

    def _invoice(self):
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 1000.0,
                            "tax_ids": [Command.set(self.tax.ids)],
                        }
                    )
                ],
            }
        )

    def test_global_discount_over_the_total_is_refused_before_sending(self):
        self.company.invoice_digital_tfhka = True
        invoice = self._invoice()
        invoice._apply_discount("global_total", "percent", 10)
        with self.assertRaisesRegex(TfhkaDataError, "over the total"):
            self.env["tfhka.document.service"].send_document(invoice)

    def test_global_discount_over_the_subtotal_goes_out_net_without_a_second_discount(self):
        invoice = self._invoice()
        invoice._apply_discount("global_subtotal", "amount", 100)
        totals, _foreign = self.env["tfhka.document.service"]._prepare_totals(invoice)
        self.assertEqual(totals["subtotal"], "900.0")
        self.assertEqual(totals["totalIVA"], "144.0")
        self.assertEqual(totals["montoTotalConIVA"], "1044.0")
        self.assertNotIn("totalDescuento", totals)
