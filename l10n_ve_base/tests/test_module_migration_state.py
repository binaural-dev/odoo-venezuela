from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestModuleMigrationState(TransactionCase):
    """The tag «Migrated» / «Pending migration» of Apps comes from the manifest of each module."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Module = cls.env["ir.module.module"]
        cls.pending = Module.create({"name": "l10n_ve_test_pending", "state": "uninstallable", "author": "binaural-dev"})
        cls.migrated = Module.create({"name": "l10n_ve_test_migrated", "state": "uninstalled", "author": "binaural-dev"})
        cls.odoo_uninstallable = Module.create(
            {"name": "l10n_ve_test_odoo", "state": "uninstallable", "author": "Odoo S.A."}
        )
        cls.manifests = {"l10n_ve_test_migrated": {"binaural_migrated": True}}

    def _with_manifests(self):
        Module = type(self.env["ir.module.module"])
        original = Module.get_module_info.__func__

        def get_module_info(cls, name):
            return self.manifests.get(name) or original(cls, name)

        return patch.object(Module, "get_module_info", classmethod(get_module_info))

    def test_the_manifest_key_marks_the_module_as_migrated(self):
        with self._with_manifests():
            self.assertEqual(self.migrated.migration_state, "migrated")

    def test_this_module_is_migrated(self):
        module = self.env["ir.module.module"].search([("name", "=", "l10n_ve_base")])
        self.assertEqual(module.migration_state, "migrated")

    def test_a_module_that_cannot_be_installed_is_pending(self):
        self.assertEqual(self.pending.migration_state, "pending")

    def test_odoo_modules_have_no_tag(self):
        base = self.env["ir.module.module"].search([("name", "=", "base")])
        self.assertFalse(base.migration_state)
        self.assertFalse(self.odoo_uninstallable.migration_state)

    def test_the_filters_find_each_state(self):
        Module = self.env["ir.module.module"]
        with self._with_manifests():
            migrated = Module.search([("migration_state", "=", "migrated")])
            pending = Module.search([("migration_state", "=", "pending")])
            untagged = Module.search([("migration_state", "not in", ["migrated", "pending"])])
        self.assertIn(self.migrated, migrated)
        self.assertNotIn(self.pending, migrated)
        self.assertIn(self.pending, pending)
        self.assertNotIn(self.odoo_uninstallable, pending | migrated)
        self.assertIn(self.odoo_uninstallable, untagged)
