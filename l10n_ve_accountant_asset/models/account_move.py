import logging

from odoo import _, api, fields, models
from odoo.addons.l10n_ve_base.models.res_partner import DEFAULT_TZ
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_date

_logger = logging.getLogger(__name__)

# Tipos de documento que admiten la publicacion personalizada. Los recibos
# (out_receipt / in_receipt) no: su campo auto_post ni siquiera se muestra.
AUTO_POST_CUSTOM_MOVE_TYPES = (
    "entry",
    "out_invoice",
    "in_invoice",
    "out_refund",
    "in_refund",
)
# Contexto que SOLO pasa el cron de publicacion personalizada: sin el, `_post`
# excluye (o rechaza) los documentos 'custom' en borrador.
AUTOPOST_CUSTOM_CONTEXT = "l10n_ve_autopost_custom"


class AccountMove(models.Model):
    _inherit = "account.move"

    auto_post = fields.Selection(
        selection_add=[("custom", "Custom")],
        ondelete={"custom": "set default"},
    )
    auto_post_custom_date = fields.Date(
        string="Custom Publication Date",
        copy=False,
        tracking=True,
        help="Day on which the document will be posted automatically. Meanwhile it stays "
        "in draft with today's date. Note: the rate of that day will be used.",
    )
    auto_post_custom_last_attempt = fields.Date(
        string="Last Custom Posting Attempt",
        copy=False,
        readonly=True,
        help="Day of the last failed automatic posting attempt. Prevents the cron from "
        "retrying the same document more than once a day.",
    )

    auto_post_custom_publish_date = fields.Date(
        string="Publication Date",
        compute="_compute_auto_post_custom_publish_date",
        help="Scheduled posting date of the entry; if it is not custom, its date.",
    )

    # ------------------------------------------------------------------
    # Validaciones y computes
    # ------------------------------------------------------------------
    @api.constrains("auto_post", "auto_post_custom_date", "move_type")
    def _check_auto_post_custom(self):
        """La publicacion 'custom' solo aplica a ciertos tipos de documento, exige fecha y
        esta no puede ser anterior a la creacion del documento.

        No se compara contra "hoy" en cada validacion: una custom vencida que fallo por
        falta de tasa no debe volverse invalida mientras espera.
        """
        for move in self:
            if move.auto_post != "custom":
                continue
            if move.move_type not in AUTO_POST_CUSTOM_MOVE_TYPES:
                raise ValidationError(
                    _("The custom auto-post is not available for this type of document.")
                )
            if move.is_invoice() and move._is_fiscal_printer_document():
                raise ValidationError(
                    _(
                        "Invoices issued through a fiscal printer cannot be posted "
                        "automatically on a custom date."
                    )
                )
            if not move.auto_post_custom_date:
                raise ValidationError(
                    _("The publication date is required for the custom auto-post.")
                )
            if isinstance(move.id, api.NewId) or not move.create_date:
                continue
            created_on = fields.Datetime.context_timestamp(move, move.create_date).date()
            if move.auto_post_custom_date < created_on:
                raise ValidationError(
                    _(
                        "The publication date (%(date)s) cannot be earlier than the "
                        "creation date of the document (%(created)s).",
                        date=format_date(self.env, move.auto_post_custom_date),
                        created=format_date(self.env, created_on),
                    )
                )

    @api.depends("auto_post_custom_date", "date")
    def _compute_auto_post_custom_publish_date(self):
        for move in self:
            move.auto_post_custom_publish_date = move.auto_post_custom_date or move.date

    def _is_fiscal_printer_document(self):
        """True si la compania imprime sus facturas por impresora fiscal.

        El campo `invoice_print_type` lo define l10n_ve_account_mf / l10n_ve_iot_mf (no son
        dependencias de este addon), por eso se consulta de forma defensiva, igual que
        hace l10n_ve_invoice en `_post`.
        """
        self.ensure_one()
        return (
            "invoice_print_type" in self.company_id._fields
            and self.company_id.invoice_print_type == "fiscal"
        )

    @api.depends("auto_post")
    def _compute_auto_post_until(self):
        super()._compute_auto_post_until()
        for record in self:
            if record.auto_post == "custom":
                record.auto_post_until = False

    # Se re-declara `date` y `auto_post`: @api.depends de un override reemplaza la lista del padre.
    @api.depends("date", "auto_post", "state")
    def _compute_hide_post_button(self):
        super()._compute_hide_post_button()
        for record in self:
            if record.auto_post == "custom" and record.state == "draft":
                record.hide_post_button = True

    @api.onchange("auto_post")
    def _onchange_auto_post_custom(self):
        """Un documento 'custom' espera en borrador con las fechas de hoy: asi no choca con
        la restriccion de tasa exacta ni con la de fecha futura. El cron pone la fecha real
        el dia de la publicacion."""
        for move in self:
            if move.auto_post == "custom" and move.state == "draft":
                today = fields.Date.context_today(move)
                move.date = today
                move.invoice_date = today
                move.invoice_date_display = today

    # ------------------------------------------------------------------
    # Publicacion
    # ------------------------------------------------------------------
    def _post(self, soft=True):
        """Un documento 'custom' en borrador solo lo publica el cron.

        Sin el contexto `l10n_ve_autopost_custom` los 'custom' se excluyen del lote
        (soft, p. ej. "Confirmar asientos" masivo) o se rechazan (no soft: `action_post`).
        Los `_post` de l10n_ve_invoice, l10n_ve_igtf y l10n_ve_deductible corren antes en el
        MRO, pero antes de llegar aqui solo hacen validaciones de lectura; la numeracion
        de l10n_ve_invoice se aplica sobre lo que devuelve el super, que no incluye los
        excluidos.
        """
        if not self.env.context.get(AUTOPOST_CUSTOM_CONTEXT):
            custom = self.filtered(
                lambda m: m.auto_post == "custom" and m.state == "draft"
            )
            if custom:
                if not soft:
                    raise UserError(
                        _(
                            "%(document)s is scheduled to be posted automatically on %(date)s.",
                            document=custom[0].display_name,
                            date=format_date(self.env, custom[0].auto_post_custom_date),
                        )
                    )
                self -= custom
        return super()._post(soft=soft)

    @api.model
    def _autopost_custom_today(self):
        """Hoy segun la zona horaria de la compania (America/Caracas por defecto), no la del
        usuario del cron."""
        tz = self.env.company.partner_id.tz or DEFAULT_TZ
        return fields.Date.context_today(self.with_context(tz=tz))

    @api.model
    def _autopost_custom_domain(self, today):
        """Custom vencidas que se pueden intentar hoy (las que ya fallaron hoy esperan a
        manana, asi el cron no gira sobre las mismas)."""
        return [
            ("state", "=", "draft"),
            ("auto_post", "=", "custom"),
            ("auto_post_custom_date", "<=", today),
            "|",
            ("auto_post_custom_last_attempt", "=", False),
            ("auto_post_custom_last_attempt", "<", today),
        ]

    @api.model
    def _autopost_draft_entries(self, batch_size=100):
        """Reemplazo SIN super de `_autopost_draft_entries` del core (account 19).

        Por que sin super: los documentos 'custom' esperan en borrador con `date` = hoy, asi
        que el dominio del core (`auto_post != 'no'`, `date <= hoy`) los incluiria siempre,
        el cron los reintentaria en bucle (ir.cron relanza mientras se procesen registros) y
        los at_date reales quedarian sin publicar tras el limit=100. La unica forma de
        sacarlos del lote es modificar el dominio, que no se puede inyectar desde un super.
        Riesgo de upgrade: si el core cambia este metodo hay que re-copiarlo; un test fija
        el dominio del core para detectarlo.

        Despues del lote estandar procesa las custom vencidas
        (`_autopost_custom_draft_entries`).
        """
        domain = [
            ("state", "=", "draft"),
            ("date", "<=", fields.Date.context_today(self)),
            ("auto_post", "!=", "no"),
            ("auto_post", "!=", "custom"),
        ]
        moves = self.search(domain, limit=batch_size)
        remaining = len(moves) if len(moves) < batch_size else self.search_count(domain)
        custom_today = self._autopost_custom_today()
        remaining += self.search_count(self._autopost_custom_domain(custom_today))
        self.env["ir.cron"]._commit_progress(remaining=remaining)

        self._autopost_standard_batch(moves, domain)
        self._autopost_custom_draft_entries(batch_size=batch_size)

    @api.model
    def _autopost_standard_batch(self, moves, domain):
        """Cuerpo del lote estandar, copia fiel del core (`_autopost_draft_entries`)."""
        try:  # try posting in batch
            moves._post()
            self.env["ir.cron"]._commit_progress(len(moves))
            return
        except UserError:  # if at least one move cannot be posted, handle moves one by one
            self.env.cr.rollback()

        for move in moves:
            try:
                move = move.try_lock_for_update().filtered_domain(domain)
                if not move:
                    continue
                move._post()
                self.env["ir.cron"]._commit_progress(1)
            except UserError as e:
                self.env.cr.rollback()
                msg = _(
                    "The move could not be posted for the following reason: %(error_message)s",
                    error_message=e,
                )
                move.message_post(body=msg, message_type="comment")
                move.auto_post = "no"
                self.env["ir.cron"]._commit_progress(1)

    @api.model
    def _autopost_custom_draft_entries(self, batch_size=100):
        """Publica un lote de documentos 'custom' cuya fecha ya llego.

        Cada documento va en su propio savepoint: si falla (p. ej. no hay tasa exacta ese
        dia) se deshace, queda 'custom' con sus fechas originales, se deja el motivo en el
        chatter y se reintenta al dia siguiente.
        """
        today = self._autopost_custom_today()
        Move = self.with_context(tz=self.env.company.partner_id.tz or DEFAULT_TZ)
        domain = Move._autopost_custom_domain(today)
        moves = Move.search(domain, order="auto_post_custom_date, id", limit=batch_size)
        for move in moves:
            move = move.try_lock_for_update().filtered_domain(domain)
            if not move:
                continue
            error = None
            try:
                with self.env.cr.savepoint():
                    move._autopost_custom_publish()
            except Exception as e:  # pylint: disable=broad-except
                if not isinstance(e, UserError):
                    _logger.exception("Custom auto-post of move %s failed", move.id)
                error = e
            if error is not None:
                # Fuera del savepoint: el rollback ya descarto los cambios del intento.
                move.message_post(
                    body=_(
                        "The automatic posting scheduled for %(date)s could not be done: "
                        "%(error)s. It will be retried the next day.",
                        date=format_date(self.env, move.auto_post_custom_date),
                        error=error,
                    ),
                    message_type="comment",
                )
                move.auto_post_custom_last_attempt = today
            self.env["ir.cron"]._commit_progress(1)

    def _autopost_custom_publish(self):
        """Pone las fechas de publicacion y publica el documento. Lanza si algo falla.

        Los chequeos que en el flujo manual viven en `action_post` (bloqueo fiscal de
        l10n_ve_fiscal_lock_days, fechas respecto al documento origen de las notas en
        l10n_ve_invoice) no corren con `_post`, asi que se ejecutan aqui de forma
        explicita. Las validaciones de accion de usuario de `action_post` (alerta de
        confirmacion, limite de credito) no aplican a una publicacion automatica, igual
        que en el cron nativo.
        """
        self.ensure_one()
        move = self.with_context(**{AUTOPOST_CUSTOM_CONTEXT: True})
        publish_date = move.auto_post_custom_date
        vals = {
            "date": publish_date,
            "invoice_date": publish_date,
            "invoice_date_display": publish_date,
        }
        dates_changed = any(
            move[fname] != value for fname, value in vals.items()
        )
        move.write(vals)
        if dates_changed and not move.manually_set_rate and not move.asset_id:
            # La tasa del dia de publicacion, exacta: si no existe lanza UserError y el
            # documento sigue en borrador. Una cuota de activo (``asset_id``) nunca la
            # recalcula: lleva la tasa de adquisicion fijada al crearla.
            move._compute_rate()
        if hasattr(move, "_check_tax_lock_date"):
            move._check_tax_lock_date()
        if hasattr(move, "_check_dates_not_in_future"):
            move._check_dates_not_in_future()
        # Se conserva `auto_post_custom_date` como historial. Con 'no' el core tampoco
        # intenta copiar el documento como recurrente (`_copy_recurring_entries`).
        move.auto_post = "no"
        move._post()
        if move.state != "posted":
            raise UserError(_("The document could not be posted."))

    # ------------------------------------------------------------------
    # Activos fijos: cuotas de depreciación futuras
    # ------------------------------------------------------------------
    @api.model
    def _prepare_move_for_asset_depreciation(self, vals):
        """
        Las cuotas de depreciación de periodos que aún no terminan quedan en borrador con la
        fecha de adquisición del activo como fecha contable (``date``, coherente con la tasa
        de adquisición que llevan como tasa manual), ``auto_post='custom'`` y
        ``auto_post_custom_date`` con la fecha real del periodo: el cron de
        l10n_ve_accountant las publica ese día y entonces escribe ``date`` = esa fecha.
        ``asset_depreciation_beginning_date`` no se toca.

        Solo se modifica el diccionario del super, sin asumir claves adicionales.

        Las cuotas de depreciación (``asset_move_type == 'depreciation'``) llevan SIEMPRE la
        tasa de la fecha de adquisición del activo como tasa manual: así la cuota publicada
        el día de su fecha conserva el valor alterno con el que se planificó y no se
        revaloriza al publicar, con o sin ``binaural_account_asset`` (que fija la tasa de la
        factura de compra; aquí se pisa con la de adquisición). La tasa se toma tal cual de
        ``compute_rate``: si no hay tasa en esa fecha lanza su UserError y no se crean las
        cuotas.

        Fuera de alcance: los demás tipos (``negative_revaluation``, ``disposal``,
        ``modify`` con moneda distinta, etc.) se dejan como los devuelve el super.
        """
        move_vals = super()._prepare_move_for_asset_depreciation(vals)
        today = fields.Date.context_today(self)
        if (
            move_vals.get("asset_move_type") == "depreciation"
            and not move_vals.get("asset_value_change")
            and move_vals.get("date")
            and move_vals["date"] > today
        ):
            move_vals.update(
                {
                    "date": vals["asset_id"].acquisition_date,
                    "auto_post": "custom",
                    "auto_post_custom_date": move_vals["date"],
                }
            )
        if move_vals.get("asset_move_type") == "depreciation":
            rate_values = vals["asset_id"]._get_acquisition_rate_values()
            if rate_values:
                move_vals.update({"manually_set_rate": True, **rate_values})
        return move_vals

    def _asset_period_sort_key(self):
        """Orden cronológico de la cuota dentro del plan: la fecha real del periodo.

        Un borrador de cuota ('custom') lleva como fecha contable la de adquisición del
        activo, así que ordenar por ``date`` lo pondría antes de las cuotas ya publicadas.
        ``auto_post_custom_date`` se conserva al publicar (con el mismo valor que ``date``),
        por lo que sirve de clave tanto para borradores como para publicadas.
        """
        self.ensure_one()
        return (self.auto_post_custom_date or self.date, self._origin.id)

    # Se re-declara el ``@api.depends`` del padre: el de un override reemplaza al original.
    @api.depends(
        "asset_id",
        "depreciation_value",
        "asset_id.total_depreciable_value",
        "asset_id.already_depreciated_amount_import",
        "state",
        "auto_post_custom_date",
    )
    def _compute_depreciation_cumulative_value(self):
        """Copia de ``account_asset`` (enterprise 19) que solo cambia la clave de orden.

        Se reemplaza sin ``super`` porque el padre ordena por ``(date, id)`` y con la fecha
        de adquisición en los borradores el saldo acumulado de cada cuota saldría mal. Riesgo
        de upgrade: si enterprise cambia el cuerpo hay que re-copiarlo; un test fija el
        resultado.
        """
        self.asset_depreciated_value = 0
        self.asset_remaining_value = 0
        fields_to_protect = [
            self._fields["asset_remaining_value"],
            self._fields["asset_depreciated_value"],
        ]
        with self.env.protecting(fields_to_protect, self.asset_id.depreciation_move_ids):
            for asset in self.asset_id:
                depreciated = asset.already_depreciated_amount_import
                remaining = asset.total_depreciable_value - asset.already_depreciated_amount_import
                for move in asset.depreciation_move_ids.sorted(
                    lambda mv: mv._asset_period_sort_key()
                ):
                    if move.state != "cancel":
                        remaining -= move.depreciation_value
                        depreciated += move.depreciation_value
                    move.asset_remaining_value = remaining
                    move.asset_depreciated_value = depreciated
