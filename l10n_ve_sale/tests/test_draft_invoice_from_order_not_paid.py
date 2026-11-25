from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "l10n_ve_sale_draft_invoice_not_paid")
class TestDraftInvoiceFromOrderNotPaid(TransactionCase):
    """La factura en borrador creada desde la cotizacion ("Crear factura")
    no queda pagada con saldo 0 (ticket 86558)."""

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.ves = self.env.ref("base.VEF")
        self.usd = self.env.ref("base.USD")
        self.company.write({"currency_id": self.ves.id, "foreign_currency_id": self.usd.id})
        today = fields.Date.today()
        for currency, rate in ((self.usd, 50.0),):
            self.env["res.currency.rate"].create({
                "currency_id": currency.id, "company_id": self.company.id,
                "name": today, "inverse_company_rate": rate,
            })
        self.partner = self.env["res.partner"].create({"name": "Partner 86558"})
        self.product = self.env["product.product"].create({"name": "Producto 86558", "list_price": 100.0})
        self.pricelist = self.env["product.pricelist"].create({
            "name": "PL 86558", "currency_id": self.usd.id, "company_id": self.company.id,
        })

    def _invoice_from_order(self):
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "pricelist_id": self.pricelist.id,
            "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 1, "price_unit": 100.0})],
        })
        order.action_confirm()
        invoice = order._create_invoices()
        self._recompute_tax_totals_first(invoice)
        return invoice

    def _recompute_tax_totals_first(self, invoice):
        """Deja pendientes tax_totals y los montos y calcula tax_totals primero:
        el orden en que queda la factura segun los modulos instalados."""
        self.env.flush_all()
        compute = invoice._fields["amount_residual"].compute
        for field in invoice._fields.values():
            if field.store and field.compute == compute:
                self.env.add_to_compute(field, invoice)
        self.env.add_to_compute(invoice._fields["payment_state"], invoice)
        invoice.invalidate_recordset(["tax_totals"])
        self.assertTrue(invoice.tax_totals)
        self.env.flush_all()
        self.env.invalidate_all()

    def test_invoice_from_order_is_not_paid(self):
        invoice = self._invoice_from_order()
        self.assertEqual(invoice.state, "draft")
        self.assertTrue(invoice.amount_total)
        self.assertAlmostEqual(invoice.amount_residual, invoice.amount_total, places=2)
        self.assertEqual(invoice.payment_state, "not_paid")

    def test_invoice_from_order_currency_change_is_not_paid(self):
        invoice = self._invoice_from_order()
        invoice.write({"currency_id": self.ves.id})
        self._recompute_tax_totals_first(invoice)
        self.assertTrue(invoice.amount_total)
        self.assertAlmostEqual(invoice.amount_residual, invoice.amount_total, places=2)
        self.assertEqual(invoice.payment_state, "not_paid")
