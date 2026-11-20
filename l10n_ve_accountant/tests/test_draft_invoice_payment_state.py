from odoo import Command
from odoo.tests import tagged

from .test_indexed_payments import TestIndexedPayments


@tagged("post_install", "-at_install", "l10n_ve_accountant_draft_invoice_payment_state")
class TestDraftInvoicePaymentState(TestIndexedPayments):
    """
    Una factura en borrador no queda pagada al guardarse.

    En borrador el nucleo calcula amount_residual a partir de tax_totals, y el
    resumen de impuestos de la localizacion lee montos de la factura mientras
    se arma. Sin volver a calcular el saldo despues, la factura quedaba con
    saldo 0 y payment_state 'paid' aunque su linea por cobrar siguiera
    pendiente.
    """

    def setUp(self):
        super().setUp()
        self._set_rate(self.currency_usd, self.invoice_date, 900.0)

    def _create_draft_invoice(self):
        return self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "currency_id": self.currency_usd.id,
            "invoice_date": self.invoice_date,
            "date": self.invoice_date,
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.product.id, "quantity": 1, "price_unit": 100.0,
                    "account_id": self.account_income.id, "tax_ids": [Command.set([self.test_tax.id])],
                }),
            ],
        })

    def _recompute_tax_totals_first(self, invoice):
        """Deja pendientes tax_totals y los montos de la factura y calcula
        tax_totals primero: el orden en que queda la factura cuando otro
        campo que depende de tax_totals se recalcula antes que los montos
        (por ejemplo, al crearla desde una cotizacion con mas modulos
        instalados). Sin forzarlo, el orden depende de los modulos
        instalados y la prueba no reproduce el caso."""
        self.env.flush_all()
        amount_fields = [
            field for field in invoice._fields.values()
            if field.store and field.compute == invoice._fields["amount_residual"].compute
        ]
        for field in amount_fields + [invoice._fields["payment_state"]]:
            self.env.add_to_compute(field, invoice)
        invoice.invalidate_recordset(["tax_totals"])
        invoice.tax_totals  # noqa: B018 - dispara el calculo en este orden

    def _assert_unpaid_draft(self, invoice):
        self._recompute_tax_totals_first(invoice)
        self.env.flush_all()
        self.env.invalidate_all()
        receivable = invoice.line_ids.filtered(lambda line: line.display_type == "payment_term")
        self.assertEqual(invoice.state, "draft")
        self.assertTrue(invoice.amount_total)
        self.assertAlmostEqual(invoice.amount_residual, invoice.amount_total, places=2)
        self.assertAlmostEqual(
            invoice.amount_residual, sum(receivable.mapped("amount_residual_currency")), places=2
        )
        self.assertEqual(invoice.payment_state, "not_paid")

    def test_new_draft_invoice_is_not_paid(self):
        self._assert_unpaid_draft(self._create_draft_invoice())

    def test_draft_invoice_currency_change_is_not_paid(self):
        invoice = self._create_draft_invoice()
        self.env.flush_all()
        invoice.write({"currency_id": self.currency_vef.id})
        self._assert_unpaid_draft(invoice)
