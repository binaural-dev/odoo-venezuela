from .common import DeductibleCase, ensure_ve_base, set_usd_rate


class TestDeductibleMultiCompany(DeductibleCase):
    """Setting, scope and exempt tax are per company: every check uses the
    company of the document, never the one the user is working in."""

    @classmethod
    def setUpClass(cls):
        """Loading a chart resets the company currency to the fiscal country's,
        so VEF base / USD alternate are set after it, in that order (the check
        compares both); there are no journal items yet."""
        super().setUpClass()
        ensure_ve_base(cls.env)
        cls.company_b = cls.env["res.company"].create({"name": "Compañía B"})
        cls.env["account.chart.template"].try_loading("generic_coa", company=cls.company_b, install_demo=False)
        cls.company_b.currency_id = cls.vef
        cls.company_b.foreign_currency_id = cls.usd
        cls.env.user.company_ids |= cls.company_b
        set_usd_rate(cls.env, cls.RATES[0], company=cls.company_b)
        cls.company_b.write({"use_deductible": True, "deductible_scope": "both"})
        cls.taxes[cls.company_b] = cls._make_taxes(cls.company_b)

    def _doc_b(self, move_type="in_invoice", **vals):
        return self._doc(move_type=move_type, company=self.company_b, **vals)

    def test_scope_is_independent_per_company(self):
        self.company.deductible_scope = "vendor"
        self.company_b.deductible_scope = "customer"
        self.assertTrue(self._doc(move_type="in_invoice", **self.PERCENT).is_deductible)
        self.assertTrue(self._doc_b("out_invoice", **self.PERCENT).is_deductible)
        with self.assertRaisesMsg(Exception, "not enabled for this company"):
            self._doc(move_type="out_invoice", **self.PERCENT)
        with self.assertRaisesMsg(Exception, "not enabled for this company"):
            self._doc_b("in_invoice", **self.PERCENT)
        self.assertFalse(self._doc_b("in_invoice").with_company(self.company).deductible_allowed)

    def test_enabling_one_company_does_not_enable_the_other(self):
        self.company.use_deductible = False
        self.assertTrue(self._doc_b(**self.PERCENT).is_deductible)
        with self.assertRaisesMsg(Exception, "not enabled for this company"):
            self._doc(**self.PERCENT)

    def test_settings_screen_edits_the_current_company_only(self):
        Settings = self.env["res.config.settings"]
        settings = Settings.with_company(self.company_b).create({})
        self.assertEqual((settings.use_deductible, settings.deductible_scope), (True, "both"))
        settings.write({"use_deductible": False, "deductible_scope": "vendor"})
        settings.execute()
        self.assertEqual((self.company_b.use_deductible, self.company_b.deductible_scope), (False, "vendor"))
        self.assertEqual((self.company.use_deductible, self.company.deductible_scope), (True, "both"))

    def test_taxed_documents_are_allowed_in_both_companies(self):
        general = {company: self.tax("general", company=company) for company in (self.company, self.company_b)}
        self.assertTrue(self._doc(tax=general[self.company], **self.PERCENT).is_deductible)
        self.assertTrue(self._doc_b(tax=general[self.company_b], **self.PERCENT).is_deductible)

    def test_same_figures_in_both_companies(self):
        for method in self.METHODS:
            for company in (self.company, self.company_b):
                company.tax_calculation_rounding_method = method
            for values in (self.PERCENT, self.AMOUNT):
                with self.subTest(method=method, mode=values["global_deductible_type"]):
                    mine, other = self._doc(**values), self._doc_b(**values)
                    self.assertEqual(mine.amount_untaxed, other.amount_untaxed)
                    self.assertEqual(mine.invoice_line_ids.mapped("balance"), other.invoice_line_ids.mapped("balance"))
                    self.assertEqual(
                        mine.invoice_line_ids.mapped("global_deductible_line_amount"),
                        other.invoice_line_ids.mapped("global_deductible_line_amount"),
                    )

    def test_credit_note_in_the_second_company_survives_disabling_the_setting(self):
        doc = self._post(self._doc_b(**self.AMOUNT))
        wizard = self.env["account.move.reversal"].with_company(self.company_b).with_context(
            active_model="account.move", active_ids=doc.ids
        ).create({"journal_id": doc.journal_id.id})
        wizard.modify_moves()
        credit = doc.reversal_move_ids
        self.assertEqual((credit.company_id, credit.is_deductible), (self.company_b, True))
        self.company_b.use_deductible = False
        self.assertEqual(doc.amount_total, credit.amount_total)
