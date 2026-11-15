import json
from datetime import timedelta
from unittest.mock import patch

from odoo import _, fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

GENERATE_DIGITAL_PATCH = "odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove.generate_document_digital"
RECOVER_STUCK_PATCH = "odoo.addons.l10n_ve_invoice_digital.models.account_move.AccountMove._tfhka_recover_stuck_processing"
BATCH_SIZE_PATCH = "odoo.addons.l10n_ve_invoice_digital.models.account_move.TFHKA_QUEUE_BATCH_SIZE"


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
            # l10n_ve_tax requires this for tax_totals, which some flows
            # (e.g. creating a second company, see
            # test_cron_process_queue_error_in_one_company_does_not_halt_another)
            # end up recomputing even on invoices with no taxes at all.
            "currency_foreign_id": self.env.ref("base.VEF").id,
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

    def test_process_digitalization_treats_silent_noop_as_error(self):
        # Fix bloqueante: generate_document_digital() puede retornar sin
        # excepcion y sin digitalizar nada (p.ej. tfhka.document.service
        # devuelve sin enviar cuando no logra determinar un tipo de
        # documento TFHKA). Eso nunca debe registrarse como 'success'.
        inv = self._create_invoice()
        inv._tfhka_enqueue_digitalization()

        with patch(GENERATE_DIGITAL_PATCH, lambda self: None):
            result = inv._tfhka_process_digitalization()

        self.assertFalse(result)
        self.assertEqual(inv.tfhka_digitalization_state, "error")
        self.assertFalse(inv.is_digitalized)

    def test_process_digitalization_rolls_back_partial_write_on_failure(self):
        # Hallazgo adicional de la ronda 3 de revision: sin savepoint, una
        # falla a medias dentro de generate_document_digital() (p.ej. TFHKA
        # responde 200 pero el payload no trae el campo esperado, ya con
        # is_digitalized=True escrito por tfhka.document.service) dejaba ese
        # write parcial comprometido junto al estado 'error' de abajo. Un
        # reintento manual entonces reenviaba un documento que TFHKA ya
        # habia recibido -- duplicado fiscal.
        inv = self._create_invoice()
        inv._tfhka_enqueue_digitalization()

        def fake_generate(self):
            self.write({"is_digitalized": True})
            raise UserError(_("boom after partial write"))

        with patch(GENERATE_DIGITAL_PATCH, fake_generate):
            result = inv._tfhka_process_digitalization()

        self.assertFalse(result)
        self.assertEqual(inv.tfhka_digitalization_state, "error")
        self.assertFalse(
            inv.is_digitalized,
            "el savepoint debe revertir el write parcial de is_digitalized",
        )

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

    def test_cron_process_queue_ignores_errored_document_that_was_cancelled(self):
        # Fix bloqueante: el lock por compania no excluia state='cancel'. Un
        # documento en 'error' que se cancela no tiene ninguna via de vuelta
        # a un estado resuelto -- un reintento no tiene sentido sobre un
        # asiento cancelado -- asi que sin este fix la cola de la compania
        # quedaba bloqueada para siempre.
        #
        # button_cancel() alcanza solo: en 17 ya resetea a draft primero si
        # hace falta (ver account_move.button_cancel en el core), y este
        # helper _create_invoice() deja el asiento en 'draft' de todas
        # formas (action_post() sin move_action_post_alert solo abre el
        # wizard de alerta, no postea -- ver l10n_ve_accountant.action_post).
        errored = self._create_invoice()
        errored.write({"tfhka_digitalization_state": "error", "tfhka_digitalization_error": "boom"})
        errored.button_cancel()

        queued = self._create_invoice()
        queued._tfhka_enqueue_digitalization()

        with patch(GENERATE_DIGITAL_PATCH, lambda self: self.write({"is_digitalized": True})):
            self.env["account.move"]._tfhka_cron_process_queue()

        self.assertEqual(
            queued.tfhka_digitalization_state, "success",
            "Un documento en error que ya fue cancelado no debe seguir bloqueando la cola.",
        )

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

    def test_cron_process_queue_error_in_one_company_does_not_halt_another(self):
        # Fix bloqueante: el halt-on-error es por compania -- un documento
        # en error de la Compania A no debe detener la cola de la Compania B.
        #
        # El documento de la otra compania se queda en 'draft' a proposito
        # (nunca se postea): este test solo verifica el scoping por
        # company_id de las busquedas del cron -- no necesita una compania
        # contable completa (plan de cuentas, impuestos, multi-moneda), y
        # postear ahi dispara maquinaria de facturacion VE no relacionada
        # con lo que se esta probando.
        errored = self._create_invoice()
        errored.write({"tfhka_digitalization_state": "error", "tfhka_digitalization_error": "boom"})

        other_company = self.env["res.company"].create({"name": "Otra Compania TFHKA Test"})
        other_seq = self.env["ir.sequence"].create(
            {"name": "Sec Test Other", "prefix": "OTH/", "padding": 4}
        )
        other_journal = self.env["account.journal"].create({
            "name": "Diario Digital Otra Compania",
            "code": "ODT",
            "type": "sale",
            "company_id": other_company.id,
            "sequence_id": other_seq.id,
        })
        other_partner = self.env["res.partner"].create({
            "name": "Cliente Otra Compania",
            "company_id": other_company.id,
        })
        other_invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "company_id": other_company.id,
            "partner_id": other_partner.id,
            "journal_id": other_journal.id,
            "invoice_date": fields.Date.today(),
        })
        other_invoice._tfhka_enqueue_digitalization()

        with patch(GENERATE_DIGITAL_PATCH, lambda self: self.write({"is_digitalized": True})):
            self.env["account.move"]._tfhka_cron_process_queue()

        self.assertEqual(
            errored.tfhka_digitalization_state, "error",
            "La compania con el error no debe verse afectada.",
        )
        self.assertEqual(
            other_invoice.tfhka_digitalization_state, "success",
            "El error de otra compania no debe detener esta cola.",
        )

    def test_cron_process_queue_continues_after_unrelated_exception_in_one_company(self):
        # Fix bloqueante (segunda ronda de revision): una excepcion NO
        # relacionada con TFHKA (p.ej. un error de infraestructura) al
        # procesar una compania no debe tumbar el tick completo -- las
        # demas compañias deben seguir procesandose.
        failing_company = self.company
        stuck_invoice = self._create_invoice()
        stuck_invoice._tfhka_enqueue_digitalization()

        other_company = self.env["res.company"].create({"name": "Otra Compania TFHKA Test 3"})
        other_seq = self.env["ir.sequence"].create(
            {"name": "Sec Test Other 3", "prefix": "OTH3/", "padding": 4}
        )
        other_journal = self.env["account.journal"].create({
            "name": "Diario Digital Otra Compania 3",
            "code": "ODT3",
            "type": "sale",
            "company_id": other_company.id,
            "sequence_id": other_seq.id,
        })
        other_partner = self.env["res.partner"].create({
            "name": "Cliente Otra Compania 3", "company_id": other_company.id,
        })
        other_invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "company_id": other_company.id,
            "partner_id": other_partner.id,
            "journal_id": other_journal.id,
            "invoice_date": fields.Date.today(),
        })
        other_invoice._tfhka_enqueue_digitalization()

        original_recover = type(self.env["account.move"])._tfhka_recover_stuck_processing

        def recover_or_raise(self_record, company):
            if company.id == failing_company.id:
                raise RuntimeError("simulated infra failure unrelated to TFHKA")
            return original_recover(self_record, company)

        with patch(RECOVER_STUCK_PATCH, recover_or_raise), \
             patch(GENERATE_DIGITAL_PATCH, lambda self: self.write({"is_digitalized": True})):
            self.env["account.move"]._tfhka_cron_process_queue()

        self.assertEqual(
            stuck_invoice.tfhka_digitalization_state, "queued",
            "La compania que lanzo la excepcion queda sin procesar este tick, pero no debe fallar el commit.",
        )
        self.assertEqual(
            other_invoice.tfhka_digitalization_state, "success",
            "La excepcion de una compania no debe impedir procesar la cola de otra.",
        )

    def test_cron_process_queue_caps_total_documents_shared_across_companies(self):
        # Fix bloqueante (segunda ronda de revision): TFHKA_QUEUE_BATCH_SIZE
        # es un presupuesto GLOBAL por tick, no un cupo independiente por
        # compania -- con el budget patcheado a 1 y dos companias con un
        # documento encolado cada una, a lo sumo 1 debe procesarse en total.
        inv = self._create_invoice()
        inv._tfhka_enqueue_digitalization()

        other_company = self.env["res.company"].create({"name": "Otra Compania TFHKA Test 4"})
        other_seq = self.env["ir.sequence"].create(
            {"name": "Sec Test Other 4", "prefix": "OTH4/", "padding": 4}
        )
        other_journal = self.env["account.journal"].create({
            "name": "Diario Digital Otra Compania 4",
            "code": "ODT4",
            "type": "sale",
            "company_id": other_company.id,
            "sequence_id": other_seq.id,
        })
        other_partner = self.env["res.partner"].create({
            "name": "Cliente Otra Compania 4", "company_id": other_company.id,
        })
        other_invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "company_id": other_company.id,
            "partner_id": other_partner.id,
            "journal_id": other_journal.id,
            "invoice_date": fields.Date.today(),
        })
        other_invoice._tfhka_enqueue_digitalization()

        with patch(BATCH_SIZE_PATCH, 1), \
             patch(GENERATE_DIGITAL_PATCH, lambda self: self.write({"is_digitalized": True})):
            self.env["account.move"]._tfhka_cron_process_queue()

        processed = (inv + other_invoice).filtered(
            lambda move: move.tfhka_digitalization_state == "success"
        )
        self.assertEqual(
            len(processed), 1,
            "El presupuesto de 1 documento debe repartirse entre companias, no aplicarse por compania.",
        )

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

    def test_retry_action_recovers_from_log_instead_of_resubmitting(self):
        """A failed attempt can still have reached TFHKA -- e.g. the HTTP
        response to /Emision was lost to a network timeout right after TFHKA
        had already processed the document. Reproduced directly at the state
        level (same end state a real interrupted response would leave: the
        document in 'error' with a success log already on record for its
        last attempt) rather than through a live HTTP failure, since under
        the test runner tfhka.api.log writes share the caller's cursor (see
        TfhkaApiClient._log_call) and would be rolled back by the savepoint
        in _tfhka_process_digitalization along with everything else -- unlike
        production, where that log survives on its own cursor precisely so
        this scenario can be told apart from a genuine failure."""
        inv = self._create_invoice()
        inv._tfhka_enqueue_digitalization()
        inv.write({
            "tfhka_digitalization_state": "error",
            "tfhka_digitalization_error": "Error connecting to the API: simulated timeout",
            "tfhka_last_attempt_at": fields.Datetime.now(),
        })
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
                    "encabezado": {"identificacionDocumento": {"numeroDocumento": "321"}},
                },
            }),
            "response_payload": json.dumps({"resultado": {"numeroControl": "00-00088888"}}),
        })

        with patch(GENERATE_DIGITAL_PATCH) as mock_generate:
            inv.action_tfhka_retry_digitalization()

        mock_generate.assert_not_called()
        self.assertEqual(inv.tfhka_digitalization_state, "success")
        self.assertTrue(inv.is_digitalized)
        self.assertEqual(inv.correlative, "00-00088888")

    def test_retry_action_requeues_blindly_when_last_attempt_not_recorded(self):
        """Documents that errored before tfhka_last_attempt_at existed never
        have it set -- must still behave like a plain requeue instead of
        erroring out on the log lookup."""
        inv = self._create_invoice()
        inv.write({"tfhka_digitalization_state": "error", "tfhka_digitalization_error": "boom"})

        inv.action_tfhka_retry_digitalization()

        self.assertEqual(inv.tfhka_digitalization_state, "queued")
        self.assertFalse(inv.is_digitalized)

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

        self.env["account.move"]._tfhka_recover_stuck_processing(self.company)

        self.assertEqual(inv.tfhka_digitalization_state, "error")
        self.assertTrue(inv.tfhka_digitalization_error)
        self.assertIn("TFHKA", inv.tfhka_digitalization_error)

    def test_recover_stuck_processing_within_grace_period_is_left_untouched(self):
        inv = self._create_invoice()
        inv.write({"tfhka_digitalization_state": "processing"})
        inv.write({"date_state": fields.Datetime.now() - timedelta(seconds=59)})

        resolved = self.env["account.move"]._tfhka_recover_stuck_processing(self.company)

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
        inv.write({"date_state": started_at, "tfhka_last_attempt_at": started_at})
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

        self.env["account.move"]._tfhka_recover_stuck_processing(self.company)

        self.assertEqual(inv.tfhka_digitalization_state, "success")
        self.assertTrue(inv.is_digitalized)
        self.assertEqual(inv.correlative, "00-00099999")

    def test_recover_stuck_processing_ignores_log_from_an_unrelated_endpoint(self):
        inv = self._create_invoice()
        started_at = fields.Datetime.now() - timedelta(minutes=2)
        inv.write({"tfhka_digitalization_state": "processing"})
        inv.write({"date_state": started_at, "tfhka_last_attempt_at": started_at})
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

        self.env["account.move"]._tfhka_recover_stuck_processing(self.company)

        self.assertEqual(inv.tfhka_digitalization_state, "error")

    def test_recover_stuck_processing_orders_oldest_first(self):
        old = self._create_invoice()
        old.write({"tfhka_digitalization_state": "processing"})
        old.write({"date_state": fields.Datetime.now() - timedelta(minutes=5)})
        fresh = self._create_invoice()
        fresh.write({"tfhka_digitalization_state": "processing"})

        resolved = self.env["account.move"]._tfhka_recover_stuck_processing(self.company)

        self.assertFalse(resolved)
        self.assertEqual(old.tfhka_digitalization_state, "error")
        self.assertEqual(fresh.tfhka_digitalization_state, "processing")

    def test_crons_are_registered_to_run_indefinitely(self):
        # Fix bloqueante: en Odoo 17 ir.cron.numbercall tiene default 1 --
        # sin numbercall=-1/doall=False el cron corre una sola vez y
        # _process_job lo desactiva (numbercall=0, active=False). Esto ya
        # paso una vez con el cron de la cola (quedaba inactivo tras su
        # primera corrida) y el mismo bug seguia sin corregir en el cron de
        # purga. Las pruebas que llaman a los metodos directamente (p.ej.
        # _tfhka_cron_process_queue()) nunca pasan por ir.cron y no lo
        # hubieran detectado -- este test lee el registro real.
        queue_cron = self.env.ref("l10n_ve_invoice_digital.ir_cron_tfhka_digitalization_queue")
        purge_cron = self.env.ref("l10n_ve_invoice_digital.ir_cron_purge_tfhka_api_log")

        for cron in (queue_cron, purge_cron):
            self.assertEqual(cron.numbercall, -1)
            self.assertFalse(cron.doall)
