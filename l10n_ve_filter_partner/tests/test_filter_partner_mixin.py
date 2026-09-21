import json

from odoo.fields import Domain
from odoo.tests.common import TransactionCase, tagged


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
