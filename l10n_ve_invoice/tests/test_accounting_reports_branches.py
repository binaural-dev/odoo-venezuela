from datetime import date

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestAccountingReportsBranches(TransactionCase):
    """Alcance del libro de ventas/compras con sucursales nativas de Odoo."""

    def setUp(self):
        super().setUp()
        Company = self.env["res.company"]
        self.main = self.env.ref("base.main_company")
        self.main.vat = "J085025545"
        self.branch_a = Company.create(
            {"name": "Sucursal A", "parent_id": self.main.id, "vat": "J-085025545"}
        )
        self.branch_b = Company.create(
            {"name": "Sucursal B", "parent_id": self.main.id, "vat": "J085025545"}
        )
        self.other_vat = Company.create(
            {"name": "Otro RIF", "parent_id": self.main.id, "vat": "J999999999"}
        )
        self.user = self.env.user
        self.user.company_ids |= self.branch_a | self.branch_b | self.other_vat

    def _wizard(self, report="sale", company=None, **kwargs):
        company = company or self.main
        vals = {
            "report": report,
            "company_id": company.id,
            "date_from": date(2026, 10, 1),
            "date_to": date(2026, 10, 31),
        }
        vals.update(kwargs)
        return self.env["wizard.accounting.reports"].create(vals)

    def test_has_branches_only_same_vat(self):
        self.assertTrue(self._wizard().has_branches)
        self.assertFalse(self._wizard(company=self.branch_a).has_branches)

    def test_has_branches_false_without_same_vat_children(self):
        self.branch_a.vat = "J111111111"
        self.branch_b.vat = "J222222222"
        self.assertFalse(self._wizard().has_branches)

    def test_scope_all_includes_same_vat_branches_only(self):
        wizard = self._wizard(branch_scope="all")
        self.assertEqual(
            wizard.report_company_ids, self.main | self.branch_a | self.branch_b
        )
        self.assertNotIn(self.other_vat, wizard.report_company_ids)

    def test_scope_main_excludes_branches(self):
        wizard = self._wizard(branch_scope="main")
        self.assertEqual(wizard.report_company_ids, self.main)

    def test_scope_branch_only_selected_branch(self):
        wizard = self._wizard(branch_scope="branch", branch_company_id=self.branch_a.id)
        self.assertEqual(wizard.report_company_ids, self.branch_a)
        self.assertEqual(wizard._get_header_company(), self.branch_a)

    def test_scope_branch_requires_branch(self):
        with self.assertRaises(UserError):
            self._wizard(branch_scope="branch")

    def test_scope_branch_rejects_other_vat(self):
        with self.assertRaises(UserError):
            self._wizard(branch_scope="branch", branch_company_id=self.other_vat.id)

    def test_active_branch_without_children_is_main(self):
        wizard = self._wizard(company=self.branch_a, branch_scope="all")
        self.assertEqual(wizard.report_company_ids, self.branch_a)

    def test_header_is_main_company_when_consolidated(self):
        self.assertEqual(self._wizard(branch_scope="all")._get_header_company(), self.main)

    def test_default_scope_is_all_with_branches(self):
        wizard = self.env["wizard.accounting.reports"].with_company(self.main).create(
            {"report": "sale", "date_from": date(2026, 10, 1), "date_to": date(2026, 10, 31)}
        )
        self.assertEqual(wizard.branch_scope, "all")

    def test_domain_uses_report_companies(self):
        wizard = self._wizard(branch_scope="all")
        self.assertIn(
            ("company_id", "in", wizard.report_company_ids.ids), wizard._get_domain()
        )

    def test_report_companies_limited_to_user_access(self):
        self.user.company_ids -= self.branch_b
        wizard = self._wizard(branch_scope="all")
        self.assertNotIn(self.branch_b, wizard.report_company_ids)
