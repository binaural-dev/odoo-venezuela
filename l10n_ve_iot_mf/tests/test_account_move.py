import logging
from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestReportZ(TransactionCase):
    """TI-14871: report_z debe usar el contador de la maquina tal cual (sin +1)
    y solo aplicar +1 en el fallback historico."""

    def setUp(self):
        super().setUp()
        self.move_model = self.env["account.move"]
        self.company = self.env.company
        self.partner = self.env["res.partner"].create({"name": "Test Partner Z"})
        self.journal = self.env["account.journal"].create(
            {
                "name": "Test Journal Z",
                "code": "TJZ",
                "type": "sale",
                "company_id": self.company.id,
            }
        )
        # Serial unico por test: evita que facturas de otros metodos de esta
        # misma clase (comparten transaccion/serial) contaminen la busqueda
        # de "ultimo Z".
        self.serial = f"SERIAL-TEST-{self._testMethodName}"

    def _create_move(self, mf_reportz=False, mf_serial=None):
        move = self.move_model.create(
            {
                "partner_id": self.partner.id,
                "move_type": "out_invoice",
                "invoice_date": date.today(),
                "date": date.today(),
                "journal_id": self.journal.id,
                "mf_serial": mf_serial or self.serial,
                "mf_reportz": mf_reportz,
                "company_id": self.company.id,
                "currency_id": self.company.currency_id.id,
            }
        )
        move.action_post()
        return move

    def _response(self, daily_closure_counter=None, registered_machine_number=None, valid=True):
        data = {"_registeredMachineNumber": registered_machine_number or self.serial}
        if daily_closure_counter is not None:
            data["_dailyClosureCounter"] = daily_closure_counter
        return {"valid": valid, "data": data, "message": "error simulado"}

    def test_direct_counter_used_as_is_without_plus_one(self):
        """Con lectura directa de la maquina, el valor se asigna tal cual (sin +1)."""
        pending = self._create_move(mf_reportz=False)

        result = self.move_model.report_z(self.serial, self._response(daily_closure_counter=108))

        self.assertEqual(result, 108)
        self.assertEqual(pending.mf_reportz, "108")

    def test_fallback_without_previous_z_returns_one(self):
        """Sin Z previo y sin contador de la maquina, el fallback devuelve 0 y se
        le suma 1 (primer cierre = 1)."""
        pending = self._create_move(mf_reportz=False)

        result = self.move_model.report_z(self.serial, self._response(daily_closure_counter=None))

        self.assertEqual(result, 1)
        self.assertEqual(pending.mf_reportz, "1")

    def test_fallback_with_previous_z_adds_one(self):
        """Sin contador de la maquina, el fallback proyecta ultimo_mf_reportz + 1."""
        self._create_move(mf_reportz="50")
        pending = self._create_move(mf_reportz=False)

        result = self.move_model.report_z(self.serial, self._response(daily_closure_counter=None))

        self.assertEqual(result, 51)
        self.assertEqual(pending.mf_reportz, "51")

    def test_invalid_response_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            self.move_model.report_z(self.serial, self._response(valid=False))

    def test_get_z_and_add_one_without_previous_moves(self):
        self.assertEqual(self.move_model._get_z_and_add_one(self.serial), 0)

    def test_get_z_and_add_one_with_previous_moves(self):
        self._create_move(mf_reportz="7")
        self.assertEqual(self.move_model._get_z_and_add_one(self.serial), "7")
