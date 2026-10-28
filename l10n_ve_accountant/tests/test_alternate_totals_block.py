import re

from lxml import etree

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_accountant_alternate_totals")
class TestAlternateTotalsBlock(TransactionCase):
    """El segundo bloque de totales (`account-tax-ves-totals-field`) muestra los
    montos en VES cuando el documento esta en otra moneda y los de la moneda de
    referencia cuando el documento esta en la moneda de la compania."""

    USD_RATE = 380.0  # 1 USD = 380 VEF

    def setUp(self):
        super().setUp()
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
        today = fields.Date.today()
        self.env["res.currency.rate"].create({
            "name": today, "currency_id": self.usd.id,
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
            "name": "Sales Alt Totals", "code": "SALT", "type": "sale",
            "company_id": self.company.id, "default_account_id": self.acc_inc.id,
        })
        self.partner = self.env["res.partner"].create({
            "name": "Alt Totals Partner", "country_id": country.id,
            "property_account_receivable_id": self.acc_rec.id,
        })
        self.product = self.env["product.product"].create({
            "name": "Alt Totals Service", "type": "service", "list_price": 100.0,
            "property_account_income_id": self.acc_inc.id,
            "taxes_id": [Command.clear()], "supplier_taxes_id": [Command.clear()],
        })

    @staticmethod
    def _digits(text):
        return re.sub(r"\D", "", text)

    def _account(self, code, name, account_type, reconcile=False):
        account = self.env["account.account"].search(
            [("code", "=", code), ("company_ids", "in", self.company.id)], limit=1
        )
        return account or self.env["account.account"].create({
            "code": code, "name": name, "account_type": account_type,
            "company_ids": [Command.set([self.company.id])], "reconcile": reconcile,
        })

    def _invoice(self, currency, price_unit):
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "currency_id": currency.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [Command.create({
                "product_id": self.product.id, "quantity": 1.0, "price_unit": price_unit,
                "account_id": self.acc_inc.id, "tax_ids": [Command.set([self.tax_16.id])],
            })],
        })
        invoice.action_post()
        return invoice

    def test_company_currency_invoice_exposes_reference_currency_amounts(self):
        """Factura en VEF: el bloque alterno usa la moneda de referencia (USD)."""
        invoice = self._invoice(self.ves, 3800.0)
        totals = invoice.tax_totals
        self.assertEqual(totals["currency_id"], self.ves.id)
        self.assertEqual(totals["ves_currency_id"], self.ves.id)
        self.assertEqual(totals["foreign_currency_id"], self.usd.id)
        self.assertAlmostEqual(totals["total_amount_currency"], 4408.0, places=2)
        self.assertAlmostEqual(totals["base_amount_foreign_currency"], 10.0, places=2)
        self.assertAlmostEqual(totals["tax_amount_foreign_currency"], 1.6, places=2)
        self.assertAlmostEqual(totals["total_amount_foreign_currency"], 11.6, places=2)
        subtotal = totals["subtotals"][0]
        self.assertAlmostEqual(subtotal["base_amount_foreign_currency"], 10.0, places=2)
        group = subtotal["tax_groups"][0]
        self.assertAlmostEqual(group["base_amount_foreign_currency"], 10.0, places=2)
        self.assertAlmostEqual(group["tax_amount_foreign_currency"], 1.6, places=2)

    def test_foreign_currency_invoice_exposes_company_currency_amounts(self):
        """Factura en USD: el bloque alterno sigue mostrando VEF, como antes."""
        invoice = self._invoice(self.usd, 100.0)
        totals = invoice.tax_totals
        self.assertEqual(totals["currency_id"], self.usd.id)
        self.assertEqual(totals["ves_currency_id"], self.ves.id)
        self.assertNotEqual(totals["currency_id"], totals["ves_currency_id"])
        self.assertAlmostEqual(totals["total_amount_currency"], 116.0, places=2)
        self.assertAlmostEqual(abs(invoice.amount_total_signed), 44080.0, places=2)
        self.assertIn("4408000", self._digits(totals["formatted_total_amount_currency_ves"]))
        self.assertIn("3800000", self._digits(totals["subtotals"][0]["formatted_base_amount_currency_ves"]))
        self.assertIn("608000", self._digits(totals["subtotals"][0]["tax_groups"][0]["formatted_tax_amount_currency_ves"]))

    def test_form_has_native_and_alternate_widgets(self):
        arch = etree.fromstring(self.env["account.move"].get_view(view_type="form")["arch"])
        for widget in ("account-tax-totals-field", "account-tax-ves-totals-field"):
            self.assertTrue(arch.xpath(f"//field[@name='tax_totals'][@widget='{widget}']"), widget)
        ves = arch.xpath("//field[@name='tax_totals'][@widget='account-tax-ves-totals-field']")[0]
        self.assertNotIn("currency_id", (ves.getparent().get("invisible") or ""))
        self.assertFalse(arch.xpath("//page[@name='foreign_currency']"))

    def test_alternate_block_has_no_residual_amount(self):
        """El unico monto adeudado es el nativo (`amount_residual`): el bloque alterno solo
        muestra `tax_totals`, sin `amount_residual_company`, en ninguna moneda del documento."""
        arch = etree.fromstring(self.env["account.move"].get_view(view_type="form")["arch"])
        self.assertFalse(arch.xpath("//field[@name='amount_residual_company']"))
        self.assertTrue(arch.xpath("//field[@name='amount_residual']"))

    def test_company_without_reference_currency(self):
        """Sin moneda de referencia no hay montos alternos que mostrar."""
        self.company.foreign_currency_id = False
        invoice = self._invoice(self.ves, 3800.0)
        self.assertFalse(invoice.foreign_currency_id)
        self.assertFalse(invoice.tax_totals.get("foreign_currency_id"))
