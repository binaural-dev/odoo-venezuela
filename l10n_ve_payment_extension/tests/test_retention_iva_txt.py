from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "retention_iva_txt")
class TestRetentionIvaTxt(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.company.partner_id.vat = "J503498757"
        self.partner = self.env["res.partner"].create(
            {
                "name": "SOLUCIONES DE LOCALIZACION TRACKER C.A.",
                "prefix_vat": "J",
                "vat": "402081146",
            }
        )
        self.journal = self.env["account.journal"].create(
            {
                "name": "Purchase TXT",
                "code": "TXTP",
                "type": "purchase",
                "company_id": self.company.id,
            }
        )
        self.wizard = self.env["wizard.retention.iva"]

    def _create_invoice(self, invoice_date):
        return self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal.id,
                "invoice_date": invoice_date,
                "date": invoice_date,
                "name": "00016422",
                "correlative": "Z7C0024536",
            }
        )

    def _create_retention(self, number, voucher_date, accounting_date):
        invoice = self._create_invoice(date(2026, 6, 17))
        retention = self.env["account.retention"].create(
            {
                "type_retention": "iva",
                "type": "in_invoice",
                "company_id": self.company.id,
                "partner_id": self.partner.id,
                "date": voucher_date,
                "date_accounting": accounting_date,
                "number": number,
                "state": "emitted",
            }
        )
        self.env["account.retention.line"].create(
            {
                "retention_id": retention.id,
                "move_id": invoice.id,
                "name": "IVA Retention",
                "aliquot": 16.0,
                "invoice_amount": 187780.65,
                "iva_amount": 30044.90,
                "retention_amount": 22533.68,
                "foreign_invoice_amount": 187780.65,
                "foreign_iva_amount": 30044.90,
                "foreign_retention_amount": 22533.68,
            }
        )
        return retention

    def test_txt_domain_uses_accounting_date(self):
        june_retention = self._create_retention(
            "20260600000239", date(2026, 7, 2), date(2026, 6, 23)
        )
        july_retention = self._create_retention(
            "20260700000001", date(2026, 6, 23), date(2026, 7, 2)
        )

        domain = self.wizard._get_iva_retention_domain(
            date(2026, 6, 16), date(2026, 6, 30), self.company.id
        )
        retentions = self.env["account.retention"].search(domain)

        self.assertIn(june_retention, retentions)
        self.assertNotIn(july_retention, retentions)

    def test_txt_period_uses_accounting_date(self):
        retention = self._create_retention(
            "20260600000239", date(2026, 7, 2), date(2026, 6, 23)
        )

        data = self.wizard._retention_iva(retention)

        self.assertEqual(data[0]["Per\u00edodo impositivo"], "202606")
