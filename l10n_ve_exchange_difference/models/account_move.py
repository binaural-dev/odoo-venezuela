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
        # `.sudo()` en el `search()` -- mismo motivo que ya justifica el
        # `.sudo()` en las búsquedas de `account.journal` (C3):
        # `account.move` también tiene reglas multi-compañía que filtran
        # por las compañías PERMITIDAS del usuario/proceso que rompe la
        # conciliación, no por la compañía de la factura. Sin esto, un
        # cron o un usuario de otra sucursal sin esa compañía en
        # `allowed_company_ids` nunca ENCUENTRA la nota -- no falla
        # ruidoso, simplemente la deja posteada, con folio fiscal
        # consumido, sin revertir.
        #
        # `.with_env(self.env)` al final -- el `sudo()` es SOLO para
        # que el `search()` pueda VER la nota más allá de las
        # compañías permitidas del usuario; la reversión en sí
        # (`_reverse_exchange_note`, disparada por el caller sobre el
        # resultado de este método) debe seguir corriendo con los
        # permisos NORMALES de quien la dispara, no heredar `sudo()`
        # de arrastre sobre TODO lo que haga después con este recordset.
        found = self.sudo().search([
            ('l10n_ve_exchange_invoice_id', '=', invoice.id),
            ('l10n_ve_exchange_payment_id', '=', payment.id),
            ('state', '!=', 'cancel'),
            ('reversal_move_ids', '=', False),
        ], order='id desc', limit=1)
        return found.with_env(self.env)

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
                    if debit_journal and debit_journal.l10n_ve_exchange_debit_note_sequence_id:
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
