"""`create()` con tasa manual y fecha sin tasa no debe fallar; sin tasa manual, una factura
en una fecha sin tasa sigue fallando (restriccion de tasa exacta)."""

from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_indexed_payments import TestIndexedPayments


@tagged("post_install", "-at_install", "l10n_ve_accountant_create_manual_rate")
class TestCreateManualRateFutureDate(TestIndexedPayments):
    def setUp(self):
        super().setUp()
        self.today = fields.Date.context_today(self.env["account.move"])
        self._set_rate(self.currency_usd, self.today, 40.0)
        self.general_journal = self.env["account.journal"].sudo().create(
            {
                "name": "General Rate",
                "code": "GRATE",
                "type": "general",
                "company_id": self.company.id,
            }
        )
        self.Move = self.env["account.move"]

    def _entry(self, **kwargs):
        vals = {
            "move_type": "entry",
            "journal_id": self.general_journal.id,
            "date": self.today,
            "line_ids": [
                Command.create(
                    {"account_id": self.account_receivable.id, "debit": 100.0, "credit": 0.0}
                ),
                Command.create(
                    {"account_id": self.account_income.id, "debit": 0.0, "credit": 100.0}
                ),
            ],
        }
        vals.update(kwargs)
        return self.Move.create(vals)

    def test_create_with_manual_rate_and_date_without_rate_does_not_fail(self):
        no_rate_date = self.today + timedelta(days=40)
        move = self._entry(
            date=no_rate_date,
            manually_set_rate=True,
            foreign_rate=45.0,
            foreign_inverse_rate=45.0,
        )
        self.assertEqual(move.foreign_rate, 45.0)

    def test_invoice_with_date_without_rate_still_fails(self):
        """Regresion: la restriccion de tasa exacta se mantiene."""
        with self.assertRaisesRegex(UserError, "no rate assigned"):
            self.Move.create(
                {
                    "move_type": "out_invoice",
                    "partner_id": self.partner.id,
                    "journal_id": self.sale_journal.id,
                    "invoice_date": self.today + timedelta(days=40),
                    "invoice_line_ids": [
                        Command.create({"product_id": self.product.id, "price_unit": 10.0})
                    ],
                }
            )
