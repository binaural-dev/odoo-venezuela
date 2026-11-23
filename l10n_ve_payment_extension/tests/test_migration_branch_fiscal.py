import importlib.util
import os
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

MIGRATION_VERSION = "19.0.2.2.10"
MIGRATION_FILE = "post-propagate_fiscal_fields_to_branches.py"
FNAMES = ("type_person_id", "withholding_type_id", "taxpayer_type")


@tagged("post_install", "-at_install", "branch_fiscal_migration")
class TestMigrationBranchFiscal(TransactionCase):
    """Cases of the 19.0.2.2.10 migration: every combination of the value of the root company
    contact and of its branches, for each synced field, and the guarantees around it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.company_vals = {
            "currency_id": env.ref("base.VEF").id,
            "foreign_currency_id": env.ref("base.USD").id,
            "country_id": env.ref("base.ve").id,
        }
        cls.person_a, cls.person_b = env["type.person"].create(
            [{"name": "Persona A"}, {"name": "Persona B"}]
        )
        cls.wh_a, cls.wh_b = env["account.withholding.type"].create(
            [{"name": "Withholding A", "value": 71.31}, {"name": "Withholding B", "value": 72.42}]
        )
        cls.values = {
            "type_person_id": (cls.person_a.id, cls.person_b.id),
            "withholding_type_id": (cls.wh_a.id, cls.wh_b.id),
            "taxpayer_type": ("special", "formal"),
        }
        cls.root = cls._create_company("Migration Root")
        cls.branch = cls._create_company("Migration Branch", cls.root)
        cls.grandchild = cls._create_company("Migration Grandchild", cls.branch)

    @classmethod
    def _create_company(cls, name, parent=None):
        vals = dict(cls.company_vals, name=name)
        if parent:
            vals["parent_id"] = parent.id
        return cls.env["res.company"].create(vals)

    def _load_migration(self):
        path = os.path.join(
            os.path.dirname(__file__), "..", "migrations", MIGRATION_VERSION, MIGRATION_FILE
        )
        spec = importlib.util.spec_from_file_location("migration_branch_fiscal_cases", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _migrate(self):
        """Run the migration and return the messages of the warnings it logged."""
        migration = self._load_migration()
        with patch.object(migration._logger, "warning") as warning:
            migration.migrate(self.env.cr, "19.0.2.2.9")
        self.env.invalidate_all()
        messages = [call.args[0] % call.args[1:] for call in warning.call_args_list]
        # Only the companies of these tests, whatever else the database has.
        return [message for message in messages if "Migration " in message]

    def _set_raw(self, partners, **vals):
        """Write the fiscal fields with SQL, as legacy data that never went through the
        propagation or the constraint. None leaves the field empty."""
        self.env.flush_all()  # pending ORM writes would overwrite the raw SQL below
        for fname, value in vals.items():
            self.env.cr.execute(
                f"UPDATE res_partner SET {fname} = %s WHERE id IN %s",  # noqa: S608
                (value, tuple(partners.ids)),
            )
        self.env.invalidate_all()

    def _clear_tree(self, *companies):
        self._set_raw(
            self.env["res.company"].union(*companies).partner_id, **dict.fromkeys(FNAMES)
        )

    def _notes(self, partner):
        return self.env["mail.message"].search_count(
            [
                ("model", "=", "res.partner"),
                ("res_id", "=", partner.id),
                ("body", "ilike", MIGRATION_VERSION),
            ]
        )

    def _value(self, partner, fname):
        return partner._fields[fname].convert_to_write(partner[fname], partner) or None

    def test_a_every_state_of_every_field(self):
        """root / branch -> final value, warning of the migration and note on the branch."""
        branches = self.branch | self.grandchild
        states = [
            # root, branch, final, warning, note
            ("empty", "empty", "empty", None, False),
            ("a", "empty", "a", None, False),
            ("a", "a", "a", None, False),
            ("a", "b", "a", "overwritten", True),
            ("empty", "b", "b", "kept", False),
        ]
        for fname in FNAMES:
            val = dict(zip(("a", "b"), self.values[fname]), empty=None)
            for root_state, branch_state, final, warning, note in states:
                with self.subTest(field=fname, root=root_state, branch=branch_state):
                    self._clear_tree(self.root, self.branch, self.grandchild)
                    self._set_raw(self.root.partner_id, **{fname: val[root_state]})
                    self._set_raw(branches.partner_id, **{fname: val[branch_state]})
                    notes_before = {c.id: self._notes(c.partner_id) for c in branches}
                    messages = self._migrate()
                    for company in branches:
                        self.assertEqual(self._value(company.partner_id, fname), val[final])
                        added = self._notes(company.partner_id) - notes_before[company.id]
                        self.assertEqual(added, 1 if note else 0)
                    matching = [m for m in messages if fname in m]
                    if warning:
                        self.assertEqual(len(matching), 2, messages)
                        self.assertTrue(all(warning in m for m in matching), messages)
                    else:
                        self.assertFalse(matching, messages)

    def test_b_every_loss_is_reported_in_the_log_and_in_a_note(self):
        self._clear_tree(self.root, self.branch, self.grandchild)
        self._set_raw(
            self.root.partner_id,
            type_person_id=self.person_a.id,
            withholding_type_id=self.wh_a.id,
            taxpayer_type="special",
        )
        self._set_raw(
            (self.branch | self.grandchild).partner_id,
            type_person_id=self.person_b.id,
            withholding_type_id=self.wh_b.id,
            taxpayer_type="ordinary",
        )
        messages = self._migrate()
        overwritten = [m for m in messages if "overwritten" in m]
        self.assertEqual(len(overwritten), 6, messages)
        for company in (self.branch, self.grandchild):
            self.assertTrue(any(company.name in m for m in overwritten))
            self.assertEqual(self._notes(company.partner_id), 1)
            note = self.env["mail.message"].search(
                [("model", "=", "res.partner"), ("res_id", "=", company.partner_id.id)],
                order="id desc",
                limit=1,
            )
            for text in ("Persona B", "Persona A", "Withholding B", "Withholding A", "ordinary", "special"):
                self.assertIn(text, note.body)

    def test_c_branches_already_aligned_are_left_alone(self):
        self._clear_tree(self.root, self.branch, self.grandchild)
        values = dict(
            type_person_id=self.person_a.id, withholding_type_id=self.wh_a.id, taxpayer_type="special"
        )
        self._set_raw((self.root | self.branch | self.grandchild).partner_id, **values)
        self.assertFalse(self._migrate())
        for company in (self.branch, self.grandchild):
            self.assertEqual(self._notes(company.partner_id), 0)

    def test_d_archived_and_nested_branches_are_reached(self):
        archived = self._create_company("Migration Archived", self.root)
        archived_child = self._create_company("Migration Archived Child", archived)
        archived_child.active = False
        archived.active = False
        branches = self.branch | self.grandchild | archived | archived_child
        self._clear_tree(self.root, *branches)
        self._set_raw(self.root.partner_id, type_person_id=self.person_a.id)
        self._migrate()
        for company in branches:
            self.assertEqual(company.partner_id.type_person_id, self.person_a, company.name)

    def test_e_roots_are_isolated_from_each_other(self):
        other_root = self._create_company("Migration Other Root")
        other_branch = self._create_company("Migration Other Branch", other_root)
        alone = self._create_company("Migration Alone")
        everything = self.root | self.branch | self.grandchild | other_root | other_branch | alone
        self._clear_tree(*everything)
        self._set_raw(self.root.partner_id, type_person_id=self.person_a.id)
        self._set_raw(other_root.partner_id, type_person_id=self.person_b.id)
        self._set_raw(alone.partner_id, type_person_id=self.person_b.id)
        self._migrate()
        for company in (self.branch, self.grandchild):
            self.assertEqual(company.partner_id.type_person_id, self.person_a)
        self.assertEqual(other_branch.partner_id.type_person_id, self.person_b)
        self.assertEqual(other_root.partner_id.type_person_id, self.person_b)
        self.assertEqual(self.root.partner_id.type_person_id, self.person_a)
        self.assertEqual(alone.partner_id.type_person_id, self.person_b)

    def test_f_running_it_twice_changes_nothing_more(self):
        self._clear_tree(self.root, self.branch, self.grandchild)
        self._set_raw(self.root.partner_id, type_person_id=self.person_a.id, taxpayer_type="special")
        self._set_raw((self.branch | self.grandchild).partner_id, type_person_id=self.person_b.id)
        self.assertTrue(self._migrate())
        state = {c.id: [self._value(c.partner_id, f) for f in FNAMES] for c in (self.branch, self.grandchild)}
        notes = {c.id: self._notes(c.partner_id) for c in (self.branch, self.grandchild)}
        self.assertFalse([m for m in self._migrate() if "overwritten" in m])
        for company in (self.branch, self.grandchild):
            self.assertEqual([self._value(company.partner_id, f) for f in FNAMES], state[company.id])
            self.assertEqual(self._notes(company.partner_id), notes[company.id])

    def test_g_the_other_data_of_the_contact_is_not_touched(self):
        self._clear_tree(self.root, self.branch, self.grandchild)
        self._set_raw(self.root.partner_id, type_person_id=self.person_a.id)
        partner = self.branch.partner_id
        partner.with_context(skip_sellers_validate=True).write(
            {"street": "Av. Principal", "email": "branch@example.com"}
        )
        fields = ["name", "vat", "street", "email", "phone", "active", "parent_id", "company_id", "country_id"]
        before = partner.read(fields)
        self._migrate()
        self.assertEqual(self.branch.partner_id.read(fields), before)

    def test_h_branch_partners_can_be_written_after_the_migration(self):
        self._clear_tree(self.root, self.branch, self.grandchild)
        self._set_raw(self.root.partner_id, type_person_id=self.person_a.id, taxpayer_type="special")
        self._set_raw((self.branch | self.grandchild).partner_id, type_person_id=self.person_b.id)
        self._migrate()
        for company in (self.branch, self.grandchild):
            partner = company.partner_id.with_context(skip_sellers_validate=True)
            partner.write({"name": "Renamed after migration"})
            partner.write({"type_person_id": self.person_a.id, "taxpayer_type": "special"})

    def test_i_the_migration_folder_is_not_ahead_of_the_manifest_version(self):
        """Odoo only runs migrations/<version> when the manifest version is at least that."""
        def as_tuple(version):
            return tuple(int(part) for part in version.split("."))

        module = self.env["ir.module.module"].search([("name", "=", "l10n_ve_payment_extension")])
        manifest_version = module.latest_version
        self.assertTrue(
            os.path.isfile(
                os.path.join(os.path.dirname(__file__), "..", "migrations", MIGRATION_VERSION, MIGRATION_FILE)
            )
        )
        self.assertLessEqual(as_tuple(MIGRATION_VERSION), as_tuple(manifest_version))
