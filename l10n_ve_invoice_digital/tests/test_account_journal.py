from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged("post_install", "-at_install", "l10n_ve_invoice_digital", "account_journal")
class TestAccountJournal(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.journal = self.env["account.journal"].create({
            "name": "Diario Test Digital",
            "code": "DTST",
            "type": "sale",
            "company_id": self.company.id,
        })

    def test_01_compute_digital_invoice_lock_no_moves(self):
        self.journal.digital_invoice = True
        self.journal._compute_digital_invoice_lock()
        self.assertFalse(self.journal.digital_invoice_lock)

    def test_02_compute_digital_invoice_lock_with_move(self):
        self.journal.digital_invoice = True
        partner = self.env["res.partner"].create({"name": "Test Partner"})
        self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": partner.id,
            "journal_id": self.journal.id,
            "is_digitalized": True,
        })
        self.journal._compute_digital_invoice_lock()
        self.assertTrue(self.journal.digital_invoice_lock)
        self.assertTrue(self.journal.digital_invoice)

    def test_03_write_disable_digital_invoice_with_moves(self):
        self.journal.digital_invoice = True
        partner = self.env["res.partner"].create({"name": "Test Partner"})
        self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": partner.id,
            "journal_id": self.journal.id,
            "is_digitalized": True,
        })
        with self.assertRaises(ValidationError):
            self.journal.write({"digital_invoice": False})

    def test_04_write_disable_digital_invoice_without_moves(self):
        self.journal.digital_invoice = True
        self.journal.write({"digital_invoice": False})
        self.assertFalse(self.journal.digital_invoice)
