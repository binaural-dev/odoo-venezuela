import logging

from odoo.tests import TransactionCase, tagged
from odoo import Command
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestCheckPriceInZero(TransactionCase):
    """Tests for `_check_price_in_zero` (`account_move.py`).

    Relocated here from `l10n_ve_accountant` (PR #1344/#1417 investigation):
    both assertions test THIS module's own constraint and can't be
    guaranteed to run in a test DB where only `l10n_ve_accountant` is
    installed -- confirmed via PR #1417, a diff isolated to that module.

    Self-contained setUp (not reusing `TestAccountMove`'s) to avoid an
    unrelated pre-existing `ValueError: Invalid field
    'confirm_invoice_with_current_date' in 'res.company'` in that class's
    own fixture (dates back to commit b9018a6c8, 2025-07-25 -- stale field
    that doesn't exist anywhere in this codebase)."""

    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.tax_16 = self.env['account.tax'].create({
            'name': 'IVA 16% (check_price_in_zero tests)',
            'amount': 16,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'company_id': self.company.id,
        })
        self.product = self.env['product.product'].create({
            'name': 'Producto check_price_in_zero tests',
            'type': 'service',
        })
        self.partner = self.env['res.partner'].create({
            'name': 'Partner check_price_in_zero tests',
        })
        self.sale_journal = self.env['account.journal'].search([
            ('type', '=', 'sale'), ('company_id', '=', self.company.id),
        ], limit=1)

    def _create_invoice(self, price_units):
        return self.env['account.move'].with_context(
            check_move_validity=False,
        ).create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'journal_id': self.sale_journal.id,
            'invoice_line_ids': [
                Command.create({
                    'product_id': self.product.id,
                    'quantity': 1.0,
                    'price_unit': price_unit,
                    'tax_ids': [(6, 0, [self.tax_16.id])],
                })
                for price_unit in price_units
            ],
        })

    def test_rejects_bare_negative_subtotal_line(self):
        """Relocated from `l10n_ve_accountant/tests/test_multi_currency_rounding.py
        ::test_31_mixed_sign_lines_both_rounding_modes`."""
        with self.assertRaises(ValidationError):
            self._create_invoice([11.16, -4.16])

    def test_rejects_negative_line_sharing_tax_with_positive_line(self):
        """Relocated from `l10n_ve_accountant/tests/test_real_portion.py
        ::test_34i_negative_line_blocked_by_existing_invoice_constraint`
        (kept as a separate case -- documents the concrete 100/-20 shape
        that test's original author found relevant)."""
        with self.assertRaises(ValidationError):
            self._create_invoice([100.0, -20.0])
