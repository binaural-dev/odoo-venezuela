import json

from odoo.fields import Domain
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_ve_filter_partner import (
    new_module,
    old_module,
    reassign_filter_partner_data_ids,
)


@tagged("post_install", "-at_install")
class TestFilterPartnerMixin(TransactionCase):
    def _new_mixin_record(self, **values):
        return self.env["filter.partner.mixin"].new(values)

    def test_get_partner_domain_no_filter(self):
        record = self._new_mixin_record()
        self.assertEqual(record.get_partner_domain(), [])

    def test_get_partner_domain_customer(self):
        record = self._new_mixin_record(filter_partner="customer")
        self.assertEqual(record.get_partner_domain(), [("customer_rank", ">=", 1)])

    def test_get_partner_domain_supplier(self):
        record = self._new_mixin_record(filter_partner="supplier")
        self.assertEqual(record.get_partner_domain(), [("supplier_rank", ">=", 1)])

    def test_get_partner_domain_contact(self):
        record = self._new_mixin_record(filter_partner="contact")
        self.assertEqual(
            record.get_partner_domain(),
            [("customer_rank", "=", 0), ("supplier_rank", "=", 0)],
        )

    def test_get_partner_domain_extend_and(self):
        record = self._new_mixin_record(filter_partner="customer")
        extend = [("id", "=", 1)]
        expected = Domain.AND([[("customer_rank", ">=", 1)], extend])
        self.assertEqual(record.get_partner_domain(extend=extend), expected)

    def test_get_partner_domain_extend_or(self):
        record = self._new_mixin_record(filter_partner="customer")
        extend = [("id", "=", 1)]
        expected = Domain.OR([[("customer_rank", ">=", 1)], extend])
        self.assertEqual(record.get_partner_domain(extend=extend, conditional="|"), expected)

    def test_get_partner_domain_requires_single_record(self):
        records = self.env["filter.partner.mixin"]
        with self.assertRaises(ValueError):
            records.get_partner_domain()

    def test_compute_partner_id_domain_customer(self):
        record = self._new_mixin_record(filter_partner="customer")
        record._compute_partner_id_domain()
        self.assertEqual(json.loads(record.partner_id_domain), [["customer_rank", ">=", 1]])

    def test_compute_partner_id_domain_no_filter(self):
        record = self._new_mixin_record()
        record._compute_partner_id_domain()
        self.assertEqual(json.loads(record.partner_id_domain), [])


@tagged("post_install", "-at_install")
class TestReassignFilterPartnerDataIds(TransactionCase):
    """Covers the hook shared by pre_init_hook (install) and migrations/19.0.0.0.1/pre-migrate.py
    (upgrade), raised as a review point on PR #1293: the reassignment previously ran silently
    inside a broad try/except and had no test at all.
    """

    def _seed_legacy_row(self, name="test_legacy_xmlid"):
        cr = self.env.cr
        cr.execute(
            "INSERT INTO ir_model_data (name, module, model, res_id, noupdate) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (name, old_module, "res.partner", self.env.user.id, True),
        )
        return cr.fetchone()[0]

    def test_reassign_moves_rows_to_new_module(self):
        cr = self.env.cr
        data_id = self._seed_legacy_row()

        reassign_filter_partner_data_ids(cr)

        cr.execute("SELECT module FROM ir_model_data WHERE id = %s", (data_id,))
        self.assertEqual(cr.fetchone()[0], new_module)

    def test_reassign_is_a_noop_when_nothing_legacy_left(self):
        cr = self.env.cr
        cr.execute("SELECT count(*) FROM ir_model_data WHERE module = %s", (old_module,))
        (before,) = cr.fetchone()
        self.assertEqual(before, 0)

        # Must not raise even with nothing to reassign.
        reassign_filter_partner_data_ids(cr)
