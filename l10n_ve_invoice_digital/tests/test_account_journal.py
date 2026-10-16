from psycopg2 import IntegrityError

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError
from odoo.tools import mute_logger


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

    # ------------------------------------------------------------------
    # _get_tfhka_series / tfhka_serie_id
    # ------------------------------------------------------------------

    def test_05_get_tfhka_series_empty_when_company_does_not_invoice_by_series(self):
        self.company.group_sales_invoicing_series = False
        serie = self.env["tfhka.serie"].create({"name": "A", "company_id": self.company.id})
        self.journal.tfhka_serie_id = serie.id

        self.assertEqual(self.journal._get_tfhka_series(), "")

    def test_06_get_tfhka_series_empty_when_no_serie_assigned(self):
        self.company.group_sales_invoicing_series = True

        self.assertEqual(self.journal._get_tfhka_series(), "")

    def test_07_get_tfhka_series_returns_assigned_serie_name(self):
        self.company.group_sales_invoicing_series = True
        serie = self.env["tfhka.serie"].create({"name": "A", "company_id": self.company.id})
        self.journal.tfhka_serie_id = serie.id

        self.assertEqual(self.journal._get_tfhka_series(), "A")

    def test_08_tfhka_serie_id_unique_per_journal(self):
        serie = self.env["tfhka.serie"].create({"name": "A", "company_id": self.company.id})
        self.journal.tfhka_serie_id = serie.id
        other_journal = self.env["account.journal"].create({
            "name": "Otro Diario",
            "code": "OTR",
            "type": "sale",
            "company_id": self.company.id,
        })

        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            other_journal.tfhka_serie_id = serie.id

    def test_09_two_journals_without_serie_do_not_conflict(self):
        # NULL no cuenta como duplicado para la restricción unique() -- dos
        # diarios sin serie asignada deben poder coexistir sin problema.
        other_journal = self.env["account.journal"].create({
            "name": "Otro Diario",
            "code": "OTR",
            "type": "sale",
            "company_id": self.company.id,
        })
        self.assertFalse(self.journal.tfhka_serie_id)
        self.assertFalse(other_journal.tfhka_serie_id)

    # ------------------------------------------------------------------
    # A lo sumo un diario de facturación digital por compañía puede quedar
    # sin tfhka_serie_id (asignar una serie sigue sin ser obligatorio).
    # ------------------------------------------------------------------

    def test_10_second_digital_journal_without_serie_warns_but_does_not_block(self):
        self.journal.digital_invoice = True

        other_journal = self.env["account.journal"].create({
            "name": "Otro Diario",
            "code": "OTR",
            "type": "sale",
            "company_id": self.company.id,
            "digital_invoice": True,
        })

        # No se bloquea la creacion.
        self.assertTrue(other_journal)
        self.assertFalse(other_journal.tfhka_serie_id)
        # Pero queda una nota en el chatter.
        self.assertTrue(
            any("TFHKA series" in (m or "") for m in other_journal.message_ids.mapped("body"))
        )

    def test_13_onchange_warns_without_blocking(self):
        self.journal.digital_invoice = True
        other_journal = self.env["account.journal"].new({
            "name": "Otro Diario",
            "code": "OTR",
            "type": "sale",
            "company_id": self.company.id,
            "digital_invoice": True,
        })

        result = other_journal._onchange_tfhka_serie_id_empty_warning()

        self.assertIn("warning", result)

    def test_11_second_non_digital_journal_without_serie_is_fine(self):
        self.journal.digital_invoice = True
        other_journal = self.env["account.journal"].create({
            "name": "Otro Diario",
            "code": "OTR",
            "type": "sale",
            "company_id": self.company.id,
        })

        self.assertFalse(other_journal.digital_invoice)
        self.assertFalse(other_journal.tfhka_serie_id)

    def test_12_second_digital_journal_without_serie_ok_if_first_has_one(self):
        serie = self.env["tfhka.serie"].create({"name": "A", "company_id": self.company.id})
        self.journal.digital_invoice = True
        self.journal.tfhka_serie_id = serie.id

        other_journal = self.env["account.journal"].create({
            "name": "Otro Diario",
            "code": "OTR",
            "type": "sale",
            "company_id": self.company.id,
            "digital_invoice": True,
        })

        self.assertFalse(other_journal.tfhka_serie_id)
