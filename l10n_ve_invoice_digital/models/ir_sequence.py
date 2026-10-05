from odoo import _, fields, models
from odoo.exceptions import UserError


class IrSequence(models.Model):
    _inherit = "ir.sequence"

    prefix_locked = fields.Boolean(
        compute="_compute_prefix_locked",
        help="Technical: true when this sequence is the invoice/refund "
        "sequence of a digital journal that already has invoices. The "
        "Factory HKA uses the prefix as the invoice series, so it can no "
        "longer be changed.",
    )

    def _get_locking_journal(self):
        """Diario digital que ya tiene facturas y usa esta secuencia, si existe.

        The Factory HKA usa el prefijo de la secuencia de facturas/notas de
        crédito del diario como la "serie" del documento (ver
        ``tfhka.document.service._get_series``). Una vez que el diario ya
        tiene facturas creadas, cambiar el prefijo desincroniza la serie que
        ya se reportó a TFHKA de la que Odoo sigue usando localmente.
        """
        self.ensure_one()
        journals = self.env["account.journal"].search(
            [
                ("digital_invoice", "=", True),
                "|",
                ("sequence_id", "=", self.id),
                ("refund_sequence_id", "=", self.id),
            ]
        )
        move_model = self.env["account.move"]
        for journal in journals:
            if move_model.search_count([("journal_id", "=", journal.id)]):
                return journal
        return self.env["account.journal"]

    def _compute_prefix_locked(self):
        for sequence in self:
            sequence.prefix_locked = bool(sequence._get_locking_journal())

    def write(self, vals):
        if "prefix" in vals:
            for sequence in self:
                if vals["prefix"] == sequence.prefix:
                    continue
                journal = sequence._get_locking_journal()
                if journal:
                    raise UserError(
                        _(
                            "Cannot change the prefix of the sequence used by journal "
                            "'%(journal)s': it already has invoices created. The Factory "
                            "HKA uses this prefix as the invoice series, and changing it "
                            "would break the fiscal correlative already reported.",
                            journal=journal.name,
                        )
                    )
        return super().write(vals)
