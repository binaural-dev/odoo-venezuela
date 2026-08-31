from odoo import models


class AccountPartialReconcile(models.Model):
    _inherit = 'account.partial.reconcile'

    def unlink(self):
        """Reverses any exchange difference Debit/Credit Note tied to an
        invoice/payment pair whose reconciliation is being broken here --
        hooked at THIS level (not only `account.move.js_remove_outstanding_partial`,
        the 'x' button on the payments widget) because it's the one place
        every way of breaking a reconciliation actually converges:
        `account.move.line.remove_move_reconcile()` (core) calls
        `(matched_debit_ids + matched_credit_ids).unlink()` directly,
        bypassing the widget entirely -- `l10n_ve_igtf`
        (`cancel_advance_payment_transaction`, advance payment
        cancellation) does exactly that. Before this, breaking a
        reconciliation through that path left the note orphaned: already
        posted, with a real fiscal sequence number consumed, but never
        reversed -- the invoice/payment showed as unreconciled while the
        note kept claiming otherwise."""
        AccountMove = self.env['account.move']
        notes_to_reverse = AccountMove.browse()
        # SIN cortocircuito por el toggle `l10n_ve_exchange_use_nd_nc` de
        # la compañía -- ya se intentó y se revirtió a propósito
        # (`bbda718c9`, `js_remove_outstanding_partial`): si alguien
        # apaga el toggle DESPUÉS de emitida la nota, la nota ya posteada
        # (folio fiscal consumido) igual necesita revertirse correctamente
        # al desconciliar. Gatear por el estado ACTUAL del toggle deja esa
        # nota huérfana. Además, leer `.l10n_ve_exchange_use_nd_nc` sobre
        # `(debit.company_id | credit.company_id)` revienta con
        # `ValueError: Expected singleton` en cuanto débito y crédito son
        # de compañías DISTINTAS (conciliación entre sucursal y matriz,
        # soportada por el núcleo) -- `_l10n_ve_exchange_note_for_partial`
        # ya hace su propio corte barato (requiere que el partial
        # involucre una factura `out_invoice`/`out_refund`) antes de
        # cualquier `search()`, así que no hace falta un cortocircuito
        # adicional aquí.
        for partial in self:
            note = AccountMove._l10n_ve_exchange_note_for_partial(partial)
            if note:
                notes_to_reverse |= note

        result = super().unlink()

        for note in notes_to_reverse:
            # Ya pudo haberse revertido dentro de este mismo `unlink()`
            # (dos partials distintos del lote resolviendo a la MISMA
            # nota) o por un guard de negocio anterior -- `reversal_move_ids`
            # es la señal real, no la mera existencia del registro.
            if note.exists() and not note.reversal_move_ids:
                note._reverse_exchange_note()

        return result
