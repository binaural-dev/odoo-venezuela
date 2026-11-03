from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from odoo import Command
from odoo.tests import Form, TransactionCase, tagged

from .common_tz_boundary import freeze_time
from .test_foreign_exchange_diff import ForeignExchangeDiffMixin

D_BILL = date(2026, 9, 1)
PAYMENTS = [  # (fecha, USD, VES por USD)
    (date(2026, 9, 3), 448.0, 804.81),
    (date(2026, 10, 1), 2000.0, 860.18),
    (date(2026, 10, 27), 800.0, 875.65),
]
BILL_RATE = 798.326


@tagged("post_install", "-at_install", "l10n_ve_exch_date_vs_native")
class TestExchangeDiffDateVsNative(ForeignExchangeDiffMixin, TransactionCase):
    """FP-DF-0002: factura de proveedor USD pagada en 3 fracciones, usando
    `Form` (bill + wizard de pago) como lo haria el usuario. Compara la fecha
    del asiento CAMBIO nativo (toggle alterno OFF) vs. el alterno (ON)."""

    purchase_tax = None

    def _setup_purchase(self):
        self.purchase_tax = self.purchase_tax or self.env["account.tax"].create({
            "name": "IVA 0% compras", "amount": 0, "amount_type": "percent",
            "type_tax_use": "purchase",
        })
        self.product.supplier_taxes_id = [Command.set(self.purchase_tax.ids)]
        self.product.taxes_id = [Command.set(self.zero_tax.ids)]
        self._set_usd_rate(D_BILL, BILL_RATE)
        for d, _usd, rate in PAYMENTS:
            self._set_usd_rate(d, rate)
        # fechas a las que el core puede 'acomodar' el CAMBIO (fin de mes)
        self._set_usd_rate(date(2026, 9, 30), 804.81)
        self._set_usd_rate(date(2026, 10, 31), 875.65)

    def _make_bill(self, currency=None, price=3248.0, move_type="in_invoice"):
        with Form(self.env["account.move"].with_context(default_move_type=move_type)) as f:
            f.partner_id = self.partner
            f.invoice_date = D_BILL
            f.currency_id = currency or self.currency_usd
            with f.invoice_line_ids.new() as line:
                line.product_id = self.product
                line.price_unit = price
        bill = f.save()
        bill.with_context(move_action_post_alert=True).action_post()
        return bill

    def _pay(self, bill, pay_date, usd):
        ctx = bill.action_register_payment()["context"]
        with Form(self.env["account.payment.register"].with_context(ctx)) as f:
            f.journal_id = self.bank_journal_usd
            f.payment_date = pay_date
            f.currency_id = self.currency_usd
            f.amount = usd
        f.record.action_create_payments()

    def _cambio_dates(self, bill):
        """(fecha del pago, fecha del CAMBIO nativo, debe Bs, debe alterno,
        es asiento alterno) por cada partial, en orden de conciliacion."""
        account_type = "liability_payable" if bill.move_type == "in_invoice" else "asset_receivable"
        line = bill.line_ids.filtered(lambda l: l.account_type == account_type)
        out = []
        for p in (line.matched_debit_ids | line.matched_credit_ids).sorted("id"):
            em = p.exchange_move_id
            out.append((
                max(p.debit_move_id.date, p.credit_move_id.date),
                em.date if em else None,
                sum(em.line_ids.mapped("debit")) if em else 0.0,
                sum(em.line_ids.mapped("foreign_debit")) if em else 0.0,
                em.l10n_ve_exchange_foreign_diff_entry if em else None,
            ))
        return out

    def _scenario(self, toggle, redo_day, ves_bill=False, move_type="in_invoice"):
        """redo_day=None: cada pago se registra el dia de su fecha.
        redo_day=fecha: todos se registran 'hoy'=redo_day (re-conciliacion)."""
        self.company.l10n_ve_use_foreign_exchange_diff = toggle
        self._setup_purchase()
        with freeze_time(f"{D_BILL} 12:00:00"):
            bill = (
                self._make_bill(self.currency_vef, 2592962.85, move_type)
                if ves_bill else self._make_bill(move_type=move_type)
            )
        for d, usd, _r in PAYMENTS:
            today = redo_day or d
            with freeze_time(f"{today} 12:00:00"):
                self._pay(bill, d, usd)
        res = self._cambio_dates(bill)
        standalone = self.env["account.move"].search([
            ("l10n_ve_exchange_foreign_source_move_id", "=", bill.id)], order="id")
        res = res + [("standalone", m.date, sum(m.line_ids.mapped("foreign_debit"))) for m in standalone]
        return res

    def _core_date(self, raw_date):
        """Fecha que el core asigna a SU asiento de diferencial para un
        par cuya fecha mayor es `raw_date` (`journal.accounting_date`)."""
        journal = self.company.currency_exchange_journal_id
        return journal.with_context(move_date=raw_date).accounting_date

    def test_usd_bill_alt_adds_nothing_and_dates_match_native(self):
        """Factura USD: el CAMBIO es 100% nativo; el alterno no agrega
        montos ni cambia fechas (toggle ON == OFF), pagando cada dia o
        re-conciliando todo 'hoy'."""
        for redo in (None, date(2026, 10, 27)):
            native = self._scenario(False, redo)
            alt = self._scenario(True, redo)
            self.assertEqual([r[:3] for r in native], [r[:3] for r in alt])
            self.assertFalse(any(r[3] for r in alt), "alterno no debe inyectar montos en factura USD")
            for (pay_date, exch_date, *_rest) in native:
                if redo is None:
                    self.assertEqual(exch_date, pay_date)
                else:
                    with freeze_time(f"{redo} 12:00:00"):
                        self.assertEqual(exch_date, self._core_date(pay_date))

    def test_alt_standalone_entry_dated_like_native(self):
        """Factura Bs pagada en USD: el asiento alterno (standalone) debe
        fecharse con la misma regla que el nativo, no con la fecha cruda."""
        for redo in (None, date(2026, 10, 27)):
            res = self._scenario(True, redo, ves_bill=True)
            standalone = [r for r in res if r[0] == "standalone"]
            self.assertEqual(len(standalone), 3)
            for (pay_date, *_r), (_tag, entry_date, _amt) in zip(
                [r for r in res if r[0] != "standalone"], standalone
            ):
                with freeze_time(f"{redo or pay_date} 12:00:00"):
                    expected = self._core_date(pay_date)
                self.assertEqual(entry_date, expected, f"pago {pay_date}, re-conciliacion {redo}")

    def test_alt_standalone_entry_dated_like_native_customer_invoice(self):
        """Lado cliente (cuenta por cobrar): misma regla que en proveedor."""
        for redo in (None, date(2026, 10, 27)):
            res = self._scenario(True, redo, ves_bill=True, move_type="out_invoice")
            standalone = [r for r in res if r[0] == "standalone"]
            self.assertEqual(len(standalone), 3)
            for (pay_date, *_r), (_tag, entry_date, _amt) in zip(
                [r for r in res if r[0] != "standalone"], standalone
            ):
                with freeze_time(f"{redo or pay_date} 12:00:00"):
                    expected = self._core_date(pay_date)
                self.assertEqual(entry_date, expected, f"pago {pay_date}, re-conciliacion {redo}")

    # ── Ramas de `_get_alt_exchange_date` ──

    def _fake_lines(self, raw_debit, raw_credit):
        return (
            SimpleNamespace(date=raw_debit, company_id=self.company),
            SimpleNamespace(date=raw_credit, company_id=self.company),
        )

    def test_alt_exchange_date_prefers_core_move_date(self):
        debit, credit = self._fake_lines(date(2026, 9, 3), date(2026, 9, 1))
        core_values = {"move_values": {"date": date(2026, 9, 15)}}
        self.assertEqual(
            self.env["account.move.line"]._get_alt_exchange_date(debit, credit, core_values),
            date(2026, 9, 15),
        )

    def test_alt_exchange_date_applies_journal_rule_when_core_built_none(self):
        """Sin asiento del core: regla del diario (diario CAMBIO nuevo, sin
        numeracion previa: fecha pasada de un mes anterior -> fin de ese mes)."""
        debit, credit = self._fake_lines(date(2026, 9, 3), date(2026, 9, 1))
        with freeze_time("2026-10-27 12:00:00"):
            result = self.env["account.move.line"]._get_alt_exchange_date(debit, credit, {})
        self.assertEqual(result, date(2026, 9, 30))
        self.assertNotEqual(result, date(2026, 9, 3), "no debe quedar la fecha cruda")

    def test_alt_exchange_date_keeps_raw_date_without_exchange_journal(self):
        debit, credit = self._fake_lines(date(2026, 9, 3), date(2026, 9, 1))
        no_journal = lambda self, company: self.env["account.journal"]  # noqa: E731
        with patch.object(self.env.registry["account.move.line"], "_get_exchange_journal", no_journal):
            result = self.env["account.move.line"]._get_alt_exchange_date(debit, credit, {})
        self.assertEqual(result, date(2026, 9, 3))

    def test_alt_exchange_date_respects_lock_date(self):
        """Con fecha de bloqueo, la regla del diario empuja la fecha fuera del
        periodo bloqueado (igual que lo haria para el asiento nativo)."""
        self.company.hard_lock_date = date(2026, 9, 30)
        debit, credit = self._fake_lines(date(2026, 9, 3), date(2026, 9, 1))
        with freeze_time("2026-10-27 12:00:00"):
            result = self.env["account.move.line"]._get_alt_exchange_date(debit, credit, {})
        self.assertGreater(result, date(2026, 9, 30))
        with freeze_time("2026-10-27 12:00:00"):
            self.assertEqual(result, self._core_date(date(2026, 9, 3)))
