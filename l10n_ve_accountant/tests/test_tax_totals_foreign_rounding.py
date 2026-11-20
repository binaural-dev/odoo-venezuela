from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTaxTotalsForeignRounding(TransactionCase):
    """Invoice in a currency worth less than the company currency (Bs with the
    company in USD): the tax the form sends (computed in the document currency)
    differs from the tax booked through company-currency cents. That gap is
    rounding, not a manual edit, and must not block the invoice."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.currency_usd = cls.env.ref("base.USD")
        cls.currency_vef = cls.env.ref("base.VEF")
        (cls.currency_usd | cls.currency_vef).active = True
        cls.company = cls.env.ref("base.main_company")
        cls.company.write(
            {
                "currency_id": cls.currency_usd.id,
                "foreign_currency_id": cls.currency_vef.id,
                "account_fiscal_country_id": cls.env.ref("base.ve").id,
                "country_id": cls.env.ref("base.ve").id,
            }
        )
        Rate = cls.env["res.currency.rate"]
        # The form asks for the rate of "today" in the user's time zone: cover the days around UTC today.
        today = fields.Date.today()
        days = ("2020-01-01", fields.Date.subtract(today, days=1), today, fields.Date.add(today, days=1))
        for day in days:
            Rate.search([("currency_id", "=", cls.currency_vef.id), ("name", "=", day)]).unlink()
            Rate.create({"currency_id": cls.currency_vef.id, "name": day, "rate": 1020.0, "company_id": cls.company.id})
        # Own tax group, accounts and journal: the test does not depend on the loaded chart of accounts.
        tax_group = cls.env["account.tax.group"].create({"name": "Rounding test VAT", "company_id": cls.company.id})
        cls.tax = cls.env["account.tax"].create(
            {
                "name": "Rounding test 16%",
                "type_tax_use": "purchase",
                "amount_type": "percent",
                "amount": 16.0,
                "company_id": cls.company.id,
                "tax_group_id": tax_group.id,
            }
        )
        cls.expense = cls.env["account.account"].create(
            {"name": "Rounding test expense", "code": "699901", "account_type": "expense"}
        )
        payable = cls.env["account.account"].create(
            {"name": "Rounding test payable", "code": "299901", "account_type": "liability_payable", "reconcile": True}
        )
        cls.env["account.journal"].create(
            {"name": "Rounding test purchases", "code": "RNDP", "type": "purchase", "company_id": cls.company.id}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Rounding test wire",
                "standard_price": 1.0,
                "supplier_taxes_id": [Command.set(cls.tax.ids)],
                "property_account_expense_id": cls.expense.id,
            }
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "Rounding test vendor", "property_account_payable_id": payable.id}
        )
        base_groups = [cls.env.ref("base.group_user").id, cls.env.ref("account.group_account_invoice").id]
        cls.fiscal_user = cls.env["res.users"].create(
            {
                "name": "Rounding fiscal",
                "login": "rounding_fiscal_test",
                "company_id": cls.company.id,
                "company_ids": [Command.set(cls.company.ids)],
                "group_ids": [
                    Command.set(base_groups + [cls.env.ref("l10n_ve_accountant.group_fiscal_config_support").id])
                ],
            }
        )
        cls.plain_user = cls.env["res.users"].create(
            {
                "name": "Rounding plain",
                "login": "rounding_plain_test",
                "company_id": cls.company.id,
                "company_ids": [Command.set(cls.company.ids)],
                "group_ids": [Command.set(base_groups)],
            }
        )

    def _form_save(self, user, price=1000000.0):
        form = Form(self.env["account.move"].with_user(user).with_context(default_move_type="in_invoice"))
        form.partner_id = self.vendor
        form.currency_id = self.currency_vef
        form.invoice_date = "2020-01-01"
        form.ref = "ROUNDING-REF"
        with form.invoice_line_ids.new() as line:
            line.product_id = self.product
            line.quantity = 1
            line.price_unit = price
        return form.save()

    def test_form_save_keeps_the_exact_tax_shown_on_screen(self):
        # 16% of 1,000,000 Bs is 160,000.00 on screen; through USD cents the server books 159,997.20.
        move = self._form_save(self.fiscal_user)
        self.assertEqual(move.currency_id, self.currency_vef)
        tax_line = move.line_ids.filtered(lambda line: line.display_type == "tax")
        self.assertAlmostEqual(tax_line.amount_currency, 160000.0, places=2)
        self.assertAlmostEqual(tax_line.balance, 156.86, places=2)
        self.assertAlmostEqual(move.amount_tax, 160000.0, places=2)
        self.assertAlmostEqual(move.amount_total, 1160000.0, places=2)
        # Rounding is not logged as a manual tax edit.
        self.assertFalse(move.message_ids.filtered(lambda m: "Manual tax amount edit" in (m.body or "")))
        move.action_post()
        self.assertEqual(move.state, "posted")
        self.assertAlmostEqual(move.amount_tax, 160000.0, places=2)

    def test_form_save_by_a_user_without_the_fiscal_group(self):
        move = self._form_save(self.plain_user)
        self.assertEqual(move.currency_id, self.currency_vef)
        self.assertTrue(move.amount_tax)

    def test_a_real_manual_edit_is_still_blocked(self):
        move = self._form_save(self.fiscal_user)
        totals = move.tax_totals
        totals["subtotals"][0]["tax_groups"][0]["tax_amount_currency"] += 1000.0
        with self.assertRaises(UserError):
            move.with_user(self.fiscal_user).write({"tax_totals": totals})

    def test_a_user_without_the_fiscal_group_cannot_edit_the_tax(self):
        move = self._form_save(self.plain_user)
        totals = move.tax_totals
        totals["subtotals"][0]["tax_groups"][0]["tax_amount_currency"] += 1000.0
        with self.assertRaises(UserError):
            move.with_user(self.plain_user).write({"tax_totals": totals})

    def test_the_gap_is_rounding_only_for_a_weaker_document_currency(self):
        move = self._form_save(self.fiscal_user)
        tolerance = self.company.tax_totals_edit_tolerance * move.invoice_currency_rate
        self.assertTrue(move._is_tax_totals_rounding_gap(tolerance))
        self.assertFalse(move._is_tax_totals_rounding_gap(tolerance + 1.0))
        usd_move = self.env["account.move"].new({"currency_id": self.currency_usd.id, "company_id": self.company.id})
        self.assertFalse(usd_move._is_tax_totals_rounding_gap(0.01))
