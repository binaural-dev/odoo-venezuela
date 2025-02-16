from odoo import fields, models

import logging

_logger = logging.getLogger(__name__)


class AccountPaymenTerm(models.Model):
    _inherit = "account.payment.term"

    # QUE PLANTEAR
    # COMO SE TOMARA EL PRECIO FIJO PARA LOS TERMINOS DEPAGO
    # CON QUETASA SE CALCULARA

