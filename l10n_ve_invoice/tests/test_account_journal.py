from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestAccountJournal(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")

    def test_create_journal_with_debit(self):
        journal = self.env["account.journal"].create(
            {
                "name": "Debit Journal Test",
                "type": "sale",
                "code": "DJT99",
                "company_id": self.company.id,
                "is_debit": True,
            }
        )
        self.assertTrue(journal.is_debit)

    def test_create_journal_with_contingency(self):
        journal = self.env["account.journal"].create(
            {
                "name": "Contingency Journal Test",
                "type": "sale",
                "code": "CJT99",
                "company_id": self.company.id,
                "is_contingency": True,
            }
        )
        self.assertTrue(journal.is_contingency)

    def test_create_journal_with_series_sequence(self):
        series_seq = self.env["ir.sequence"].create(
            {
                "name": "Series Seq Test",
                "code": "test.series.jrn",
                "padding": 5,
            }
        )
        journal = self.env["account.journal"].create(
            {
                "name": "Series Journal Test",
                "type": "sale",
                "code": "SJT99",
                "company_id": self.company.id,
                "series_correlative_sequence_id": series_seq.id,
            }
        )
        self.assertEqual(journal.series_correlative_sequence_id, series_seq)

    def test_fields_default_values(self):
        journal = self.env["account.journal"].create(
            {
                "name": "Default Journal Test",
                "type": "sale",
                "code": "DFT99",
                "company_id": self.company.id,
            }
        )
        self.assertFalse(journal.is_contingency)
        self.assertFalse(journal.is_debit)
        self.assertFalse(journal.series_correlative_sequence_id)
