from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_ve_exchange_diff_entry = fields.Boolean(
        default=False,
        copy=False,
    )
    l10n_ve_exchange_original_id = fields.Many2one(
        'account.move',
        string='Exchange Debit Note Reversed',
        copy=False,
        check_company=True,
        help="Credit Note that reverses the original exchange difference "
             "Debit Note. Only set on automatically generated reversal entries.",
    )
    l10n_ve_exchange_is_credit_note = fields.Boolean(
        default=False,
        copy=False,
        help="Set when this note was created directly as a Credit Note "
             "(exchange gain), as opposed to being a reversal of a Debit "
             "Note (see `l10n_ve_exchange_original_id`).",
    )
    l10n_ve_exchange_invoice_id = fields.Many2one(
        'account.move',
        string='Factura de Origen (Diferencial Cambiario)',
        copy=False,
        check_company=True,
        help="Factura/Nota original cuyo residual (en moneda de compañía) "
             "esta Nota de Débito/Crédito de diferencial cambiario liquida.",
    )

    def _is_exchange_debit_note(self):
        return (
            self.l10n_ve_exchange_diff_entry
            and not self.l10n_ve_exchange_original_id
            and not self.l10n_ve_exchange_is_credit_note
        )

    def _is_exchange_credit_note(self):
        return bool(self.l10n_ve_exchange_original_id) or bool(self.l10n_ve_exchange_is_credit_note)

    @api.depends(
        'posted_before', 'state', 'journal_id', 'date', 'move_type',
        'origin_payment_id', 'l10n_ve_exchange_diff_entry',
        'l10n_ve_exchange_original_id',
    )
    def _compute_name_by_sequence(self):
        # `od_journal_sequence` reemplaza por completo el compute nativo del
        # campo `name` (`_compute_name` -> `_compute_name_by_sequence`) --
        # por eso hay que enganchar la numeración de ND/NC de diferencial
        # cambiario aquí, y NO en `_compute_name` (quedaría muerto: el ORM
        # ya no invoca ese método para este campo).
        exchange_moves = self.filtered(
            lambda m: m._is_exchange_debit_note() or m._is_exchange_credit_note()
        )
        other_moves = self - exchange_moves
        if other_moves:
            super(AccountMove, other_moves)._compute_name_by_sequence()

        for move in exchange_moves:
            if move.state != 'posted':
                move.name = move.name or '/'
                continue
            if move.name and move.name != '/':
                continue

            # Notas de crédito: reutilizamos `refund_sequence_id`, ya
            # provisto por `od_journal_sequence` para cualquier diario --
            # no hace falta un campo propio (a diferencia de las notas de
            # débito, que no tienen equivalente nativo).
            sequence = (
                move.journal_id.l10n_ve_exchange_debit_note_sequence_id
                if move._is_exchange_debit_note()
                else move.journal_id.refund_sequence_id
            )

            if sequence and move.date:
                move.name = sequence.next_by_id()
            else:
                # Sin secuencia dedicada configurada: cae al comportamiento
                # nativo (sequence_id del diario).
                super(AccountMove, move)._compute_name_by_sequence()

    def _sequence_matches_date(self):
        if self.l10n_ve_exchange_diff_entry or self.l10n_ve_exchange_original_id:
            return True
        return super()._sequence_matches_date()

    def js_remove_outstanding_partial(self, partial_id):
        # Mismo patrón que `l10n_ve_igtf_note_debit`/`l10n_ve_igtf` para su
        # propia ND (ver `l10n_ve_igtf/models/account_move.py`,
        # `js_remove_outstanding_partial` -> `create_note_credit_igtf`): si
        # la conciliación que se está rompiendo es la de la factura de
        # origen (no la de nuestra propia ND/NC contra ella), y esa factura
        # ya tiene una ND/NC de diferencial cambiario emitida, hay que
        # revertirla ANTES de romper la conciliación -- igual que hace
        # Odoo con su propio asiento genérico de diferencial
        # (`account.partial.reconcile.unlink()`, `account_partial_reconcile.py`:
        # revierte si está posteado, borra directo si sigue en borrador --
        # nunca se cancela/borra un documento fiscal ya posteado).
        self.ensure_one()
        partial = self.env['account.partial.reconcile'].browse(partial_id)
        related_moves = partial.debit_move_id.move_id | partial.credit_move_id.move_id

        # La conciliación de la NOTA contra la factura/pago (la que la
        # cierra) NO se puede romper suelta -- solo debe desconciliarse
        # como CONSECUENCIA de que se rompa la conciliación ORIGINAL
        # factura<->pago (manejado más abajo). Si alguno de los dos lados
        # de este `partial` ya es una nota nuestra, se bloquea: da igual
        # si el click vino desde la propia nota o desde la factura viendo
        # esa reconciliación puntual en su lista de pagos.
        if any(related_moves.mapped('l10n_ve_exchange_diff_entry')):
            raise UserError(_(
                "No se puede desconciliar directamente una Nota de Débito/Crédito "
                "de diferencial cambiario. Para deshacerla, rompa la conciliación "
                "original entre la factura y el pago -- la nota se revertirá "
                "automáticamente."
            ))

        invoice = related_moves.filtered(
            lambda m: m.move_type in ('out_invoice', 'out_refund')
        )[:1]
        if invoice:
            # No se condiciona a `company_id.l10n_ve_exchange_use_nd_nc`: la
            # sola existencia de una nota vinculada a esta factura ya prueba
            # que se usó este flujo al conciliar -- revisar el toggle aquí
            # es redundante (y frágil: si alguien desactiva la opción
            # después de emitida la nota, esta seguiría necesitando
            # revertirse correctamente al desconciliar).
            note = self.env['account.move'].search([
                ('l10n_ve_exchange_invoice_id', '=', invoice.id),
                ('state', '!=', 'cancel'),
            ], limit=1)
            if note:
                note._reverse_exchange_note()
        return super().js_remove_outstanding_partial(partial_id)

    def _reverse_exchange_note(self):
        """Revierte esta ND/NC de diferencial cambiario porque la
        conciliación factura/pago que la originó se está rompiendo -- por
        lógica de negocio, un documento fiscal ya posteado (con
        correlativo real) no se puede cancelar/borrar sin más, hay que
        revertirlo (mismo criterio que usa Odoo con su propio asiento
        genérico de diferencial al desconciliar)."""
        self.ensure_one()
        if self.state == 'draft':
            self.unlink()
            return
        if self.state != 'posted':
            return
        # `cancel=True`: además de crear la reversión, desconcilia y
        # concilia la reversión contra esta nota para cerrarla por
        # completo -- mismo parámetro que usa
        # `account.partial.reconcile.unlink()` para el asiento genérico de
        # diferencial y las entradas de base imponible en caja (CABA).
        self.with_context(move_reverse_cancel=True)._reverse_moves(
            default_values_list=[{
                'ref': _('Reversión de: %s', self.name),
                'l10n_ve_exchange_diff_entry': True,
                'l10n_ve_exchange_invoice_id': self.l10n_ve_exchange_invoice_id.id,
            }],
            cancel=True,
        )

    def _reverse_moves(self, default_values_list=None, cancel=False):
        if default_values_list is None:
            default_values_list = [{} for _ in self]

        for move, default_values in zip(self, default_values_list):
            if (
                move._is_exchange_debit_note()
                and move.company_id.l10n_ve_exchange_use_nd_nc
            ):
                default_values.update({
                    'l10n_ve_exchange_original_id': move.id,
                    'name': '/',
                })

        return super()._reverse_moves(default_values_list, cancel=cancel)
