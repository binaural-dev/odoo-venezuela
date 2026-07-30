# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo import _
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_pos_mf")
class TestPosOrderDryRun(TransactionCase):
    """Unit tests del helper de validación dry-run del POS (Odoo 19).

    En 19 el dry-run envuelve ``sync_from_ui`` en un SAVEPOINT con ROLLBACK
    incondicional. Ya no hay secuencias de pos.config que restaurar (la
    referencia del pedido se deriva del uuid).
    """

    def setUp(self):
        super().setUp()
        self.pos_order_model = self.env["pos.order"]

    def test_01_validate_order_dry_run_returns_true(self):
        """Devuelve True cuando la validación dry-run completa sin errores."""
        orders = [{"name": "Test Order", "session_id": 1, "state": "paid"}]

        with patch.object(
            self.pos_order_model.__class__, "sync_from_ui", return_value=None
        ) as sync_mock:
            result = self.pos_order_model.validate_order_dry_run(orders)

        sync_mock.assert_called_once_with(orders)
        self.assertTrue(result)

    def test_02_validate_order_dry_run_propagates_error_and_rolls_back(self):
        """Propaga la excepción de sync_from_ui y revierte los cambios."""
        orders = [{"name": "Test Order", "session_id": 1, "state": "paid"}]

        def sync_side_effect(_orders):
            # Simula escritura colateral que debe revertirse con el rollback
            self.env["res.partner"].create({"name": "MF Dry Run Partner"})
            raise UserError(_("Simulated failure"))

        with patch.object(
            self.pos_order_model.__class__, "sync_from_ui", side_effect=sync_side_effect
        ):
            with self.assertRaises(UserError):
                self.pos_order_model.validate_order_dry_run(orders)

        self.assertFalse(
            self.env["res.partner"].search([("name", "=", "MF Dry Run Partner")]),
            "El rollback del dry-run no revirtió los cambios tras el error.",
        )

    def test_03_validate_order_dry_run_rolls_back_on_success(self):
        """Incluso en éxito, el dry-run NO debe persistir nada."""
        orders = [{"name": "Test Order", "session_id": 1, "state": "paid"}]

        def sync_side_effect_success(_orders):
            self.env["res.partner"].create({"name": "MF Dry Run Partner OK"})
            return {}

        with patch.object(
            self.pos_order_model.__class__,
            "sync_from_ui",
            side_effect=sync_side_effect_success,
        ):
            result = self.pos_order_model.validate_order_dry_run(orders)

        self.assertTrue(result)
        self.assertFalse(
            self.env["res.partner"].search([("name", "=", "MF Dry Run Partner OK")]),
            "El dry-run exitoso persistió cambios que debía revertir.",
        )
