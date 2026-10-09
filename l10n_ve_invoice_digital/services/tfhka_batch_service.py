from datetime import timedelta

from odoo import _, fields, models
from odoo.exceptions import UserError


class TfhkaBatchService(models.AbstractModel):
    """Batch digitalization against TFHKA.

    Unlike Unidigital (a single POST carrying N documents), TFHKA only
    exposes an endpoint to *reserve* a range of ``numeroDocumento`` ahead of
    time (``/AsignarNumeraciones``, see ``tfhka.api.client``). Each document
    in the batch is still emitted one at a time through the existing queue
    (``tfhka.digitalization.mixin``); this service only reserves the range,
    forces each invoice's number inside that range, and enqueues the batch.

    Only usable when the company has ``batch_invoicing_tfhka`` enabled, which
    itself requires ``digitalization_with_payment_tfhka`` (enforced in
    ``res.config.settings``, onchange + ``set_values``, same pattern as
    ``dispatch_guide_digital_tfhka``). Because of that, this enqueues directly via
    ``tfhka.digitalization.mixin._tfhka_enqueue_digitalization`` instead of
    ``account.move._tfhka_enqueue_eligible_for_digitalization`` -- the latter
    deliberately excludes payment-driven companies (their invoices normally
    digitalize when a payment reconciles, not at posting time), which would
    make it silently enqueue nothing here. A batch is an explicit, one-off
    action on invoices already validated by ``_check_eligibility``, so that
    exclusion doesn't apply.
    """

    _name = "tfhka.batch.service"
    _description = "TFHKA Batch Digitalization Service"

    # ------------------------------------------------------------------
    # Validación
    # ------------------------------------------------------------------

    def _check_eligibility(self, moves):
        """Rejects, naming the invoices, anything in ``moves`` that isn't
        actually postable to TFHKA -- a batch action must not silently drop
        an invoice the user explicitly selected. Deliberately does not
        reject payment-driven companies (unlike
        ``account.move._tfhka_enqueue_eligible_for_digitalization``): a batch
        requires ``company.batch_invoicing_tfhka``, which in turn requires
        ``digitalization_with_payment_tfhka`` to be enabled, so every batch
        call is expected to run under that mode."""
        not_posted = moves.filtered(lambda m: m.state != "posted")
        if not_posted:
            raise UserError(
                _("The following invoices are not posted: %(names)s")
                % {"names": ", ".join(not_posted.mapped("name"))}
            )

        already_digitalized = moves.filtered(lambda m: m.is_digitalized)
        if already_digitalized:
            raise UserError(
                _("The following invoices are already digitalized: %(names)s")
                % {"names": ", ".join(already_digitalized.mapped("name"))}
            )

        already_queued = moves.filtered(
            lambda m: m.tfhka_digitalization_state in ("queued", "processing")
        )
        if already_queued:
            raise UserError(
                _("The following invoices are already queued for digitalization: %(names)s")
                % {"names": ", ".join(already_queued.mapped("name"))}
            )

        not_digital_journal = moves.filtered(lambda m: not m.journal_id.digital_invoice)
        if not_digital_journal:
            raise UserError(
                _("The following invoices belong to a journal that is not digital: %(names)s")
                % {"names": ", ".join(not_digital_journal.mapped("name"))}
            )

    def _group_by_type_and_series(self, moves):
        doc_service = self.env["tfhka.document.service"]
        grouped = {}
        for move in moves:
            document_type = doc_service._get_document_type(move)
            if not document_type:
                raise UserError(
                    _(
                        "Invoice %(name)s has no valid TFHKA document type (only "
                        "invoices, credit notes and debit notes can be batched)."
                    )
                    % {"name": move.name}
                )
            series = doc_service._get_series(move)
            key = (document_type, series)
            grouped.setdefault(key, self.env["account.move"])
            grouped[key] += move
        return grouped

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def create_batch(self, moves):
        """Reserves a numbering range per (document type, series) group and
        enqueues the batch's invoices into the existing digitalization
        queue. Returns a ``display_notification`` client action with
        reload, mirroring ``unidigital.batch.service.create_batch``."""
        if not moves:
            return False

        companies = moves.mapped("company_id")
        if len(companies) > 1:
            raise UserError(_("All invoices in a batch must belong to the same company."))
        company = companies

        if not company.invoice_digital_tfhka:
            raise UserError(_("TFHKA digital invoicing is not enabled for this company."))
        if not company.batch_invoicing_tfhka:
            raise UserError(
                _(
                    "TFHKA batch invoicing is not enabled for this company. Enable "
                    "'Batch Invoicing' in Accounting > Configuration > Settings."
                )
            )
        # Defensa adicional: batch_invoicing_tfhka debería implicar este modo
        # (impuesto en la UI de Ajustes, no con un @api.constrains -- ver
        # comentario en res.company.batch_invoicing_tfhka), pero se revalida
        # aquí por si el flag se puso en True por otra vía (RPC/import).
        if not company.digitalization_with_payment_tfhka:
            raise UserError(
                _(
                    "TFHKA batch invoicing requires 'Digital invoicing with payment "
                    "registration' to be enabled for this company."
                )
            )

        self._check_eligibility(moves)

        client = self.env["tfhka.api.client"]
        account_move = self.env["account.move"]

        for (document_type, series), group in self._group_by_type_and_series(moves).items():
            # Orden real de confirmación: ``sequence_number`` (campo nativo
            # de Odoo, asignado de forma estrictamente atómica en el momento
            # exacto de action_post() vía la secuencia del diario) es la
            # única fuente de verdad de ese orden. ``invoice_date`` es solo
            # una fecha (sin hora) y ``id`` es el orden de CREACIÓN del
            # borrador -- ninguno de los dos refleja el orden de posteo
            # cuando las facturas se crean en un orden y se confirman en
            # otro (caso real: id 115 se creó después que el id 113 pero se
            # confirmó antes, con sequence_number menor). El fallback a
            # fecha+id solo aplica al caso patológico de sequence_number
            # vacío (0), que en la práctica no debería darse sobre facturas
            # ya ``posted``.
            sorted_moves = group.sorted(
                key=lambda m: (
                    m.sequence_number or 0,
                    m.invoice_date_display or m.invoice_date or m.date,
                    m.id,
                )
            )
            count = len(sorted_moves)

            last = client.get_last_document_number(company, document_type, series)
            start = int(last) + 1
            end = start + count - 1

            detail = [{
                "serie": series,
                "tipoDocumento": document_type,
                "numeroDocumentoInicio": str(start),
                "numeroDocumentoFin": str(end),
            }]
            client.assign_numbering(company, detail, origin=sorted_moves[0])

            batch_ref = f"{document_type}-{series or 'NA'}-{start}-{end}"
            for idx, move in enumerate(sorted_moves):
                document_number = start + idx
                move.write({
                    "tfhka_batch_ref": batch_ref,
                    "tfhka_batch_document_number": document_number,
                })
                move.message_post(
                    body=_(
                        "Invoice included in TFHKA batch %(ref)s (assigned "
                        "document number: %(number)s)."
                    )
                    % {"ref": batch_ref, "number": document_number},
                )

            # Encolado directo (no _tfhka_enqueue_eligible_for_digitalization):
            # ese punto de entrada excluye compañías en modo pago a propósito
            # (sus facturas digitalizan al conciliar el pago, no al postear),
            # pero un lote es una compañía que SIEMPRE está en ese modo (ver
            # docstring de la clase) y una acción explícita ya validada arriba.
            sorted_moves._tfhka_enqueue_digitalization()

            # tfhka_queued_at solo tiene precisión de segundo completo
            # (fields.Datetime.now() descarta los microsegundos porque el
            # formato de fecha/hora del servidor no los admite -- ver
            # odoo.orm.fields_temporal.Datetime.now). El bucle de arriba
            # encola las N facturas del lote en bien menos de un segundo, así
            # que todas empatan en tfhka_queued_at, y el cron
            # (ORDER BY tfhka_queued_at asc, id asc) cae a ordenar por id --
            # que no necesariamente coincide con el orden en el que se les
            # acaba de asignar numeroDocumento. Se fuerza aquí un
            # tfhka_queued_at estrictamente creciente, un segundo aparte por
            # posición, para que el cron respete siempre el mismo orden en el
            # que se armó el lote.
            base_queued_at = fields.Datetime.now()
            for idx, move in enumerate(sorted_moves):
                move.tfhka_queued_at = base_queued_at + timedelta(seconds=idx)

            # Explicit commit: the TFHKA-side reservation above is already
            # irreversible even if this Odoo transaction later rolls back --
            # if a later group in this same selection fails, this group must
            # stay confirmed (invoices marked + enqueued), not undone along
            # with the next group's error.
            account_move._tfhka_commit()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Batch digitalization queued"),
                "message": _(
                    "The selected invoices were queued for TFHKA batch digitalization."
                ),
                "sticky": False,
                "type": "success",
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }
