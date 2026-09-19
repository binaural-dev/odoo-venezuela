import json
from datetime import timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.addons.l10n_ve_invoice_digital.services.tfhka_client import TfhkaBusinessError
from odoo.addons.l10n_ve_invoice_digital.services.tfhka_service_base import TfhkaDataError
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

GENERATE_DIGITAL_PATCH = "odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.generate_document_digital"
SLEEP_PATCH = "odoo.addons.l10n_ve_invoice_digital.models.tfhka_digitalization_mixin.time.sleep"


@tagged("post_install", "-at_install", "l10n_ve_invoice_digital", "tfhka_digitalization_mixin")
class TestTfhkaDigitalizationMixin(TransactionCase):
    """Dedicated coverage for tfhka.digitalization.mixin itself (enqueue,
    single-document processing, the per-model queue/halt-on-error guard,
    manual retry/generate actions, crash recovery, and the alert banner
    data), using account.move as the concrete vehicle since it's the
    lightest of the three models this mixin is applied to.

    The other models' own test files (test_account_retention.py,
    test_stock_picking.py, test_wizard_move_action_post_alert.py, ...)
    already cover that each model wires the mixin correctly end-to-end;
    this file covers the mixin's own logic once, in isolation.
    """

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
        self.tax_group = self.env["account.tax.group"].create({"name": "IVA 16%"})
        self.tax_iva16 = self.env["account.tax"].create({
            "name": "IVA 16%",
            "amount": 16,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "tax_group_id": self.tax_group.id,
        })
        self.acc_income = self.env["account.account"].create({
            "name": "Ingresos",
            "code": "4001",
            "account_type": "income",
            "company_ids": [Command.link(self.company.id)],
        })

    def _create_invoice(self):
        prod = self.env["product.product"].create({
            "name": "Prod",
            "type": "service",
            "list_price": 100,
            "taxes_id": [Command.set([self.tax_iva16.id])],
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
                "tax_ids": [Command.set([self.tax_iva16.id])],
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

    def test_process_digitalization_retries_once_on_rate_limit_then_succeeds(self):
        inv = self._create_invoice()
        inv._tfhka_enqueue_digitalization()
        calls = []

        def fake_generate(self):
            calls.append(1)
            if len(calls) == 1:
                raise UserError("Consulta realizada previamente, favor de intentarlo en 30 segundos")
            self.write({"is_digitalized": True})

        with patch(GENERATE_DIGITAL_PATCH, fake_generate), patch(SLEEP_PATCH):
            result = inv._tfhka_process_digitalization()

        self.assertTrue(result)
        self.assertEqual(len(calls), 2)
        self.assertEqual(inv.tfhka_digitalization_state, "success")

    def test_process_digitalization_rate_limit_retry_also_fails(self):
        inv = self._create_invoice()
        inv._tfhka_enqueue_digitalization()

        def fake_generate(self):
            raise UserError("Consulta realizada previamente, favor de intentarlo en 30 segundos")

        with patch(GENERATE_DIGITAL_PATCH, fake_generate), patch(SLEEP_PATCH):
            result = inv._tfhka_process_digitalization()

        self.assertFalse(result)
        self.assertEqual(inv.tfhka_digitalization_state, "error")
        self.assertIn("realizada previamente", inv.tfhka_digitalization_error)

    def test_process_digitalization_non_rate_limit_error_does_not_retry(self):
        inv = self._create_invoice()
        inv._tfhka_enqueue_digitalization()
        calls = []

        def fake_generate(self):
            calls.append(1)
            raise UserError("Some unrelated business error")

        with patch(GENERATE_DIGITAL_PATCH, fake_generate):
            result = inv._tfhka_process_digitalization()

        self.assertFalse(result)
        self.assertEqual(len(calls), 1, "A non-rate-limit error must not be retried.")
        self.assertEqual(inv.tfhka_digitalization_state, "error")
        self.assertIn("Some unrelated business error", inv.tfhka_digitalization_error)

    # ------------------------------------------------------------------
    # error vs data_error classification (by TFHKA business code)
    # ------------------------------------------------------------------

    def test_process_digitalization_data_error_code_203(self):
        inv = self._create_invoice()
        inv._tfhka_enqueue_digitalization()

        def fake_generate(self):
            raise TfhkaBusinessError("Missing required field", tfhka_code="203")

        with patch(GENERATE_DIGITAL_PATCH, fake_generate):
            result = inv._tfhka_process_digitalization()

        self.assertFalse(result)
        self.assertEqual(inv.tfhka_digitalization_state, "data_error")
        self.assertIn("Missing required field", inv.tfhka_digitalization_error)

    def test_process_digitalization_data_error_code_205(self):
        inv = self._create_invoice()
        inv._tfhka_enqueue_digitalization()

        def fake_generate(self):
            raise TfhkaBusinessError("Does not meet minimum validations", tfhka_code="205")

        with patch(GENERATE_DIGITAL_PATCH, fake_generate):
            result = inv._tfhka_process_digitalization()

        self.assertFalse(result)
        self.assertEqual(inv.tfhka_digitalization_state, "data_error")

    def test_process_digitalization_other_tfhka_code_stays_grave_error(self):
        inv = self._create_invoice()
        inv._tfhka_enqueue_digitalization()

        def fake_generate(self):
            raise TfhkaBusinessError("Duplicate document", tfhka_code="201")

        with patch(GENERATE_DIGITAL_PATCH, fake_generate):
            result = inv._tfhka_process_digitalization()

        self.assertFalse(result)
        self.assertEqual(inv.tfhka_digitalization_state, "error")

    def test_process_digitalization_local_validation_is_a_data_error(self):
        # TfhkaDataError is raised by tfhka.service.base/tfhka.document.service
        # BEFORE any call to TFHKA (e.g. the customer's NIF is empty, the
        # invoice date is missing) -- it has no .tfhka_code at all, but it
        # must still classify as 'data_error', not the grave 'error'.
        inv = self._create_invoice()
        inv._tfhka_enqueue_digitalization()

        def fake_generate(self):
            raise TfhkaDataError("The 'NIF' field of the Customer cannot be empty for digitalization.")

        with patch(GENERATE_DIGITAL_PATCH, fake_generate):
            result = inv._tfhka_process_digitalization()

        self.assertFalse(result)
        self.assertEqual(inv.tfhka_digitalization_state, "data_error")
        self.assertIn("NIF", inv.tfhka_digitalization_error)

    def test_process_digitalization_error_without_tfhka_code_stays_grave_error(self):
        # A plain UserError (401, HTTP != 200, RequestException, ...) has no
        # .tfhka_code at all -- must default to the grave 'error' state, not
        # crash on the getattr lookup.
        inv = self._create_invoice()
        inv._tfhka_enqueue_digitalization()

        with patch(GENERATE_DIGITAL_PATCH, side_effect=UserError("HTTP error 500: boom")):
            result = inv._tfhka_process_digitalization()

        self.assertFalse(result)
        self.assertEqual(inv.tfhka_digitalization_state, "error")

    # ------------------------------------------------------------------
    # _tfhka_cron_process_queue: halt-on-error guard + FIFO halt
    # ------------------------------------------------------------------

    def test_cron_process_queue_does_nothing_while_model_has_an_error(self):
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
        self.assertEqual(inv2.tfhka_digitalization_state, "queued", "The 2nd document must not be touched once the 1st halts the queue.")

    def test_cron_process_queue_does_nothing_while_model_has_a_data_error(self):
        data_errored = self._create_invoice()
        data_errored.write({"tfhka_digitalization_state": "data_error", "tfhka_digitalization_error": "bad field"})
        queued = self._create_invoice()
        queued._tfhka_enqueue_digitalization()

        with patch(GENERATE_DIGITAL_PATCH) as mock_generate:
            self.env["account.move"]._tfhka_cron_process_queue()

        mock_generate.assert_not_called()
        self.assertEqual(queued.tfhka_digitalization_state, "queued")

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
        errored.write({"tfhka_digitalization_state": "error", "tfhka_digitalization_error": "boom"})
        queued = self._create_invoice()
        queued._tfhka_enqueue_digitalization()

        with patch(GENERATE_DIGITAL_PATCH, lambda self: self.write({"is_digitalized": True})):
            errored.action_tfhka_retry_digitalization()

        self.assertEqual(errored.tfhka_digitalization_state, "success")
        self.assertEqual(queued.tfhka_digitalization_state, "success", "A successful retry must resume the rest of the queue right away.")

    def test_retry_action_resumes_the_rest_of_the_queue_from_data_error(self):
        data_errored = self._create_invoice()
        data_errored.write({"tfhka_digitalization_state": "data_error", "tfhka_digitalization_error": "bad field"})
        queued = self._create_invoice()
        queued._tfhka_enqueue_digitalization()

        with patch(GENERATE_DIGITAL_PATCH, lambda self: self.write({"is_digitalized": True})):
            data_errored.action_tfhka_retry_digitalization()

        self.assertEqual(data_errored.tfhka_digitalization_state, "success")
        self.assertEqual(queued.tfhka_digitalization_state, "success")

    def test_retry_action_does_not_resume_queue_when_retry_itself_fails(self):
        errored = self._create_invoice()
        errored.write({"tfhka_digitalization_state": "error", "tfhka_digitalization_error": "boom"})
        queued = self._create_invoice()
        queued._tfhka_enqueue_digitalization()

        with patch(GENERATE_DIGITAL_PATCH, side_effect=UserError("still broken")):
            errored.action_tfhka_retry_digitalization()

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
        # Well past STUCK_PROCESSING_GRACE_PERIOD (1 minute), no log evidence
        # at all -- must not be silently requeued (that would risk a
        # duplicate if TFHKA actually received it): a human must review it.
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
        # 59s < the 1-minute grace period: no log yet is indistinguishable
        # from "TFHKA hasn't answered/logged it yet" -- must not error out a
        # call that may still be in flight.
        inv = self._create_invoice()
        inv.write({"tfhka_digitalization_state": "processing"})
        inv.write({"date_state": fields.Datetime.now() - timedelta(seconds=59)})

        resolved = self.env["account.move"]._tfhka_recover_stuck_processing()

        self.assertFalse(resolved)
        self.assertEqual(inv.tfhka_digitalization_state, "processing")
        self.assertTrue(inv.date_state)

    def test_recover_stuck_processing_within_grace_period_halts_only_this_model_queue(self):
        # A halts on its own stuck 'processing' record (still fresh); B is a
        # separate, unrelated 'queued' document of the SAME model -- it must
        # not be touched either, since the whole model's queue is frozen
        # until A is resolved one way or the other.
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
        # An hour old -- well past the grace period -- but the log still
        # wins: TFHKA actually received it, so it must be 'success', never
        # 'error', regardless of how long ago the attempt started.
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
        # started, but not the submission itself (e.g. ConsultaNumeraciones,
        # which also logs with origin=invoice) -- must not count as proof
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
        # Two stuck documents of the same model: an old one (past the grace
        # period, no log -> resolves to 'error') and a fresh one (within
        # grace). Without ordering by date_state asc, the fresh one could be
        # visited first and halt the loop before the old one is ever
        # resolved.
        old = self._create_invoice()
        old.write({"tfhka_digitalization_state": "processing"})
        old.write({"date_state": fields.Datetime.now() - timedelta(minutes=5)})
        fresh = self._create_invoice()
        fresh.write({"tfhka_digitalization_state": "processing"})

        resolved = self.env["account.move"]._tfhka_recover_stuck_processing()

        self.assertFalse(resolved)
        self.assertEqual(old.tfhka_digitalization_state, "error")
        self.assertEqual(fresh.tfhka_digitalization_state, "processing")

    # ------------------------------------------------------------------
    # _tfhka_digitalization_alert_data (top-of-page banner)
    # ------------------------------------------------------------------

    def test_alert_data_lists_errored_documents_for_internal_users(self):
        errored = self._create_invoice()
        errored.write({"tfhka_digitalization_state": "error", "tfhka_digitalization_error": "boom"})
        queued = self._create_invoice()
        queued._tfhka_enqueue_digitalization()

        alerts = self.env["account.move"]._tfhka_digitalization_alert_data(["account.move"])

        self.assertEqual([a["name"] for a in alerts], [errored.display_name])
        self.assertIn("model=account.move", alerts[0]["url"])
        self.assertIn("res_id=%s" % errored.id, alerts[0]["url"])

    def test_alert_data_lists_data_errored_documents_too(self):
        data_errored = self._create_invoice()
        data_errored.write({"tfhka_digitalization_state": "data_error", "tfhka_digitalization_error": "bad field"})

        alerts = self.env["account.move"]._tfhka_digitalization_alert_data(["account.move"])

        self.assertEqual([a["name"] for a in alerts], [data_errored.display_name])

    def test_alert_data_empty_for_non_internal_user(self):
        errored = self._create_invoice()
        errored.write({"tfhka_digitalization_state": "error", "tfhka_digitalization_error": "boom"})
        portal_user = self.env["res.users"].create({
            "name": "Portal User",
            "login": "tfhka_portal_test_user",
            "email": "portal_tfhka_test@test.com",
            "group_ids": [Command.set([self.env.ref("base.group_portal").id])],
        })

        alerts = self.env["account.move"].with_user(portal_user)._tfhka_digitalization_alert_data(["account.move"])

        self.assertEqual(alerts, [])
