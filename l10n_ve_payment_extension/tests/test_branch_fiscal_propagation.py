import importlib.util
import os
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "branch_fiscal_propagation")
class TestBranchFiscalPropagation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.vef = env.ref("base.VEF")
        cls.usd = env.ref("base.USD")
        cls.company_vals = {
            "currency_id": cls.vef.id,
            "foreign_currency_id": cls.usd.id,
            "country_id": env.ref("base.ve").id,
        }
        cls.person_a, cls.person_b = env["type.person"].create(
            [{"name": "Persona A"}, {"name": "Persona B"}]
        )
        cls.wh_a, cls.wh_b = env["account.withholding.type"].create(
            [{"name": "Withholding A", "value": 71.31}, {"name": "Withholding B", "value": 72.42}]
        )
        cls.root = cls._create_company("Root Branch Test")
        cls.branch = cls._create_company("Branch 1", cls.root)
        cls.grandchild = cls._create_company("Branch 1.1", cls.branch)

    @classmethod
    def _create_company(cls, name, parent=None):
        vals = dict(cls.company_vals, name=name)
        if parent:
            vals["parent_id"] = parent.id
        return cls.env["res.company"].create(vals)

    def _set_root_values(self, person, wh, taxpayer):
        self.root.partner_id.write(
            {
                "type_person_id": person.id,
                "withholding_type_id": wh.id,
                "taxpayer_type": taxpayer,
            }
        )

    def _assert_values(self, partner, person, wh, taxpayer):
        self.assertEqual(partner.type_person_id, person)
        self.assertEqual(partner.withholding_type_id, wh)
        self.assertEqual(partner.taxpayer_type, taxpayer)

    def test_a_root_edit_propagates_to_descendants(self):
        self._set_root_values(self.person_a, self.wh_a, "special")
        for company in (self.branch, self.grandchild):
            self._assert_values(company.partner_id, self.person_a, self.wh_a, "special")

    def test_b_edit_on_branch_partner_is_blocked(self):
        self._set_root_values(self.person_a, self.wh_a, "special")
        with self.assertRaises(ValidationError):
            self.branch.partner_id.write({"type_person_id": self.person_b.id})
        with self.assertRaises(ValidationError):
            self.branch.partner_id.write({"taxpayer_type": "formal"})

    def test_c_new_branch_inherits_values(self):
        self._set_root_values(self.person_a, self.wh_a, "formal")
        new_branch = self._create_company("Branch New", self.root)
        self._assert_values(new_branch.partner_id, self.person_a, self.wh_a, "formal")

    def _load_migration(self):
        path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "migrations",
            "19.0.2.2.9",
            "post-propagate_fiscal_fields_to_branches.py",
        )
        spec = importlib.util.spec_from_file_location("migration_branch_fiscal", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _run_migration(self):
        self._load_migration().migrate(self.env.cr, "19.0.2.2.8")
        self.env.invalidate_all()

    def _write_on_root_without_propagation(self, vals):
        """Simulate legacy data: the root is configured but branches were never synced."""
        partner_model = type(self.env["res.partner"])
        with patch.object(
            partner_model, "_l10n_ve_propagate_fiscal_fields_to_branches", lambda *a, **k: None
        ):
            self.root.partner_id.write(vals)

    def test_d_migration_aligns_branches(self):
        self._write_on_root_without_propagation({"type_person_id": self.person_a.id})
        self.assertFalse(self.branch.partner_id.type_person_id)
        self._run_migration()
        for company in (self.branch, self.grandchild):
            self.assertEqual(company.partner_id.type_person_id, self.person_a)

    def _set_branch_person_without_constraint(self, person):
        """Simulate legacy data: a value configured by hand on the branches."""
        partners = (self.branch | self.grandchild).partner_id
        self.env.flush_all()  # pending ORM writes would overwrite the raw SQL below
        self.env.cr.execute(
            "UPDATE res_partner SET type_person_id = %s WHERE id IN %s",
            (person.id, tuple(partners.ids)),
        )
        self.env.invalidate_all()

    def test_e_migration_overwrites_branch_values_and_warns(self):
        self._set_root_values(self.person_a, self.wh_a, "special")
        self._set_branch_person_without_constraint(self.person_b)
        migration = self._load_migration()
        with self.assertLogs(migration._logger, level="WARNING") as logs:
            migration.migrate(self.env.cr, "19.0.2.2.8")
        self.env.invalidate_all()
        for company in (self.branch, self.grandchild):
            self.assertEqual(company.partner_id.type_person_id, self.person_a)
        self.assertTrue(any("type_person_id" in message for message in logs.output))
        self.assertTrue(any("overwritten" in message for message in logs.output))

    def test_g_migration_keeps_branch_value_when_root_is_empty(self):
        self._set_root_values(self.person_a, self.wh_a, "special")
        self.root.partner_id.write({"type_person_id": False})
        self._set_branch_person_without_constraint(self.person_b)
        self._write_on_root_without_propagation({"withholding_type_id": self.wh_b.id})
        migration = self._load_migration()
        with self.assertLogs(migration._logger, level="WARNING") as logs:
            migration.migrate(self.env.cr, "19.0.2.2.8")
        self.env.invalidate_all()
        for company in (self.branch, self.grandchild):
            self.assertEqual(
                company.partner_id.type_person_id,
                self.person_b,
                "A field empty on the root must not be touched on the branches.",
            )
            self.assertEqual(
                company.partner_id.withholding_type_id,
                self.wh_b,
                "The fields with a value on the root are still propagated.",
            )
        kept = [
            m for m in logs.output
            if "type_person_id" in m and "kept" in m and self.root.name in m
        ]
        self.assertEqual(len(kept), 2, logs.output)

    def _set_branches_keeping_own_person(self):
        """Root with a value in every field but the person type, which the branches keep."""
        self._set_root_values(self.person_a, self.wh_a, "special")
        self.root.partner_id.write({"type_person_id": False})
        self._set_branch_person_without_constraint(self.person_b)

    def test_h_root_edit_only_propagates_the_written_fields(self):
        self._set_branches_keeping_own_person()
        self.root.partner_id.write({"withholding_type_id": self.wh_b.id})
        for company in (self.branch, self.grandchild):
            self.assertEqual(company.partner_id.withholding_type_id, self.wh_b)
            self.assertEqual(
                company.partner_id.type_person_id,
                self.person_b,
                "A field that was not written on the root must not be touched on the branches.",
            )

    def test_i_new_branch_does_not_touch_existing_branches(self):
        self._set_branches_keeping_own_person()
        new_branch = self._create_company("Branch New", self.root)
        self._assert_values(new_branch.partner_id, self.env["type.person"], self.wh_a, "special")
        for company in (self.branch, self.grandchild):
            self.assertEqual(company.partner_id.type_person_id, self.person_b)

    def test_j_clearing_a_field_on_the_root_clears_it_on_the_branches(self):
        self._set_root_values(self.person_a, self.wh_a, "special")
        self.root.partner_id.write({"withholding_type_id": False})
        for company in (self.branch, self.grandchild):
            self.assertFalse(company.partner_id.withholding_type_id)
            self.assertEqual(company.partner_id.type_person_id, self.person_a)

    def test_k_propagation_only_writes_the_synced_fields(self):
        self._set_root_values(self.person_a, self.wh_a, "special")
        name = self.branch.partner_id.name
        root_partner = self.root.partner_id
        # The root changes without propagating, so the branches are behind it.
        self._write_on_root_without_propagation({"withholding_type_id": self.wh_b.id})
        root_partner._l10n_ve_propagate_fiscal_fields_to_branches(
            {"name": "Other name", "withholding_type_id": self.wh_b.id}
        )
        self.assertEqual(self.branch.partner_id.name, name)
        self.assertEqual(self.branch.partner_id.withholding_type_id, self.wh_b)
        # With nothing to write the branches are left as they are.
        self._write_on_root_without_propagation({"withholding_type_id": self.wh_a.id})
        root_partner._l10n_ve_propagate_fiscal_fields_to_branches({})
        self.assertEqual(self.branch.partner_id.withholding_type_id, self.wh_b)

    def test_l_constraint_ignores_the_fields_empty_on_the_root(self):
        self._set_branches_keeping_own_person()
        self.branch.partner_id.write({"taxpayer_type": "special"})
        with self.assertRaises(ValidationError):
            self.branch.partner_id.write({"withholding_type_id": self.wh_b.id})

    def test_m_archived_branches_also_receive_the_values(self):
        self.branch.active = False
        self._set_root_values(self.person_a, self.wh_a, "special")
        self._assert_values(self.branch.partner_id, self.person_a, self.wh_a, "special")
        self._assert_values(self.grandchild.partner_id, self.person_a, self.wh_a, "special")

    def test_n_several_branches_created_at_once_inherit_their_root_values(self):
        self._set_root_values(self.person_a, self.wh_a, "formal")
        new_branches = self.env["res.company"].create(
            [
                dict(self.company_vals, name="Branch New 1", parent_id=self.root.id),
                dict(self.company_vals, name="Branch New 2", parent_id=self.branch.id),
            ]
        )
        for company in new_branches:
            self._assert_values(company.partner_id, self.person_a, self.wh_a, "formal")

    def test_f_customer_islr_type_person_from_branch(self):
        self._set_root_values(self.person_a, self.wh_a, "special")
        retention = self.env["account.retention"].new(
            {"type_retention": "islr", "type": "out_invoice", "company_id": self.branch.id}
        )
        line = self.env["account.retention.line"].new(
            {"retention_id": retention, "company_id": self.branch.id}
        )
        self.assertEqual(line._get_islr_type_person_id(), self.person_a)
