import inspect
import unittest

from odoo.addons.account.models.chart_template import AccountChartTemplate as CoreChart
from odoo.tests import TransactionCase, tagged

LOGGER = "odoo.addons.l10n_ve_accountant.models.account_chart_template"


@tagged("post_install", "-at_install", "l10n_ve_accountant")
class TestChartTemplateRelink(TransactionCase):
    """ti-15416: una sucursal debe cargar aunque la raíz haya perdido xmlids de cuentas."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.template = "ve"
        cls.ChartTemplate = cls.env["account.chart.template"]
        if cls.env["ir.module.module"]._get("l10n_ve").state != "installed":
            raise unittest.SkipTest("l10n_ve no instalado")
        cls.root = cls.env["res.company"].create({
            "name": "Relink Root",
            "country_id": cls.env.ref("base.ve").id,
        })
        cls.ChartTemplate.try_loading(cls.template, cls.root)
        template_data = cls.ChartTemplate._get_chart_template_data(cls.template)["template_data"]
        cls.recv_xmlid = template_data["property_account_receivable_id"]
        cls.recv = cls.ChartTemplate.with_company(cls.root).ref(cls.recv_xmlid)

    # -- helpers
    def _imd(self, root=None):
        root = root or self.root
        return self.env["ir.model.data"].search([
            ("module", "=", "account"),
            ("name", "=", f"{root.id}_{self.recv_xmlid}"),
        ])

    def _account_xmlid_count(self):
        return self.env["ir.model.data"].search_count([("model", "=", "account.account")])

    def _account_count(self):
        return self.env["account.account"].with_context(active_test=False).sudo().search_count([])

    def _create_branch(self, parent=None, name="Relink Branch"):
        branch = self.env["res.company"].create({"name": name, "parent_id": (parent or self.root).id})
        self.env.cr.precommit.run()
        return branch

    def _assert_relinked(self):
        imd = self._imd()
        self.assertEqual(len(imd), 1)
        self.assertEqual(imd.res_id, self.recv.id)
        self.assertTrue(imd.noupdate)

    # -- tests
    def test_01_healthy_noop(self):
        xmlids, accounts = self._account_xmlid_count(), self._account_count()
        self._create_branch()
        self.assertEqual(self._account_xmlid_count(), xmlids)
        self.assertEqual(self._account_count(), accounts)

    def test_02_missing_xmlid_branch_creation(self):
        self._imd().unlink()
        accounts = self._account_count()
        self._create_branch()
        self.assertEqual(self._account_count(), accounts)
        self._assert_relinked()

    def test_03_reload_loaded_branch(self):
        """Límite conocido: recargar una sucursal que ya tiene el plan.

        El core toma el camino de recarga (`_pre_reload_data`), que descarta
        los `property_*` antes de `_pre_load_data`, así que no se hace `ref()`
        sobre los xmlids de la raíz y el error del ticket no puede ocurrir. El
        helper no tiene nada que re-vincular ahí: no debe fallar ni crear cuentas.
        """
        branch = self._create_branch()
        self._imd().unlink()
        accounts = self._account_count()
        self.ChartTemplate.try_loading(self.template, branch)
        self.assertEqual(self._account_count(), accounts)

    def test_04_orphan_xmlid(self):
        imd = self._imd()
        self.env.cr.execute("UPDATE ir_model_data SET res_id = 999999999 WHERE id = %s", [imd.id])
        imd.invalidate_recordset()
        self.env["ir.model.data"].invalidate_model()
        self.env.registry.clear_cache()  # el ormcache de _xmlid_lookup ocultaría el huérfano
        accounts = self._account_count()
        self._create_branch()
        self.assertEqual(self._account_count(), accounts)
        self._assert_relinked()

    def test_05_archived_account(self):
        self.recv.sudo().active = False
        self._imd().unlink()
        accounts = self._account_count()
        self._create_branch()
        self.assertEqual(self._account_count(), accounts)
        self._assert_relinked()

    def test_06_different_code_not_relinked(self):
        self.recv.sudo().with_company(self.root).code = "9999999"
        self._imd().unlink()
        with self.assertLogs(LOGGER, level="WARNING") as logs, self.assertRaises(ValueError):
            self._create_branch()
        self.assertTrue(any(self.recv_xmlid in line for line in logs.output))
        self.assertFalse(self._imd())

    def test_07_idempotent(self):
        self._imd().unlink()
        self._create_branch(name="Relink Branch 1")
        accounts = self._account_count()
        self._create_branch(name="Relink Branch 2")
        self.assertEqual(self._account_count(), accounts)
        self._assert_relinked()

    def test_08_multilevel(self):
        child = self._create_branch(name="Relink Child")
        self._imd().unlink()
        accounts = self._account_count()
        grandchild = self._create_branch(parent=child, name="Relink Grandchild")
        self.assertEqual(grandchild.parent_ids[0], self.root)
        self.assertEqual(self._account_count(), accounts)
        self._assert_relinked()

    def test_09_core_contract(self):
        """Fija el contrato del core del que depende el override.

        El orden `_pre_load_data` -> `_load_data` -> `_post_load_data` de
        `_load` lo cubren de punta a punta test_02 y test_08.
        """
        self.assertEqual(self.ChartTemplate.company_xmlid("x", self.root), f"account.{self.root.id}_x")
        self.assertIn("property_account_receivable_id", self.ChartTemplate._get_property_accounts({}))
        branch = self._create_branch()
        self.assertEqual(self.ChartTemplate.with_company(branch).ref(self.recv_xmlid), self.recv)
        # Firma del método ORIGINAL del core (no la de nuestro override)
        params = list(inspect.signature(CoreChart._pre_load_data).parameters)
        self.assertEqual(params, ["self", "template_code", "company", "template_data", "data"])

    def test_10_orphan_without_account_with_code(self):
        """xmlid huérfano y ninguna cuenta con ese código: warning y falla normal del core."""
        self.recv.sudo().with_company(self.root).code = "9999999"
        imd = self._imd()
        self.env.cr.execute("UPDATE ir_model_data SET res_id = 999999999 WHERE id = %s", [imd.id])
        imd.invalidate_recordset()
        self.env["ir.model.data"].invalidate_model()
        self.env.registry.clear_cache()
        with self.assertLogs(LOGGER, level="WARNING") as logs, self.assertRaises(ValueError):
            self._create_branch()
        self.assertTrue(any(self.recv_xmlid in line for line in logs.output))

    def test_11_several_non_exact_matches_not_guessed(self):
        """Varias coincidencias `{code}0*` sin la exacta: se avisa y no se adivina."""
        Account = self.env["account.account"].sudo().with_company(self.root)
        self.recv.sudo().with_company(self.root).code = "11220010"
        Account.create({"name": "Relink extra", "code": "112200100", "account_type": "asset_receivable"})
        self._imd().unlink()
        with self.assertLogs(LOGGER, level="WARNING") as logs, self.assertRaises(ValueError):
            self._create_branch()
        self.assertTrue(any(self.recv_xmlid in line for line in logs.output))
        self.assertFalse(self._imd())

    def test_12_res_company_account_xmlid(self):
        """Rama res.company: `account_default_pos_receivable_account_id` también se re-vincula.

        El core carga `data['res.company']` en sucursales y resuelve el xmlid
        con `ref()` (cae a la raíz), así que sin el re-vínculo la creación falla.
        Se verifica que se re-vincula a la misma cuenta sin crear cuentas.
        """
        xmlid = "account_activa_account_1122003"
        account = self.ChartTemplate.with_company(self.root).ref(xmlid)
        imd = self.env["ir.model.data"].search([("module", "=", "account"), ("name", "=", f"{self.root.id}_{xmlid}")])
        self.assertEqual(len(imd), 1)
        imd.unlink()
        accounts = self._account_count()
        self._create_branch()
        self.assertEqual(self._account_count(), accounts)
        imd = self.env["ir.model.data"].search([("module", "=", "account"), ("name", "=", f"{self.root.id}_{xmlid}")])
        self.assertEqual(imd.res_id, account.id)
