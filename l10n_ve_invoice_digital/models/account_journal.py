from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from ..utils import status_message


class AccountJournal(models.Model):
    _inherit = "account.journal"

    digital_invoice = fields.Boolean(tracking=True)

    digital_invoice_lock = fields.Boolean(
        compute="_compute_digital_invoice_lock",
        string="Digital invoice lock",
    )

    payment_method_code = fields.Many2one(
        "payment.method.tfhka",
        help="This code identifies the payment method. It is used to digitize and link the corresponding payment method.",
    )

    tfhka_serie_id = fields.Many2one(
        "tfhka.serie",
        string="TFHKA Series",
        tracking=True,
        domain="[('company_id', '=', company_id)]",
        help="Series sent to TFHKA for documents on this journal. Synchronized "
             "from the TFHKA API (Settings > The Factory HKA > Generate Token). "
             "Optional: a journal without one sends an empty series to TFHKA. "
             "You'll get a (non-blocking) warning if another digital-invoice "
             "journal in the company is also without one.",
    )

    def _tfhka_serie_sharing_is_allowed(self, other):
        """True si ``self`` y ``other`` pueden compartir ``tfhka_serie_id``
        sin bloquearse. Dos casos, cada uno porque el diario en cuestión
        emite documentos bajo la identidad fiscal de otro diario a
        propósito, no por error de configuración:

        - Uno de los dos es el diario de facturación a terceros
          (``is_third_party_invoice_journal``, del módulo opcional
          ``binaural_third_party_invoice`` -- ``getattr`` con default porque
          ese módulo no es dependencia de este; si no está instalado, el
          campo no existe y nunca cuenta como "permitido").
        - Uno de los dos es el diario de notas de débito (``is_debit``, de
          ``l10n_ve_invoice`` -- esa sí es dependencia de este módulo, así
          que se lee directo, sin getattr)."""
        return bool(
            getattr(self, "is_third_party_invoice_journal", False)
            or getattr(other, "is_third_party_invoice_journal", False)
            or self.is_debit
            or other.is_debit
        )

    def _find_other_journal_sharing_tfhka_serie(self):
        """Otro diario de la misma compañía que ya use esta misma
        ``tfhka_serie_id`` (no vacía), si lo hay."""
        self.ensure_one()
        if not self.tfhka_serie_id:
            return self.browse()
        return self.search([
            ("id", "!=", self.id),
            ("company_id", "=", self.company_id.id),
            ("tfhka_serie_id", "=", self.tfhka_serie_id.id),
        ], limit=1)

    @api.constrains("tfhka_serie_id")
    def _check_tfhka_serie_id_not_shared(self):
        """Dos diarios no pueden compartir la misma serie TFHKA -- salvo las
        excepciones de _tfhka_serie_sharing_is_allowed (facturación a
        terceros, notas de débito), en cuyo caso solo se avisa (no
        bloqueante, ver _onchange_tfhka_serie_id_warning / write() /
        create()). Reemplaza un ``unique()`` de ``_sql_constraints``: una
        restricción SQL no puede tener esta excepción."""
        for journal in self:
            other = journal._find_other_journal_sharing_tfhka_serie()
            if other and not journal._tfhka_serie_sharing_is_allowed(other):
                raise ValidationError(
                    _(
                        "This TFHKA series is already assigned to "
                        "'%(other)s'. Two journals can't share the same "
                        "series unless one of them is the third-party "
                        "invoicing journal or the debit note journal."
                    )
                    % {"other": other.display_name}
                )

    def _tfhka_serie_is_empty(self):
        """True si este diario, a efectos de TFHKA, no manda serie: ni
        tfhka_serie_id vacío ni explícitamente "NO APLICA" cuentan como una
        serie real (ver _get_tfhka_series(), que trata ambos casos igual)."""
        self.ensure_one()
        return (
            not self.tfhka_serie_id
            or self.tfhka_serie_id.name == self.env["tfhka.serie"].NO_APLICA
        )

    def _find_other_journal_without_tfhka_serie(self):
        """Otro diario de facturación digital de la misma compañía que
        también mande serie vacía a TFHKA (sin tfhka_serie_id, o con
        "NO APLICA"), si lo hay. No es obligatorio asignar una serie (ver
        _get_tfhka_series()), pero más de un diario mandando serie vacía los
        deja indistinguibles entre sí del mismo modo que si compartieran
        serie -- de ahí el aviso (no bloqueante, ver
        _onchange_tfhka_serie_id_empty_warning / write() / create())."""
        self.ensure_one()
        if not self.digital_invoice or not self._tfhka_serie_is_empty():
            return self.browse()
        return self.search([
            ("id", "!=", self.id),
            ("company_id", "=", self.company_id.id),
            ("digital_invoice", "=", True),
            "|",
            ("tfhka_serie_id", "=", False),
            ("tfhka_serie_id.name", "=", self.env["tfhka.serie"].NO_APLICA),
        ], limit=1)

    @api.onchange("tfhka_serie_id", "digital_invoice")
    def _onchange_tfhka_serie_id_warning(self):
        """Aviso no bloqueante en el formulario -- no impide guardar. Dos
        casos, en este orden: comparte una serie no vacía (permitido para
        las excepciones de _tfhka_serie_sharing_is_allowed, ver
        _check_tfhka_serie_id_not_shared), o queda sin serie y otro diario
        también."""
        for journal in self:
            shared_with = journal._find_other_journal_sharing_tfhka_serie()
            if shared_with and journal._tfhka_serie_sharing_is_allowed(shared_with):
                return {
                    "warning": {
                        "title": _("Shared TFHKA series"),
                        "message": _(
                            "This journal shares its TFHKA series with "
                            "'%(other)s'. Make sure that's intentional -- "
                            "usually only the third-party invoicing journal "
                            "or the debit note journal should share one with "
                            "its parent journal."
                        )
                        % {"other": shared_with.display_name},
                    }
                }
            other_empty = journal._find_other_journal_without_tfhka_serie()
            if other_empty:
                return {
                    "warning": {
                        "title": _("More than one journal without a TFHKA series"),
                        "message": _(
                            "'%(other)s' is already configured without a TFHKA "
                            "series. Both will send an empty series to TFHKA -- "
                            "consider assigning one to this journal."
                        )
                        % {"other": other_empty.display_name},
                    }
                }

    def _warn_tfhka_serie_id(self):
        """Mismos avisos que el onchange, pero como nota en el chatter --
        para que quede un rastro visible también cuando el diario se crea o
        edita fuera del formulario (API, import, script)."""
        for journal in self:
            shared_with = journal._find_other_journal_sharing_tfhka_serie()
            if shared_with and journal._tfhka_serie_sharing_is_allowed(shared_with):
                journal.message_post(
                    body=status_message(
                        _(
                            "This journal shares its TFHKA series with "
                            "'%(other)s'. Make sure that's intentional -- "
                            "usually only the third-party invoicing journal "
                            "or the debit note journal should share one with "
                            "its parent journal."
                        )
                        % {"other": shared_with.display_name},
                        "warning",
                    ),
                )
                continue
            other_empty = journal._find_other_journal_without_tfhka_serie()
            if other_empty:
                journal.message_post(
                    body=status_message(
                        _(
                            "This journal has no TFHKA series assigned, and "
                            "'%(other)s' already doesn't have one either. Both "
                            "will send an empty series to TFHKA."
                        )
                        % {"other": other_empty.display_name},
                        "warning",
                    ),
                )

    def _get_tfhka_series(self):
        """Letras de serie a enviar a TFHKA para este diario: única fuente de
        verdad (``tfhka_serie_id.name``), para que ``tfhka.document.service``
        no tenga que derivarla del prefijo de una secuencia no relacionada.

        Deliberadamente independiente de ``company.group_sales_invoicing_series``
        -- ese flag controla la numeración legacy por secuencia
        (``l10n_ve_invoice``'s ``get_sequence()``), un mecanismo no
        relacionado; acoplarlos significaba que desactivar la numeración
        legacy apagaba también la serie enviada a TFHKA (unidigital, en
        ``binaural_unidigital``, tampoco los acopla).

        Vacío si el diario no tiene serie asignada, o si la serie asignada es
        "NO APLICA" -- esa es la forma en que TFHKA representa "sin serie" en
        /ConsultaNumeraciones, pero no es un valor que se le pueda reenviar
        tal cual en /Emision. TFHKA acepta serie vacía para sistemas
        centralizados (ver el instructivo técnico de su API)."""
        self.ensure_one()
        name = self.tfhka_serie_id.name or ""
        if name == self.env["tfhka.serie"].NO_APLICA:
            return ""
        return name

    def _compute_digital_invoice_lock(self):
        """Compute if the journal has digital invoices and lock the field with readonly attr.

        Sin ``@api.depends`` a propósito: la dependencia real es la existencia de
        account.move digitalizados, que no es expresable como ruta de campos. Al
        no estar almacenado, se recalcula al leer el formulario, que es cuando
        importa. ``limit=1`` porque solo interesa si hay al menos uno.
        """
        move_obj = self.env["account.move"]
        for journal in self:
            has_moves = bool(
                move_obj.search_count(
                    [
                        ("journal_id", "=", journal.id),
                        ("is_digitalized", "=", True),
                    ],
                    limit=1,
                )
            )
            journal.digital_invoice_lock = has_moves
            if has_moves:
                journal.digital_invoice = True

    def write(self, vals):
        """Prevent disabling digital_invoice if there are existing digital invoices."""
        if "digital_invoice" in vals and not vals.get("digital_invoice"):
            move_obj = self.env["account.move"]
            for journal in self:
                has_moves = move_obj.search_count(
                    [
                        ("journal_id", "=", journal.id),
                        ("is_digitalized", "=", True),
                    ]
                )
                if has_moves:
                    raise ValidationError(
                        _(
                            "Cannot disable digital billing on a journal with existing digital invoices."
                        )
                    )
        res = super().write(vals)
        if (
            "tfhka_serie_id" in vals
            or "digital_invoice" in vals
            or "is_third_party_invoice_journal" in vals
        ):
            self._warn_tfhka_serie_id()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        journals = super().create(vals_list)
        journals.filtered(lambda j: j.digital_invoice or j.tfhka_serie_id)._warn_tfhka_serie_id()
        return journals
