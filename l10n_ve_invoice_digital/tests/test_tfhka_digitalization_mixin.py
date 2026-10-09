import json
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

GENERATE_DIGITAL_PATCH = "odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.generate_document_digital"


@tagged("post_install", "-at_install", "l10n_ve_invoice_digital", "tfhka_digitalization_mixin")
class TestTfhkaDigitalizationMixin(TransactionCase):
    """Dedicated coverage for tfhka.digitalization.mixin itself (enqueue,
    single-document processing, the halt-on-error queue guard, manual
    retry/generate actions, and crash recovery), using account.move as the
    only model this mixin is applied to in this version."""

    def setUp(self):
        super().setUp()
        self.env.user.tz = "America/Caracas"
        self.company = self.env.ref("base.main_company")
        self.company.write({
            "invoice_digital_tfhka": True,
            "url_tfhka": "https://api.tfhka.com",
            "token_auth_tfhka": "token_fake",
            "country_id": self.env.ref("base.ve").id,
        })

        seq = self.env["ir.sequence"].create({"name": "Sec Test", "prefix": "INV/", "padding": 4})
        self.journal = self.env["account.journal"].create({
            "name": "Diario Digital Test",
            "code": "DDT",
            "type": "sale",
            "company_id": self.company.id,
            "digital_invoice": True,
            "sequence_id": seq.id,
        })
        self.partner = self.env["res.partner"].create({
            "name": "Cliente Test",
            "vat": "J12345678",
            "prefix_vat": "J",
            "country_id": self.env.ref("base.ve").id,
            "phone": "04141234567",
            "email": "test@test.com",
            "street": "Calle Test",
        })
        self.acc_income = self.env["account.account"].create({
            "name": "Ingresos",
            "code": "4001",
            "account_type": "income",
            "company_id": self.company.id,
        })

    def _create_invoice(self):
        prod = self.env["product.product"].create({
            "name": "Prod",
            "type": "service",
            "list_price": 100,
            "taxes_id": [(5, 0, 0)],
        })
        inv = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [(0, 0, {
                "product_id": prod.id,
                "quantity": 1,
                "price_unit": 100,
                "account_id": self.acc_income.id,
                "tax_ids": [(5, 0, 0)],
            })],
        })
        inv.action_post()
        return inv

    # ------------------------------------------------------------------
    # _tfhka_enqueue_digitalization
    # ------------------------------------------------------------------

    def test_enqueue_skips_records_already_queued_or_processing(self):
        inv = self._create_invoice()
        inv.write({"tfhka_digitalization_state": "processing", "tfhka_digitalization_error": "sentinel"})

        inv._tfhka_enqueue_digitalization()

        # Untouched: enqueue must not clobber an attempt already in flight.
        self.assertEqual(inv.tfhka_digitalization_state, "processing")
        self.assertEqual(inv.tfhka_digitalization_error, "sentinel")

    # ------------------------------------------------------------------
    # _tfhka_process_digitalization
    # ------------------------------------------------------------------

    def test_process_digitalization_success(self):
        inv = self._create_invoice()
        inv._tfhka_enqueue_digitalization()

        with patch(GENERATE_DIGITAL_PATCH, lambda self: self.write({"is_digitalized": True})):
            result = inv._tfhka_process_digitalization()

        self.assertTrue(result)
        self.assertEqual(inv.tfhka_digitalization_state, "success")
        self.assertTrue(inv.is_digitalized)
        self.assertFalse(inv.tfhka_digitalization_error)

    def test_process_digitalization_error_halts_with_message(self):
        inv = self._create_invoice()
        inv._tfhka_enqueue_digitalization()

        with patch(GENERATE_DIGITAL_PATCH, side_effect=UserError("Some business error")):
            result = inv._tfhka_process_digitalization()

        self.assertFalse(result)
        self.assertEqual(inv.tfhka_digitalization_state, "error")
        self.assertIn("Some business error", inv.tfhka_digitalization_error)

    def test_process_digitalization_refuses_record_not_queued(self):
        # Defensive guard: only ever called by the cron on a document it
        # just fetched as 'queued'. Any other state must not trigger a real
        # TFHKA call.
        inv = self._create_invoice()

        with patch(GENERATE_DIGITAL_PATCH) as mock_generate:
            result = inv._tfhka_process_digitalization()

        mock_generate.assert_not_called()
        self.assertFalse(result)

    # ------------------------------------------------------------------
    # _tfhka_cron_process_queue: halt-on-error guard + FIFO halt
    # ------------------------------------------------------------------

    def test_cron_process_queue_does_nothing_while_there_is_an_error(self):
        errored = self._create_invoice()
        errored.write({"tfhka_digitalization_state": "error", "tfhka_digitalization_error": "boom"})
        queued = self._create_invoice()
        queued._tfhka_enqueue_digitalization()

        with patch(GENERATE_DIGITAL_PATCH) as mock_generate:
            self.env["account.move"]._tfhka_cron_process_queue()

        mock_generate.assert_not_called()
        self.assertEqual(queued.tfhka_digitalization_state, "queued")

    def test_cron_process_queue_halts_after_first_failure_leaving_rest_queued(self):
        inv1 = self._create_invoice()
        inv1._tfhka_enqueue_digitalization()
        inv2 = self._create_invoice()
        inv2._tfhka_enqueue_digitalization()

        with patch(GENERATE_DIGITAL_PATCH, side_effect=UserError("boom")):
            self.env["account.move"]._tfhka_cron_process_queue()

        self.assertEqual(inv1.tfhka_digitalization_state, "error")
        self.assertEqual(
            inv2.tfhka_digitalization_state, "queued",
            "The 2nd document must not be touched once the 1st halts the queue.",
        )

    def test_cron_process_queue_processes_all_when_all_succeed(self):
        inv1 = self._create_invoice()
        inv1._tfhka_enqueue_digitalization()
        inv2 = self._create_invoice()
        inv2._tfhka_enqueue_digitalization()

        with patch(GENERATE_DIGITAL_PATCH, lambda self: self.write({"is_digitalized": True})):
            self.env["account.move"]._tfhka_cron_process_queue()

        self.assertEqual(inv1.tfhka_digitalization_state, "success")
        self.assertEqual(inv2.tfhka_digitalization_state, "success")

    # ------------------------------------------------------------------
    # action_tfhka_retry_digitalization / action_tfhka_generate_digital
    # ------------------------------------------------------------------

    def test_retry_action_resumes_the_rest_of_the_queue_on_success(self):
        errored = self._create_invoice()
        errored._tfhka_enqueue_digitalization()
        errored.write({"tfhka_digitalization_state": "error", "tfhka_digitalization_error": "boom"})
        queued = self._create_invoice()
        queued._tfhka_enqueue_digitalization()

        errored.action_tfhka_retry_digitalization()
        self.assertEqual(errored.tfhka_digitalization_state, "queued")

        with patch(GENERATE_DIGITAL_PATCH, lambda self: self.write({"is_digitalized": True})):
            self.env["account.move"]._tfhka_cron_process_queue()

        self.assertEqual(errored.tfhka_digitalization_state, "success")
        self.assertEqual(
            queued.tfhka_digitalization_state, "success",
            "A successful retry must resume the rest of the queue on the cron's next tick.",
        )

    def test_retry_action_does_not_resume_queue_when_retry_itself_fails(self):
        errored = self._create_invoice()
        errored._tfhka_enqueue_digitalization()
        errored.write({"tfhka_digitalization_state": "error", "tfhka_digitalization_error": "boom"})
        queued = self._create_invoice()
        queued._tfhka_enqueue_digitalization()

        errored.action_tfhka_retry_digitalization()
        self.assertEqual(errored.tfhka_digitalization_state, "queued")

        with patch(GENERATE_DIGITAL_PATCH, side_effect=UserError("still broken")):
            self.env["account.move"]._tfhka_cron_process_queue()

        self.assertEqual(errored.tfhka_digitalization_state, "error")
        self.assertEqual(queued.tfhka_digitalization_state, "queued")

    def test_action_generate_digital_only_enqueues_never_calls_tfhka_inline(self):
        inv = self._create_invoice()

        with patch(GENERATE_DIGITAL_PATCH) as mock_generate:
            inv.action_tfhka_generate_digital()

        mock_generate.assert_not_called()
        self.assertEqual(inv.tfhka_digitalization_state, "queued")

    # ------------------------------------------------------------------
    # _tfhka_recover_stuck_processing (crash-recovery on the next cron tick)
    # ------------------------------------------------------------------

    def test_recover_stuck_processing_without_matching_log_and_past_grace_period_errors(self):
        inv = self._create_invoice()
        inv.write({"tfhka_digitalization_state": "processing"})
        # A second, separate write: date_state is auto-stamped to now()
        # whenever tfhka_digitalization_state is written (see write()), so
        # backdating it must happen in its own call afterwards.
        inv.write({"date_state": fields.Datetime.now() - timedelta(minutes=2)})

        self.env["account.move"]._tfhka_recover_stuck_processing()

        self.assertEqual(inv.tfhka_digitalization_state, "error")
        self.assertTrue(inv.tfhka_digitalization_error)
        self.assertIn("TFHKA", inv.tfhka_digitalization_error)

    def test_recover_stuck_processing_within_grace_period_is_left_untouched(self):
        inv = self._create_invoice()
        inv.write({"tfhka_digitalization_state": "processing"})
        inv.write({"date_state": fields.Datetime.now() - timedelta(seconds=59)})

        resolved = self.env["account.move"]._tfhka_recover_stuck_processing()

        self.assertFalse(resolved)
        self.assertEqual(inv.tfhka_digitalization_state, "processing")

    def test_recover_stuck_processing_within_grace_period_halts_the_whole_queue(self):
        stuck = self._create_invoice()
        stuck.write({"tfhka_digitalization_state": "processing"})
        queued = self._create_invoice()
        queued._tfhka_enqueue_digitalization()

        with patch(GENERATE_DIGITAL_PATCH) as mock_generate:
            self.env["account.move"]._tfhka_cron_process_queue()

        mock_generate.assert_not_called()
        self.assertEqual(stuck.tfhka_digitalization_state, "processing")
        self.assertEqual(queued.tfhka_digitalization_state, "queued")

    def test_recover_stuck_processing_with_matching_success_log_recovers_success_even_when_old(self):
        inv = self._create_invoice()
        started_at = fields.Datetime.now() - timedelta(hours=1)
        inv.write({"tfhka_digitalization_state": "processing"})
        inv.write({"date_state": started_at})
        self.env["tfhka.api.log"].sudo().create({
            "company_id": self.company.id,
            "res_model": "account.move",
            "res_id": inv.id,
            "endpoint": "/Emision",
            "http_method": "POST",
            "success": True,
            "status_code": 200,
            "request_payload": json.dumps({
                "documentoElectronico": {
                    "encabezado": {"identificacionDocumento": {"numeroDocumento": "123"}},
                },
            }),
            "response_payload": json.dumps({"resultado": {"numeroControl": "00-00099999"}}),
        })

        self.env["account.move"]._tfhka_recover_stuck_processing()

        self.assertEqual(inv.tfhka_digitalization_state, "success")
        self.assertTrue(inv.is_digitalized)
        self.assertEqual(inv.correlative, "00-00099999")

    def test_recover_stuck_processing_ignores_log_from_an_unrelated_endpoint(self):
        inv = self._create_invoice()
        started_at = fields.Datetime.now() - timedelta(minutes=2)
        inv.write({"tfhka_digitalization_state": "processing"})
        inv.write({"date_state": started_at})
        # A successful call did happen for this document after the attempt
        # started, but not the submission itself -- must not count as proof
        # that TFHKA actually received the document.
        self.env["tfhka.api.log"].sudo().create({
            "company_id": self.company.id,
            "res_model": "account.move",
            "res_id": inv.id,
            "endpoint": "/ConsultaNumeraciones",
            "http_method": "POST",
            "success": True,
            "status_code": 200,
            "request_payload": "{}",
            "response_payload": "{}",
        })

        self.env["account.move"]._tfhka_recover_stuck_processing()

        self.assertEqual(inv.tfhka_digitalization_state, "error")

    def test_recover_stuck_processing_orders_oldest_first(self):
        old = self._create_invoice()
        old.write({"tfhka_digitalization_state": "processing"})
        old.write({"date_state": fields.Datetime.now() - timedelta(minutes=5)})
        fresh = self._create_invoice()
        fresh.write({"tfhka_digitalization_state": "processing"})

        resolved = self.env["account.move"]._tfhka_recover_stuck_processing()

        self.assertFalse(resolved)
        self.assertEqual(old.tfhka_digitalization_state, "error")
        self.assertEqual(fresh.tfhka_digitalization_state, "processing")
