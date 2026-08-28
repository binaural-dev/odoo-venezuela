from datetime import date, datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_ve_exchange_diff_entry = fields.Boolean(
        string='Is Exchange Difference Note/Entry',
        default=False,
        copy=False,
    )
    l10n_ve_exchange_original_id = fields.Many2one(
        'account.move',
        string='Reversed Exchange Difference Debit Note',
        copy=False,
        check_company=True,
        help="Credit Note that reverses the original exchange difference "
             "Debit Note. Only set on automatically generated reversal "
             "entries.",
    )
    l10n_ve_exchange_is_credit_note = fields.Boolean(
        string='Is Direct Exchange Difference Credit Note',
        default=False,
        copy=False,
        help="Set when this note was created directly as a Credit Note "
             "(exchange gain), as opposed to being the reversal of a Debit "
             "Note (see `l10n_ve_exchange_original_id`).",
    )
    l10n_ve_exchange_invoice_id = fields.Many2one(
        'account.move',
        string='Source Customer Invoice (Exchange Difference)',
        copy=False,
        check_company=True,
        help="Original CUSTOMER invoice/note whose residual (in company "
             "currency) this exchange difference Debit/Credit Note "
             "settles.",
    )
    l10n_ve_exchange_payment_id = fields.Many2one(
        'account.move',
        string='Settled Payment (Exchange Difference)',
        copy=False,
        check_company=True,
        help="Payment entry whose reconciliation against the source "
             "invoice originated this exchange difference Debit/Credit "
             "Note. Used to tell apart the note from a SPECIFIC partial "
             "payment from a note already issued for the same invoice "
             "from an EARLIER partial payment -- an invoice paid in "
             "several installments can accrue a distinct exchange "
             "difference note per installment.",
    )

    def _is_exchange_debit_note(self):
        """True if this document is an exchange difference Debit Note
        issued by this module -- never a native Odoo generic entry tagged
        with `l10n_ve_exchange_diff_entry`."""
        return (
            self.move_type == 'out_invoice'
            and self.l10n_ve_exchange_diff_entry
            and not self.l10n_ve_exchange_original_id
            and not self.l10n_ve_exchange_is_credit_note
        )

    def _is_exchange_credit_note(self):
        """True if this document is an exchange difference Credit Note
        (issued directly, or as the reversal of our own Debit Note)."""
        return self.move_type == 'out_refund' and (
            bool(self.l10n_ve_exchange_original_id) or bool(self.l10n_ve_exchange_is_credit_note)
        )

    def _compute_payment_state(self):
        """Corrects core's own `payment_state` computation for the ONE
        combination it doesn't anticipate: an invoice closed ENTIRELY by
        non-payment documents where one of them is our own exchange
        difference Debit/Credit Note.

        Concretely: `l10n_ve_igtf`'s "cruce de anticipo" mechanism
        (`_reconcile_move_with_payment_difference`, `l10n_ve_igtf/models/account_move.py`)
        closes an invoice against a hand-built `account.move`
        (`move_type='entry'`, created WITHOUT `origin_payment_id` -- it
        isn't a real `account.payment`, just an accounting entry moving
        an existing advance balance onto the receivable account). If
        that reconciliation also leaves a currency residual, THIS module
        intercepts it and documents it with a real `out_refund` Credit
        Note (`_create_exchange_difference_note`,
        `account_move_line.py`), reconciled against the SAME invoice
        line to close it.

        Core's `_compute_payment_state` (`account/models/account_move.py`)
        decides `'reversed'` vs `'paid'` by looking at the `move_type` of
        EVERY counterpart ever reconciled against the invoice's
        receivable line, but ONLY when NONE of them carries a real
        `account.payment` (`has_payment`) or bank statement line
        (`has_st_line`) -- in that branch, if the counterpart types are
        exactly `{'out_refund'}` or `{'out_refund', 'entry'}` (for an
        `out_invoice`), it concludes the invoice was REVERSED, not paid.
        Without this module, that branch was unreachable for this
        scenario: Odoo's own generic exchange-difference entry is ALSO
        `move_type='entry'`, so the counterpart set stayed `{'entry'}`
        (never includes `'out_refund'`) and correctly resolved to
        `'paid'`. This module's whole point is replacing that generic
        entry with a REAL fiscal Credit Note -- which is exactly what
        introduces `'out_refund'` into the set, and exactly what flips a
        genuinely-paid invoice into `'reversed'`. `payment_state` itself
        is the only thing this corrects -- checked empirically whether
        it also rescued `l10n_ve_igtf.compute_bi_igtf`'s IGTF base in
        this same scenario (a fully-closed invoice reads as `'reversed'`
        instead of `'paid'`, and that field only computes when
        `payment_state in ('paid', 'in_payment')` or there's still a
        residual) and it does NOT: whenever this bug can trigger (the
        invoice's ENTIRE reconciliation history has zero real payments),
        `compute_bi_igtf`'s own formula also finds zero real
        IGTF-carrying counterparts to build a base from, so it computes
        to 0 regardless of whether `payment_state` is right or wrong.
        There is no reachable scenario mixing a real IGTF payment with
        this bug: any real payment in the invoice's history keeps core's
        computation in its `has_payment` branch, which never evaluates
        the `'reversed'` condition at all. So the value of this fix is
        `payment_state` accuracy on its own merits (reporting, filters,
        anything else that reads it) -- not IGTF base protection.

        Verified this scenario is REAL and specific to this module: with
        it uninstalled/disabled, the same anticipo-cross-with-currency-
        residual case always resolves to `'paid'` (confirmed by tracing
        core's set-comparison with `'entry'` on both sides instead of
        `'entry'`/`'out_refund'`).

        This override does NOT reimplement or bypass core's SQL-based
        computation (`_compute_payment_state` builds `reconciliation_vals`
        via a raw SQL query joining `account_payment`, which -- being raw
        SQL -- never hits `ir.rule`/`AccessError` in the first place).
        Instead, it lets `super()` compute normally, then -- ONLY for
        moves core marked `'reversed'` -- re-derives the SAME
        `move_type` set-comparison core just used, EXCLUDING our own
        notes from that set. If removing our notes changes the verdict
        (the note was the deciding factor), corrects to `'paid'` -- the
        exact value core's own branch defaults to before evaluating the
        reversal condition. If removing our notes does NOT change the
        verdict (some OTHER, unrelated reversal-causing document is
        still in the mix -- e.g. a genuine business Credit Note that
        happens to also touch an invoice one of our notes touched on an
        earlier, unrelated partial payment), leaves `'reversed'` alone:
        that classification is real and not our module's doing.

        No `.sudo()` here, unlike `compute_bi_igtf`'s -- deliberate.
        Reading `matched_debit_ids`/`matched_credit_ids` via the ORM
        (instead of raw SQL) DOES apply `ir.rule`, so a counterpart in a
        company the current user/process can't see would raise
        `AccessError` here. In the actual scenario this override exists
        for, invoice/anticipo-cross/note are always the SAME company
        (`_create_exchange_difference_note` forces `company =
        invoice.company_id`), so this never triggers in practice. If it
        ever does (a parent/subsidiary company structure, out of scope
        for this fix), failing loud is the correct behavior: a
        user/process that can't see a company's records shouldn't
        silently complete a flow that depends on them."""
        super()._compute_payment_state()
        for move in self:
            if move.payment_state != 'reversed':
                continue
            rp_lines = move.line_ids.filtered(
                lambda l: l.account_type in ('asset_receivable', 'liability_payable')
            )
            counterparts = (
                rp_lines.matched_debit_ids.debit_move_id
                | rp_lines.matched_credit_ids.credit_move_id
            ).move_id
            flagged = counterparts.filtered('l10n_ve_exchange_diff_entry')
            # `l10n_ve_exchange_diff_entry=True` SOLO tiene dos usos
            # legítimos en todo el módulo: nuestras propias ND/NC
            # (`out_invoice`/`out_refund`) y el etiquetado de
            # trazabilidad sobre el asiento GENÉRICO nativo de Odoo
            # (siempre `move_type='entry'`, ver
            # `_prepare_exchange_difference_move_vals`,
            # `account_move_line.py`). Cualquier otro `move_type` con
            # ese flag es un estado que este módulo NUNCA debería poder
            # producir -- si aparece, es porque algo (una extensión
            # futura, propia o de terceros, o un bug) está marcando un
            # documento con nuestro flag sin ser ninguna de esas dos
            # cosas. Dejarlo pasar en silencio (tratándolo simplemente
            # como "no es una nota nuestra") escondería ese problema y
            # podría romper esta misma lógica más adelante, de una forma
            # mucho más difícil de diagnosticar que un error acá mismo,
            # en el momento exacto en que se detecta la inconsistencia.
            unexpected = flagged.filtered(lambda c: c.move_type not in ('entry', 'out_invoice', 'out_refund'))
            if unexpected:
                raise UserError(_(
                    "Internal consistency error: found %(count)s move(s) "
                    "tagged with 'l10n_ve_exchange_diff_entry' whose "
                    "move_type ('%(types)s') is neither one this module "
                    "issues ('out_invoice'/'out_refund') nor the native "
                    "generic entry it tags for traceability ('entry'). "
                    "This flag must never be set on any other document "
                    "type -- aborting instead of silently miscomputing "
                    "payment_state.",
                    count=len(unexpected),
                    types=", ".join(sorted(set(unexpected.mapped('move_type')))),
                ))
            our_notes = flagged.filtered(lambda c: c.move_type in ('out_invoice', 'out_refund'))
            if not our_notes:
                continue
            remaining_types = set((counterparts - our_notes).mapped('move_type'))
            in_reverse = move.move_type in ('in_invoice', 'in_receipt') and remaining_types in (
                {'in_refund'}, {'in_refund', 'entry'},
            )
            out_reverse = move.move_type in ('out_invoice', 'out_receipt') and remaining_types in (
                {'out_refund'}, {'out_refund', 'entry'},
            )
            misc_reverse = (
                move.move_type in ('entry', 'out_refund', 'in_refund')
                and remaining_types == {'entry'}
            )
            if not (in_reverse or out_reverse or misc_reverse):
                move.payment_state = 'paid'

    @api.depends(
        'posted_before', 'state', 'journal_id', 'date', 'move_type',
        'origin_payment_id', 'l10n_ve_exchange_diff_entry',
        'l10n_ve_exchange_original_id',
    )
    def _compute_name_by_sequence(self):
        """Numbers exchange difference Debit/Credit Notes with their own
        sequence (`l10n_ve_exchange_debit_note_sequence_id` for Debit
        Notes, native `refund_sequence_id` for Credit Notes) instead of
        the journal's normal sequence -- hooked here, not in
        `_compute_name`, because `od_journal_sequence` already replaced
        that native compute."""
        # OJO: filtro deliberadamente MÁS AMPLIO que
        # `_is_exchange_debit_note()`/`_is_exchange_credit_note()` --
        # esos dos excluyen a propósito cualquier documento con
        # `l10n_ve_exchange_original_id` ya seteado (para no confundir
        # la REVERSIÓN de una nota con una ND/NC genuina en la lógica de
        # negocio, ver sus propios docstrings). Pero eso significa que la
        # reversión de una NC directa (`out_invoice`,
        # `l10n_ve_exchange_diff_entry=True`, con `original_id` seteado
        # por `_reverse_moves` más abajo) no matchea NINGUNO de los dos
        # helpers y caía al numerador normal del diario -- consumiendo un
        # correlativo de FACTURA real (bug real, confirmado en runtime).
        # Para efectos de NUMERACIÓN (a diferencia de clasificación de
        # negocio), lo único que importa es el `move_type`: cualquier
        # documento propio (nota directa O reversión) tipo `out_invoice`
        # se numera con la secuencia de ND; tipo `out_refund`, con la de
        # NC -- exactamente simétrico a como ya se trataba la reversión
        # de una ND (sale `out_refund`, y sí matcheaba
        # `_is_exchange_credit_note()` porque esa NO excluye
        # `original_id`).
        exchange_moves = self.filtered(
            lambda m: m.l10n_ve_exchange_diff_entry
            and m.move_type in ('out_invoice', 'out_refund')
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

            sequence = (
                move.journal_id.l10n_ve_exchange_debit_note_sequence_id
                if move.move_type == 'out_invoice'
                else move.journal_id.refund_sequence_id
            )

            if sequence and move.date:
                # `sequence_date` explícito -- estas notas se emiten con
                # `date`/`invoice_date` BACKDATEADO a la fecha del pago
                # (nunca la de hoy, ver `account_move_line.py`), y
                # `ir.sequence.next_by_id()` sin `sequence_date` usa la
                # fecha de HOY para decidir el rango vigente cuando la
                # secuencia tiene `use_date_range=True` (el caso normal,
                # ver `od_journal_sequence._prepare_sequence`) -- sin
                # esto, una nota backdateada a un mes/año anterior
                # tomaría el correlativo del rango de HOY, no el del mes
                # al que en realidad pertenece. Mismo patrón que
                # `od_journal_sequence.account_move._compute_name_by_sequence`.
                if isinstance(move.date, date) and not isinstance(move.date, datetime):
                    sequence_date = datetime.combine(move.date, datetime.min.time())
                else:
                    sequence_date = fields.Datetime.to_datetime(move.date)
                # El kwarg `sequence_date` de `next_by_id()` SOLO afecta
                # la rama `use_date_range=True` de `ir.sequence._next()`
                # (`odoo/addons/base/models/ir_sequence.py`): si la
                # secuencia NO usa rangos por fecha (el caso normal
                # cuando el usuario crea la secuencia dedicada de ND a
                # mano por la UI, sin pasar por
                # `od_journal_sequence._prepare_sequence`, que sí fuerza
                # `use_date_range=True`), cae a `_next_do()`, que ignora
                # el kwarg por completo y arma el prefijo (`%(year)s`)
                # con `datetime.now()` salvo que la fecha venga por
                # CONTEXTO (`ir_sequence_date`) -- sin esto, una ND
                # backdateada seguía saliendo con el año de HOY en el
                # prefijo aunque el kwarg estuviera bien pasado.
                move.name = sequence.with_context(
                    ir_sequence_date=fields.Datetime.to_string(sequence_date),
                ).next_by_id(sequence_date=sequence_date)
                # `od_journal_sequence` (`models/account_move.py`) ya
                # reemplazó el compute NATIVO de `name` -- en core,
                # `payment_reference` depende de `name` vía la cadena de
                # `@api.depends` nativa, así que asignar `move.name`
                # DIRECTO acá (sin pasar por ningún compute que lo
                # dispare) nunca recalcula `payment_reference`. Mismo
                # patrón que ya usa `od_journal_sequence` para sus
                # propias asignaciones directas: sin esto, toda ND/NC de
                # este módulo quedaba con `payment_reference` vacío
                # (relevante para conciliación bancaria/matching).
                move._compute_payment_reference()
            else:
                # NUNCA caer al numerador normal del diario para un
                # documento que es NUESTRO (`exchange_moves`, filtrado
                # arriba): ese numerador es el de facturas/NC del propio
                # diario -- consumir un correlativo de ahí para una ND/NC
                # de diferencial es exactamente el bug que este módulo
                # existe para evitar (confirmado en runtime: una
                # reversión de ND cayendo acá salía numerada con la
                # secuencia PRINCIPAL del diario dedicado de ND, la misma
                # que usa `l10n_ve_invoice`/`l10n_ve_iot_mf` para
                # identificar Notas de Débito reales de cliente vía
                # `journal_id.is_debit`). Si llegamos aquí es porque la
                # secuencia dedicada esperada (`l10n_ve_exchange_debit_note_sequence_id`
                # para ND, `refund_sequence_id` para NC) no está
                # configurada en el diario de este `move` -- un fallo de
                # configuración que debe abortar la conciliación, no
                # numerar en silencio con un correlativo ajeno.
                raise UserError(_(
                    "Cannot number this exchange difference Debit/Credit "
                    "Note: journal %(journal)s has no dedicated sequence "
                    "configured for %(kind)s (date=%(date)s). Configure "
                    "the journal before reconciling foreign-currency "
                    "invoices with the exchange difference Debit/Credit "
                    "Note mode enabled.",
                    journal=move.journal_id.display_name,
                    kind=_("Debit Notes") if move.move_type == 'out_invoice' else _("Credit Notes"),
                    date=move.date,
                ))

    def _sequence_matches_date(self):
        """Exchange difference Debit/Credit Notes (and their reversals)
        use their own dedicated sequence, unrelated to the journal's --
        validating them against the native sequence's date makes no
        sense.

        Scoped to `move_type in ('out_invoice', 'out_refund')` -- without
        it, this also matched Odoo's own GENERIC exchange-difference
        entries that `_prepare_exchange_difference_move_vals`
        (`account_move_line.py`) tags with `l10n_ve_exchange_diff_entry`
        purely for traceability (vendor bills, misc entries, any line
        that fell to `remaining_lines`), which are NOT ND/NC and DO still
        use the journal's normal sequence -- skipping Odoo's native
        sequence-date validation for those was never correct."""
        if (
            self.move_type in ('out_invoice', 'out_refund')
            and (self.l10n_ve_exchange_diff_entry or self.l10n_ve_exchange_original_id)
        ):
            return True
        return super()._sequence_matches_date()

    def js_remove_outstanding_partial(self, partial_id):
        """Blocks breaking the note<->invoice/payment reconciliation
        DIRECTLY from the payments widget (that should only be undone as
        a consequence of breaking the invoice<->payment one). The actual
        reversal of the note when the invoice<->payment reconciliation
        IS broken doesn't happen here anymore -- see
        `account.partial.reconcile.unlink()`
        (`models/account_partial_reconcile.py`), the lower level where
        this delegates via `super()`."""
        self.ensure_one()
        partial = self.env['account.partial.reconcile'].browse(partial_id)
        related_moves = partial.debit_move_id.move_id | partial.credit_move_id.move_id

        if any(related_moves.mapped('l10n_ve_exchange_diff_entry')):
            raise UserError(_(
                "You cannot directly unreconcile an exchange difference "
                "Debit/Credit Note. To undo it, break the original "
                "reconciliation between the invoice and the payment -- the "
                "note will be reversed automatically."
            ))

        # Solo se necesita ANTES de romper la conciliación (para el
        # `UserError` de arriba): la búsqueda/reversión de la nota en sí
        # ya no ocurre acá -- ver `account.partial.reconcile.unlink()`
        # (`models/account_partial_reconcile.py`), que engancha la
        # reversión al nivel donde de verdad convergen TODAS las formas
        # de romper una conciliación (este botón, pero también
        # `remove_move_reconcile()` usado directo por otros módulos, ej.
        # `l10n_ve_igtf` para cancelar pagos anticipados -- antes de ese
        # cambio, romper la conciliación por esa otra vía dejaba la nota
        # huérfana: posteada, con folio fiscal consumido, sin revertir).
        return super().js_remove_outstanding_partial(partial_id)

    @api.model
    def _l10n_ve_exchange_note_for_partial(self, partial):
        """Returns the (single) exchange difference Debit/Credit Note tied
        to the invoice/payment pair that `partial`
        (`account.partial.reconcile`) reconciles -- an empty recordset if
        `partial` doesn't tie an invoice to a payment, or no such note
        exists (already reversed, or none was ever generated for that
        pair). Used by `account.partial.reconcile.unlink()`
        (`models/account_partial_reconcile.py`) -- kept as a separate
        `account.move` method (instead of inlined there) so the query
        that decides WHICH note a broken reconciliation reverses lives
        next to `_reverse_exchange_note`, the method that actually
        reverses it."""
        related_moves = partial.debit_move_id.move_id | partial.credit_move_id.move_id
        invoice = related_moves.filtered(
            lambda m: m.move_type in ('out_invoice', 'out_refund')
        )[:1]
        payment = related_moves - invoice
        if not invoice:
            return self.browse()
        # Buscada por (factura, pago) y no solo por factura: una misma
        # factura pagada en varias cuotas puede acumular una ND/NC
        # distinta por cada pago parcial (ver `l10n_ve_exchange_payment_id`)
        # -- al romper la conciliación de UN pago puntual, solo debe
        # revertirse la nota de ESE pago.
        #
        # `.sudo()` -- mismo motivo que ya justifica el `.sudo()` en las
        # búsquedas de `account.journal` (C3): `account.move` también
        # tiene reglas multi-compañía que filtran por las compañías
        # PERMITIDAS del usuario/proceso que rompe la conciliación, no
        # por la compañía de la factura.
        #
        # A propósito, el `sudo()` acá NO se acota solo al `search()`
        # (a diferencia del de C3/las búsquedas de diario) -- se
        # propaga al recordset devuelto, y de ahí a TODA la reversión
        # que el caller dispara sobre él (`_reverse_exchange_note()`,
        # `account_partial_reconcile.unlink()`). Probado primero acotado
        # (`.with_env(self.env)` después del `search()`): el resultado
        # era peor que el bug original -- el `search()` SÍ encontraba la
        # nota, pero la reversión corría con los permisos normales de
        # quien rompe la conciliación (que son justo los que no le
        # alcanzan), y el `AccessError` resultante abortaba el
        # `unlink()` COMPLETO -- cambiando "la nota queda huérfana en
        # silencio" por "nadie puede desconciliar", peor para el usuario
        # legítimo y sin resolver tampoco el caso del cron.
        #
        # Revertir una ND/NC de diferencial es una operación de
        # INTEGRIDAD DEL SISTEMA, no una acción del usuario accediendo a
        # datos de otra compañía a propósito: se dispara automáticamente
        # como consecuencia de romper la conciliación factura-pago
        # (`account.partial.reconcile.unlink()`), nunca porque alguien
        # pidió ver o tocar esa nota directamente. Es coherente con que
        # este módulo ya crea y postea la nota sin pedirle permisos
        # extra al usuario en primer lugar.
        return self.sudo().search([
            ('l10n_ve_exchange_invoice_id', '=', invoice.id),
            ('l10n_ve_exchange_payment_id', '=', payment.id),
            ('state', '!=', 'cancel'),
            ('reversal_move_ids', '=', False),
        ], order='id desc', limit=1)

    def _reverse_exchange_note(self):
        """Reverses this exchange difference Debit/Credit Note because the
        invoice/payment reconciliation that originated it is being broken
        -- an already posted fiscal document (with a real sequence number)
        gets reversed, never cancelled or deleted."""
        self.ensure_one()
        if self.state == 'draft':
            self.unlink()
            return
        if self.state != 'posted':
            return
        # `l10n_ve_skip_refund_origin_validation` -- todavía un no-op (ver
        # nota completa en `_create_exchange_difference_note`,
        # `account_move_line.py`): reversar una ND produce una NC
        # (`out_refund`) que tampoco debe validarse contra el producto de
        # su ND de origen cuando esa validación externa exista.
        self.with_context(
            move_reverse_cancel=True,
            l10n_ve_skip_refund_origin_validation=True,
        )._reverse_moves(
            default_values_list=[{
                'ref': _('Reversal of: %s', self.name),
                'l10n_ve_exchange_diff_entry': True,
                'l10n_ve_exchange_invoice_id': self.l10n_ve_exchange_invoice_id.id,
            }],
            cancel=True,
        )

    def _reverse_moves(self, default_values_list=None, cancel=False):
        """When reversing any of this module's own exchange difference
        notes -- a Debit Note (ND) OR a Credit Note (NC, whether issued
        directly or itself already a reversal of a ND) -- links the
        reversal via `l10n_ve_exchange_original_id` instead of letting it
        be numbered with the normal sequence.

        Checked via `l10n_ve_exchange_diff_entry` (true for ANY of our
        own notes), not `_is_exchange_debit_note()` alone: reversing a
        NC produces an `out_invoice` reversal that, without
        `l10n_ve_exchange_original_id` set, would satisfy
        `_is_exchange_debit_note()` on its own merits (right `move_type`,
        no `original_id`/`is_credit_note` set) -- misclassifying a mere
        reversal as a genuine new ND, consuming the (already scarce)
        dedicated ND sequence for a document that isn't actually one."""
        if default_values_list is None:
            default_values_list = [{} for _ in self]

        for move, default_values in zip(self, default_values_list):
            # SIN gate por `move.company_id.l10n_ve_exchange_use_nd_nc`
            # (el estado ACTUAL del toggle) -- ya se corrigió este mismo
            # patrón en `account.partial.reconcile.unlink()`
            # (`models/account_partial_reconcile.py`, B1/B2): una nota
            # emitida mientras el toggle estaba activo debe poder
            # revertirse correctamente aunque el toggle se desactive
            # DESPUÉS. Gatear por el toggle actual aquí dejaba la
            # reversión SIN el flag/numeración propios -- cayendo al
            # numerador normal del diario -- exactamente el mismo bug,
            # solo que por esta otra vía (`_reverse_moves`, no
            # `unlink()`). `l10n_ve_exchange_diff_entry` (`copy=False`,
            # nunca seteado fuera de este módulo) ya identifica de forma
            # confiable "es una nota nuestra", sin necesitar el toggle.
            if (
                move.l10n_ve_exchange_diff_entry
                and move.move_type in ('out_invoice', 'out_refund')
            ):
                # `l10n_ve_exchange_diff_entry` FORZADO acá, no asumido
                # "copiado" -- el campo tiene `copy=False`, y core arma
                # la reversión con `move.copy(default_values)`
                # (`account/models/account_move.py`), así que sin
                # pasarlo explícito la reversión nace con el flag en
                # `False`. Nuestro propio `_reverse_exchange_note` YA lo
                # pasa en su propio `default_values_list`, así que hasta
                # acá nunca se notó -- pero cualquier otro camino que
                # llame `_reverse_moves()` sobre una de nuestras notas
                # (ej. el wizard estándar de Odoo, "Reverse Entry" desde
                # la UI, disponible en cualquier factura posteada)
                # producía una reversión con `diff_entry=False`, que el
                # filtro de `_compute_name_by_sequence` (más abajo) ya no
                # reconocía como propia -- bug real, confirmado en
                # runtime: la reversión caía al numerador normal del
                # diario, consumiendo un correlativo ajeno.
                #
                # OJO con `'name'`: a propósito NO se fuerza acá (a
                # diferencia de antes). `name` (núcleo,
                # `account/models/account_move.py`) tiene
                # `inverse='_inverse_name'` además de `compute` -- pasar
                # un valor explícito para él en `default_values` (como
                # `'/'`) dispara el inverse, y Odoo entonces trata ese
                # valor como una escritura MANUAL del usuario: lo saca
                # para siempre de la cola de recómputo automático por
                # dependencia (mismo mecanismo que respeta un número de
                # factura tipeado a mano en el form, para no pisarlo
                # solo porque cambió el diario). Confirmado en runtime:
                # con `'name': '/'` explícito acá, `_compute_name_by_sequence`
                # NUNCA se volvía a invocar para la reversión al
                # postearla (ni una sola vez, ver log de depuración),
                # así que se quedaba en '/' para siempre. Sin pasarlo,
                # el propio compute de acá abajo (`move.name = move.name
                # or '/'`) le da el mismo '/' de exhibición mientras está
                # en borrador, pero por la vía de COMPUTE normal -- que
                # SÍ se re-dispara cuando `state` cambia a `posted`.
                default_values.update({
                    'l10n_ve_exchange_diff_entry': True,
                    'l10n_ve_exchange_original_id': move.id,
                })
                if move.move_type == 'out_refund':
                    # Revertir una NC DIRECTA produce un `out_invoice` --
                    # ese documento se numera con la secuencia DEDICADA
                    # de ND (ver el ternario en
                    # `_compute_name_by_sequence`), que solo puede
                    # resolverse si el documento vive en el diario que
                    # tiene esa secuencia asignada
                    # (`l10n_ve_exchange_debit_note_sequence_id` es un
                    # campo de `account.journal`, no de la nota). Sin
                    # esto, la reversión hereda por copia el diario de
                    # venta NORMAL de la NC original (el mismo de la
                    # factura de origen) y cae al numerador de FACTURAS
                    # de ese diario -- bug real, confirmado en runtime
                    # (reversión de NC saliendo `INV/.../0001`). Mismo
                    # lookup que usa `_create_exchange_difference_note`
                    # al emitir una ND nueva.
                    #
                    # `.sudo()` -- `journal_comp_rule` (núcleo) filtra
                    # `account.journal` por las compañías PERMITIDAS del
                    # usuario/proceso que dispara la reversión, no por
                    # `move.company_id`. Sin esto, un cron o un usuario
                    # de otra sucursal sin esa compañía en
                    # `allowed_company_ids` encuentra el diario vacío en
                    # SILENCIO (`if debit_journal and ...`, sin
                    # `UserError`), y la reversión de la NC queda
                    # numerada con el diario de venta normal en vez del
                    # dedicado -- exactamente el bug que este bloque
                    # existe para evitar, solo que por una vía distinta.
                    debit_journal = self.env['account.journal'].sudo().search([
                        ('company_id', '=', move.company_id.id),
                        ('is_debit', '=', True),
                        ('type', '=', 'sale'),
                    ], order='id', limit=1)
                    # Explícito acá, no confiar en que
                    # `_compute_name_by_sequence` lo atrape después: si
                    # no se redirige `journal_id`, la reversión hereda
                    # por copia el diario de venta NORMAL de la factura
                    # -- y como ese diario típicamente SÍ tiene su propio
                    # `refund_sequence_id` (numera sus propias NC de
                    # negocio con normalidad), `_compute_name_by_sequence`
                    # encontraría una secuencia "válida" ahí y numeraría
                    # la reversión con el correlativo de NC de ese
                    # diario -- consumiendo un folio de NC de NEGOCIO en
                    # silencio, sin lanzar ningún error (a diferencia del
                    # caso donde ese diario tampoco tiene refund_sequence,
                    # que sí queda cubierto por el `UserError` de
                    # `_compute_name_by_sequence`). Ese fallback silencioso
                    # es exactamente el tipo de bug que este bloque existe
                    # para evitar -- fallar acá mismo, en el punto exacto
                    # donde se detecta, en vez de confiar en que otro
                    # método más abajo en la cadena lo atrape (y solo lo
                    # atrapa a medias).
                    if not debit_journal or not debit_journal.l10n_ve_exchange_debit_note_sequence_id:
                        raise UserError(_(
                            "Configure a sale journal with 'Is Debit' "
                            "enabled and its dedicated Exchange Difference "
                            "Debit Note sequence assigned before reversing "
                            "this exchange difference Credit Note -- the "
                            "reversal must never be numbered with the "
                            "invoice journal's own Credit Note sequence."
                        ))
                    default_values['journal_id'] = debit_journal.id
                else:
                    # Revertir una ND (`out_invoice`) produce un
                    # `out_refund` que -- a diferencia del caso de arriba
                    # -- NO necesita redirigirse de diario: por
                    # construcción, una ND siempre vive YA en el diario
                    # dedicado (`is_debit=True`, ver
                    # `_create_exchange_difference_note`,
                    # `account_move_line.py`), así que la reversión lo
                    # hereda por copia sin más. Lo que sí falta puede ser
                    # que ESE diario tenga su propia `refund_sequence_id`
                    # configurada -- el `UserError` de pre-vuelo al crear
                    # la ND solo exige `l10n_ve_exchange_debit_note_sequence_id`
                    # (la secuencia de ND), nunca la de NC de ese mismo
                    # diario.
                    #
                    # NO se autoprovisiona acá -- a propósito, a
                    # diferencia de una versión anterior de este mismo
                    # bloque: ese diario `is_debit=True` NO es exclusivo
                    # de este módulo, es infraestructura fiscal REAL que
                    # `l10n_ve_invoice`/`l10n_ve_iot_mf` usan para
                    # identificar Notas de Débito de NEGOCIO genuinas
                    # (`journal_id.is_debit`) -- exactamente el mismo
                    # riesgo que ya se corrigió en la rama de NC directa
                    # de `_create_exchange_difference_note`
                    # (`account_move_line.py`): autoprovisionar con
                    # `sudo()` sería un cambio PERMANENTE y silencioso en
                    # la numeración fiscal de un diario de negocio real,
                    # disparado por quien sea que rompa una conciliación.
                    # Ser simétrico con esa decisión: `UserError`
                    # explícito pidiendo configuración, en vez de
                    # numerar en silencio o mutar el diario.
                    debit_journal = move.journal_id
                    if debit_journal.is_debit and not debit_journal.refund_sequence_id:
                        raise UserError(_(
                            "Configure a dedicated 'Refund Sequence' (Credit "
                            "Note sequence) on journal %(journal)s before "
                            "reversing this exchange difference Debit Note "
                            "-- the reversal must never be numbered with "
                            "that journal's own main sequence.",
                            journal=debit_journal.display_name,
                        ))

        return super()._reverse_moves(default_values_list, cancel=cancel)
