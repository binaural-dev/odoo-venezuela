from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestResConfigSettings(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")

    def test_max_product_invoice_propagates(self):
        config = self.env["res.config.settings"].create(
            {"max_product_invoice": 42}
        )
        config.flush_recordset()
        self.assertEqual(self.company.max_product_invoice, 42)
        self.assertEqual(config.max_product_invoice, 42)

    def test_group_sales_invoicing_series_propagates(self):
        config = self.env["res.config.settings"].create(
            {"group_sales_invoicing_series": True}
        )
        config.flush_recordset()
        self.assertTrue(self.company.group_sales_invoicing_series)

    def test_show_total_on_usd_invoice_propagates(self):
        self.company.show_total_on_usd_invoice = False
        config = self.env["res.config.settings"].create(
            {"show_total_on_usd_invoice": True}
        )
        config.flush_recordset()
        self.assertTrue(self.company.show_total_on_usd_invoice)

    def test_show_tag_on_usd_invoice_propagates(self):
        self.company.show_tag_on_usd_invoice = False
        config = self.env["res.config.settings"].create(
            {"show_tag_on_usd_invoice": True}
        )
        config.flush_recordset()
        self.assertTrue(self.company.show_tag_on_usd_invoice)

    def test_auto_select_debit_note_journal_propagates(self):
        config = self.env["res.config.settings"].create(
            {"auto_select_debit_note_journal": True}
        )
        config.flush_recordset()
        self.assertTrue(self.company.auto_select_debit_note_journal)

    def test_block_invoice_display_date_propagates(self):
        config = self.env["res.config.settings"].create(
            {"block_invoice_display_date_upper_than_date": True}
        )
        config.flush_recordset()
        self.assertTrue(self.company.block_invoice_display_date_upper_than_date)

    def test_onchange_group_sales_invoicing_series_activates_sequence(self):
        self.env["ir.sequence"].search(
            [("code", "=", "series.invoice.correlative")]
        ).write({"active": False})

        config = self.env["res.config.settings"].create(
            {"group_sales_invoicing_series": True}
        )
        config.onchange_group_sales_invoicing_series()

        seq = self.env["ir.sequence"].search(
            [("code", "=", "series.invoice.correlative")], limit=1
        )
        self.assertTrue(seq.active)

    def test_onchange_group_sales_invoicing_series_deactivates_sequence(self):
        self.env["ir.sequence"].search(
            [("code", "=", "series.invoice.correlative")]
        ).write({"active": True})

        config = self.env["res.config.settings"].create(
            {"group_sales_invoicing_series": False}
        )
        config.onchange_group_sales_invoicing_series()

        seq = self.env["ir.sequence"].search(
            [("code", "=", "series.invoice.correlative")], limit=1
        )
        self.assertFalse(seq.active)
