# -*- coding: utf-8 -*-
from datetime import date
from unittest.mock import MagicMock, patch

from odoo.tests import TransactionCase, tagged


class _FakeRecordset(list):
    """Simula lo minimo que report_z (pos_mf) necesita de un recordset real:
    iterable, .filtered() para el acotamiento por mf_invoice_number, y
    .ids (para el log)."""

    @property
    def ids(self):
        return list(range(1, len(self) + 1))

    def filtered(self, func):
        return _FakeRecordset([item for item in self if func(item)])


@tagged("post_install", "-at_install", "l10n_ve_pos_mf")
class TestAccountMove(TransactionCase):
    """TI-14871: la version pos_mf de account_move.report_z debe reusar el valor
    ya resuelto por l10n_ve_iot_mf (res) sin volver a sumarle 1, tanto si vino
    directo de la maquina como si vino del fallback, y acotar las pos.order
    pendientes por mf_invoice_number (no create_date ni invoice_date)."""

    def setUp(self):
        super().setUp()
        self.move_model = self.env["account.move"]
        self.company = self.env.company
        self.partner = self.env["res.partner"].create({"name": "Test Partner Z POS"})
        self.journal = self.env["account.journal"].create(
            {
                "name": "Test Journal Z POS",
                "code": "TJZP",
                "type": "sale",
                "company_id": self.company.id,
            }
        )
        self.serial = f"SERIAL-TEST-POS-{self._testMethodName}"

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

    def _response(self, daily_closure_counter=None, registered_machine_number=None):
        data = {"_registeredMachineNumber": registered_machine_number or self.serial}
        if daily_closure_counter is not None:
            data["_dailyClosureCounter"] = daily_closure_counter
        return {"valid": True, "data": data}

    def test_direct_counter_applied_to_pos_order_without_extra_plus_one(self):
        """res=108 (lectura directa) debe escribirse tal cual en pos.order.mf_reportz,
        no 109."""
        self._create_move(mf_reportz=False)
        pending_order = MagicMock()
        pending_order.mf_reportz = False
        pending_order.mf_invoice_number = "1"

        with patch.object(
            type(self.move_model), "_get_last_z_order_number", return_value=None
        ), patch.object(
            type(self.env["pos.order"]), "search", return_value=_FakeRecordset([pending_order])
        ):
            result = self.move_model.report_z(self.serial, self._response(daily_closure_counter=108))

        self.assertEqual(result, 108)
        pending_order.write.assert_called_once_with({"mf_reportz": 108})

    def test_fallback_value_applied_to_pos_order_without_extra_plus_one(self):
        """Cuando report_z cae al fallback (sin contador de la maquina), res ya
        trae el +1 aplicado una sola vez; pos_mf no debe sumarle otro +1."""
        self._create_move(mf_reportz="20")
        self._create_move(mf_reportz=False)
        pending_order = MagicMock()
        pending_order.mf_reportz = False
        pending_order.mf_invoice_number = "1"

        with patch.object(
            type(self.move_model), "_get_last_z_order_number", return_value=None
        ), patch.object(
            type(self.env["pos.order"]), "search", return_value=_FakeRecordset([pending_order])
        ):
            result = self.move_model.report_z(self.serial, self._response(daily_closure_counter=None))

        self.assertEqual(result, 21)
        pending_order.write.assert_called_once_with({"mf_reportz": 21})

    def test_pos_order_filtered_by_mf_invoice_number_after_last_z(self):
        """Las pos.order pendientes se filtran (en Python, via .filtered()) por
        mf_invoice_number > el del ultimo cierre de ese serial — no por
        create_date ni invoice_date."""
        self._create_move(mf_reportz=False)

        old_order = MagicMock()
        old_order.mf_invoice_number = "50"
        new_order = MagicMock()
        new_order.mf_invoice_number = "101"

        with patch.object(
            type(self.move_model), "_get_last_z_order_number", return_value=50
        ), patch.object(
            type(self.move_model), "_max_mf_invoice_number_for_order_z", return_value=100
        ), patch.object(
            type(self.env["pos.order"]), "search", return_value=_FakeRecordset([old_order, new_order])
        ):
            self.move_model.report_z(self.serial, self._response(daily_closure_counter=108))

        old_order.write.assert_not_called()
        new_order.write.assert_called_once_with({"mf_reportz": 108})

    def test_non_numeric_mf_invoice_number_on_last_z_includes_all_pending(self):
        """Si el ultimo cierre quedo con mf_invoice_number no numerico (dato
        historico corrupto) en TODAS sus ordenes, no debe reventar report_z:
        se incluyen todas las pendientes, igual que si no hubiera Z previo."""
        self._create_move(mf_reportz=False)

        pending_order = MagicMock()
        pending_order.mf_reportz = False
        pending_order.mf_invoice_number = "1"

        with patch.object(
            type(self.move_model), "_get_last_z_order_number", return_value=50
        ), patch.object(
            type(self.move_model), "_max_mf_invoice_number_for_order_z", return_value=None
        ), patch.object(
            type(self.env["pos.order"]), "search", return_value=_FakeRecordset([pending_order])
        ):
            result = self.move_model.report_z(self.serial, self._response(daily_closure_counter=108))

        self.assertEqual(result, 108)
        pending_order.write.assert_called_once_with({"mf_reportz": 108})

    def test_pending_with_non_numeric_invoice_number_is_excluded(self):
        """Una pos.order pendiente con mf_invoice_number corrupto no debe
        recibir mf_reportz automaticamente, aunque el resto de las pendientes
        si se procesen con normalidad."""
        self._create_move(mf_reportz=False)

        broken_order = MagicMock()
        broken_order.mf_invoice_number = "ERROR"
        new_order = MagicMock()
        new_order.mf_invoice_number = "101"

        with patch.object(
            type(self.move_model), "_get_last_z_order_number", return_value=50
        ), patch.object(
            type(self.move_model), "_max_mf_invoice_number_for_order_z", return_value=100
        ), patch.object(
            type(self.env["pos.order"]), "search", return_value=_FakeRecordset([broken_order, new_order])
        ):
            self.move_model.report_z(self.serial, self._response(daily_closure_counter=108))

        broken_order.write.assert_not_called()
        new_order.write.assert_called_once_with({"mf_reportz": 108})

    def test_pending_with_non_numeric_invoice_number_excluded_without_previous_z(self):
        """Sin ningun Z previo para el serial, una pos.order pendiente con
        mf_invoice_number corrupto tampoco debe marcarse: mismo criterio que
        cuando el historico esta corrupto."""
        self._create_move(mf_reportz=False)

        broken_order = MagicMock()
        broken_order.mf_invoice_number = "ERROR"
        new_order = MagicMock()
        new_order.mf_invoice_number = "1"

        with patch.object(
            type(self.move_model), "_get_last_z_order_number", return_value=None
        ), patch.object(
            type(self.env["pos.order"]), "search", return_value=_FakeRecordset([broken_order, new_order])
        ):
            result = self.move_model.report_z(self.serial, self._response(daily_closure_counter=108))

        self.assertEqual(result, 108)
        broken_order.write.assert_not_called()
        new_order.write.assert_called_once_with({"mf_reportz": 108})

    def test_get_last_z_order_number_parses_sql_result_as_integer(self):
        """La logica de "mayor mf_reportz numerico" vive en SQL (CASE + regex,
        igual criterio que _get_last_z_number en l10n_ve_iot_mf, cubierto ahi
        con datos reales); aca solo confirmamos que el metodo devuelve tal
        cual el entero que la base calculo, sin transformarlo."""
        with patch.object(type(self.env.cr), "execute") as execute_mock, patch.object(
            self.env.cr, "fetchone", return_value=(19,)
        ):
            result = self.move_model._get_last_z_order_number(self.serial)

        execute_mock.assert_called_once()
        query, params = execute_mock.call_args[0]
        self.assertIn("pos_order", query)
        self.assertIn("fiscal_machine", query)
        self.assertIn("company_id", query)
        self.assertEqual(params, (self.serial, self.company.id))
        self.assertEqual(result, 19)

    def test_get_last_z_order_number_query_runs_against_real_table(self):
        """Sin mockear el cursor: si la tabla o alguna columna del SQL
        estuviera mal escrita, esto revienta en vez de pasar en silencio."""
        result = self.move_model._get_last_z_order_number(self.serial)

        self.assertIsNone(result)
