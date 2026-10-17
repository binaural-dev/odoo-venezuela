from odoo import Command, fields
from odoo.tests import TransactionCase, tagged

from .common import AssertMixin, ensure_ve_base, set_usd_rate


@tagged("post_install", "-at_install", "l10n_ve_deductible")
class TestDeductibleMultiCompany(AssertMixin, TransactionCase):
    """The deductible is configured per company: the setting, the exempt tax
    and every check use the company of the bill, never the user's current one.
    Two VEF-base / USD-alternate companies, each with its own chart."""

    RATE = 0.00116565386887513
    LINES = [(10.3333, 3), (7.1249, 7), (0.9999, 13), (123.4567, 1), (3.3333, 9)]

    @classmethod
    def setUpClass(cls):
        """Loading a chart resets the company currency to the fiscal country's,
        so VEF base / USD alternate are set after it, in that order (the check
        compares both); there are no journal items yet."""
        super().setUpClass()
        ensure_ve_base(cls.env)
        cls.env.ref("product.decimal_price").digits = 4
        cls.vef, cls.usd = cls.env.ref("base.VEF"), cls.env.ref("base.USD")
        cls.company_a = cls.env.company
        cls.company_b = cls.env["res.company"].create({"name": "Compañía B"})
        cls.env["account.chart.template"].try_loading(
            "generic_coa", company=cls.company_b, install_demo=False
        )
        cls.company_b.currency_id = cls.vef
        cls.company_b.foreign_currency_id = cls.usd
        cls.env.user.company_ids |= cls.company_b
        for company in (cls.company_a, cls.company_b):
            set_usd_rate(cls.env, cls.RATE, company=company)
        cls.company_a.write({"use_deductible": True})
        cls.company_b.write({"use_deductible": False})
        cls.partner = cls.env["res.partner"].create({"name": "Proveedor MC2", "company_id": False})
        cls.tax = {}
        cls.product = cls.env["product.product"].create({"name": "Prod MC2", "company_id": False})
        for company in (cls.company_a, cls.company_b):
            cls.tax[company] = cls.env["account.tax"].with_company(company).create(
                {"name": "Ex MC2", "amount_type": "percent", "amount": 0.0,
                 "type_tax_use": "purchase", "company_id": company.id}
            )

    def _bill(self, company, **vals):
        return self.env["account.move"].with_company(company).create(
            {
                "move_type": "in_invoice",
                "company_id": company.id,
                "partner_id": self.partner.id,
                "currency_id": self.usd.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create({"product_id": self.product.id, "name": "L",
                                    "quantity": q, "price_unit": p,
                                    "tax_ids": [Command.set(self.tax[company].ids)]})
                    for p, q in self.LINES
                ],
                **vals,
            }
        )

    PERCENT = {"is_deductible": True, "global_deductible_type": "percent",
               "global_deductible_percent": 12.5}
    AMOUNT = {"is_deductible": True, "global_deductible_type": "amount",
              "global_deductible_amount": 77.77}

    def test_setting_is_per_company(self):
        self.assertTrue(self._bill(self.company_a).use_deductible)
        self.assertFalse(self._bill(self.company_b).use_deductible)
        bill_b = self._bill(self.company_b)
        self.assertFalse(bill_b.with_company(self.company_a).use_deductible)
        with self.assertRaisesMsg(Exception, "not enabled for this company"):
            self._bill(self.company_b, **self.PERCENT)
        self.assertTrue(self._bill(self.company_a, **self.PERCENT).is_deductible)

    def test_enabling_in_one_company_does_not_enable_the_other(self):
        self.company_b.use_deductible = True
        self.company_a.use_deductible = False
        self.assertTrue(self._bill(self.company_b, **self.PERCENT).is_deductible)
        with self.assertRaisesMsg(Exception, "not enabled for this company"):
            self._bill(self.company_a, **self.PERCENT)

    def test_settings_screen_edits_the_current_company_only(self):
        Settings = self.env["res.config.settings"]
        settings_b = Settings.with_company(self.company_b).create({})
        self.assertFalse(settings_b.use_deductible)
        settings_b.use_deductible = True
        settings_b.execute()
        self.assertTrue(self.company_b.use_deductible)
        self.assertTrue(self.company_a.use_deductible)
        settings_a = Settings.with_company(self.company_a).create({})
        self.assertTrue(settings_a.use_deductible)
        settings_a.use_deductible = False
        settings_a.execute()
        self.assertFalse(self.company_a.use_deductible)
        self.assertTrue(self.company_b.use_deductible)

    def test_exempt_tax_configuration_is_per_company(self):
        self.company_b.use_deductible = True
        fixed = {}
        for company in (self.company_a, self.company_b):
            fixed[company] = self.env["account.tax"].with_company(company).create(
                {"name": "Exento fijo", "amount_type": "fixed", "amount": 0.0,
                 "type_tax_use": "purchase", "company_id": company.id}
            )
        self.company_a.exent_aliquot_purchase = fixed[self.company_a]
        self.tax[self.company_a], keep_a = fixed[self.company_a], self.tax[self.company_a]
        self.tax[self.company_b], keep_b = fixed[self.company_b], self.tax[self.company_b]
        try:
            self.assertTrue(self._bill(self.company_a, **self.PERCENT).is_deductible)
            with self.assertRaisesMsg(Exception, "exempt tax"):
                self._bill(self.company_b, **self.PERCENT)
            self.company_b.exent_aliquot_purchase = fixed[self.company_b]
            self.assertTrue(self._bill(self.company_b, **self.PERCENT).is_deductible)
        finally:
            self.tax[self.company_a], self.tax[self.company_b] = keep_a, keep_b

    def test_same_figures_in_both_companies(self):
        self.company_b.use_deductible = True
        for method in ("round_per_line", "round_globally"):
            self.company_a.tax_calculation_rounding_method = method
            self.company_b.tax_calculation_rounding_method = method
            for deductible in (self.PERCENT, self.AMOUNT):
                with self.subTest(method=method, **deductible):
                    bill_a = self._bill(self.company_a, **deductible)
                    bill_b = self._bill(self.company_b, **deductible)
                    self.assertEqual(bill_a.amount_untaxed, bill_b.amount_untaxed)
                    self.assertEqual(bill_a.amount_total_signed, bill_b.amount_total_signed)
                    self.assertEqual(bill_a.invoice_line_ids.mapped("balance"),
                                     bill_b.invoice_line_ids.mapped("balance"))
                    self.assertEqual(bill_a.tax_totals["formatted_deductible_amount_ves"],
                                     bill_b.tax_totals["formatted_deductible_amount_ves"])
                    self.assertEqual(
                        bill_a.invoice_line_ids.mapped("global_deductible_line_amount"),
                        bill_b.invoice_line_ids.mapped("global_deductible_line_amount"),
                    )

    def test_credit_note_in_the_second_company(self):
        self.company_b.use_deductible = True
        bill = self._bill(self.company_b, **self.AMOUNT)
        bill.action_post()
        wizard = self.env["account.move.reversal"].with_company(self.company_b).with_context(
            active_model="account.move", active_ids=bill.ids
        ).create({"journal_id": bill.journal_id.id, "date": fields.Date.today()})
        wizard.modify_moves()
        refund = bill.reversal_move_ids
        self.assertEqual(refund.company_id, self.company_b)
        self.assertTrue(refund.is_deductible)
        self.assertEqual(refund.amount_total, bill.amount_total)
        self.company_b.use_deductible = False
        self.assertTrue(bill.is_deductible)
        self.assertEqual(bill.amount_total, refund.amount_total)
