from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def reconcile(self):
        """When reconciling customer invoices (`out_invoice`/`out_refund`)
        whose company has the exchange difference Debit/Credit Note flow
        enabled, lets Odoo's native reconciliation run WITHOUT suppressing
        its exchange-difference computation (`no_exchange_difference` is
        never set here) -- Odoo's own engine is what reliably determines,
        for ANY combination of partial/full/grouped payments, exactly
        which lines still need a currency correction and by how much.
        `_prepare_exchange_difference_move_vals` below intercepts that
        computation for qualifying lines and queues a real Debit/Credit
        Note for them instead of letting Odoo create its generic entry --
        actually created in `_create_exchange_difference_moves`, at the
        exact point in the same reconciliation transaction where Odoo
        itself creates its own generic entry (see that method's
        docstring for why the timing matters).

        The candidate payment lines are passed through context
        (`l10n_ve_exchange_payment_line_ids`) because
        `_prepare_exchange_difference_move_vals` only receives the
        line(s) needing a fix, not the counterpart they were reconciled
        against.
        """
        invoice_lines = self.filtered(
            lambda l: (
                l.account_type == 'asset_receivable'
                and l.move_id.move_type in ('out_invoice', 'out_refund')
                and l.company_id.l10n_ve_exchange_use_nd_nc
                and not l.move_id.debit_origin_id
                and not l.move_id.reversed_entry_id
                and not getattr(l.move_id, 'l10n_ve_igtf_note_debit_origin', False)
                # Nunca una nota (o la reversión de una nota) generada por
                # este propio módulo -- ej. al desconciliar y revertir una
                # ND, `_reverse_moves` reconcilia la reversión contra la
                # ND original; sin este guard, esa reconciliación
                # calificaría igual como "factura de cliente" y
                # dispararía una SEGUNDA reversión/nota espuria.
                and not l.move_id.l10n_ve_exchange_diff_entry
                and not l.move_id.l10n_ve_exchange_original_id
            )
        )
        if not invoice_lines:
            return super().reconcile()
        payment_lines = (self - invoice_lines).filtered(
            lambda l: l.account_type == 'asset_receivable'
        )

        return super(AccountMoveLine, self.with_context(
            l10n_ve_exchange_payment_line_ids=payment_lines.ids,
            l10n_ve_exchange_invoice_line_ids=invoice_lines.ids,
        )).reconcile()

    def _prepare_reconciliation_single_partial(self, debit_values, credit_values, shadowed_aml_values=None):
        """Stashes the REAL pairing of this single partial (`debit_values['aml']`,
        `credit_values['aml']`) on the cursor right before delegating to
        `super()` -- `super()` calls our own
        `_prepare_exchange_difference_move_vals` override synchronously,
        from inside this very call, for whichever of the two lines needs
        a currency fix. That override reads (and clears) this stash to
        find the EXACT counterpart line Odoo just matched, instead of
        guessing which candidate invoice a payment-side residual belongs
        to when a grouped payment has more than one -- a per-payment
        round-robin guess used to be the only option here (no direct
        access to the counterpart otherwise) and could silently attribute
        a residual to the WRONG invoice when their amounts differ (see
        `test_grouped_payment_gain_direction_invoice_attribution_is_exact`,
        which exposed exactly this by using two invoices of different
        amounts -- confirmed with a real swap before this fix).

        NOTE on core coupling: this overrides an INTERNAL method of
        Odoo's reconciliation engine (`account.move.line`, core
        `addons/account/models/account_move_line.py`), not the public
        `_prepare_exchange_difference_move_vals` hook this module
        otherwise relies on -- verified against Odoo 19.0-20260710,
        where the signature is exactly
        `(self, debit_values, credit_values, shadowed_aml_values=None)`
        and `debit_values['aml']`/`credit_values['aml']` hold the two
        matched lines. If a future Odoo 19.x point release changes this
        signature or drops the `'aml'` key, the `**kwargs`-less call
        below raises a loud `TypeError` on the very next reconciliation
        instead of silently mis-attributing notes -- deliberately NOT
        swallowed with a `try/except`, so an incompatible core update
        fails fast instead of guessing again."""
        # Runtime guard: verify the expected keys exist before stashing
        # (line 1: signature change is caught by TypeError above, but key
        # changes are silent -- catch them here as early as possible).
        if 'aml' not in debit_values or 'aml' not in credit_values:
            # `UserError`, no `RuntimeError` -- ambos abortan la
            # transacción igual de ruidoso, pero un `RuntimeError` sale
            # al usuario como "Internal Server Error" genérico (Odoo solo
            # muestra en un diálogo legible las excepciones que hereden
            # de `odoo.exceptions.UserError`/`ValidationError`); el
            # mensaje de abajo, cuidadosamente redactado y traducido con
            # `_()` para explicar justo esto, nunca llegaría a
            # mostrarse.
            raise UserError(_(
                "Odoo core API incompatibility detected in "
                "`_prepare_reconciliation_single_partial`: expected keys "
                "'aml' in debit_values and credit_values, but got "
                "debit_values.keys()=%(debit_keys)s, credit_values.keys()=%(credit_keys)s. "
                "This module is tightly coupled to Odoo 19.0-20260710 internal API. "
                "Reconciliation aborted to prevent silent mis-attribution of "
                "exchange difference notes to the wrong invoice.",
                debit_keys=', '.join(debit_values.keys()),
                credit_keys=', '.join(credit_values.keys()),
            ))
        self.env.cr._l10n_ve_exchange_current_partial_amls = (debit_values['aml'], credit_values['aml'])
        try:
            return super()._prepare_reconciliation_single_partial(
                debit_values, credit_values, shadowed_aml_values=shadowed_aml_values,
            )
        finally:
            # `try/finally`, no un simple `return` -- este stash vive en
            # un atributo plano del CURSOR, no en una transacción ORM:
            # un rollback a SAVEPOINT (`Savepoint.rollback()`, núcleo
            # `sql_db.py`) no dispara `cr.postrollback` (ese hook SOLO
            # corre en un rollback de cursor completo, nunca en uno a
            # savepoint -- y los savepoints son exactamente lo que usa
            # `TransactionCase` entre tests, y cualquier
            # `@api.constrains`/guard interno de Odoo). Sin este
            # `finally`, si `super()` (que llama SINCRÓNICAMENTE a
            # `_prepare_exchange_difference_move_vals` desde adentro,
            # ver docstring de ese método) lanzara una excepción ANTES
            # de que ese método alcance a leer y limpiar este mismo
            # atributo, el stash sobreviviría un rollback a savepoint y
            # podría filtrarse a un partial NO relacionado en un intento
            # posterior sobre el mismo cursor.
            self.env.cr._l10n_ve_exchange_current_partial_amls = None

    def _prepare_exchange_difference_move_vals(
        self, amounts_list, company=None, exchange_date=None, **kwargs
    ):
        """Odoo calls this with `self` = the line(s) whose residual still
        needs a currency correction, and `amounts_list` = the exact
        amount computed for each (`{'amount_residual': X}`, in company
        currency). This is authoritative: Odoo already determined it
        correctly for the specific partial/full/grouped reconciliation
        just performed, immune to the drift and cross-currency
        apportionment issues a hand-rolled recomputation runs into
        across multiple installments on the same invoice.

        For each line that belongs to a CUSTOMER invoice/note under this
        company's ND/NC toggle (and isn't itself a derived note/payment
        correction), that amount is queued (`self.env.cr` -- a plain
        list, NOT `precommit`) for `_create_exchange_difference_moves`
        below to actually create as a real Debit/Credit Note, INSTEAD of
        being passed to Odoo's own generic entry here -- so Odoo never
        creates nor reconciles anything for that line. Any other line
        (vendor bills, misc entries, toggle disabled) still gets Odoo's
        untouched native behaviour, just tagged as before for
        identification.

        Queueing here (called BEFORE the reconciliation's own partials
        exist in the database yet -- too early to create/close a note
        against an accurate residual) instead of creating inline is
        exactly why `_create_exchange_difference_moves` is also
        overridden below, instead of doing everything here.
        """
        payment_line_ids = self.env.context.get('l10n_ve_exchange_payment_line_ids')
        invoice_line_ids = self.env.context.get('l10n_ve_exchange_invoice_line_ids')
        payment_lines = self.env['account.move.line'].browse(payment_line_ids) if payment_line_ids else self.env['account.move.line']
        invoice_lines_ctx = self.env['account.move.line'].browse(invoice_line_ids) if invoice_line_ids else self.env['account.move.line']
        default_payment = payment_lines[:1].move_id

        partial_amls = getattr(self.env.cr, '_l10n_ve_exchange_current_partial_amls', None)
        self.env.cr._l10n_ve_exchange_current_partial_amls = None
        counterpart_of = self.env['account.move.line']
        if partial_amls:
            counterpart_of = partial_amls[0] + partial_amls[1]

        pending_notes = []
        remaining_lines = []
        remaining_amounts = []
        for line, amounts in zip(self, amounts_list):
            # El ajuste puede caer del lado de la FACTURA (caso común) o
            # del lado del PAGO (Odoo suele atribuírselo así en la
            # dirección de ganancia). En AMBOS casos se prefiere la
            # pareja REAL de este partial puntual, ya dejada en
            # `partial_amls` por `_prepare_reconciliation_single_partial`
            # (sobrescrito arriba) -- nunca se adivina por orden (un pago
            # agrupado con más de una factura candidata de montos
            # distintos SÍ puede confundir cuál residual pertenece a cuál
            # factura si solo se mira el orden de aparición, confirmado
            # con `test_grouped_payment_gain_direction_invoice_attribution_is_exact`).
            # `default_payment` (`payment_lines[:1]`, adivinado por
            # orden) solo se usa como ÚLTIMO fallback si `counterpart_of`
            # no trajo nada -- ej. algún camino de reconciliación que no
            # pase por `_prepare_reconciliation_single_partial`. Antes,
            # la rama del lado-factura (este `if`) usaba SIEMPRE
            # `default_payment`, aun cuando `counterpart_of` ya tenía la
            # pareja real -- si un solo `reconcile()` empareja una
            # factura contra más de una línea de pago (ej.
            # `binaural_advance_payment`/`binaural_mobile`, que llaman
            # `.reconcile()` con conjuntos arbitrarios de líneas), TODAS
            # las notas de esa factura quedaban atribuidas al primer
            # pago -- dejando las demás huérfanas al desconciliar el pago
            # real, con fecha/tasa del pago equivocado.
            if line in invoice_lines_ctx:
                invoice_line, invoice = line, line.move_id
                # Guard de singleton explícito -- si `line` no es
                # realmente parte de la pareja estampada en
                # `counterpart_of` (stash vacío o desactualizado; ver
                # docstring de `_prepare_reconciliation_single_partial`),
                # `counterpart_of - line` devuelve el par SIN restar
                # nada (2 líneas), y leer `.move_id` sobre un recordset
                # de más de un registro revienta con
                # `ValueError: Expected singleton` en vez de caer al
                # fallback.
                real_counterpart = counterpart_of - line
                payment = real_counterpart.move_id if len(real_counterpart) == 1 else default_payment
            elif line in payment_lines and (counterpart_of - line) & invoice_lines_ctx:
                invoice_line = (counterpart_of - line) & invoice_lines_ctx
                invoice, payment = invoice_line.move_id, line.move_id
            else:
                invoice_line = None

            company_of_line = invoice.company_id if invoice_line is not None else None
            is_own_invoice_line = invoice_line is not None and (
                company_of_line.l10n_ve_exchange_use_nd_nc
                and invoice.move_type in ('out_invoice', 'out_refund')
                and not invoice.debit_origin_id
                and not invoice.reversed_entry_id
                and not getattr(invoice, 'l10n_ve_igtf_note_debit_origin', False)
            )
            residual = amounts.get('amount_residual')
            if (
                is_own_invoice_line
                and payment
                and residual is not None
                and not company_of_line.currency_id.is_zero(residual)
            ):
                pending_notes.append({
                    'line': line, 'invoice': invoice, 'payment': payment, 'residual': residual,
                })
            else:
                remaining_lines.append(line)
                remaining_amounts.append(amounts)

        if pending_notes:
            queued = getattr(self.env.cr, '_l10n_ve_exchange_pending_notes', None)
            if queued is None:
                queued = []
                self.env.cr._l10n_ve_exchange_pending_notes = queued
            queued.extend(pending_notes)

        if not remaining_lines:
            # NUNCA `None`: el núcleo de Odoo, justo después de llamar a
            # este método, hace `res['exchange_values']['to_post'] = ...`
            # sin chequear `None` -- solo el llamador MÁS ARRIBA (que
            # arma `exchange_diff_values_list`) sí chequea
            # `results['exchange_values']['move_values']['line_ids']`
            # como falsy. Un dict con `line_ids` vacío sobrevive la
            # primera asignación y queda descartado en la segunda,
            # sin crear ni conciliar ningún asiento genérico.
            return {'move_values': {'line_ids': []}}

        remaining = self.browse([l.id for l in remaining_lines])
        res = super(AccountMoveLine, remaining)._prepare_exchange_difference_move_vals(
            remaining_amounts, company=company, exchange_date=exchange_date, **kwargs
        )
        if not res:
            return res

        # Se etiqueta CUALQUIER asiento genérico que Odoo termine creando
        # con el toggle de la compañía activo -- para trazabilidad, sin
        # importar el motivo por el que la línea cayó en `remaining`
        # (proveedor, asiento misceláneo, o un documento de cliente con
        # `debit_origin_id`/`reversed_entry_id` propios de OTRO proceso de
        # negocio, sin relación con este módulo). No se excluye por tener
        # esos campos: eso solo describía documentos ajenos a este módulo,
        # que igual merecen la misma trazabilidad que un asiento genérico
        # cualquiera (ver `test_fallback_tags_generic_exchange_move_for_vendor_bill`/
        # `test_fallback_tags_generic_exchange_move_for_misc_entries`).
        company = (remaining.move_id.company_id or company)[:1]
        if company.l10n_ve_exchange_use_nd_nc:
            res['move_values']['l10n_ve_exchange_diff_entry'] = True

        return res

    @api.model
    def _create_exchange_difference_moves(self, exchange_diff_values_list):
        """Odoo calls this exactly ONCE per `.reconcile()` transaction,
        right after ALL the partials of the reconciliation (the actual
        invoice<->payment matches) are created in the database, but
        BEFORE it decides which lines are now fully closed
        (`full_reconcile_id`). That timing window is the whole reason
        this method (and not `_prepare_exchange_difference_move_vals`,
        which runs too early -- before those partials exist, so a
        line's real remaining residual isn't settled yet) is where the
        queued Debit/Credit Notes actually get created and closed: doing
        it any later (e.g. in a `precommit`, after the whole transaction
        already ran) means Odoo has ALREADY marked the line as fully
        reconciled on its own by then for some currency combinations
        (company-currency invoice against a foreign-currency payment),
        and trying to reconcile a note against it afterwards raises
        "you are trying to reconcile some entries that are already
        reconciled".

        The queue is consumed (popped, not just read) BEFORE creating
        any note, because posting/closing a note can itself trigger a
        nested reconciliation (closing the note's own receivable line)
        that runs through this same override again -- it must find an
        empty queue, not reprocess (or duplicate) what the outer call
        already claimed.

        Only OUR queued entries are handled here; `exchange_diff_values_list`
        (Odoo's own generic-entry batch, potentially covering vendor
        bills, misc entries, other companies, or invoices with the ND/NC
        toggle off in the same transaction) is passed to `super()`
        completely untouched.
        """
        pending_notes = getattr(self.env.cr, '_l10n_ve_exchange_pending_notes', None) or []
        self.env.cr._l10n_ve_exchange_pending_notes = []
        try:
            exchange_moves = super()._create_exchange_difference_moves(exchange_diff_values_list)

            for descriptor in pending_notes:
                descriptor['line']._create_exchange_difference_note(
                    descriptor['invoice'], descriptor['payment'], descriptor['residual'],
                )

            # Nuestras notas NUNCA se incluyen en el recordset retornado: el
            # llamador (`_reconcile_plan_with_sync`, núcleo) usa ese valor
            # para auto-vincular `partial.exchange_move_id` a cualquier
            # línea cuyo `reconciled_lines_ids` coincida con un partial de
            # esta conciliación -- y `account.partial.reconcile.unlink()`
            # (núcleo) revierte AUTOMÁTICAMENTE ese `exchange_move_id` al
            # desconciliar. Como este módulo ya revierte sus propias notas
            # explícitamente (`_reverse_exchange_note`, disparada desde
            # `account.partial.reconcile.unlink()`,
            # `models/account_partial_reconcile.py`), dejar que el núcleo
            # también las vincule produce una reversión DUPLICADA.
            return exchange_moves
        finally:
            # Mismo motivo que el `try/finally` de
            # `_prepare_reconciliation_single_partial` -- ESTE stash es
            # el más peligroso de los dos: si algo lanza entre el
            # `getattr` de arriba y el final de la creación de las
            # notas, la cola sobrevive un rollback a savepoint (los
            # stashes en atributos planos del cursor no se limpian con
            # `cr.postrollback`, que nunca corre en un rollback a
            # savepoint -- ver el otro `try/finally`). Acá lo que se
            # filtraría no es solo una pareja de líneas: es una ND/NC
            # completa por emitir, con su monto, lista para postearse en
            # el SIGUIENTE intento sobre el mismo cursor -- un documento
            # fiscal con correlativo consumido por un monto que ya no
            # corresponde a nada, sin ningún error visible.
            self.env.cr._l10n_ve_exchange_pending_notes = []

    def _create_exchange_difference_note(self, invoice, payment, residual):
        """Settles the exchange difference (exact `residual` amount, in
        company currency, taken directly from Odoo's own
        `_prepare_exchange_difference_move_vals` computation) with a real
        Credit or Debit Note linked to `invoice` and `payment`, dated the
        day of the PAYMENT (not today), built manually with `create()`:

        - Residual on DEBIT ("short"): CREDIT Note, posted to the
          company's exchange LOSS account.
        - Residual on CREDIT ("over"/gain): DEBIT Note, posted to the
          company's exchange GAIN account.

        Both branches close the note's receivable line against `self`
        -- the EXACT line Odoo's own engine flagged as still holding
        this residual (never a re-derived/re-looked-up reference) --
        via the `reconciled_lines_ids` inverse (the SAME mechanism
        Odoo's own generic exchange-difference entry uses to close
        itself, see `_get_exchange_difference_move_vals` in core: it
        never calls `.reconcile()` a second time either). Because this
        runs from `_create_exchange_difference_moves`, still inside the
        original reconciliation's transaction, `self`'s residual is
        already the final, accurate leftover for this partial -- no
        risk of eroding a foreign-currency balance the way closing
        against a re-derived, possibly stale invoice line could.

        Does nothing if an exchange difference Debit/Credit Note already
        exists for this (invoice, payment) pair -- guards against two
        queued entries from near-simultaneous reconciliations of the
        SAME payment, without blocking a genuinely distinct exchange
        difference from a LATER, separate partial payment on the same
        invoice.
        """
        self.ensure_one()
        # `l10n_ve_exchange_invoice_line_ids`/`l10n_ve_exchange_payment_line_ids`
        # (stashed by `reconcile()` above) also need clearing here, not
        # just `skip_invoice_sync` -- the note we're about to `create()`
        # inherits this env's context, and if a nested reconciliation
        # triggered later by closing the note's own line (see
        # `reconciled_lines_ids` below) ever re-entered
        # `_prepare_exchange_difference_move_vals` while these were
        # still set, it would consume a stash meant for the ORIGINAL
        # reconciliation, not this note's own closing.
        self = self.with_context(
            skip_invoice_sync=False, active_model=False, active_id=False,
            l10n_ve_exchange_invoice_line_ids=False,
            l10n_ve_exchange_payment_line_ids=False,
        )
        # `invoice.company_id`, NO `self.company_id` -- `self` (`line`) es
        # la línea que Odoo determinó que TODAVÍA tiene el residual, y en
        # la rama de atribución del lado-PAGO (ver
        # `_prepare_exchange_difference_move_vals`) esa línea es la del
        # PAGO, no la de la factura. En un esquema de sucursales
        # (compañía hija conciliando contra la matriz, soportado por el
        # núcleo), la compañía del pago puede ser DISTINTA de la de la
        # factura -- pero el gate que decide si esta nota se emite
        # (`is_own_invoice_line`, más arriba) ya se evaluó sobre
        # `invoice.company_id`, así que toda la configuración que se lee
        # de `company` de acá en adelante (producto/tarifa/diario/cuentas
        # de cambio dedicados) debe ser la MISMA compañía, la de la
        # factura -- nunca la de la línea con el residual.
        company = invoice.company_id

        # `state != 'cancel'` NO alcanza: revertir una nota
        # (`_reverse_exchange_note`) NO la cancela -- queda `posted`
        # (comportamiento nativo de `_reverse_moves`, igual que
        # cualquier reversión de Odoo). Sin excluir también las ya
        # revertidas (`reversal_move_ids`, nativo -- el One2many inverso
        # de `reversed_entry_id`, se llena en CUALQUIER reversión sea
        # ND o NC), re-conciliar el mismo (factura, pago) tras romper y
        # re-asignar el pago encontraría la nota vieja ya revertida y
        # saldría aquí sin crear una nueva NI conciliar nada -- el
        # residual quedaría sin ningún documento que lo respalde.
        existing_note = self.env['account.move'].search([
            ('l10n_ve_exchange_invoice_id', '=', invoice.id),
            ('l10n_ve_exchange_payment_id', '=', payment.id),
            ('state', '!=', 'cancel'),
            ('reversal_move_ids', '=', False),
        ], order='id desc', limit=1)
        if existing_note:
            return existing_note

        product = company.l10n_ve_exchange_note_product_id
        if not product:
            raise UserError(_(
                "Configure the 'Exchange Difference Note Product' in "
                "Settings > Binaural Settings before reconciling "
                "foreign-currency invoices with the exchange difference "
                "Debit/Credit Note mode enabled."
            ))

        # `account_invoice_pricelist` requires every invoice/note to have
        # a `pricelist_id` in its OWN currency -- these notes are always
        # created in company currency, so the configured pricelist must
        # be too (enforced by `_check_l10n_ve_exchange_note_pricelist_id`).
        pricelist = company.l10n_ve_exchange_note_pricelist_id
        if not pricelist:
            raise UserError(_(
                "Configure the 'Exchange Difference Note Pricelist' (in "
                "the company's own currency) in Settings > Binaural "
                "Settings before reconciling foreign-currency invoices "
                "with the exchange difference Debit/Credit Note mode "
                "enabled."
            ))

        is_credit_note = company.currency_id.compare_amounts(residual, 0.0) > 0

        debit_journal = self.env['account.journal']
        if not is_credit_note:
            # Requerido -- nunca cae en silencio al diario de venta de la
            # factura: ese diario numera facturas normales, así que una
            # ND ahí consumiría un número de FACTURA en vez de uno propio
            # de ND. `is_debit=True` solo puede marcarse desde la UI en
            # diarios `type in ('sale', 'purchase')` (l10n_ve_invoice), y
            # la vista de este módulo solo expone
            # `l10n_ve_exchange_debit_note_sequence_id` quando ese diario
            # además tiene `is_debit=True` -- así que exigir AMBOS aquí
            # (diario Y secuencia configurada) es justo lo que la UI deja
            # configurar, nunca más.
            #
            # `.sudo()` -- `journal_comp_rule` (núcleo,
            # `account/security/account_security.xml`) filtra
            # `account.journal` por las compañías PERMITIDAS del usuario
            # (`allowed_company_ids`), no por `company` (la de la
            # factura). Si el usuario/proceso que dispara la
            # conciliación no tiene esa compañía en sus compañías
            # permitidas (ej. un cron, o un usuario de otra sucursal),
            # este `search()` devolvía vacío en silencio -- disparando el
            # `UserError` de abajo por una razón que no era la real
            # (diario no configurado, cuando en realidad SÍ lo está, solo
            # que el usuario no puede verlo). Es una búsqueda de solo
            # lectura sobre infraestructura propia del módulo, no datos
            # de negocio del usuario -- `sudo()` es seguro acá.
            debit_journal = self.env['account.journal'].sudo().search([
                ('company_id', '=', company.id),
                ('is_debit', '=', True),
                ('type', '=', 'sale'),
            ], order='id', limit=1)
            if not debit_journal or not debit_journal.l10n_ve_exchange_debit_note_sequence_id:
                raise UserError(_(
                    "Configure a sale journal with 'Is Debit' enabled and "
                    "its dedicated Exchange Difference Debit Note sequence "
                    "assigned before reconciling foreign-currency invoices "
                    "with the exchange difference Debit/Credit Note mode "
                    "enabled -- a Debit Note must never be numbered with "
                    "the invoice journal's own sequence."
                ))
        else:
            # Mismo requisito que la ND arriba, pero para la NC: se
            # postea en el MISMO diario que la factura de origen (Odoo
            # numera NC con `refund_sequence_id`, no con un diario
            # dedicado), así que si ese diario no tiene su propia
            # `refund_sequence_id` configurada, `_compute_name_by_sequence`
            # (`account_move.py`) ahora aborta con `UserError` en vez de
            # caer al numerador NORMAL del diario -- consumir un
            # correlativo de FACTURA sería exactamente el bug que este
            # módulo existe para evitar.
            #
            # A propósito ya NO se autoprovisiona acá (a diferencia de
            # una versión anterior): `invoice.journal_id` es el diario de
            # VENTA del cliente, compartido con cualquier factura/NC de
            # negocio normal -- autoprovisionar `refund_sequence=True`
            # ahí es un cambio PERMANENTE y silencioso en la numeración
            # fiscal de ese diario (correlativo controlado por el
            # SENIAT), disparado dentro de `reconcile()` por un contador
            # sin permisos de manager que simplemente registra un pago.
            # La rama de ND (arriba) ya elige bloquear con `UserError` en
            # vez de autoprovisionar sobre su diario dedicado -- ser
            # simétrico acá: fallar ruidoso pidiendo configuración
            # explícita es peor UX pero infinitamente más barato que
            # reordenar correlativos de NC de negocio a mitad de
            # ejercicio.
            if not invoice.journal_id.refund_sequence_id:
                raise UserError(_(
                    "Configure a dedicated 'Refund Sequence' (Credit Note "
                    "sequence) on journal %(journal)s before reconciling "
                    "foreign-currency invoices with the exchange "
                    "difference Debit/Credit Note mode enabled -- a "
                    "Credit Note must never be numbered with the invoice "
                    "journal's own sequence.",
                    journal=invoice.journal_id.display_name,
                ))

        # `product.taxes_id` (core `account/models/product.py`) solo
        # filtra por `type_tax_use='sale'` en su dominio -- SIN filtro de
        # compañía. Si el producto de diferencial es compartido entre
        # varias compañías y acumuló impuestos de OTRA compañía (ej. por
        # import de datos o un `product_id` reutilizado a mano),
        # pasarlos todos sin filtrar a `tax_ids` -- que sí exige
        # `check_company=True` (core `account_move_line.py`) -- aborta
        # la conciliación entera con un `UserError` de multi-compañía en
        # medio de un `reconcile()` ya en curso.
        # `t.company_id == company` (igualdad estricta) NO es el filtro
        # correcto: `account.tax._check_company_domain` (core) es
        # `check_company_domain_parent_of`, así que un impuesto de la
        # COMPAÑÍA MATRIZ es válido en una línea de una sucursal -- con
        # igualdad estricta esos impuestos se descartaban en silencio,
        # dejando la nota fiscal armada SIN su impuesto exento en vez de
        # abortar (peor: un error silencioso, no uno visible).
        note_taxes = product.taxes_id.filtered_domain(
            self.env['account.tax']._check_company_domain(company)
        )
        # `account_id` explícito para AMBAS ramas -- no se deja que Odoo
        # lo derive de `product_id` en el `create()` crudo (sin pasar
        # por `Form`/onchange): en la práctica funciona en la mayoría de
        # bases, pero depende de que la derivación automática de cuenta
        # por producto resuelva algo, y en al menos un entorno real (no
        # una fixture de test) resolvió a NULL -- violando el `CHECK`
        # `account_move_line_check_accountable_required_fields` de
        # Postgres al insertar la línea.
        #
        # Con FALLBACK a la cuenta propia del producto
        # (`property_account_income_id`/`property_account_expense_id`)
        # si la compañía no tiene configuradas
        # `income_currency_exchange_account_id`/`expense_currency_exchange_account_id`
        # (campos nativos de Odoo, Ajustes > Contabilidad > Cuentas por
        # Defecto -- no todas las bases los traen configurados, ej. una
        # instalación vieja migrada, o un chart of accounts que nunca
        # los completó): sin este fallback, una compañía así deja
        # `company.income_currency_exchange_account_id` vacío, y fijar
        # el `account_id` directo desde ahí (sin fallback) produce el
        # MISMO `NULL` que se estaba corrigiendo, solo que explícito en
        # vez de implícito. `_check_l10n_ve_exchange_note_product_id`
        # (`res_company.py`) exige que AMBAS cuentas coincidan CUANDO la
        # compañía sí las tiene configuradas, así que este fallback no
        # cambia el resultado esperado en ese caso -- solo cubre el caso
        # en que la compañía nunca las configuró pero el producto sí
        # tiene sus propias cuentas.
        # `product.with_company(company)` -- `property_account_income_id`/
        # `property_account_expense_id` son `company_dependent=True`
        # (`account/models/product.py`), así que leerlos DIRECTO sobre
        # `product` (sin `with_company`) los resuelve para
        # `self.env.company`, no para `company` (la de la factura, ver el
        # fix de más arriba). En una compañía donde `self.env.company` no
        # es `company` (multi-compañía, el usuario/cron que dispara la
        # conciliación con otra compañía activa), este fallback podía
        # volver vacío (el NULL que existe para evitar) o traer la cuenta
        # de OTRA compañía -- `UserError` de `check_company` en
        # `account_id` más abajo. Mismo patrón que ya usa
        # `_check_l10n_ve_exchange_note_product_id` (`res_company.py`).
        product_accounts = product.with_company(company)
        income_account = company.income_currency_exchange_account_id or product_accounts.property_account_income_id
        expense_account = company.expense_currency_exchange_account_id or product_accounts.property_account_expense_id
        line_vals = {
            'product_id': product.id,
            'quantity': 1.0,
            'price_unit': abs(residual),
            'tax_ids': [Command.set(note_taxes.ids)],
            'account_id': (expense_account if is_credit_note else income_account).id,
            'name': _(
                'Exchange difference (%(concept)s) on %(invoice)s',
                concept=_('loss') if is_credit_note else _('gain'),
                invoice=invoice.name,
            ),
        }
        if not line_vals['account_id']:
            raise UserError(_(
                "Cannot determine the accounting account for this exchange "
                "difference Debit/Credit Note line: neither the company's "
                "%(account_field)s nor the note product's own "
                "%(product_field)s is configured. Set at least one of them "
                "(Accounting Settings > Default Accounts, or the product's "
                "Income/Expense account) before reconciling foreign-currency "
                "invoices with the exchange difference Debit/Credit Note "
                "mode enabled.",
                account_field=(
                    _("Loss Exchange Rate Account")
                    if is_credit_note else _("Gain Exchange Rate Account")
                ),
                product_field=(
                    _("Expense Account") if is_credit_note else _("Income Account")
                ),
            ))
        note_date = payment.date or fields.Date.context_today(self)

        # `_create_exchange_difference_moves` runs nested inside the
        # ORIGINAL reconciliation's `_sync_dynamic_lines` context manager
        # (see `account.move._reconcile_plan`), which pushes
        # `skip_invoice_sync=True` onto a CURSOR-GLOBAL recursion-guard
        # stack (`env.cr.cache['account_disable_recursion_stack']`) for
        # the whole duration of that reconciliation -- not scoped to the
        # invoice/payment being reconciled. Without unwinding that layer
        # here, our brand new note's own line auto-computation (the
        # receivable line derived from `invoice_line_ids`) would be
        # silently skipped by that same guard, even though it has
        # nothing to do with the reconciliation in progress. Pushing our
        # own `target=False` layer (the exact API Odoo itself uses to
        # compose these context managers) unblocks it just for this
        # note's creation/posting.
        with self.env['account.move']._disable_recursion({}, 'skip_invoice_sync', target=False):
            if not is_credit_note:
                # `with_company(company)` -- `company` es
                # `invoice.company_id` (fijado explícito más arriba,
                # C1), NUNCA `self.env.company`. Sin este `with_company`,
                # cualquier lógica de creación que resuelva su
                # comportamiento por la compañía ACTIVA del entorno (ej.
                # la moneda alterna/tasa que `l10n_ve_accountant`
                # deriva en `account.move.create()`) queda resuelta para
                # `self.env.company` -- que en un entorno multi-compañía
                # puede no ser la de la factura (un cron, o un usuario
                # cuya compañía activa es otra).
                note = self.env['account.move'].with_company(company).create({
                    'move_type': 'out_invoice',
                    'partner_id': invoice.partner_id.id,
                    'invoice_date': note_date,
                    'invoice_date_display': note_date,
                    'date': note_date,
                    'currency_id': company.currency_id.id,
                    'pricelist_id': pricelist.id,
                    'journal_id': debit_journal.id,
                    'debit_origin_id': invoice.id,
                    'invoice_origin': invoice.name,
                    'invoice_line_ids': [Command.create(line_vals)],
                    'l10n_ve_exchange_diff_entry': True,
                    'l10n_ve_exchange_is_credit_note': False,
                    'l10n_ve_exchange_invoice_id': invoice.id,
                    'l10n_ve_exchange_payment_id': payment.id,
                })
                note.with_context(move_action_post_alert=True).action_post()
            else:
                # `account_id` ya viene fijado arriba en `line_vals`
                # (rama `is_credit_note` -> cuenta de PÉRDIDA) -- sin
                # eso, `is_sale_document()` (núcleo) trata `out_refund`
                # igual que `out_invoice` para elegir la cuenta de la
                # línea, y una NC de PÉRDIDA terminaría acreditando la
                # cuenta de GANANCIA cambiaria en vez de la de pérdida.
                # `with_company(company)` -- mismo motivo que la rama de
                # ND arriba.
                #
                # `l10n_ve_skip_refund_origin_validation` -- HOY es un
                # no-op: ningún módulo en este repo lee esta clave de
                # contexto todavía. Coordina por adelantado con
                # `_validate_refund_lines_against_origin()`, una
                # validación en desarrollo en OTRO módulo/PR (que valida
                # que las líneas de una NC repitan el producto de su
                # factura de origen) -- esta NC de diferencial nunca
                # usa el producto de la factura original, siempre el
                # producto dedicado de diferencial cambiario, así que
                # NO debe pasar por esa validación cuando exista. Se
                # coordina vía contexto (no un campo persistido) porque
                # ese otro módulo no puede depender de este (`c571d9e1a`).
                note = self.env['account.move'].with_company(company).with_context(
                    l10n_ve_skip_refund_origin_validation=True,
                ).create({
                    'move_type': 'out_refund',
                    'partner_id': invoice.partner_id.id,
                    'invoice_date': note_date,
                    'invoice_date_display': note_date,
                    'date': note_date,
                    'currency_id': company.currency_id.id,
                    'pricelist_id': pricelist.id,
                    'journal_id': invoice.journal_id.id,
                    # `reversed_entry_id` NO se setea acá, a propósito --
                    # ver el `note.write({'reversed_entry_id': ...})`
                    # DESPUÉS de conciliar, más abajo, para el porqué.
                    'invoice_origin': invoice.name,
                    'invoice_line_ids': [Command.create(line_vals)],
                    'l10n_ve_exchange_diff_entry': True,
                    'l10n_ve_exchange_is_credit_note': True,
                    'l10n_ve_exchange_invoice_id': invoice.id,
                    'l10n_ve_exchange_payment_id': payment.id,
                })
                # NO se re-calcula/escribe `foreign_rate` acá -- a
                # propósito, a diferencia de una versión anterior de
                # este bloque. Esa escritura manual existía para pisar
                # una herencia no deseada: `l10n_ve_accountant.create()`
                # (`models/account_move.py:533-536`) solo hereda
                # `foreign_rate`/`foreign_inverse_rate` del documento
                # revertido cuando el `create()` trae `reversed_entry_id`
                # en los `vals` -- y ya NO lo trae (ver más arriba). Sin
                # esa rama de herencia, el `move._compute_rate()`
                # incondicional de ese mismo `create()` (línea 532) es
                # el único que corre, y ya calcula la tasa NATURAL
                # correcta: usa `invoice_date` (= `note_date`, la fecha
                # del pago) como fecha de la tasa, y hereda el
                # `with_company(company)` de nuestro propio `create()`
                # de arriba (mismo `self.env` en toda la cadena). Repetir
                # el cálculo acá a mano era redundante Y más riesgoso --
                # es justo donde se coló el bug real de `with_company`
                # faltante (una tasa de `0` en la NC cuando
                # `self.env.company != company`), porque esta escritura
                # manual usaba `self.env['res.currency.rate']` sin
                # `with_company`, mientras el `create()` de arriba
                # SÍ lo tenía.
                # `l10n_ve_skip_refund_origin_validation` -- repetido acá
                # (no heredado del `create()` de arriba) porque
                # `action_post()` es una llamada NUEVA, con su propio
                # contexto; ver la nota completa junto al `create()`.
                note.with_context(
                    move_action_post_alert=True,
                    l10n_ve_skip_refund_origin_validation=True,
                ).action_post()

        note_line = note.line_ids.filtered(lambda l: l.account_type == 'asset_receivable')
        if not note_line:
            # Defensa en profundidad: nunca debería pasar (la nota es
            # `out_invoice`/`out_refund` con una línea de producto, Odoo
            # siempre agrega la línea `asset_receivable` automáticamente
            # al postear), pero si alguna vez ocurriera, un `.write()`
            # sobre un recordset vacío no haría NADA ni lanzaría error --
            # la nota quedaría posteada (correlativo fiscal ya consumido)
            # pero SIN conciliar contra `self`, dejando el residual
            # cambiario abierto sin ningún aviso. Falla ruidoso en vez de
            # silencioso.
            raise UserError(_(
                "Could not find the receivable line on the newly created "
                "exchange difference note '%(note)s' -- this should never "
                "happen for a posted customer invoice/note.",
                note=note.display_name,
            ))
        # `no_exchange_difference=True` -- SAME context key Odoo's own
        # `_reconcile_plan` uses to close its own generic exchange-diff
        # entry (`account_move_line.py`, core: `self.env['account.move']
        # .with_context(no_exchange_difference=True, ...).create(...)`)
        # -- without it, this nested conciliation (triggered by the
        # `reconciled_lines_ids` inverse) would re-enter the exchange
        # difference engine and could queue a SPURIOUS residual for this
        # note's own closing line.
        note_line.with_context(no_exchange_difference=True).write(
            {'reconciled_lines_ids': [Command.set(self.ids)]}
        )

        if is_credit_note:
            # `reversed_entry_id` se setea AQUÍ, DESPUÉS de que la NC ya
            # está posteada y conciliada -- nunca en el `create()` de
            # arriba. Confirmado contra el núcleo
            # (`account/models/account_move.py::_post`): CUALQUIER move
            # que se postea con `reversed_entry_id` ya seteado dispara,
            # sin poder desactivarse por contexto,
            # `reversed_entry_id._reconcile_reversed_moves(...)` --
            # agrupa las líneas SIN conciliar de la NC y de la factura
            # por `(account_id, currency_id)` y las concilia entre sí
            # directo. Cuando la factura está en moneda de COMPAÑÍA (el
            # caso "factura en VES pagada con USD", ver
            # `test_ves_invoice_paid_in_usd_generates_rounding_exchange_difference_note`),
            # la línea por cobrar de la factura y la de esta NC quedan en
            # la MISMA cuenta y MISMA moneda -- ese auto-reconcile las
            # concilia ANTES de que el `write` de `reconciled_lines_ids`
            # de arriba corra, y como `account.move.line.reconcile()`
            # está sobrescrito por este mismo módulo, ese auto-reconcile
            # del núcleo re-entra `reconcile()` sobre el par
            # factura/nota -- una conciliación espuria, no la que este
            # método ya cerró explícito. Set explícito y tardío para
            # conservar el vínculo nativo de Odoo (banner "Nota de
            # Crédito de", helpers de `l10n_ve_invoice`) sin disparar
            # ese camino: para cuando este `write` corre, la NC ya está
            # `posted` (no vuelve a pasar por `_post()`) y ya está
            # conciliada por el paso de arriba.
            #
            # `skip_is_manually_modified=True` -- sin este contexto,
            # `account.move.write()` (núcleo,
            # `account/models/account_move.py`) marca CUALQUIER `write()`
            # sobre un move posteado como `is_manually_modified=True`
            # salvo que ese contexto esté presente o el propio `vals`
            # incluya el campo explícito. Esta escritura la hace el
            # SISTEMA para completar la creación de un documento propio,
            # no un usuario editando la nota a mano -- sin este flag, la
            # NC quedaría marcada en auditoría como "editada
            # manualmente" cuando en realidad nadie la tocó.
            # `l10n_ve_skip_refund_origin_validation` -- este `write` es el
            # único punto que setea `reversed_entry_id` en esta nota (el
            # `create()` de arriba deliberadamente no lo trae), así que es
            # el único lugar donde el constrains de origen de
            # `l10n_ve_invoice` podría llegar a evaluarla. Hoy ese
            # constrains no se dispara por escribir `reversed_entry_id`
            # (solo por `invoice_line_ids`/`product_id`/`price_unit`/
            # `quantity`/`discount`), pero repetir el flag acá deja esto a
            # prueba de que ese alcance cambie más adelante.
            note.with_context(
                skip_is_manually_modified=True,
                l10n_ve_skip_refund_origin_validation=True,
            ).write({'reversed_entry_id': invoice.id})

        return note
