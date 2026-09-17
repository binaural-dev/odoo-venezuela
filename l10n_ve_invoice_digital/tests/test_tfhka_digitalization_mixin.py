from datetime import timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

GENERATE_DIGITAL_PATCH = "odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.generate_document_digital"
SLEEP_PATCH = "odoo.addons.l10n_ve_invoice_digital.models.tfhka_digitalization_mixin.time.sleep"


@tagged("post_install", "-at_install", "l10n_ve_invoice_digital", "tfhka_digitalization_mixin")
class TestTfhkaDigitalizationMixin(TransactionCase):
    """Dedicated coverage for tfhka.digitalization.mixin itself (enqueue,
    single-document processing, the one-document-per-tick cron step,
    manual retry/generate actions, the stuck-'processing' timeout, and the
    alert banner data), using account.move as the concrete vehicle since
    it's the lightest of the three models this mixin is applied to.

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
    # date_state: stamped automatically on every state-changing write
    # ------------------------------------------------------------------

    def test_date_state_is_stamped_on_every_state_change(self):
        inv = self._create_invoice()
        self.assertFalse(inv.date_state)

        inv._tfhka_enqueue_digitalization()
        self.assertTrue(inv.date_state)
        queued_stamp = inv.date_state

        with patch(GENERATE_DIGITAL_PATCH, lambda self: self.write({"is_digitalized": True})):
            inv._tfhka_process_digitalization()

        self.assertGreaterEqual(inv.date_state, queued_stamp)

    def test_date_state_is_not_touched_by_unrelated_writes(self):
        inv = self._create_invoice()
        inv._tfhka_enqueue_digitalization()
        stamp = inv.date_state

        inv.write({"tfhka_digitalization_error": "unrelated update"})

        self.assertEqual(inv.date_state, stamp)

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

    def test_process_digitalization_refuses_when_not_queued(self):
        """Guards against any caller (button, wizard, future code) triggering
        a real TFHKA call outside the queue on a document that isn't
        actually pending -- e.g. a stale 'Retry' click racing the cron, or
        code trying to re-run an already-'success' document."""
        inv = self._create_invoice()
        inv.write({"tfhka_digitalization_state": "processing"})

        with patch(GENERATE_DIGITAL_PATCH) as mock_generate:
            result = inv._tfhka_process_digitalization()

        mock_generate.assert_not_called()
        self.assertFalse(result)
        self.assertEqual(inv.tfhka_digitalization_state, "processing", "Must be left untouched.")

    def test_process_digitalization_on_already_success_is_a_harmless_noop(self):
        inv = self._create_invoice()
        inv.write({"tfhka_digitalization_state": "success", "is_digitalized": True})

        with patch(GENERATE_DIGITAL_PATCH) as mock_generate:
            result = inv._tfhka_process_digitalization()

        mock_generate.assert_not_called()
        self.assertTrue(result, "Already-successful must be reported as success, not failure.")
        self.assertEqual(inv.tfhka_digitalization_state, "success")

    def test_process_digitalization_local_failure_is_logged_even_without_a_real_api_call(self):
        """A failure that never reaches TFHKA (e.g. a payload validation
        error, like a tax group with no TFHKA equivalent) must still show
        up in tfhka.api.log -- otherwise it's only visible in the
        document's chatter, not in the query history a human checks first
        when investigating TFHKA issues."""
        inv = self._create_invoice()
        inv._tfhka_enqueue_digitalization()

        with patch(GENERATE_DIGITAL_PATCH, side_effect=UserError("no TFHKA mapping configured")):
            inv._tfhka_process_digitalization()

        log = self.env["tfhka.api.log"].sudo().search([
            ("res_model", "=", "account.move"), ("res_id", "=", inv.id),
        ])
        self.assertEqual(len(log), 1)
        self.assertFalse(log.success)
        self.assertIn("no TFHKA mapping configured", log.response_payload)

    def test_process_digitalization_real_api_failure_is_not_logged_twice(self):
        """When generate_document_digital() itself already logged the
        failed call (a real HTTP request to TFHKA), the local-failure
        fallback must not add a second, redundant entry."""
        inv = self._create_invoice()
        inv._tfhka_enqueue_digitalization()

        def fake_generate(self):
            self.env["tfhka.api.log"].sudo().create({
                "company_id": self.company_id.id,
                "endpoint": "/Emision",
                "res_model": self._name,
                "res_id": self.id,
                "success": False,
                "response_payload": "HTTP 400",
            })
            raise UserError("HTTP error 400")

        with patch(GENERATE_DIGITAL_PATCH, fake_generate):
            inv._tfhka_process_digitalization()

        log = self.env["tfhka.api.log"].sudo().search([
            ("res_model", "=", "account.move"), ("res_id", "=", inv.id),
        ])
        self.assertEqual(len(log), 1, "Must not add a synthetic entry on top of the real one.")
        self.assertEqual(log.endpoint, "/Emision")

    # ------------------------------------------------------------------
    # _tfhka_cron_step / _tfhka_cron_process_queue_multi: drains the queue
    # ------------------------------------------------------------------

    def test_cron_process_queue_does_nothing_while_model_has_an_error(self):
        errored = self._create_invoice()
        errored.write({"tfhka_digitalization_state": "error", "tfhka_digitalization_error": "boom"})
        queued = self._create_invoice()
        queued._tfhka_enqueue_digitalization()

        with patch(GENERATE_DIGITAL_PATCH) as mock_generate:
            self.env["account.move"]._tfhka_cron_process_queue_multi(["account.move"])

        mock_generate.assert_not_called()
        self.assertEqual(queued.tfhka_digitalization_state, "queued")

    def test_cron_process_queue_multi_drains_the_whole_queue_oldest_first(self):
        inv1 = self._create_invoice()
        inv1._tfhka_enqueue_digitalization()
        inv2 = self._create_invoice()
        inv2._tfhka_enqueue_digitalization()
        inv3 = self._create_invoice()
        inv3._tfhka_enqueue_digitalization()
        order = []

        def fake_generate(self):
            order.append(self.id)
            self.write({"is_digitalized": True})

        with patch(GENERATE_DIGITAL_PATCH, fake_generate):
            self.env["account.move"]._tfhka_cron_process_queue_multi(["account.move"])

        self.assertEqual(inv1.tfhka_digitalization_state, "success")
        self.assertEqual(inv2.tfhka_digitalization_state, "success")
        self.assertEqual(inv3.tfhka_digitalization_state, "success")
        self.assertEqual(order, [inv1.id, inv2.id, inv3.id], "A single run must drain the whole queue, oldest first.")

    def test_cron_process_queue_failure_halts_the_rest_of_the_queue(self):
        inv1 = self._create_invoice()
        inv1._tfhka_enqueue_digitalization()
        inv2 = self._create_invoice()
        inv2._tfhka_enqueue_digitalization()

        with patch(GENERATE_DIGITAL_PATCH, side_effect=UserError("boom")):
            self.env["account.move"]._tfhka_cron_process_queue_multi(["account.move"])
            # A 2nd tick must do nothing further: inv1 is now the model's
            # one-and-only 'error' document, blocking everything.
            self.env["account.move"]._tfhka_cron_process_queue_multi(["account.move"])

        self.assertEqual(inv1.tfhka_digitalization_state, "error")
        self.assertEqual(inv2.tfhka_digitalization_state, "queued", "The 2nd document must not be touched once the 1st halts the queue.")

    # ------------------------------------------------------------------
    # _tfhka_cron_step: stuck 'processing' timeout
    # ------------------------------------------------------------------

    def test_cron_step_does_nothing_when_processing_is_recent(self):
        stuck = self._create_invoice()
        stuck.write({"tfhka_digitalization_state": "processing"})
        queued = self._create_invoice()
        queued._tfhka_enqueue_digitalization()

        with patch(GENERATE_DIGITAL_PATCH) as mock_generate:
            self.env["account.move"]._tfhka_cron_process_queue_multi(["account.move"])

        mock_generate.assert_not_called()
        self.assertEqual(stuck.tfhka_digitalization_state, "processing", "Too soon to consider it abandoned.")
        self.assertEqual(queued.tfhka_digitalization_state, "queued", "Must not skip ahead of the stuck document.")

    def test_cron_step_times_out_processing_stuck_past_the_threshold(self):
        stuck = self._create_invoice()
        stuck.write({"tfhka_digitalization_state": "processing"})
        stuck.write({"date_state": fields.Datetime.now() - timedelta(minutes=2)})
        queued = self._create_invoice()
        queued._tfhka_enqueue_digitalization()

        with patch(GENERATE_DIGITAL_PATCH) as mock_generate:
            self.env["account.move"]._tfhka_cron_process_queue_multi(["account.move"])

        mock_generate.assert_not_called()
        self.assertEqual(stuck.tfhka_digitalization_state, "error")
        self.assertIn("Processing", stuck.tfhka_digitalization_error)
        self.assertEqual(queued.tfhka_digitalization_state, "queued", "Marking the timeout must not also advance the queue in the same tick.")

    # ------------------------------------------------------------------
    # action_tfhka_retry_digitalization / action_tfhka_generate_digital
    # ------------------------------------------------------------------

    def test_retry_action_only_requeues_never_digitalizes_inline(self):
        errored = self._create_invoice()
        errored.write({"tfhka_digitalization_state": "error", "tfhka_digitalization_error": "boom"})

        with patch(GENERATE_DIGITAL_PATCH) as mock_generate:
            errored.action_tfhka_retry_digitalization()

        mock_generate.assert_not_called()
        self.assertEqual(errored.tfhka_digitalization_state, "queued")
        self.assertFalse(errored.tfhka_digitalization_error)

    def test_retry_action_preserves_original_queue_position(self):
        """A retried document must resume at its original place in the
        FIFO order, not move to the back behind documents queued while it
        sat in 'error' -- e.g. document #5 of 10 fails and gets retried:
        it must still be processed before #6-#10, not after them."""
        older = self._create_invoice()
        older._tfhka_enqueue_digitalization()
        original_queued_at = fields.Datetime.now() - timedelta(minutes=5)
        older.tfhka_queued_at = original_queued_at
        older.write({"tfhka_digitalization_state": "error", "tfhka_digitalization_error": "boom"})

        newer = self._create_invoice()
        newer._tfhka_enqueue_digitalization()

        older.action_tfhka_retry_digitalization()

        self.assertEqual(older.tfhka_digitalization_state, "queued")
        self.assertEqual(older.tfhka_queued_at, original_queued_at, "Retry must not reset the FIFO timestamp.")

        order = []

        def fake_generate(self):
            order.append(self.id)
            self.write({"is_digitalized": True})

        with patch(GENERATE_DIGITAL_PATCH, fake_generate):
            self.env["account.move"]._tfhka_cron_process_queue_multi(["account.move"])

        self.assertEqual(older.tfhka_digitalization_state, "success")
        self.assertEqual(newer.tfhka_digitalization_state, "success")
        self.assertEqual(order, [older.id, newer.id], "The retried document must be processed before the one queued after it.")

    def test_retry_action_ignores_documents_not_in_error(self):
        queued = self._create_invoice()
        queued._tfhka_enqueue_digitalization()
        stamp = queued.date_state

        with patch(GENERATE_DIGITAL_PATCH) as mock_generate:
            queued.action_tfhka_retry_digitalization()

        mock_generate.assert_not_called()
        self.assertEqual(queued.tfhka_digitalization_state, "queued")
        self.assertEqual(queued.date_state, stamp, "A no-op retry must not touch the document at all.")

    def test_action_generate_digital_only_enqueues_never_calls_tfhka_inline(self):
        inv = self._create_invoice()

        with patch(GENERATE_DIGITAL_PATCH) as mock_generate:
            inv.action_tfhka_generate_digital()

        mock_generate.assert_not_called()
        self.assertEqual(inv.tfhka_digitalization_state, "queued")

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
