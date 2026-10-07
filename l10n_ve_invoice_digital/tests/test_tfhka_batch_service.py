from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

REQUEST_PATCH = "odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.TfhkaApiClient._request"
GET_SERIES_PATCH = "odoo.addons.l10n_ve_invoice_digital.services.tfhka_document_service.TfhkaDocumentService._get_series"


def _mock_api(last_document_number=0):
    """Simula las respuestas de TFHKA para ultimo_documento/asignar_numeraciones,
    mismo estilo que ``test_account_move.py.mock_api``."""

    def _side_effect(company, endpoint_key, payload, *args, **kwargs):
        if endpoint_key == "ultimo_documento":
            return {"codigo": "200", "numeroDocumento": last_document_number}
        if endpoint_key == "asignar_numeraciones":
            detalle = payload["detalleAsignacion"][0]
            return {
                "codigo": "200",
                "mensaje": "Números de Control reservados exitosamente",
                "fechaAsignacion": "2026-09-15 03:24:40 PM",
                "rangosAsignados": [{
                    "asignado": "Nros. de Control desde el %s hasta %s"
                    % (detalle["numeroDocumentoInicio"], detalle["numeroDocumentoFin"]),
                    "global": "Nros. de Control desde el 00-00000001 hasta 00-00100000",
                }],
                "detallesReserva": [{
                    "numeroDocumentoInicio": int(detalle["numeroDocumentoInicio"]),
                    "numeroDocumentoFin": int(detalle["numeroDocumentoFin"]),
                    "serie": detalle["serie"],
                }],
            }
        return None

    return _side_effect


@tagged("post_install", "-at_install", "l10n_ve_invoice_digital", "tfhka_batch_service")
class TestTfhkaBatchService(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env.user.tz = "America/Caracas"
        self.company = self.env.ref("base.main_company")
        self.company.write({
            "invoice_digital_tfhka": True,
            # batch_invoicing_tfhka requiere digitalization_with_payment_tfhka
            # (ver res.config.settings: onchange + set_values).
            "digitalization_with_payment_tfhka": True,
            "batch_invoicing_tfhka": True,
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
        self.batch_service = self.env["tfhka.batch.service"]

    def _create_invoice(self, invoice_date=None, post=True):
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
            "invoice_date": invoice_date or fields.Date.today(),
            "invoice_line_ids": [(0, 0, {
                "product_id": prod.id,
                "quantity": 1,
                "price_unit": 100,
                "account_id": self.acc_income.id,
                "tax_ids": [Command.set([self.tax_iva16.id])],
            })],
        })
        if post:
            # l10n_ve_accountant.account_move.action_post() intercepta el
            # posteo de out_invoice/out_refund con un wizard de alerta salvo
            # que se pase este contexto -- mismo patrón que
            # test_account_move.py._create_invoice.
            inv.with_context(move_action_post_alert=True).action_post()
        return inv

    # ------------------------------------------------------------------
    # create_batch: caso feliz
    # ------------------------------------------------------------------

    @patch(REQUEST_PATCH)
    def test_create_batch_assigns_numbers_and_enqueues(self, mock_request):
        mock_request.side_effect = _mock_api(last_document_number=100)
        inv1 = self._create_invoice()
        inv2 = self._create_invoice()
        moves = inv1 + inv2

        result = self.batch_service.create_batch(moves)

        self.assertTrue(result)
        self.assertEqual(inv1.tfhka_batch_document_number, 101)
        self.assertEqual(inv2.tfhka_batch_document_number, 102)
        self.assertTrue(inv1.tfhka_batch_ref)
        self.assertEqual(inv1.tfhka_batch_ref, inv2.tfhka_batch_ref)
        self.assertEqual(inv1.tfhka_digitalization_state, "queued")
        self.assertEqual(inv2.tfhka_digitalization_state, "queued")

        assign_calls = [
            call for call in mock_request.call_args_list
            if call.args[1] == "asignar_numeraciones"
        ]
        self.assertEqual(len(assign_calls), 1)
        detalle = assign_calls[0].args[2]["detalleAsignacion"][0]
        self.assertEqual(detalle["numeroDocumentoInicio"], "101")
        self.assertEqual(detalle["numeroDocumentoFin"], "102")
        self.assertEqual(detalle["tipoDocumento"], "01")

    @patch(REQUEST_PATCH)
    def test_create_batch_queue_order_survives_out_of_order_confirmation(self, mock_request):
        # Caso real reproducido: inv_a se CREA como borrador antes que inv_b
        # (su id es menor), pero se CONFIRMA (action_post()) después -- ni la
        # fecha de factura (ambas de hoy, sin hora) ni el id reflejan el
        # orden real de confirmación. inv_b, al confirmarse primero, recibe
        # el sequence_number menor pese a tener un id mayor.
        mock_request.side_effect = _mock_api(last_document_number=0)
        inv_a = self._create_invoice(post=False)
        inv_b = self._create_invoice(post=False)
        self.assertLess(inv_a.id, inv_b.id)

        inv_b.with_context(move_action_post_alert=True).action_post()
        inv_a.with_context(move_action_post_alert=True).action_post()
        self.assertLess(inv_b.sequence_number, inv_a.sequence_number)

        self.batch_service.create_batch(inv_a + inv_b)

        # Orden de asignación: por sequence_number (orden real de
        # confirmación), así que inv_b recibe el primer número del lote
        # aunque su id sea mayor y se haya creado después.
        self.assertEqual(inv_b.tfhka_batch_document_number, 1)
        self.assertEqual(inv_a.tfhka_batch_document_number, 2)

        # La cola (tfhka_queued_at) debe respetar ese mismo orden -- antes del
        # fix de ordenamiento, el desempate por fecha+id habría asignado el
        # primer número a inv_a (id menor); antes del fix de tfhka_queued_at,
        # ambas habrían empatado (Datetime.now() trunca a segundos) y el cron
        # habría caído a "ORDER BY id asc", procesando inv_a primero pese a
        # haberse confirmado después.
        self.assertLess(inv_b.tfhka_queued_at, inv_a.tfhka_queued_at)

    def test_create_batch_returns_false_for_empty_recordset(self):
        self.assertFalse(self.batch_service.create_batch(self.env["account.move"]))

    def test_create_batch_rejects_when_company_batch_invoicing_disabled(self):
        self.company.batch_invoicing_tfhka = False
        inv = self._create_invoice()
        with self.assertRaises(UserError):
            self.batch_service.create_batch(inv)

    # ------------------------------------------------------------------
    # esLote + numeración forzada en el envío individual
    # ------------------------------------------------------------------

    @patch(REQUEST_PATCH)
    def test_es_lote_flag_reflects_batch_membership(self, mock_request):
        mock_request.side_effect = _mock_api(last_document_number=0)
        inv_in_batch = self._create_invoice()
        inv_standalone = self._create_invoice()

        self.batch_service.create_batch(inv_in_batch)

        doc_service = self.env["tfhka.document.service"]
        self.assertTrue(doc_service._prepare_additional_flags(inv_in_batch)["esLote"])
        self.assertFalse(doc_service._prepare_additional_flags(inv_standalone)["esLote"])

    @patch(REQUEST_PATCH)
    def test_send_document_uses_forced_batch_number(self, mock_request):
        mock_request.side_effect = _mock_api(last_document_number=500)
        inv = self._create_invoice()
        self.batch_service.create_batch(inv)
        self.assertEqual(inv.tfhka_batch_document_number, 501)

        # send_document empieza con query_numbering (consulta_numeraciones),
        # que exige un "numeraciones" con una entrada "NO APLICA" (comodín)
        # o de la serie real -- sin esto, query_numbering rechaza la serie
        # antes de llegar a emision, mismo criterio que
        # test_account_move.py.mock_api.
        def side_effect(company, endpoint_key, payload, *args, **kwargs):
            if endpoint_key == "consulta_numeraciones":
                return {
                    "codigo": "200",
                    "numeraciones": [
                        {"serie": "NO APLICA", "hasta": "100000", "correlativo": "1"},
                    ],
                }
            return {"codigo": "200", "resultado": {"numeroControl": "00-00000099"}}

        mock_request.side_effect = side_effect

        self.env["tfhka.document.service"].send_document(inv)

        emision_calls = [
            call for call in mock_request.call_args_list
            if call.args[1] == "emision"
        ]
        self.assertEqual(len(emision_calls), 1)
        sent_payload = emision_calls[0].args[2]
        numero = sent_payload["documentoElectronico"]["encabezado"]["identificacionDocumento"]["numeroDocumento"]
        self.assertEqual(numero, "501")
        self.assertTrue(
            sent_payload["documentoElectronico"]["encabezado"]["banderasAdicionales"]["esLote"]
        )

    # ------------------------------------------------------------------
    # Validaciones de elegibilidad
    # ------------------------------------------------------------------

    def test_create_batch_rejects_non_posted_invoice(self):
        inv = self._create_invoice()
        inv.button_draft()
        with self.assertRaises(UserError):
            self.batch_service.create_batch(inv)

    def test_create_batch_rejects_already_digitalized_invoice(self):
        inv = self._create_invoice()
        inv.write({"is_digitalized": True})
        with self.assertRaises(UserError):
            self.batch_service.create_batch(inv)

    def test_create_batch_rejects_already_queued_invoice(self):
        inv = self._create_invoice()
        inv._tfhka_enqueue_digitalization()
        with self.assertRaises(UserError):
            self.batch_service.create_batch(inv)

    # ------------------------------------------------------------------
    # Agrupación por serie + falla parcial en una selección multi-grupo
    # ------------------------------------------------------------------

    @patch(REQUEST_PATCH)
    @patch(GET_SERIES_PATCH)
    def test_create_batch_groups_by_series_and_partial_failure_keeps_first_group(
        self, mock_get_series, mock_request
    ):
        inv_a = self._create_invoice()
        inv_b = self._create_invoice()
        mock_get_series.side_effect = lambda invoice: "A" if invoice.id == inv_a.id else "B"

        # La falla se ata a la serie "B" (no a un contador global de
        # llamadas): más robusto que depender de que sea exactamente la
        # segunda llamada a asignar_numeraciones en todo el test, que un
        # request de más (de cualquier origen) desalinearía.
        def side_effect(company, endpoint_key, payload, *args, **kwargs):
            if endpoint_key == "ultimo_documento":
                return {"codigo": "200", "numeroDocumento": 0}
            if endpoint_key == "asignar_numeraciones":
                detalle = payload["detalleAsignacion"][0]
                if detalle["serie"] == "B":
                    raise UserError("Rango agotado")
                return {"codigo": "200", "rangosAsignados": [{}], "detallesReserva": [{}]}
            return None

        mock_request.side_effect = side_effect

        with self.assertRaises(UserError):
            self.batch_service.create_batch(inv_a + inv_b)

        # La durabilidad real de _tfhka_commit() (que el grupo "A" quede
        # confirmado pese al fallo del grupo "B") es una garantía de
        # PRODUCCIÓN -- _tfhka_commit() se documenta a sí mismo como no-op
        # bajo test_enable, precisamente porque el framework de tests de
        # Odoo revierte todo lo no confirmado apenas una UserError se
        # propaga (verificado: el campo queda escrito y confirmado por una
        # lectura fresca desde la DB *antes* de que la excepción se
        # propague, y ya no está una vez que sale de create_batch()). Lo que
        # sí es determinístico aquí, y lo que se verifica, es el ORDEN y
        # CONTENIDO real de las llamadas: el grupo "A" se reserva completo
        # (con el rango correcto) antes de que el grupo "B" falle.
        assign_calls = [
            call for call in mock_request.call_args_list
            if call.args[1] == "asignar_numeraciones"
        ]
        self.assertEqual(len(assign_calls), 2)
        first_detail = assign_calls[0].args[2]["detalleAsignacion"][0]
        self.assertEqual(first_detail["serie"], "A")
        self.assertEqual(first_detail["numeroDocumentoInicio"], "1")
        self.assertEqual(first_detail["numeroDocumentoFin"], "1")
        second_detail = assign_calls[1].args[2]["detalleAsignacion"][0]
        self.assertEqual(second_detail["serie"], "B")
