from datetime import date

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMfPendingSync(TransactionCase):
    """TI-16293: documento impreso en la máquina fiscal sin poder leer S1.

    El documento queda marcado como pendiente (no se puede volver a imprimir)
    y los datos fiscales se recuperan comparando S1 con la foto previa a la
    impresión. Solo se asigna el número cuando no hay ambigüedad.
    """

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.partner = self.env["res.partner"].create({"name": "Cliente 16293"})
        self.journal = self.env["account.journal"].create(
            {
                "name": "Diario 16293",
                "code": "T1629",
                "type": "sale",
                "company_id": self.company.id,
            }
        )
        self.serial = "Z6C3000455"
        self.move = self._create_move()

    def _create_move(self, **vals):
        return self.env["account.move"].create(
            {
                "partner_id": self.partner.id,
                "move_type": "out_invoice",
                "invoice_date": date.today(),
                "date": date.today(),
                "journal_id": self.journal.id,
                "company_id": self.company.id,
                "currency_id": self.company.currency_id.id,
                **vals,
            }
        )

    def _s1(self, number, serial=None, z=41):
        return {
            "last_invoice_number": number,
            "last_nc_number": 7,
            "last_debit_note_number": 3,
            "serial": self.serial if serial is None else serial,
            "daily_closure_counter": z,
        }

    def _mark_pending(self, before=None):
        self.move.mf_mark_pending_sync(
            action="print_out_invoice",
            reason="Factura impresa, pero no se pudo leer S1: Respuesta no comienza con STX",
            before=before,
        )

    def _last_message(self):
        return self.move.message_ids.sorted("id")[-1].body

    def test_mark_pending_stores_snapshot_and_explains_in_chatter(self):
        self._mark_pending(self._s1(56382))

        self.assertTrue(self.move.mf_pending_sync)
        self.assertEqual(
            self.move.mf_pending_sync_data,
            {"doc_type": "invoice", "number_before": 56382, "serial": self.serial, "z_before": 41},
        )
        body = self._last_message()
        self.assertIn("Recuperar datos fiscales", body)
        self.assertNotIn("no hay máquina fiscal conectada", body)

    def test_pending_document_cannot_be_printed_again(self):
        self._mark_pending(self._s1(56382))

        with self.assertRaises(ValidationError):
            self.move.check_print_out_invoice()

    def test_sync_assigns_next_number_serial_and_snapshot_z(self):
        self._mark_pending(self._s1(56382, z=41))

        # Entre la impresión y la recuperación se cerró un Z: el documento
        # pertenece al Z abierto cuando se imprimió (el de la foto).
        result = self.move.mf_sync_fiscal_data(self._s1(56383, z=42))

        self.assertEqual(result["sequence"], "56383")
        self.assertEqual(self.move.mf_invoice_number, "56383")
        self.assertEqual(self.move.mf_serial, self.serial)
        self.assertEqual(self.move.mf_reportz, "42")
        self.assertFalse(self.move.mf_pending_sync)
        self.assertFalse(self.move.mf_pending_sync_data)

    def test_sync_refuses_when_other_documents_were_printed_after(self):
        self._mark_pending(self._s1(56382))

        with self.assertRaisesRegex(UserError, "56383"):
            self.move.mf_sync_fiscal_data(self._s1(56385))
        self.assertTrue(self.move.mf_pending_sync)
        self.assertFalse(self.move.mf_invoice_number)

    def test_sync_refuses_when_counter_did_not_advance(self):
        self._mark_pending(self._s1(56382))

        with self.assertRaises(UserError):
            self.move.mf_sync_fiscal_data(self._s1(56382))
        self.assertTrue(self.move.mf_pending_sync)

    def test_sync_refuses_other_fiscal_machine(self):
        self._mark_pending(self._s1(56382))

        with self.assertRaisesRegex(UserError, "OTRA0001"):
            self.move.mf_sync_fiscal_data(self._s1(56383, serial="OTRA0001"))
        self.assertTrue(self.move.mf_pending_sync)

    def test_sync_without_snapshot_requires_manual_review(self):
        self._mark_pending(before=None)

        with self.assertRaises(UserError):
            self.move.mf_sync_fiscal_data(self._s1(56383))
        self.assertTrue(self.move.mf_pending_sync)

    def test_sync_refuses_number_already_assigned(self):
        self._create_move(mf_invoice_number="56383", mf_serial=self.serial)
        self._mark_pending(self._s1(56382))

        with self.assertRaisesRegex(UserError, "56383"):
            self.move.mf_sync_fiscal_data(self._s1(56383))
        self.assertTrue(self.move.mf_pending_sync)

    def test_sync_credit_note_uses_credit_note_counter(self):
        self.move = self._create_move(move_type="out_refund")
        self._mark_pending(self._s1(56382))
        self.assertEqual(self.move.mf_pending_sync_data["number_before"], 7)

        s1 = self._s1(56382)
        s1["last_nc_number"] = 8
        self.move.mf_sync_fiscal_data(s1)

        self.assertEqual(self.move.mf_invoice_number, "8")

    def test_sync_requires_pending_document(self):
        with self.assertRaises(ValidationError):
            self.move.mf_sync_fiscal_data(self._s1(56383))

    def test_manual_load_clears_pending(self):
        self._mark_pending(before=None)

        self.move.write({"mf_invoice_number": "56383", "mf_serial": self.serial, "mf_reportz": "42"})

        self.assertFalse(self.move.mf_pending_sync)
        self.assertFalse(self.move.mf_pending_sync_data)

    def test_failure_log_only_blames_connection_when_there_is_none(self):
        self.move.log_mf_print_failure(action="print_out_invoice", reason="Error en comando [202]: NAK")
        self.assertNotIn("no hay", self._last_message())
        self.assertIn("reportó un error", self._last_message())

        self.move.log_mf_print_failure(
            action="print_out_invoice", reason="Sin conexión", kind="no_connection"
        )
        self.assertIn("no hay conexión con la máquina fiscal", self._last_message())
