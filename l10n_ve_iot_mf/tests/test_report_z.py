# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "l10n_ve_iot_mf")
class TestReportZ(TransactionCase):
    """Regresión del ticket 13283: el listener del IoT puede resolver con un
    evento válido que todavía no trae "data" (ACK del comando, antes de que
    la impresora termine el Z físico). report_z no debe reventar en ese caso
    y su retorno debe ser numérico (l10n_ve_pos_mf hace int(...) + 1)."""

    def _report_z(self, response):
        return self.env["account.move"].report_z("Z1M2AQ3", response)

    def test_01_valid_response_without_data_does_not_crash(self):
        # Antes: data quedaba en False y data.get(...) reventaba con
        # AttributeError: 'bool' object has no attribute 'get'.
        result = self._report_z({"valid": True, "message": "Comando enviado"})
        self.assertEqual(result, 0, "Sin data ni históricos, el Z recuperado es 0")

    def test_02_invalid_response_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            self._report_z({"valid": False, "message": "Impresora sin papel"})

    def test_03_return_value_is_numeric_for_pos_mf_contract(self):
        # Antes: return response (dict) → int(dict) + 1 en l10n_ve_pos_mf
        # con órdenes POS pendientes de reportar.
        result = self._report_z(
            {"valid": True, "data": {"_dailyClosureCounter": 7}}
        )
        self.assertEqual(int(result) + 1, 8)
