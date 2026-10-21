"""Convención de la tasa en el asiento de pago del PdV con IGTF (tarea 83148, H18).

``pos.payment._create_payment_moves`` se reimplementa aquí sin ``super()``, así
que repite el estampado de la tasa de ``l10n_ve_pos``: ``foreign_inverse_rate``
= multiplicador compañía → alterna del pago y ``foreign_rate`` = su inverso
(la pareja de ``l10n_ve_rate`` ``compute_rate``), con ``manually_set_rate``.
"""

from odoo.tests import tagged

from odoo.addons.l10n_ve_pos.tests.test_pos_session_accounting_common import (
    TestPosSessionAccountingBase,
)

RATE = 36.5


@tagged("post_install", "-at_install", "l10n_ve_pos_igtf")
class TestPosIgtfPaymentMoveRate(TestPosSessionAccountingBase):
    def test_payment_move_rate_convention(self):
        session = self.env["pos.session"].create(
            {
                "config_id": self.config.id,
                "user_id": self.env.ref("base.user_admin").id,
            }
        )
        order = self._create_paid_order(
            session, method=self.combined_bank_method, foreign_rate=RATE, invoiced=True
        )
        payment = order.payment_ids

        move = payment._create_payment_moves()

        self.assertEqual(len(move), 1)
        self.assertAlmostEqual(move.foreign_inverse_rate, RATE, places=12)
        # foreign_rate tiene la precisión "Tasa" (6 decimales).
        self.assertAlmostEqual(move.foreign_rate, 1 / RATE, places=6)
        self.assertTrue(move.manually_set_rate)
