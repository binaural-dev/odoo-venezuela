from odoo import Command, fields
from odoo.tests import Form, tagged

from .test_exchange_note_reversal import TestExchangeNoteReversal


@tagged("l10n_ve_exchange_difference", "-at_install", "post_install")
class TestExchangeNoteMixedFlow(TestExchangeNoteReversal):
    """Cubre el flujo mixto por cliente
    (`l10n_ve_exchange_validate_partner_note` + `res.partner.l10n_ve_exchange_allow_note`)
    y la exclusión de pagos de retención
    (`l10n_ve_exchange_is_retention_reconcile`) descritos en
    `openspec/changes/l10n-ve-exchange-difference-mixed-flow`. Ninguno de
    los dos tenía test hasta ahora (`tasks.md` 6.1).

    Subclasea `TestExchangeNoteReversal` para reutilizar íntegro su
    `setUpClass` (compañía, tasas, cuentas, diarios, producto/lista de ND)
    en vez de rearmar ese fixture desde cero. Costo conocido: al correr la
    suite COMPLETA del módulo (sin filtrar por clase), los ~80 tests de
    `TestExchangeNoteReversal` se descubren y corren una segunda vez bajo
    este nombre (mismo `setUpClass`, cero cobertura nueva) -- se intentó
    evitarlo invocando `TestExchangeNoteReversal.setUpClass.__func__(cls)`
    sin heredar, pero el `super()` sin argumentos de ese método está
    ligado por closure a `TestExchangeNoteReversal` y revienta
    (`TypeError: super(type, obj): obj must be an instance or subtype of
    type`) si `cls` no es realmente una subclase suya. Extraer el fixture
    a una clase base no-`TestCase` compartida evitaría la duplicación,
    pero implica tocar la clase existente de 4000+ líneas -- fuera de
    alcance acá; el costo es solo tiempo de CI (~85s), no incorrección."""

    def _settle_and_get_notes(self, invoice):
        """Mismo flujo de `test_exchange_difference_settled_by_real_note_via_register_payment`
        (factura en USD, pago vía `action_register_payment` en una fecha
        con tasa distinta) reducido a un helper -- devuelve las ND/NC
        generadas para `self.partner`, si las hay."""
        invoice.with_context(move_action_post_alert=True).action_post()
        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        payment_wizard.action_create_payments()
        self.env.cr.flush()
        invoice.invalidate_recordset()
        return self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("partner_id", "=", self.partner.id),
        ])

    def test_client_gate_disabled_still_creates_note(self):
        """Regresión: con `l10n_ve_exchange_validate_partner_note`
        desactivado (default), el flag del cliente no se consulta -- se
        emite ND/NC sin importar su valor, igual que antes de que esta
        opción existiera."""
        self.assertFalse(self.company.l10n_ve_exchange_validate_partner_note)
        self.partner.with_company(self.company).l10n_ve_exchange_allow_note = False

        invoice = self._create_invoice("2026-01-01")
        notes = self._settle_and_get_notes(invoice)

        self.assertEqual(len(notes), 1, "Con el flujo mixto desactivado, debió emitirse la ND/NC igual.")

    def test_client_gate_enabled_with_permission_creates_note(self):
        """Flujo mixto activado, cliente CON permiso: se emite la ND/NC
        fiscal real."""
        self.company.l10n_ve_exchange_validate_partner_note = True
        self.partner.with_company(self.company).l10n_ve_exchange_allow_note = True

        invoice = self._create_invoice("2026-01-01")
        notes = self._settle_and_get_notes(invoice)

        self.assertEqual(len(notes), 1, "Cliente con permiso debió recibir la ND/NC fiscal.")

    def test_client_gate_enabled_without_permission_uses_native_entry(self):
        """Flujo mixto activado, cliente SIN permiso (default): no se
        emite ninguna ND/NC -- el diferencial queda con el asiento
        genérico nativo de Odoo, igual que con el toggle de compañía
        apagado."""
        self.company.l10n_ve_exchange_validate_partner_note = True
        self.assertFalse(self.partner.with_company(self.company).l10n_ve_exchange_allow_note)

        invoice = self._create_invoice("2026-01-01")
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        notes = self._settle_and_get_notes(invoice)

        self.assertFalse(notes, "Cliente sin permiso no debió recibir ninguna ND/NC.")
        inv_line.invalidate_recordset()
        self.assertTrue(inv_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(inv_line.amount_residual))

    def test_client_gate_permission_is_company_dependent(self):
        """`res.partner.l10n_ve_exchange_allow_note` es `company_dependent`
        -- el mismo contacto puede tener el permiso otorgado en una
        compañía y negado en otra, reflejando negociaciones distintas por
        compañía sobre el mismo cliente (motivo por el que se corrigió a
        `company_dependent`, ver `res_partner.py`)."""
        other_company = self.env["res.company"].create({"name": "Otra Compañía (Mixed Flow)"})

        self.partner.with_company(self.company).l10n_ve_exchange_allow_note = True
        self.partner.with_company(other_company).l10n_ve_exchange_allow_note = False

        self.assertTrue(self.partner.with_company(self.company).l10n_ve_exchange_allow_note)
        self.assertFalse(self.partner.with_company(other_company).l10n_ve_exchange_allow_note)

    def test_retention_reconcile_excluded_from_nd_nc(self):
        """Reproduce, sin depender de `l10n_ve_payment_extension`, lo que
        `account_retention.py::_reconcile_all_payments` hace: reconciliar
        la línea por cobrar de la factura contra otra línea con el
        contexto propio `l10n_ve_exchange_is_retention_reconcile=True`
        (vía `js_assign_outstanding_line`, el mismo método público que usa
        ese módulo). Aun con una tasa de cambio distinta entre ambas
        fechas -- que en cualquier otra reconciliación SÍ dispararía una
        ND/NC -- no debe crearse ninguna."""
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        # Línea "de pago" manual sobre la MISMA cuenta por cobrar del
        # cliente (no vía `account.payment`/cuenta puente de tránsito) --
        # así `js_assign_outstanding_line` (que solo empareja líneas de la
        # MISMA cuenta) puede reconciliarla directo contra la factura,
        # igual que hace `_reconcile_all_payments` con la línea de la
        # retención.
        retention_entry = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": self.exchange_journal.id,
            "date": "2026-08-01",
            "line_ids": [
                Command.create({
                    "account_id": self.acc_receivable.id,
                    "partner_id": self.partner.id,
                    "currency_id": self.usd.id,
                    "amount_currency": -100.0,
                    "balance": -100.0 / self.rate_payment_date,
                }),
                Command.create({
                    "account_id": self.acc_exchange_loss.id,
                    "currency_id": self.usd.id,
                    "amount_currency": 100.0,
                    "balance": 100.0 / self.rate_payment_date,
                }),
            ],
        })
        retention_entry.action_post()
        retention_line = retention_entry.line_ids.filtered(lambda l: l.account_id == self.acc_receivable)

        invoice.with_context(
            l10n_ve_exchange_is_retention_reconcile=True,
        ).js_assign_outstanding_line(retention_line.id)
        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()
        self.assertTrue(inv_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(inv_line.amount_residual))

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertFalse(
            notes,
            "Una reconciliación de retención no debe generar ninguna ND/NC, "
            "pese a la diferencia de tasa entre las dos fechas.",
        )
