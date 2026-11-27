import logging
from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestReportZ(TransactionCase):
    """TI-14871: report_z debe usar el contador de la maquina tal cual (sin +1)
    y solo aplicar +1 en el fallback historico. Ademas, la busqueda de facturas
    pendientes debe acotarse por mf_invoice_number (secuencia real de la
    maquina fiscal) al ultimo Z cerrado para ese serial."""

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
        self.serial = f"SERIAL-TEST-{self._testMethodName}"

    def _create_move(self, mf_reportz=False, mf_serial=None, mf_invoice_number=False):
        move = self.move_model.create(
            {
                "partner_id": self.partner.id,
                "move_type": "out_invoice",
                "invoice_date": date.today(),
                "date": date.today(),
                "journal_id": self.journal.id,
                "mf_serial": mf_serial or self.serial,
                "mf_reportz": mf_reportz,
                "mf_invoice_number": mf_invoice_number,
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
        self._create_move(mf_reportz="50", mf_invoice_number="100")
        pending = self._create_move(mf_reportz=False, mf_invoice_number="101")

        result = self.move_model.report_z(self.serial, self._response(daily_closure_counter=None))

        self.assertEqual(result, 51)
        self.assertEqual(pending.mf_reportz, "51")

    def test_mf_invoice_number_boundary_excludes_records_before_last_z(self):
        """Facturas viejas con mf_reportz=False y mf_invoice_number ANTERIOR al
        ultimo Z cerrado no deben tocarse: solo las impresas despues (numero de
        secuencia mayor) entran en el siguiente Z."""
        old_orphan = self._create_move(mf_reportz=False, mf_invoice_number="50")
        self._create_move(mf_reportz="50", mf_invoice_number="100")
        new_pending = self._create_move(mf_reportz=False, mf_invoice_number="101")

        result = self.move_model.report_z(self.serial, self._response(daily_closure_counter=108))

        self.assertEqual(result, 108)
        self.assertEqual(new_pending.mf_reportz, "108")
        self.assertEqual(
            old_orphan.mf_reportz,
            False,
            "El registro huerfano anterior al ultimo Z no debe modificarse",
        )

    def test_mf_invoice_number_boundary_ignores_invoice_date(self):
        """Una factura backdateada (invoice_date de ayer) cargada HOY, despues
        del ultimo Z, debe incluirse en el Z actual: lo que importa es el
        numero de secuencia real de la maquina, no la fecha contable."""
        self._create_move(mf_reportz="50", mf_invoice_number="100")
        from datetime import timedelta

        yesterday = date.today() - timedelta(days=1)
        backdated_pending = self.move_model.create(
            {
                "partner_id": self.partner.id,
                "move_type": "out_invoice",
                "invoice_date": yesterday,
                "date": yesterday,
                "journal_id": self.journal.id,
                "mf_serial": self.serial,
                "mf_reportz": False,
                "mf_invoice_number": "101",
                "company_id": self.company.id,
                "currency_id": self.company.currency_id.id,
            }
        )
        backdated_pending.action_post()

        result = self.move_model.report_z(self.serial, self._response(daily_closure_counter=108))

        self.assertEqual(result, 108)
        self.assertEqual(backdated_pending.mf_reportz, "108")

    def test_non_numeric_mf_invoice_number_on_last_z_includes_all_pending(self):
        """Si el ultimo Z cerrado quedo con mf_invoice_number no numerico (dato
        historico corrupto), no debe reventar report_z: sin limite conocido, las
        pendientes con numero valido se incluyen igual (mismo criterio que si no
        hubiera Z previo)."""
        self._create_move(mf_reportz="50", mf_invoice_number="ERROR")
        pending = self._create_move(mf_reportz=False, mf_invoice_number="101")

        result = self.move_model.report_z(self.serial, self._response(daily_closure_counter=108))

        self.assertEqual(result, 108)
        self.assertEqual(pending.mf_reportz, "108")

    def test_invalid_response_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            self.move_model.report_z(self.serial, self._response(valid=False))

    def test_get_last_z_number_orders_numerically_not_lexicographically(self):
        """mf_reportz es Char: "19" debe considerarse mas reciente que "9",
        no al reves como ordenaria un sort de texto ("9" > "19" alfabeticamente)."""
        self._create_move(mf_reportz="9")
        self._create_move(mf_reportz="19")

        self.assertEqual(self.move_model._get_last_z_number(self.serial), 19)

    def test_max_mf_invoice_number_for_z_picks_highest_among_tied_moves(self):
        """Varias facturas del mismo cierre comparten mf_reportz: el limite para
        el siguiente Z debe tomar la de mayor mf_invoice_number entre todas
        ellas, no una cualquiera del grupo."""
        self._create_move(mf_reportz="50", mf_invoice_number="98")
        self._create_move(mf_reportz="50", mf_invoice_number="100")
        self._create_move(mf_reportz="50", mf_invoice_number="99")
        pending = self._create_move(mf_reportz=False, mf_invoice_number="101")

        result = self.move_model.report_z(self.serial, self._response(daily_closure_counter=108))

        self.assertEqual(result, 108)
        self.assertEqual(pending.mf_reportz, "108")

    def test_pending_with_non_numeric_invoice_number_is_excluded(self):
        """Una factura pendiente con mf_invoice_number corrupto no debe
        asignarsele mf_reportz automaticamente: no hay forma de saber si va
        antes o despues del ultimo Z, asi que se deja huerfana para revision
        manual en vez de arriesgar duplicar un cierre."""
        self._create_move(mf_reportz="50", mf_invoice_number="100")
        broken = self._create_move(mf_reportz=False, mf_invoice_number="ERROR")

        self.move_model.report_z(self.serial, self._response(daily_closure_counter=108))

        self.assertEqual(broken.mf_reportz, False)

    def test_pending_with_non_numeric_invoice_number_excluded_without_previous_z(self):
        """Sin ningun Z previo para el serial, una pendiente con mf_invoice_number
        corrupto tampoco debe marcarse: la falta de limite no distingue si es el
        primer cierre o si el historico esta corrupto, asi que el criterio es el
        mismo en ambos casos."""
        broken = self._create_move(mf_reportz=False, mf_invoice_number="ERROR")
        pending = self._create_move(mf_reportz=False, mf_invoice_number="1")

        result = self.move_model.report_z(self.serial, self._response(daily_closure_counter=108))

        self.assertEqual(result, 108)
        self.assertEqual(pending.mf_reportz, "108")
        self.assertEqual(broken.mf_reportz, False)
