# -*- coding: utf-8 -*-

from odoo import api, fields, models
import base64
from datetime import datetime, timedelta
from odoo.exceptions import UserError, ValidationError
from ..utils.constants import *

import logging

_logger = logging.getLogger(__name__)

MAX_CHAR_LINE = 64
CHAR_PER_LINE = 35


def get_spaces(string1, string2, type_a=True):
    char = MAX_CHAR_LINE if not type_a else 48
    len_char = char - len(string1) - len(string2)
    spaces = "".join([" " for x in range(len_char)])
    return string1 + spaces + string2


class Invoice(models.Model):
    _inherit = "sale.order"

    def get_receipt_base(self):
        lines = []
        lines.append(TXT_NORMAL + TXT_ALIGN_CT + TXT_BOLD_OFF + b"Pedido: " + self.name.encode())
        lines.append(b"")
        lines.append(TXT_ALIGN_LT + b"Cliente: " + str(self.partner_id.name).encode())
        lines.append(TXT_ALIGN_LT + b"R.I.F: " + str(self.partner_id.vat).encode())
        lines.append(TXT_ALIGN_LT + b"Telefono: " + str(self.partner_id.phone).encode())
        lines.append(
            TXT_ALIGN_LT + b"Direccion: " + str(self.partner_id.contact_address_complete).encode()
        )
        lines.append(TXT_ALIGN_LT + get_spaces("Fecha Emision:", str(self.date_order)).encode())
        lines.append(b"")
        lines.append(get_spaces("DESCRIPCION", "CANTIDAD").encode())
        for line in self.order_line:
            text_lines = []
            text = line.name

            while len(text) > CHAR_PER_LINE:
                if len(text) > CHAR_PER_LINE:
                    text_lines.append(text[:CHAR_PER_LINE])
                    text = text[CHAR_PER_LINE:]

            text_lines.append(get_spaces(text, str(line.product_uom_qty)))
            lines.append(SEPARATOR)
            lines.append("\n".join(text_lines).encode("latin-1"))
        lines.append(b"")
        lines.append(b"")
        data = b""
        for line in lines:
            data += TXT_FONT_A + line + b"\n"
        data += b"\x1d\x56\x41\n"
        return data.decode("latin-1")
