from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

CORE_POST_LOAD = "odoo.addons.account.models.chart_template.AccountChartTemplate._post_load_data"
LOGGER = "odoo.addons.l10n_ve_accountant.models.account_chart_template"
RECEIVABLE = "property_account_receivable_id"
PAYABLE = "property_account_payable_id"
RECEIVABLE_XMLID = "account_activa_account_1122001"
PAYABLE_XMLID = "account_activa_account_2122001"


@tagged("post_install", "-at_install")
class TestBranchChartTemplateDefaults(TransactionCase):
    """A branch takes the account defaults of its root when the template xmlid does not exist.

    A root whose chart did not come from the template (custom or migrated chart) has no
    ``account.<root_id>_<xmlid>``: the branch creation used to fail on it.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root = cls.env["res.company"].create({"name": "Chart root"})
        cls.branch = cls.env["res.company"].create({"name": "Chart branch", "parent_id": cls.root.id})
        cls.receivable = cls._create_account("1.1.3.2.001", "asset_receivable")
        cls.payable = cls._create_account("2.1.3.1.001", "liability_payable")
        cls.template_data = {RECEIVABLE: RECEIVABLE_XMLID, PAYABLE: PAYABLE_XMLID}

    @classmethod
    def _create_account(cls, code, account_type):
        return cls.env["account.account"].with_company(cls.root).create({
            "name": code,
            "code": code,
            "account_type": account_type,
            "company_ids": [(6, 0, cls.root.ids)],
        })

    def _set_root_defaults(self):
        self.env["ir.default"].set("res.partner", RECEIVABLE, self.receivable.id, company_id=self.root.id)
        self.env["ir.default"].set("res.partner", PAYABLE, self.payable.id, company_id=self.root.id)

    def _branch_default(self, field):
        return self.env["ir.default"]._get("res.partner", field, company_id=self.branch.id)

    def _post_load(self, company, template_data=None):
        """Run the override with the core step mocked: returns the data the core received."""
        template = self.env["account.chart.template"].with_company(company)
        with patch(CORE_POST_LOAD, autospec=True) as core:
            template._post_load_data("ve", company, dict(template_data or self.template_data))
        return core.call_args.args[3]

    def test_branch_takes_root_defaults_when_xmlid_is_missing(self):
        self._set_root_defaults()
        with self.assertLogs(LOGGER, "WARNING") as logs:
            received = self._post_load(self.branch)
        self.assertNotIn(RECEIVABLE, received, "The core must not resolve the missing xmlid")
        self.assertNotIn(PAYABLE, received)
        self.assertEqual(self._branch_default(RECEIVABLE), self.receivable.id)
        self.assertEqual(self._branch_default(PAYABLE), self.payable.id)
        self.assertEqual(len(logs.records), 2, "One warning for each default taken from the root")
        self.assertIn(RECEIVABLE_XMLID, logs.output[0])

    def test_branch_without_root_default_raises(self):
        with self.assertRaises(UserError) as error:
            self._post_load(self.branch)
        message = str(error.exception)
        self.assertIn(RECEIVABLE_XMLID, message)
        self.assertIn(self.root.display_name, message)
        self.assertIn(f"res.partner.{RECEIVABLE}", message)

    def test_global_default_is_not_copied_nor_raises(self):
        """A default for all the companies is already inherited by the branch."""
        self.env["ir.default"].set("res.partner", RECEIVABLE, self.receivable.id)
        self.env["ir.default"].set("res.partner", PAYABLE, self.payable.id, company_id=self.root.id)
        with self.assertLogs(LOGGER, "INFO"):
            self._post_load(self.branch)
        self.assertFalse(self._branch_default(RECEIVABLE), "Nothing is copied: the global default applies")
        self.assertEqual(self._branch_default(PAYABLE), self.payable.id)

    def test_existing_xmlid_is_left_to_the_core(self):
        self._set_root_defaults()
        self.env["ir.model.data"].create({
            "module": "account",
            "name": f"{self.root.id}_{RECEIVABLE_XMLID}",
            "model": "account.account",
            "res_id": self.receivable.id,
            "noupdate": True,
        })
        received = self._post_load(self.branch)
        self.assertEqual(received.get(RECEIVABLE), RECEIVABLE_XMLID)
        self.assertNotIn(PAYABLE, received)
        self.assertFalse(self._branch_default(RECEIVABLE), "The core sets it, not the fallback")
        self.assertEqual(self._branch_default(PAYABLE), self.payable.id)

    def test_company_properties_are_left_to_the_core(self):
        """Fields of res.company (e.g. the down payment account) are not defaults to copy."""
        self._set_root_defaults()
        data = {**self.template_data, "downpayment_account_id": "account_not_in_the_database"}
        with patch.object(
            type(self.env["account.chart.template"]),
            "_get_property_accounts",
            lambda self, additional: {RECEIVABLE: "res.partner", PAYABLE: "res.partner",
                                      "downpayment_account_id": "res.company"},
        ):
            received = self._post_load(self.branch, data)
        self.assertEqual(received.get("downpayment_account_id"), "account_not_in_the_database")
        self.assertNotIn(RECEIVABLE, received)

    def test_root_company_is_not_affected(self):
        received = self._post_load(self.root)
        self.assertEqual(received, self.template_data)
        self.assertFalse(self.env["ir.default"]._get("res.partner", RECEIVABLE, company_id=self.root.id))

    def test_branch_creation_with_a_chart_not_loaded_from_the_template(self):
        """End to end: root with the template, its xmlids gone (migrated chart), then a branch.

        Uses `generic_coa` (always available with `account`): loading a localization chart would
        install its module, which Odoo forbids inside a test.
        """
        root = self.env["res.company"].create({"name": "Migrated root"})
        self.env["account.chart.template"].try_loading("generic_coa", root, install_demo=False)
        defaults = {
            field: self.env["ir.default"]._get("res.partner", field, company_id=root.id)
            for field in (RECEIVABLE, PAYABLE)
        }
        self.assertTrue(all(defaults.values()), "The template sets the receivable and payable defaults of the root")
        self.env["ir.model.data"].search([
            ("module", "=", "account"),
            ("model", "=", "account.account"),
            ("name", "=like", f"{root.id}\\_%"),
        ]).unlink()
        branch = self.env["res.company"].create({"name": "Migrated branch", "parent_id": root.id})
        with self.assertLogs(LOGGER, "WARNING"):
            self.env.cr.precommit.run()
        self.assertEqual(branch.chart_template, "generic_coa")
        for field, account_id in defaults.items():
            self.assertEqual(self.env["ir.default"]._get("res.partner", field, company_id=branch.id), account_id)
