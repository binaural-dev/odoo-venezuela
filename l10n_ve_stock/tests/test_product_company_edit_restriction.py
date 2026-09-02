from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestProductCompanyEditRestriction(TransactionCase):
    def setUp(self):
        super().setUp()
        self.group = self.env.ref("l10n_ve_stock.group_edit_product_company")
        self.user = self.env["res.users"].create({
            "name": "Test User Company Edit",
            "login": "test_user_company_edit",
            "email": "test_user_company_edit@example.com",
            # Passing group_ids explicitly skips res.users' own default
            # (base.group_user + implied groups), so it has to be listed here
            # too - otherwise the user lacks even base internal-user access
            # (e.g. to res.company) and every write() fails before it ever
            # reaches the company_id guard being tested.
            "group_ids": [(6, 0, [
                self.env.ref("base.group_user").id,
                # Base write access to product.template (Products/Create), so
                # the write()-level tests below exercise the company_id guard
                # itself instead of failing earlier on the base ACL.
                self.env.ref("product.group_product_manager").id,
            ])],
        })
        self.template = self.env["product.template"].create({
            "name": "Product Company Edit Restriction",
            "type": "consu",
        })
        # Odoo's mail.thread.create() discards pending write-tracking for the
        # new record right after logging its creation message, but only
        # finalizes that discard on a real DB flush/commit. Flush here so
        # creation-time bookkeeping doesn't leak into a later write() within
        # this same test transaction (this has no effect outside tests,
        # where each request is its own transaction).
        self.env.flush_all()
        self.cr.flush()

    def test_can_edit_company_id_false_without_group(self):
        template = self.template.with_user(self.user)
        self.assertFalse(template.can_edit_company_id)

    def test_can_edit_company_id_true_with_group(self):
        self.user.group_ids = [(4, self.group.id)]
        template = self.template.with_user(self.user)
        self.assertTrue(template.can_edit_company_id)

    def test_company_id_change_is_tracked_in_chatter(self):
        other_company = self.env["res.company"].create({"name": "Other Company"})
        message_count_before = len(self.template.message_ids)
        self.template.write({"company_id": other_company.id})
        # Odoo defers tracking-message creation to a cr.precommit hook, which
        # only runs on a real DB commit. Force it here so the assertions
        # below see the tracking message within this test's transaction.
        self.env.flush_all()
        self.cr.flush()
        tracking_values = self.template.message_ids[0].tracking_value_ids
        self.assertGreater(
            len(self.template.message_ids), message_count_before,
            "Changing company_id should post a tracking message to the chatter.",
        )
        self.assertTrue(
            any(tv.field_id.name == "company_id" for tv in tracking_values),
            "The tracking message should include a tracking value for company_id.",
        )

    def test_write_company_id_without_group_raises_access_error(self):
        other_company = self.env["res.company"].create({"name": "Other Company"})
        template = self.template.with_user(self.user)
        with self.assertRaises(AccessError):
            template.write({"company_id": other_company.id})

    def test_write_company_id_with_group_is_allowed(self):
        other_company = self.env["res.company"].create({"name": "Other Company"})
        self.user.group_ids = [(4, self.group.id)]
        template = self.template.with_user(self.user)
        template.write({"company_id": other_company.id})
        self.assertEqual(self.template.company_id, other_company)

    def test_write_without_company_id_is_allowed_without_group(self):
        template = self.template.with_user(self.user)
        template.write({"name": "Renamed by unprivileged user"})
        self.assertEqual(self.template.name, "Renamed by unprivileged user")
