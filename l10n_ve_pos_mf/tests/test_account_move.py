# -*- coding: utf-8 -*-
from datetime import date
from unittest.mock import MagicMock, patch

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_pos_mf")
class TestAccountMove(TransactionCase):
    """TI-14871: la version pos_mf de account_move.report_z debe reusar el valor
    ya resuelto por l10n_ve_iot_mf (res) sin volver a sumarle 1, tanto si vino
    directo de la maquina como si vino del fallback."""

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
        # Serial unico por test para no depender de datos de otros metodos
        # que compartan la misma transaccion.
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

        with patch.object(type(self.env["pos.order"]), "search", return_value=[pending_order]):
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

        with patch.object(type(self.env["pos.order"]), "search", return_value=[pending_order]):
            result = self.move_model.report_z(self.serial, self._response(daily_closure_counter=None))

        self.assertEqual(result, 21)
        pending_order.write.assert_called_once_with({"mf_reportz": 21})
