from odoo import _, fields
from odoo.tests import Form
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo.tests import tagged
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_sale")
class TestSaleOrderInvoice(TransactionCase):
    """Tests for generating invoices from sale orders in Venezuelan localization."""

    def setUp(self):
        super(TestSaleOrderInvoice, self).setUp()
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")
        self.company.write(
            {
                "currency_id": self.currency_vef.id,
                "currency_foreign_id": self.currency_usd.id,
            }
        )

        self.partner = self.env["res.partner"].create(
            {
                "name": "Cliente Prueba",
                "vat": "J12345678",
                "prefix_vat": "J",
                "country_id": self.env.ref("base.ve").id,
                "phone": "04141234567",
                "email": "cliente@prueba.com",
                "street": "Calle Falsa 123",
            }
        )

        self.tax_group = self.env["account.tax.group"].create(
            {
                "name": "IVA",
                "sequence": 10,
            }
        )

        # Crear impuesto IVA 16%
        self.tax_iva16 = self.env["account.tax"].create(
            {
                "name": "IVA 16%",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "tax_group_id": self.tax_group.id,
                "country_id": self.env.ref("base.ve").id,
            }
        )

        # Crear el producto
        self.product = self.env["product.product"].create(
            {
                "name": "Producto Prueba",
                "type": "service",
                "list_price": 100,
                "barcode": "123456789",
                "taxes_id": [(6, 0, [self.tax_iva16.id])],
            }
        )

        self.partner_a = self.env["res.partner"].create(
            {
                "name": "Test Partner A",
                "customer_rank": 1,
            }
        )

        sequence = self.env["ir.sequence"].create(
            {
                "name": "Secuencia Factura",
                "code": "account.move",
                "prefix": "INV/",
                "padding": 8,
                "number_next_actual": 2,
            }
        )
        refund_sequence = self.env["ir.sequence"].create(
            {
                "name": "nota de credito",
                "code": "",
                "prefix": "NC/",
                "padding": 8,
                "number_next_actual": 2,
            }
        )

        self.journal = self.env["account.journal"].create(
            {
                "name": "Diario de Ventas",
                "code": "VEN",
                "type": "sale",
                "sequence_id": sequence.id,
                "refund_sequence_id": refund_sequence.id,
                "company_id": self.env.company.id,
            }
        )

    def test_01_generate_invoice_from_sale_order(self):
        rate = 5.0
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "manually_set_rate": True,
                "foreign_rate": rate,
                "foreign_inverse_rate": 1 / rate,
            }
        )

        order_line_01 = self.env["sale.order.line"].create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 2,
                "price_unit": 100,
                "tax_id": [(6, 0, [self.tax_iva16.id])],
                "order_id": order.id,
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
                "foreign_rate": rate,
                "display_type": False,
                "name": "Test Product Line",
            }
        )

        order_line_02 = self.env["sale.order.line"].create(
            {
                "product_id": False,
                "product_uom_qty": 0,
                "price_unit": 0,
                "tax_id": [(6, 0, [self.tax_iva16.id])],
                "order_id": order.id,
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
                "foreign_rate": 0,
                "display_type": "line_section",
                "name": "Section Line",
            }
        )

        order_line_03 = self.env["sale.order.line"].create(
            {
                "product_id": False,
                "product_uom_qty": 0,
                "price_unit": 0,
                "tax_id": [(6, 0, [self.tax_iva16.id])],
                "order_id": order.id,
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
                "foreign_rate": 0,
                "display_type": "line_note",
                "name": "Section Line",
            }
        )

        order.write(
            {
                "order_line": [order_line_01.id, order_line_02.id, order_line_03.id],
            }
        )

        order.action_confirm()
        invoice = order._create_invoices()

        self.assertTrue(
            len(order.order_line) == len(invoice.invoice_line_ids),
            "The invoice created from the sales order must have the same number of lines as the sales order.",
        )
        _logger.info("test_01_generate_invoice_from_sale_order --- successfully")

    def test_02_error_generate_invoice_from_sale_order(self):
        rate = 5.0
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "manually_set_rate": True,
                "foreign_rate": rate,
                "foreign_inverse_rate": 1 / rate,
            }
        )

        order_line_02 = self.env["sale.order.line"].create(
            {
                "product_id": False,
                "product_uom_qty": 0,
                "price_unit": 0,
                "tax_id": [(6, 0, [self.tax_iva16.id])],
                "order_id": order.id,
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
                "foreign_rate": 0,
                "display_type": "line_section",
                "name": "Section Line",
            }
        )

        order_line_03 = self.env["sale.order.line"].create(
            {
                "product_id": False,
                "product_uom_qty": 0,
                "price_unit": 0,
                "tax_id": [(6, 0, [self.tax_iva16.id])],
                "order_id": order.id,
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
                "foreign_rate": 0,
                "display_type": "line_note",
                "name": "Section Line",
            }
        )

        order.write(
            {
                "order_line": [order_line_02.id, order_line_03.id],
            }
        )

        with self.assertRaises(UserError) as e:
            order.action_confirm()
            order._create_invoices()
        _logger.info("test_02_error_generate_invoice_from_sale_order --- successfully (%s)",e.exception,)


@tagged("post_install", "-at_install", "l10n_ve_sale")
class TestSaleOrderDuplicateForeignRate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")
        self.company.write({
            "currency_id": self.currency_vef.id,
            "currency_foreign_id": self.currency_usd.id,
        })
        self.partner = self.env["res.partner"].create({
            "name": "Cliente Prueba",
            "vat": "J12345678",
            "prefix_vat": "J",
            "country_id": self.env.ref("base.ve").id,
        })

    def _set_old_and_today_rates(self):
        old_date = fields.Datetime.now() - timedelta(days=60)
        rate_model = self.env["res.currency.rate"]
        rate_model.search([
            ("currency_id", "=", self.currency_usd.id),
            ("company_id", "=", self.company.id),
            ("name", "in", [old_date.date(), fields.Date.today()]),
        ]).unlink()
        rate_model.create({
            "currency_id": self.currency_usd.id,
            "company_id": self.company.id,
            "name": old_date.date(),
            "rate": 1 / 100.0,
        })
        rate_model.create({
            "currency_id": self.currency_usd.id,
            "company_id": self.company.id,
            "name": fields.Date.today(),
            "rate": 1 / 200.0,
        })
        return old_date

    def test_01_duplicate_order_updates_foreign_rate(self):
        self.company.update_sale_order_rate_using_date_order = False
        old_date = self._set_old_and_today_rates()

        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "date_order": old_date,
        })
        self.assertAlmostEqual(
            order.foreign_rate, 100.0, places=4,
            msg="test premise: the original order must pick up the old rate",
        )

        duplicate = order.copy()

        self.assertAlmostEqual(
            duplicate.foreign_rate, 200.0, places=4,
            msg="duplicating an old order must refresh the alterno rate to "
                "today's, not keep it frozen at the original order's rate",
        )
        _logger.info("test_01_duplicate_order_updates_foreign_rate --- successfully")

    def test_02_duplicate_manual_rate_order_also_updates_rate(self):
        self.company.update_sale_order_rate_using_date_order = False
        old_date = self._set_old_and_today_rates()

        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "date_order": old_date,
            "manually_set_rate": True,
            "foreign_rate": 999.99,
            "foreign_inverse_rate": 1 / 999.99,
        })

        duplicate = order.copy()

        self.assertFalse(
            duplicate.manually_set_rate,
            "manually_set_rate must not survive a duplicate",
        )
        self.assertAlmostEqual(
            duplicate.foreign_rate, 200.0, places=4,
            msg="a duplicate must get today's alterno rate even if the "
                "original had manually_set_rate=True",
        )
        _logger.info("test_02_duplicate_manual_rate_order_also_updates_rate --- successfully")
