from odoo import fields, models

import logging

_logger = logging.getLogger(__name__)


class AccountPaymenTerm(models.Model):
    _inherit = "account.payment.term"

    # QUE PLANTEAR
    # COMO SE TOMARA EL PRECIO FIJO PARA LOS TERMINOS DEPAGO
    # CON QUETASA SE CALCULARA

    def _compute_terms(self, date_ref, *args, **kwargs):
        """El plazo se cuenta desde la fecha de la factura, no desde la fecha de tasa.

        El core calcula los vencimientos con `invoice_date`, que esta localizacion
        redefine como "Fecha de tasa". `account.move._compute_needed_terms` pasa la
        fecha de la factura (`invoice_date_display`) por el contexto
        `l10n_ve_term_date_ref`; sin ese contexto el calculo no cambia.
        """
        date_ref = self.env.context.get("l10n_ve_term_date_ref") or date_ref
        return super()._compute_terms(date_ref, *args, **kwargs)
