# -*- coding: utf-8 -*-
from unittest.mock import patch, MagicMock

from odoo.tests import TransactionCase, tagged
from odoo import fields
from odoo.exceptions import UserError

@tagged('post_install', '-at_install', 'l10n_ve_pos_mf')
class TestPosOrderDryRun(TransactionCase):
    """Unit tests for the POS dry-run validation helper."""

    def setUp(self):
        super().setUp()
        self.pos_order_model = self.env['pos.order']
        self.sequence = self.env['ir.sequence'].search([('code', '=', 'pos.order')], limit=1)
        if not self.sequence:
            self.sequence = self.env['ir.sequence'].create({
                'name': 'POS Order Sequence',
                'code': 'pos.order',
                'prefix': 'POS',
                'padding': 5,
                'number_next_actual': 1,
            })

        self.invoice_sequence = self.env['ir.sequence'].search([('code', '=', 'account.move')], limit=1)
        if not self.invoice_sequence:
            self.invoice_sequence = self.env['ir.sequence'].create({
                'name': 'Invoice Sequence',
                'code': 'account.move',
                'prefix': 'INV/',
                'padding': 5,
                'number_next_actual': 500,
            })

    def test_01_validate_order_dry_run_returns_true(self):
        """Returns True when dry-run order validation completes without errors."""
        orders = [{'data': {'name': 'Test Order', 'pos_session_id': 1}}]

        session_mock = MagicMock()
        session_mock.config_id.sequence_id = self.sequence

        with patch.object(type(self.env['pos.session']), 'browse', return_value=session_mock):
            with patch.object(self.pos_order_model.__class__, 'create_from_ui', return_value=None) as create_from_ui_mock:
                result = self.pos_order_model.validate_order_dry_run(orders)

        create_from_ui_mock.assert_called_once_with(orders)
        self.assertTrue(result)

    def test_02_validate_order_dry_run_rolls_back_sequence_on_error(self):
        """Restores sequence counter when an exception occurs during dry-run validation."""
        orders = [{'data': {'name': 'Test Order', 'pos_session_id': 1}}]
        original_next = self.sequence.number_next_actual

        def create_from_ui_side_effect(_orders):
            self.sequence.write({'number_next_actual': self.sequence.number_next_actual + 1})
            raise UserError('Simulated failure')

        session_mock = MagicMock()
        session_mock.config_id.sequence_id = self.sequence

        with patch.object(type(self.env['pos.session']), 'browse', return_value=session_mock):
            with patch.object(self.pos_order_model.__class__, 'create_from_ui', side_effect=create_from_ui_side_effect):
                with self.assertRaises(UserError):
                    self.pos_order_model.validate_order_dry_run(orders)

        self.sequence = self.env['ir.sequence'].browse(self.sequence.id)
        self.assertEqual(self.sequence.number_next_actual, original_next)

    def test_03_validate_order_dry_run_restores_invoice_sequence_on_success(self):
        """Ensures format/POS sequence is restored when simulation succeeds."""
        orders = [{'data': {
            'name': 'Test Order Invoiced', 
            'to_invoice': True,
            'pos_session_id': 1
        }}]
        original_next = self.sequence.number_next_actual

        def create_from_ui_side_effect_success(_orders):
            self.sequence.write({'number_next_actual': self.sequence.number_next_actual + 1})
            return []

        session_mock = MagicMock()
        session_mock.config_id.sequence_id = self.sequence

        with patch.object(type(self.env['pos.session']), 'browse', return_value=session_mock):
            with patch.object(self.pos_order_model.__class__, 'create_from_ui', side_effect=create_from_ui_side_effect_success):
                result = self.pos_order_model.validate_order_dry_run(orders)

        self.assertTrue(result)
        self.sequence = self.env['ir.sequence'].browse(self.sequence.id)
        self.assertEqual(
            self.sequence.number_next_actual, 
            original_next,
            "The POS billing sequence increased during successful simulation."
        )