from odoo import Command, fields
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_accountant_invoice_details")
class TestInvoiceDetailsReport(TransactionCase):
    """Reporte "Detalle de ventas" (`account.invoices.details`) con documentos y pagos
    en distintas monedas.

    Cubre: el calculo de `detailed_amounts` por lote con varias monedas
    (`Expected singleton`), las claves de `tax_totals` de Odoo 19, el estado de los
    pagos en 19 y los totales del reporte en moneda de la compania."""

    USD_RATE = 380.0  # 1 USD = 380 VEF
    REPORT = "l10n_ve_accountant.report_account_invoices_details"

    def setUp(self):
        super().setUp()
        self.env.user.tz = "America/Caracas"
        self.ves = self.env.ref("base.VEF")
        self.usd = self.env.ref("base.USD")
        self.company = self.env.ref("base.main_company")
        country = self.env.ref("base.ve")
        self.company.write({
            "currency_id": self.ves.id,
            "foreign_currency_id": self.usd.id,
            "account_fiscal_country_id": country.id,
            "country_id": country.id,
        })
        self.today = fields.Date.today()
        self.env["res.currency.rate"].search(
            [("currency_id", "=", self.usd.id), ("name", "=", self.today)]
        ).unlink()
        self.env["res.currency.rate"].create({
            "name": self.today, "currency_id": self.usd.id,
            "company_id": self.company.id, "rate": 1.0 / self.USD_RATE,
        })
        self.acc_rec = self._account("120000", "Receivable", "asset_receivable", reconcile=True)
        self.acc_inc = self._account("400000", "Income", "income")
        self.acc_tax = self._account("200000", "Tax Payable", "liability_current", reconcile=True)
        group = self.env["account.tax.group"].create({
            "name": "IVA", "company_id": self.company.id, "country_id": country.id,
        })
        repartition = [
            Command.create({"repartition_type": "base", "factor_percent": 100.0}),
            Command.create({"repartition_type": "tax", "factor_percent": 100.0, "account_id": self.acc_tax.id}),
        ]
        self.tax_16 = self.env["account.tax"].with_company(self.company).create({
            "name": "IVA 16%", "amount": 16.0, "amount_type": "percent",
            "type_tax_use": "sale", "company_id": self.company.id,
            "tax_group_id": group.id,
            "invoice_repartition_line_ids": repartition,
            "refund_repartition_line_ids": repartition,
        })
        self.journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].create({
            "name": "Sales Details", "code": "SDET", "type": "sale",
            "company_id": self.company.id, "default_account_id": self.acc_inc.id,
        })
        self.bank = self.env["account.journal"].search(
            [("type", "=", "bank"), ("company_id", "=", self.company.id)], limit=1
        )
        self.partner = self.env["res.partner"].create({
            "name": "Detalle Partner", "country_id": country.id,
            "property_account_receivable_id": self.acc_rec.id,
        })
        self.product = self.env["product.product"].create({
            "name": "Detalle Service", "type": "service", "list_price": 100.0,
            "property_account_income_id": self.acc_inc.id,
            "taxes_id": [Command.clear()], "supplier_taxes_id": [Command.clear()],
        })
        self.pricelists = {
            cur: self.env["product.pricelist"].create(
                {"name": "PL " + cur.name, "currency_id": cur.id}
            )
            for cur in (self.ves, self.usd)
        }

    def _account(self, code, name, account_type, reconcile=False):
        account = self.env["account.account"].search(
            [("code", "=", code), ("company_ids", "in", self.company.id)], limit=1
        )
        return account or self.env["account.account"].create({
            "code": code, "name": name, "account_type": account_type,
            "company_ids": [Command.set([self.company.id])], "reconcile": reconcile,
        })

    def _invoice(self, currency, price_unit, quantity=1.0, discount=0.0, move_type="out_invoice"):
        invoice = self.env["account.move"].create({
            "move_type": move_type,
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "currency_id": currency.id,
            "pricelist_id": self.pricelists[currency].id,
            "invoice_date": self.today,
            "invoice_line_ids": [Command.create({
                "product_id": self.product.id, "quantity": quantity, "price_unit": price_unit,
                "discount": discount, "account_id": self.acc_inc.id,
                "tax_ids": [Command.set([self.tax_16.id])],
            })],
        })
        invoice._post()
        return invoice

    def _payment(self, currency, amount):
        payment = self.env["account.payment"].create({
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": self.partner.id, "amount": amount,
            "currency_id": currency.id, "journal_id": self.bank.id, "date": self.today,
        })
        payment.action_post()
        return payment

    def _mixed_invoices(self):
        """VEF 2.000 (+16%), USD 150 con 10% de descuento, VEF 4.750 con 5%, USD 120."""
        return (
            self._invoice(self.ves, 1000.0, quantity=2.0),
            self._invoice(self.usd, 50.0, quantity=3.0, discount=10.0),
            self._invoice(self.ves, 5000.0, discount=5.0),
            self._invoice(self.usd, 120.0),
        )

    def _wizard(self):
        form = Form(self.env["account.invoices.details"])
        form.date_from = self.today
        form.date_to = self.today
        return form.save()

    def _report_values(self):
        report = self.env["report." + self.REPORT]
        return report.get_sale_details(self._wizard())

    # ------------------------------------------------------------------
    # detailed_amounts
    # ------------------------------------------------------------------
    def test_detailed_amounts_batch_with_mixed_currencies(self):
        """Calcular el campo sobre un lote VEF+USD no debe fallar con `Expected singleton`
        y cada factura se formatea con su propia moneda."""
        invoices = self.env["account.move"].concat(*self._mixed_invoices())
        invoices.invalidate_recordset(["detailed_amounts"])
        amounts = {inv: inv.detailed_amounts for inv in invoices}
        ves_invoice, usd_invoice = invoices[0], invoices[1]
        self.assertIn("Bs", amounts[ves_invoice]["formatted_gross_amount"])
        self.assertIn("$", amounts[usd_invoice]["formatted_gross_amount"])
        self.assertIn("$", amounts[usd_invoice]["formatted_taxes_amount"])

    def test_detailed_amounts_values(self):
        """Bruto, descuento, base y IVA (claves de `tax_totals` de Odoo 19)."""
        usd_invoice = self._invoice(self.usd, 50.0, quantity=3.0, discount=10.0)
        amounts = usd_invoice.detailed_amounts
        self.assertAlmostEqual(amounts["gross_amount"], 150.0, places=2)
        self.assertAlmostEqual(amounts["discount_amount"], 15.0, places=2)
        # Base - descuento, no el bruto.
        self.assertAlmostEqual(amounts["gross_discount_amount"], 135.0, places=2)
        # IVA 16% sobre 135: antes salia 0 por leer claves inexistentes.
        self.assertAlmostEqual(amounts["taxes_amount"], 21.6, places=2)

    # ------------------------------------------------------------------
    # get_sale_details / render
    # ------------------------------------------------------------------
    def test_report_totals_are_in_company_currency(self):
        """Los totales convierten las facturas en USD a VEF con la tasa de cada una."""
        self._mixed_invoices()
        totals = self._report_values()["invoices"]["totals"]
        rate = self.USD_RATE
        gross = 2000.0 + 150.0 * rate + 5000.0 + 120.0 * rate
        discount = 0.0 + 15.0 * rate + 250.0 + 0.0
        taxes = 320.0 + 21.6 * rate + 760.0 + 19.2 * rate
        net = gross - discount + taxes
        self.assertAlmostEqual(totals["gross_amount"], gross, places=2)
        self.assertAlmostEqual(totals["discount_amount"], discount, places=2)
        self.assertAlmostEqual(totals["gross_discount_amount"], gross - discount, places=2)
        self.assertAlmostEqual(totals["taxes_amount"], taxes, places=2)
        self.assertAlmostEqual(totals["total_amount"], net, places=2)
        self.assertEqual(totals["total_items"], 4)
        self.assertIn("Bs", totals["formatted_total_amount"])
        self.assertNotIn("$", totals["formatted_total_amount"])

    def test_report_subtotals_by_currency(self):
        """Cada grupo de moneda lleva su subtotal en esa moneda, sin convertir."""
        self._mixed_invoices()
        invoices = self._report_values()["invoices"]
        journal = str(self.journal.id)
        by_currency = invoices[journal]["totals_out_invoice"]
        self.assertEqual(set(by_currency), {self.ves.id, self.usd.id})
        usd, ves = by_currency[self.usd.id], by_currency[self.ves.id]
        self.assertAlmostEqual(usd["gross_amount"], 270.0, places=2)
        self.assertAlmostEqual(usd["discount_amount"], 15.0, places=2)
        self.assertAlmostEqual(usd["taxes_amount"], 40.8, places=2)
        self.assertAlmostEqual(usd["total_amount"], 295.8, places=2)
        self.assertEqual(usd["total_items"], 2)
        self.assertIn("$", usd["formatted_total_amount"])
        self.assertAlmostEqual(ves["gross_amount"], 7000.0, places=2)
        self.assertAlmostEqual(ves["total_amount"], 7830.0, places=2)
        self.assertIn("Bs", ves["formatted_total_amount"])

    def test_report_html_groups_by_currency_and_ends_in_company_currency(self):
        self._mixed_invoices()
        self._payment(self.usd, 100.0)
        html = self.env["ir.actions.report"]._render_qweb_html(
            self.REPORT, self._wizard().ids
        )[0].decode()
        self.assertIn("Total Sales (VEF)", html)
        self.assertIn("Total Payments (VEF)", html)
        self.assertIn("$\xa0295.80", html)  # subtotal del grupo USD
        self.assertIn("7,830.00\xa0Bs", html)  # subtotal del grupo VEF
        # El total general en VEF va despues de los subtotales por moneda.
        self.assertGreater(html.index("Total Sales (VEF)"), html.index("$\xa0295.80"))

    def test_report_credit_note_subtracts(self):
        invoice = self._invoice(self.usd, 100.0)
        self._invoice(self.usd, 40.0, move_type="out_refund")
        totals = self._report_values()["invoices"]["totals"]
        # (100 - 40) * 1,16 USD en VEF
        self.assertAlmostEqual(totals["total_amount"], 60.0 * 1.16 * self.USD_RATE, places=2)
        self.assertEqual(invoice.currency_id, self.usd)

    def test_report_renders_html_with_mixed_currencies(self):
        """Imprimir desde el asistente: no falla y muestra cada linea en su moneda."""
        self._mixed_invoices()
        wizard = self._wizard()
        html = self.env["ir.actions.report"]._render_qweb_html(self.REPORT, wizard.ids)[0].decode()
        for name in self.env["account.move"].search([("move_type", "=", "out_invoice")]).mapped("name"):
            self.assertIn(name, html)
        self.assertIn("$\xa0150.00", html)
        self.assertIn("2,320.00\xa0Bs", html)

    def test_report_without_documents_renders(self):
        """`show_documents` desactivado tambien debe poder imprimirse."""
        self._mixed_invoices()
        wizard = self._wizard()
        wizard.show_documents = False
        html = self.env["ir.actions.report"]._render_qweb_html(self.REPORT, wizard.ids)[0]
        self.assertTrue(html)

    # ------------------------------------------------------------------
    # pagos
    # ------------------------------------------------------------------
    def test_report_includes_payments_and_totals(self):
        """Los pagos publicados en Odoo 19 (in_process/paid) aparecen; se subtotalizan por
        moneda y el total general va en moneda de la compania."""
        payments = self._payment(self.ves, 2320.0) | self._payment(self.usd, 100.0)
        payments |= self._payment(self.usd, 30.0)
        values = self._report_values()
        journal = str(self.bank.id)
        self.assertEqual(set(values["payments"][journal].ids), set(payments.ids))
        by_currency = values["payments"]["totals_" + journal]
        self.assertAlmostEqual(by_currency[self.usd.id]["amount"], 130.0, places=2)
        self.assertAlmostEqual(by_currency[self.ves.id]["amount"], 2320.0, places=2)
        self.assertIn("$", by_currency[self.usd.id]["formatted_amount"])
        total = values["payments"]["totals"]
        self.assertAlmostEqual(total["amount"], 2320.0 + 130.0 * self.USD_RATE, places=2)
        self.assertIn("Bs", total["formatted_amount"])

    def test_report_ignores_draft_payments(self):
        draft = self.env["account.payment"].create({
            "payment_type": "inbound", "partner_type": "customer",
            "partner_id": self.partner.id, "amount": 10.0,
            "currency_id": self.ves.id, "journal_id": self.bank.id, "date": self.today,
        })
        self.assertEqual(draft.state, "draft")
        self.assertFalse(self._report_values()["payments"])
