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

        # Reinicia el reparto ordenado de residuales atribuidos al lado
        # del pago (ver `_next_payment_side_invoice_line`) para ESTA
        # llamada -- evita que un pago agrupado reconciliado en dos
        # `reconcile()` distintos arrastre el índice de una llamada
        # anterior no relacionada.
        self.env.cr._l10n_ve_exchange_payment_side_index = {}

        return super(AccountMoveLine, self.with_context(
            l10n_ve_exchange_payment_line_ids=payment_lines.ids,
            l10n_ve_exchange_invoice_line_ids=invoice_lines.ids,
        )).reconcile()

    def _next_payment_side_invoice_line(self, payment_move, invoice_lines_ctx):
        """Returns the next candidate invoice line, in order, for a
        residual Odoo attributed to the PAYMENT side of `payment_move`
        (see `_prepare_exchange_difference_move_vals`) -- a per-payment
        counter (reset once per `reconcile()` call, see above) advances
        each time this is called for the SAME payment, so N distinct
        residuals against the same grouped payment get matched to N
        distinct candidate invoices instead of all collapsing onto the
        first one. Clamped to the last candidate if there somehow end up
        more payment-side residuals than candidate invoices (should not
        happen structurally, but never raises)."""
        index_map = self.env.cr._l10n_ve_exchange_payment_side_index
        idx = index_map.get(payment_move.id, 0)
        index_map[payment_move.id] = idx + 1
        return invoice_lines_ctx[min(idx, len(invoice_lines_ctx) - 1)]

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

        pending_notes = []
        remaining_lines = []
        remaining_amounts = []
        for line, amounts in zip(self, amounts_list):
            # El ajuste puede caer del lado de la FACTURA (caso común) o
            # del lado del PAGO (Odoo suele atribuírselo así en la
            # dirección de ganancia). Cuando cae del lado del pago y hay
            # MÁS de una factura candidata (pago agrupado), Odoo no
            # expone en este punto a cuál factura pertenece cada
            # residual puntual -- pero la nota se DEBE crear igual (no
            # cae al asiento genérico nativo): se reparte cada residual
            # del lado del pago, EN ORDEN, contra una factura candidata
            # distinta cada vez (`_next_payment_side_invoice_line`),
            # nunca repitiendo la misma dos veces para el mismo pago --
            # así nunca colisiona contra el guard de duplicados de
            # `_create_exchange_difference_note` (que sí bloquearía dos
            # residuales DISTINTOS que compartieran por error el mismo
            # par factura/pago). El cierre contable en sí (contra `line`,
            # la línea real que Odoo flageó) es correcto sin importar el
            # orden -- lo único que depende del orden es a cuál factura
            # queda vinculada la nota para trazabilidad.
            if line in invoice_lines_ctx:
                invoice_line, invoice, payment = line, line.move_id, default_payment
            elif line in payment_lines and invoice_lines_ctx:
                invoice_line = self._next_payment_side_invoice_line(line.move_id, invoice_lines_ctx)
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
        # explícitamente (`_reverse_exchange_note`, en
        # `account_move.js_remove_outstanding_partial`), dejar que el
        # núcleo también las vincule produce una reversión DUPLICADA.
        return exchange_moves

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
        self = self.with_context(skip_invoice_sync=False, active_model=False, active_id=False)
        company = self.company_id

        existing_note = self.env['account.move'].search([
            ('l10n_ve_exchange_invoice_id', '=', invoice.id),
            ('l10n_ve_exchange_payment_id', '=', payment.id),
            ('state', '!=', 'cancel'),
        ], limit=1)
        if existing_note:
            return existing_note

        product = company.l10n_ve_exchange_note_product_id
        if not product:
            raise UserError(_(
                "Configure the 'Exchange Difference Note Product' in "
                "Settings > Accounting before reconciling foreign-currency "
                "invoices with the exchange difference Debit/Credit Note "
                "mode enabled."
            ))

        # `account_invoice_pricelist` requires every invoice/note to have
        # a `pricelist_id` in its OWN currency -- these notes are always
        # created in company currency, so the configured pricelist must
        # be too (enforced by `_check_l10n_ve_exchange_note_pricelist_id`).
        pricelist = company.l10n_ve_exchange_note_pricelist_id
        if not pricelist:
            raise UserError(_(
                "Configure the 'Exchange Difference Note Pricelist' (in "
                "the company's own currency) in Settings > Accounting "
                "before reconciling foreign-currency invoices with the "
                "exchange difference Debit/Credit Note mode enabled."
            ))

        is_credit_note = company.currency_id.compare_amounts(residual, 0.0) > 0

        line_vals = {
            'product_id': product.id,
            'quantity': 1.0,
            'price_unit': abs(residual),
            'tax_ids': [(6, 0, product.taxes_id.ids)],
            'name': _(
                'Exchange difference (%(concept)s) on %(invoice)s',
                concept=_('loss') if is_credit_note else _('gain'),
                invoice=invoice.name,
            ),
        }
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
                debit_journal = self.env['account.journal'].search([
                    ('company_id', '=', company.id),
                    ('is_debit', '=', True),
                    ('type', '=', 'sale'),
                ], limit=1)
                journal = debit_journal or invoice.journal_id

                note = self.env['account.move'].create({
                    'move_type': 'out_invoice',
                    'partner_id': invoice.partner_id.id,
                    'invoice_date': note_date,
                    'date': note_date,
                    'currency_id': company.currency_id.id,
                    'pricelist_id': pricelist.id,
                    'journal_id': journal.id,
                    'debit_origin_id': invoice.id,
                    'invoice_origin': invoice.name,
                    'invoice_line_ids': [(0, 0, line_vals)],
                    'l10n_ve_exchange_diff_entry': True,
                    'l10n_ve_exchange_is_credit_note': False,
                    'l10n_ve_exchange_invoice_id': invoice.id,
                    'l10n_ve_exchange_payment_id': payment.id,
                })
                note.with_context(move_action_post_alert=True).action_post()
            else:
                # `account_id` explícito, en vez de dejar que Odoo lo derive del
                # producto: `is_sale_document()` (núcleo) trata `out_refund`
                # igual que `out_invoice` para elegir la cuenta de la línea --
                # ambas ramas usarían la cuenta `income` del producto (la de
                # GANANCIA, según exige `_check_l10n_ve_exchange_note_product_id`).
                # Sin este override, una NC de PÉRDIDA terminaría acreditando la
                # cuenta de ganancia cambiaria en vez de la de pérdida.
                line_vals['account_id'] = company.expense_currency_exchange_account_id.id
                note = self.env['account.move'].with_context(
                    l10n_ve_skip_refund_origin_validation=True,
                ).create({
                    'move_type': 'out_refund',
                    'partner_id': invoice.partner_id.id,
                    'invoice_date': note_date,
                    'date': note_date,
                    'currency_id': company.currency_id.id,
                    'pricelist_id': pricelist.id,
                    'journal_id': invoice.journal_id.id,
                    'reversed_entry_id': invoice.id,
                    'invoice_origin': invoice.name,
                    'invoice_line_ids': [(0, 0, line_vals)],
                    'l10n_ve_exchange_diff_entry': True,
                    'l10n_ve_exchange_is_credit_note': True,
                    'l10n_ve_exchange_invoice_id': invoice.id,
                    'l10n_ve_exchange_payment_id': payment.id,
                })
                note.with_context(
                    move_action_post_alert=True,
                    l10n_ve_skip_refund_origin_validation=True,
                ).action_post()

        note_line = note.line_ids.filtered(lambda l: l.account_type == 'asset_receivable')
        note_line.write({'reconciled_lines_ids': [Command.set(self.ids)]})
        return note
