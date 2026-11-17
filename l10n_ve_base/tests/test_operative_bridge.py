from odoo.tests import TransactionCase, tagged

from ..migrations import _common


@tagged("post_install", "-at_install", "l10n_ve_base")
class TestOperativeBridge(TransactionCase):
    """Conversion of a database of the v17 operativa line, on made-up module names."""

    def _create_module(self, name, state="installed", version="17.0.1.0.5"):
        self.env.cr.execute(
            """
            INSERT INTO ir_module_module (name, state, latest_version, auto_install, demo)
                 VALUES (%s, %s, %s, false, false)
              RETURNING id
            """,
            [name, state, version],
        )
        (module_id,) = self.env.cr.fetchone()
        self.env.cr.execute(
            """
            INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
                 VALUES ('base', %s, 'ir.module.module', %s, true)
            """,
            ["module_" + name, module_id],
        )
        return module_id

    def _module(self, name):
        self.env.cr.execute(
            "SELECT state, latest_version FROM ir_module_module WHERE name = %s", [name]
        )
        return self.env.cr.fetchone()

    def _create_xmlid(self, module, name, record):
        self.env["ir.model.data"].create(
            {"module": module, "name": name, "model": record._name, "res_id": record.id}
        )

    def _xmlid_record(self, module, name):
        self.env.cr.execute(
            "SELECT model, res_id FROM ir_model_data WHERE module = %s AND name = %s",
            [module, name],
        )
        row = self.env.cr.fetchone()
        return row and self.env[row[0]].browse(row[1])

    def _convert(self, pairs, xmlid_renames=None):
        self.env.flush_all()
        lines = _common.convert(self.env.cr, renamed_modules=pairs, xmlid_renames=xmlid_renames or {})
        self.env.invalidate_all()
        return lines

    def test_legacy_module_becomes_its_successor(self):
        self._create_module("x_legacy_rate")
        partner = self.env["res.partner"].create({"name": "Legacy Record"})
        self._create_xmlid("x_legacy_rate", "partner_binaural", partner)
        view = self.env["ir.ui.view"].create(
            {
                "name": "x.legacy.rate.view",
                "model": "res.partner",
                "arch": "<form><field name='name'/></form>",
            }
        )
        self._create_xmlid("x_legacy_rate", "view_legacy", view)

        lines = self._convert(
            (("x_legacy_rate", "x_new_rate"),),
            {"x_legacy_rate": {"partner_binaural": "partner_l10n_ve"}},
        )

        self.assertFalse(self._module("x_legacy_rate"))
        self.assertEqual(self._module("x_new_rate"), ("to upgrade", "17.0.1.0.5"))
        self.assertEqual(self._xmlid_record("x_new_rate", "partner_l10n_ve"), partner)
        self.assertFalse(self._xmlid_record("x_new_rate", "partner_binaural"))
        self.assertFalse(view.exists())
        self.assertFalse(self._xmlid_record("base", "module_x_legacy_rate"))
        self.assertTrue(self._xmlid_record("base", "module_x_new_rate"))
        self.assertTrue(any("x_legacy_rate -> x_new_rate (renamed)" in line for line in lines))

    def test_placeholder_of_the_successor_is_replaced(self):
        self._create_module("x_legacy_rate")
        self._create_module("x_new_rate", state="uninstalled", version=None)

        self._convert((("x_legacy_rate", "x_new_rate"),))

        self.env.cr.execute("SELECT count(*) FROM ir_module_module WHERE name = 'x_new_rate'")
        self.assertEqual(self.env.cr.fetchone()[0], 1)
        self.assertEqual(self._module("x_new_rate"), ("to upgrade", "17.0.1.0.5"))

    def test_legacy_module_is_merged_into_an_installed_successor(self):
        self._create_module("x_legacy_igtf")
        self._create_module("x_new_igtf", version="19.0.1.0.0")
        kept, dropped, moved = self.env["res.partner"].create(
            [{"name": "Kept"}, {"name": "Dropped"}, {"name": "Moved"}]
        )
        self._create_xmlid("x_new_igtf", "shared", kept)
        self._create_xmlid("x_legacy_igtf", "shared", dropped)
        self._create_xmlid("x_legacy_igtf", "own", moved)

        lines = self._convert((("x_legacy_igtf", "x_new_igtf"),))

        self.assertFalse(self._module("x_legacy_igtf"))
        self.assertEqual(self._module("x_new_igtf"), ("to upgrade", "19.0.1.0.0"))
        self.assertEqual(self._xmlid_record("x_new_igtf", "shared"), kept)
        self.assertEqual(self._xmlid_record("x_new_igtf", "own"), moved)
        self.assertTrue(dropped.exists())
        self.assertTrue(any("x_legacy_igtf -> x_new_igtf (merged)" in line for line in lines))

    def test_dependents_follow_the_successor(self):
        self._create_module("x_legacy_rate")
        dependent_id = self._create_module("x_dependent")
        self.env.cr.execute(
            "INSERT INTO ir_module_module_dependency (module_id, name) VALUES (%s, 'x_legacy_rate')",
            [dependent_id],
        )

        self._convert((("x_legacy_rate", "x_new_rate"),))

        self.env.cr.execute(
            "SELECT name FROM ir_module_module_dependency WHERE module_id = %s", [dependent_id]
        )
        self.assertEqual([row[0] for row in self.env.cr.fetchall()], ["x_new_rate"])

    def test_database_without_legacy_modules_is_left_alone(self):
        self._create_module("x_legacy_rate", state="uninstalled")

        lines = self._convert((("x_legacy_rate", "x_new_rate"),))

        self.assertEqual(lines, [])
        self.assertFalse(self._module("x_new_rate"))
        self.assertEqual(self._module("x_legacy_rate"), ("uninstalled", "17.0.1.0.5"))

    def test_v17_flags_are_snapshotted_once(self):
        self._create_module("x_legacy_fiscal")
        partner = self.env["res.partner"].create({"name": "Flagged"})
        self._create_xmlid("x_legacy_fiscal", "field_res_partner__x_flag", partner)
        self.env.flush_all()
        self.env.cr.execute("ALTER TABLE res_partner ADD COLUMN x_flag boolean")
        self.env.cr.execute("UPDATE res_partner SET x_flag = true WHERE id = %s", [partner.id])
        snapshots = (
            ("x_v17_partner_flag", "res_partner", "id, x_flag", "x_flag",
             ("x_legacy_fiscal", "field_res_partner__x_flag")),
        )
        self.assertEqual(_common.missing_snapshots(self.env.cr, snapshots), ["x_v17_partner_flag"])

        created = _common.take_snapshots(self.env.cr, snapshots)

        self.assertEqual(created, ["x_v17_partner_flag"])
        self.env.cr.execute("SELECT id FROM x_v17_partner_flag WHERE x_flag")
        self.assertEqual(self.env.cr.fetchall(), [(partner.id,)])
        self.assertEqual(_common.take_snapshots(self.env.cr, snapshots), [])
        self.assertEqual(_common.missing_snapshots(self.env.cr, snapshots), [])

    def test_same_named_19_column_is_not_snapshotted(self):
        self.env.cr.execute("ALTER TABLE res_partner ADD COLUMN x_flag boolean")
        snapshots = (
            ("x_v17_partner_flag", "res_partner", "id, x_flag", "x_flag",
             ("x_legacy_fiscal", "field_res_partner__x_flag")),
        )

        self.assertEqual(_common.take_snapshots(self.env.cr, snapshots), [])

    def test_operativa_only_fields_are_backed_up(self):
        partner = self.env["res.partner"].create({"name": "Backed Up"})
        self.env.flush_all()
        self.env.cr.execute("ALTER TABLE res_partner ADD COLUMN x_legacy_flag boolean")
        self.env.cr.execute(
            "UPDATE res_partner SET x_legacy_flag = true WHERE id = %s", [partner.id]
        )
        fields = (
            ("x_legacy_rate", "res.partner", "res_partner", "x_legacy_flag", "x_legacy_flag IS TRUE"),
            ("x_other", "res.partner", "res_partner", "x_legacy_flag", "x_legacy_flag IS TRUE"),
            ("x_legacy_rate", "res.partner", "res_partner", "x_gone", "x_gone IS TRUE"),
        )

        counts = _common.backup_fields(self.env.cr, {"x_legacy_rate"}, "17.0.1.0.5", fields)

        self.assertEqual(counts, {"res_partner.x_legacy_flag": 1})
        self.env.cr.execute(
            f"SELECT model, res_id, field, value, source_version FROM {_common.BACKUP_TABLE} "
            "WHERE field = 'x_legacy_flag'"
        )
        self.assertEqual(
            self.env.cr.fetchall(),
            [("res.partner", partner.id, "x_legacy_flag", "true", "17.0.1.0.5")],
        )

    def test_installed_base_module_is_not_registered_again(self):
        before = self._module(_common.BASE_MODULE)

        self.assertFalse(_common.register_base_module(self.env.cr))

        self.assertEqual(self._module(_common.BASE_MODULE), before)

    def _create_journal_snapshot(self):
        self.env.cr.execute(
            "CREATE TABLE %s (journal_id integer, fiscal boolean)"
            % _common.JOURNAL_FISCAL_SNAPSHOT
        )

    def _install_operative(self, module):
        self.env.flush_all()
        lines = _common.install_operative_module(self.env, module=module)
        self.env.invalidate_all()
        return lines

    def test_operative_module_is_marked_to_install(self):
        self._create_journal_snapshot()
        self._create_module("x_operative", state="uninstalled", version=None)

        lines = self._install_operative("x_operative")

        self.assertEqual(self._module("x_operative")[0], "to install")
        self.assertTrue(lines)

    def test_operative_module_is_left_alone_without_snapshot(self):
        self.env.cr.execute("SELECT to_regclass(%s)", [_common.JOURNAL_FISCAL_SNAPSHOT])
        if self.env.cr.fetchone()[0]:
            self.skipTest("this database already has the journal fiscal snapshot")
        self._create_module("x_operative", state="uninstalled", version=None)

        self.assertEqual(self._install_operative("x_operative"), [])

        self.assertEqual(self._module("x_operative")[0], "uninstalled")

    def test_missing_operative_module_is_reported(self):
        self._create_journal_snapshot()

        lines = self._install_operative("x_operative_not_in_addons_path")

        self.assertEqual(len(lines), 1)
        self.assertIn("not in the addons path", lines[0])
