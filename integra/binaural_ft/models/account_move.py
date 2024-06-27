from odoo import api, fields, models
import base64
from datetime import datetime, timedelta
from odoo.exceptions import UserError, ValidationError
from ..utils.constants import *

import logging

_logger = logging.getLogger(__name__)

MAX_CHAR_LINE = 64
CHAR_PER_LINE = 44


def get_spaces(string1, string2, type_a=False):
    char = MAX_CHAR_LINE if not type_a else 48
    len_char = char - len(string1) - len(string2)
    spaces = "".join([" " for x in range(len_char)])
    return string1 + spaces + string2


class AccountMove(models.Model):
    _inherit = "account.move"

    def get_receipt_base(self):
        lines = []
        lines.append(TXT_ALIGN_CT + TXT_BOLD_ON + b"SENIAT")
        lines.append(encode_text("RIF " + self.company_id.vat))
        for line in self.set_info_in_receipt().get(str(self.company_id.id), False)["header"]:
            lines.append(TXT_BOLD_OFF + encode_text(line))
        lines.append(
            TXT_ALIGN_LT
            + b"RIF/C.I.: "
            + encode_text(self.partner_id.prefix_vat + "-" + self.partner_id.vat)
        )
        lines.append(TXT_ALIGN_LT + b"RAZON SOCIAL: " + encode_text(self.partner_id.name))
        lines.append(
            TXT_ALIGN_LT + b"DIRECCION: " + encode_text(self.partner_id.contact_address_complete)
        )
        if self.partner_id.phone:
            lines.append(TXT_ALIGN_LT + b"TELEFONO: " + encode_text(self.partner_id.phone))
        lines = self.set_info_extra(lines)
        text_move_type = "FACTURA"
        if self.move_type == "out_invoice":
            lines.append(TXT_ALIGN_CT + encode_text(text_move_type))
        if self.move_type == "out_refund":
            text_move_type = "NOTA DE CREDITO"
            lines.append(b"#FAC: " + encode_text(self.reversed_entry_id.name))
            lines.append(
                encode_text(
                    "#CONTROL/SERIAL IF: "
                    + self.set_info_in_receipt().get(str(self.company_id.id), False)["serial"]
                )
            )
            lines.append(TXT_ALIGN_CT + encode_text(text_move_type))
        lines.append(
            TXT_ALIGN_LT + encode_text(get_spaces(text_move_type + ":", self.remove_code_in_name()))
        )
        lines.append(
            encode_text(
                get_spaces(
                    "FECHA: " + datetime.now().strftime("%d-%m-%Y"),
                    "HORA: " + datetime.now().strftime("%H:%M:%S"),
                )
            )
        )
        lines.append(SEPARATOR_SMALL)

        subtotal = 0
        subtotal_16 = 0
        exento = 0

        for line in self.invoice_line_ids:
            text_lines = []
            aliquot = " (E)"
            quantity = ""
            amount = line.foreign_subtotal

            if line.tax_ids and line.tax_ids[0].amount > 0:
                aliquot = " (G)"
            if line.quantity != 1:
                lines.append(
                    encode_text(
                        str(line.quantity) + "x Bs " + "{0:,.2f}".format(line.foreign_price)
                    )
                )

            text = quantity + line.name + aliquot
            subtotal = round(subtotal + line.foreign_subtotal, 2)
            if line.tax_ids and line.tax_ids[0].amount == 16.00:
                subtotal_16 = round(amount + subtotal_16, 2)
            else:
                exento = round(amount + exento, 2)

            price = "Bs " + "{0:,.2f}".format(amount)

            while len(text) > CHAR_PER_LINE:
                if len(text) > CHAR_PER_LINE:
                    text_lines.append(text[:CHAR_PER_LINE])
                    text = text[CHAR_PER_LINE:]

            text_lines.append(get_spaces(text, price))
            lines.append(encode_text("\n".join(text_lines)))

        iva_16 = round(subtotal_16 * 0.16, 2)

        lines.append(SEPARATOR_SMALL)
        lines.append(encode_text(get_spaces("SUBTTL", "Bs " + "{0:,.2f}".format(subtotal))))
        lines.append(SEPARATOR_SMALL)
        if exento > 0:
            lines.append(
                encode_text(get_spaces("EXENTO          Bs " + "{0:,.2f}".format(exento), ""))
            )
        if iva_16:
            lines.append(
                encode_text(
                    get_spaces(
                        "BI G16,00%      Bs " + "{0:,.2f}".format(subtotal_16) + "   IVA G16,00%",
                        "Bs " + "{0:,.2f}".format(iva_16),
                    )
                )
            )
        lines.append(SEPARATOR_SMALL)
        # AGREGA LOS PAGOS HECHOS EN POS ANTES DEL TOTAL
        if self.pos_order_ids[0].payment_ids:
            for payment in reversed(self.pos_order_ids[0].payment_ids):
                lines.append(
                    TXT_ALIGN_LT
                    + encode_text(
                        get_spaces(
                            payment.payment_method_id.payment_name_in_mf,
                            "Bs " + "{0:,.2f}".format(payment.foreign_amount),
                        )
                    )
                )
            lines.append(SEPARATOR_SMALL)
        # _________________________________________________________
        lines.append(
            TXT_FONT_A
            + TXT_BOLD_ON
            + encode_text(get_spaces("TOTAL", "Bs " + "{0:,.2f}".format(subtotal + iva_16), True))
        )
        # MOSTRAR EL TOTAL EFECTIVO AL FINAL DEL TICKET
        # lines.append(
        #     TXT_BOLD_OFF
        #     + encode_text(get_spaces("EFECTIVO", "Bs " + "{0:,.2f}".format(subtotal + iva_16)))
        # )
        # _________________________________________________________
        lines.append(
            TXT_FONT_A
            + TXT_BOLD_OFF
            + TXT_ITALICS
            + encode_text(
                get_spaces(
                    "MH",
                    self.set_info_in_receipt().get(str(self.company_id.id), False)["serial"],
                    True,
                )
            )
        )

        data = b"\x1b\x74\x02"
        for line in lines:
            data += TXT_FONT_B + line + b"\n"

        data += b"\x1d\x56\x41\n"
        return data.decode("latin-1")

    def set_info_in_receipt(self):
        return {}

    def set_info_extra(self, lines):
        if self.pos_order_ids:
            lines.append(
                TXT_ALIGN_LT + b"OPERADOR: " + encode_text(self.pos_order_ids[0].employee_id.name)
            )
            lines.append(
                TXT_ALIGN_LT
                + encode_text(self.pos_order_ids[0].pos_reference.upper().replace(" ", ": "))
            )
        return lines

    def remove_code_in_name(self):
        name_without_code = ""
        if self.journal_id.code:
            name_without_code = self.name.replace(
                f"{self.journal_id.code}/{self.invoice_date.year}/", ""
            )
            name_without_code = name_without_code.zfill(8)
        return name_without_code or self.name


def encode_text(text):
    return str(text).replace('"', "").replace("ñ", "n").replace("Ñ", "N").encode("latin-1")
