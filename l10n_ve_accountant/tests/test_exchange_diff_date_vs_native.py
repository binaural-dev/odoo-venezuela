from datetime import date

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
        self._set_usd_rate(D_BILL, BILL_RATE)
        for d, _usd, rate in PAYMENTS:
            self._set_usd_rate(d, rate)
        # fechas a las que el core puede 'acomodar' el CAMBIO (fin de mes)
        self._set_usd_rate(date(2026, 9, 30), 804.81)
        self._set_usd_rate(date(2026, 10, 31), 875.65)

    def _make_bill(self, currency=None, price=3248.0):
        with Form(self.env["account.move"].with_context(default_move_type="in_invoice")) as f:
            f.partner_id = self.partner
            f.invoice_date = D_BILL
            f.currency_id = currency or self.currency_usd
            with f.invoice_line_ids.new() as line:
                line.product_id = self.product
                line.price_unit = price
        bill = f.save()
        bill.action_post()
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
        payable = bill.line_ids.filtered(lambda l: l.account_type == "liability_payable")
        partials = payable.matched_debit_ids
        out = []
        for p in partials.sorted("id"):
            em = p.exchange_move_id
            pay_date = p.debit_move_id.date
            out.append((
                pay_date, em.date if em else None,
                sum(em.line_ids.mapped("debit")) if em else 0.0,
                sum(em.line_ids.mapped("foreign_debit")) if em else 0.0,
                em.l10n_ve_exchange_foreign_diff_entry if em else None,
            ))
        # entradas standalone alternas sin exchange nativo
        return out, payable

    def _scenario(self, toggle, redo_day, ves_bill=False):
        """redo_day=None: cada pago se registra el dia de su fecha.
        redo_day=fecha: todos se registran 'hoy'=redo_day (re-conciliacion)."""
        self.company.l10n_ve_use_foreign_exchange_diff = toggle
        self._setup_purchase()
        with freeze_time(f"{D_BILL} 12:00:00"):
            bill = self._make_bill(self.currency_vef, 2592962.85) if ves_bill else self._make_bill()
        for d, usd, _r in PAYMENTS:
            today = redo_day or d
            with freeze_time(f"{today} 12:00:00"):
                self._pay(bill, d, usd)
        res, payable = self._cambio_dates(bill)
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
