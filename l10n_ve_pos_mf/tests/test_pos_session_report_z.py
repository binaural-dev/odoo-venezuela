# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_pos_mf")
class TestPosSessionReportZ(TransactionCase):
    """Registro del Reporte Z al cerrar la sesión (ticket 16520)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env["pos.config"].create({"name": "Caja MF test"})
        cls.session = cls.env["pos.session"].create({"config_id": cls.config.id})

    def _value(self, counter, serial="Z7C7048697"):
        return {
            "valid": True,
            "data": {"_registeredMachineNumber": serial, "_dailyClosureCounter": counter},
        }

    def test_01_report_z_is_the_printed_z_not_the_next(self):
        """El S1 leído tras el Z ya trae el número del Z impreso: no se suma 1."""
        self.session.set_report_z(self._value(21))
        self.assertEqual(self.session.report_z, "21")
        self.assertTrue(self.session.mf_z_printed)

    def test_02_serial_is_stored_on_session_and_config(self):
        self.session.set_report_z(self._value(21))
        self.assertEqual(self.session.serial_machine, "Z7C7048697")
        self.assertEqual(self.config.serial_machine, "Z7C7048697")

    def test_03_placeholder_serial_is_ignored(self):
        self.session.set_report_z(self._value(21, serial="TFHKA-LOCAL"))
        self.assertEqual(self.session.report_z, "21")
        self.assertFalse(self.session.serial_machine)

    def test_04_invalid_counter_raises(self):
        for counter in (None, "abc", 0):
            with self.assertRaises(UserError):
                self.session.set_report_z(self._value(counter))

    def test_05_close_state_flags(self):
        state = self.session.get_mf_close_state()
        self.assertFalse(state["report_z"])
        self.assertFalse(state["mf_z_printed"])

        self.session.mark_mf_z_printed()
        state = self.session.get_mf_close_state()
        self.assertTrue(state["mf_z_printed"])
        self.assertFalse(state["report_z"])
