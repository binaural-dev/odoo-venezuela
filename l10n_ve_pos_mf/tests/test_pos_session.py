# -*- coding: utf-8 -*-
from unittest.mock import MagicMock

from odoo.tests import TransactionCase, tagged

from odoo.addons.l10n_ve_pos_mf.models.pos_session import PosSession


@tagged("post_install", "-at_install", "l10n_ve_pos_mf")
class TestPosSession(TransactionCase):
    """TI-14871: set_report_z lee _dailyClosureCounter directo del dispositivo
    (fuera del flujo de account_move.report_z) y no debe aplicarle +1."""

    def test_set_report_z_writes_raw_counter_without_plus_one(self):
        fake_self = MagicMock()
        values = {"data": {"_dailyClosureCounter": 108}}

        PosSession.set_report_z(fake_self, values)

        fake_self.write.assert_called_once_with({"report_z": 108})
