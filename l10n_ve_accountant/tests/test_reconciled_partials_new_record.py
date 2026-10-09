from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_reconciled_partials_new_record")
class TestReconciledPartialsNewRecord(TransactionCase):
    """`_get_all_reconciled_invoice_partials` must not feed a `NewId` into a
    search domain (onchange/form preview of an unsaved invoice) and must keep
    behaving the same for saved invoices."""

    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")

    def test_new_invoice_does_not_search_with_newid(self):
        move = self.env["account.move"].new({
            "move_type": "out_invoice",
            "company_id": self.company.id,
        })
        self.assertFalse(move.id)
        with self.assertNoLogs("odoo.domains", level="WARNING"):
            partials = move._get_all_reconciled_invoice_partials()
        self.assertFalse(partials)

    def test_saved_invoice_without_entries_returns_no_extra_partials(self):
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "company_id": self.company.id,
        })
        with self.assertNoLogs("odoo.domains", level="WARNING"):
            partials = move._get_all_reconciled_invoice_partials()
        self.assertFalse([p for p in partials if p.get("is_exchange")])

    def test_origin_of_new_record_is_searched_by_real_id(self):
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "company_id": self.company.id,
        })
        draft_copy = move.new(origin=move)
        with self.assertNoLogs("odoo.domains", level="WARNING"):
            partials = draft_copy._get_all_reconciled_invoice_partials()
        self.assertFalse([p for p in partials if p.get("is_exchange")])
