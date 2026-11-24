from odoo import Command
from odoo.tests import new_test_user, tagged

from .common_currency import CurrencyFixtureCommon


@tagged("l10n_ve_igtf", "-at_install", "post_install")
class TestPaymentsWidgetViewButton(CurrencyFixtureCommon):
    """El widget de pagos de la factura lo arma l10n_ve_igtf sin super(): debe traer
    can_open_move, que decide si se muestra el botón "Ver" del pago (core, odoo/odoo#302668)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.misc_journal = cls.env["account.journal"].create({
            "name": "Varios Prueba Ver", "type": "general", "code": "MVER", "company_id": cls.company.id,
        })
        cls.accounting_user = new_test_user(
            cls.env,
            login="contador_ver",
            groups="account.group_account_readonly,account.group_account_invoice",
            company_id=cls.company.id,
            company_ids=[Command.set(cls.company.ids)],
        )
        cls.invoicing_user = new_test_user(
            cls.env,
            login="facturacion_ver",
            groups="account.group_account_invoice",
            company_id=cls.company.id,
            company_ids=[Command.set(cls.company.ids)],
        )

    def _widget_entries(self, invoice, user=None):
        invoice = invoice.with_user(user) if user else invoice
        invoice.invalidate_recordset(["invoice_payments_widget"])
        return {entry["move_id"]: entry for entry in invoice.invoice_payments_widget["content"]}

    def _invoice_with_payment(self):
        invoice = self._invoice("2026-08-01", 4000.0)
        line = self._outstanding_line(self.bank["VEF"], 1000.0, self.vef, "2026-08-01")
        invoice.js_assign_outstanding_line(line.id)
        return invoice, line.move_id

    def _reconcile_with_entry(self, invoice, amount):
        """Asiento manual (no es pago ni factura) conciliado con la factura."""
        entry = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": self.misc_journal.id,
            "date": "2026-08-01",
            "line_ids": [
                Command.create({
                    "account_id": self.acc_receivable.id,
                    "partner_id": self.partner.id,
                    "credit": amount,
                }),
                Command.create({"account_id": self.bank["VEF"].default_account_id.id, "debit": amount}),
            ],
        })
        entry.action_post()
        lines = (invoice.line_ids | entry.line_ids).filtered(
            lambda l: l.account_id == self.acc_receivable and not l.reconciled
        )
        lines.reconcile()
        return entry

    def test_accounting_user_can_open_every_move(self):
        invoice, payment_move = self._invoice_with_payment()
        entry = self._reconcile_with_entry(invoice, 500.0)

        entries = self._widget_entries(invoice, self.accounting_user)

        self.assertTrue(entries[payment_move.id]["can_open_move"])
        self.assertTrue(entries[entry.id]["can_open_move"])

    def test_invoicing_user_only_opens_payments(self):
        invoice, payment_move = self._invoice_with_payment()
        entry = self._reconcile_with_entry(invoice, 500.0)

        entries = self._widget_entries(invoice, self.invoicing_user)

        self.assertTrue(entries[payment_move.id]["can_open_move"])
        self.assertFalse(entries[entry.id]["can_open_move"])
