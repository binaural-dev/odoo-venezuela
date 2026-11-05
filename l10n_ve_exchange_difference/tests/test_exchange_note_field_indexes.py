from odoo.tests import TransactionCase, tagged


@tagged("l10n_ve_exchange_difference", "-at_install", "post_install")
class TestExchangeNoteFieldIndexes(TransactionCase):
    """`_get_exchange_note_partials_against_counterparts` busca por `l10n_ve_exchange_invoice_id` cada vez que
    se calcula el widget de una factura con parciales; sin índice es un seq scan sobre `account_move`."""

    def _indexed_columns(self):
        self.env.cr.execute(
            "SELECT indexdef FROM pg_indexes WHERE schemaname = current_schema() AND tablename = 'account_move'"
        )
        return " ".join(row[0] for row in self.env.cr.fetchall())

    def test_exchange_note_link_fields_are_indexed(self):
        fields = self.env["account.move"]._fields
        self.assertEqual(fields["l10n_ve_exchange_invoice_id"].index, "btree_not_null")
        self.assertEqual(fields["l10n_ve_exchange_line_id"].index, "btree_not_null")

    def test_exchange_note_link_indexes_exist_in_database(self):
        """El índice debe existir de verdad en PostgreSQL (no solo estar declarado en el campo)."""
        indexes = self._indexed_columns()
        self.assertIn("l10n_ve_exchange_invoice_id", indexes)
        self.assertIn("l10n_ve_exchange_line_id", indexes)
