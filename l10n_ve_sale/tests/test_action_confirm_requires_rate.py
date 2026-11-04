from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo import fields


@tagged("post_install", "-at_install", "l10n_ve_sale")
class TestActionConfirmRequiresRate(TransactionCase):
    """compute_rate() raises by default when there is no rate for the date,
    so an order can no longer be created without one; action_confirm()
    keeps its own check for orders whose foreign_rate ended up at 0.
    """

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.ves = self.env.ref("base.VEF")
        self.usd = self.env.ref("base.USD")
        self.company.currency_id = self.ves
        self.company.foreign_currency_id = self.usd
        self.partner = self.env["res.partner"].create({"name": "Test Partner"})
        self.product = self.env["product.product"].create({
            "name": "Test Product",
            "list_price": 100.0,
        })

    def _create_rate(self):
        return self.env["res.currency.rate"].create({
            "currency_id": self.usd.id,
            "company_id": self.company.id,
            "name": fields.Date.today(),
            "rate": 1.0 / 380.0,
        })

    def _create_order(self, date_order):
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "date_order": date_order,
        })
        self.env["sale.order.line"].create({
            "order_id": so.id,
            "product_id": self.product.id,
            "product_uom_qty": 1,
            "price_unit": 100.0,
        })
        return so

    def test_create_without_rate_raises(self):
        """No USD rate exists for the date - creating the order raises the
        "no rate assigned" UserError of compute_rate()."""
        with self.assertRaises(UserError):
            self._create_order(fields.Date.today())

    def test_confirm_without_rate_raises(self):
        """An order whose foreign_rate ended up at 0 and has no rate for its
        date must not be confirmed silently."""
        rate = self._create_rate()
        so = self._create_order(fields.Date.today())
        rate.unlink()
        so.foreign_rate = 0.0

        with self.assertRaises(UserError):
            so.action_confirm()

    def test_confirm_with_rate_is_allowed(self):
        self._create_rate()
        so = self._create_order(fields.Date.today())
        self.assertNotEqual(so.foreign_rate, 0.0)

        so.action_confirm()
        self.assertEqual(so.state, "sale")

    def test_confirm_with_manually_set_rate_is_allowed(self):
        """manually_set_rate freezes the rate from outside compute_rate()
        entirely, so a missing currency-rate record must not block
        confirmation in that case."""
        rate = self._create_rate()
        so = self._create_order(fields.Date.today())
        so.write({"manually_set_rate": True, "foreign_rate": 123.0})
        rate.unlink()

        so.action_confirm()
        self.assertEqual(so.state, "sale")
