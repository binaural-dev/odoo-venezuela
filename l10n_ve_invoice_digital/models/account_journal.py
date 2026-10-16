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

    _sql_constraints = [
        (
            "tfhka_serie_id_uniq",
            "unique(tfhka_serie_id)",
            "This TFHKA series is already assigned to another journal.",
        ),
    ]

    def _find_other_journal_without_tfhka_serie(self):
        """Otro diario de facturación digital de la misma compañía que
        también esté sin tfhka_serie_id, si lo hay. No es obligatorio asignar
        una serie (ver _get_tfhka_series()), pero más de un diario mandando
        serie vacía a TFHKA los deja indistinguibles entre sí del mismo modo
        que si compartieran serie -- de ahí el aviso (no bloqueante, ver
        _onchange_tfhka_serie_id_empty_warning / write() / create())."""
        self.ensure_one()
        if self.tfhka_serie_id or not self.digital_invoice:
            return self.browse()
        return self.search([
            ("id", "!=", self.id),
            ("company_id", "=", self.company_id.id),
            ("digital_invoice", "=", True),
            ("tfhka_serie_id", "=", False),
        ], limit=1)

    @api.onchange("tfhka_serie_id", "digital_invoice")
    def _onchange_tfhka_serie_id_empty_warning(self):
        """Aviso no bloqueante en el formulario -- no impide guardar, solo
        avisa que ya hay otro diario sin serie."""
        for journal in self:
            other = journal._find_other_journal_without_tfhka_serie()
            if other:
                return {
                    "warning": {
                        "title": _("More than one journal without a TFHKA series"),
                        "message": _(
                            "'%(other)s' is already configured without a TFHKA "
                            "series. Both will send an empty series to TFHKA -- "
                            "consider assigning one to this journal."
                        )
                        % {"other": other.display_name},
                    }
                }

    def _warn_tfhka_serie_id_empty(self):
        """Mismo aviso que el onchange, pero como nota en el chatter -- para
        que quede un rastro visible también cuando el diario se crea o edita
        fuera del formulario (API, import, script)."""
        for journal in self:
            other = journal._find_other_journal_without_tfhka_serie()
            if other:
                journal.message_post(
                    body=status_message(
                        _(
                            "This journal has no TFHKA series assigned, and "
                            "'%(other)s' already doesn't have one either. Both "
                            "will send an empty series to TFHKA."
                        )
                        % {"other": other.display_name},
                        "warning",
                    ),
                )

    def _get_tfhka_series(self):
        """Letras de serie a enviar a TFHKA para este diario: única fuente de
        verdad (``tfhka_serie_id.name``), para que ``tfhka.document.service``
        no tenga que derivarla del prefijo de una secuencia no relacionada.

        Vacío si la compañía no factura por series (TFHKA acepta serie vacía
        para sistemas centralizados, ver el instructivo técnico de su API)."""
        self.ensure_one()
        if not self.company_id.group_sales_invoicing_series:
            return ""
        return self.tfhka_serie_id.name or ""

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
        if "tfhka_serie_id" in vals or "digital_invoice" in vals:
            self._warn_tfhka_serie_id_empty()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        journals = super().create(vals_list)
        journals.filtered(lambda j: j.digital_invoice)._warn_tfhka_serie_id_empty()
        return journals
