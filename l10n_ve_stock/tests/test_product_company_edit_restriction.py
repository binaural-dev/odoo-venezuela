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
