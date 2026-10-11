import logging
import re
import unicodedata

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_round

_logger = logging.getLogger(__name__)


class AccountMoveInh(models.Model):
    _inherit = "account.move"

    is_credit = fields.Boolean(default=False)
    mf_serial = fields.Char(
        string="Fiscal machine serial", default=False, copy=False, tracking=True
    )
    mf_invoice_number = fields.Char(
        string="Sequence number", default=False, copy=False, tracking=True
    )
    mf_reportz = fields.Char(string="Report number Z", default=False, copy=False, tracking=True)

    print_type = fields.Selection(related="company_id.invoice_print_type", store=True)

    def has_printed(self, invoice_number):
        """Verifica si el número fiscal ya fue usado en otra factura.

        :return: True si existe más de un account.move con ese número
        """
        if not invoice_number:
            return False

        return (
            len(
                self.env["account.move"].search(
                    [("mf_invoice_number", "=", invoice_number)], limit=2
                )
            )
            > 1
        )

    def report_z(self, serial, response):
        """Asigna el reporte Z (contador + 1) a todas las facturas de la
        máquina que están pendientes de Z.

        Llamado desde el frontend tras imprimir el Reporte Z (I0Z) y leer S1.
        """
        data = response.get("data", False)

        if not response.get("valid", False):
            raise ValidationError(response.get("message", "No se pudo imprimir el reporte Z"))

        serial = data.get("_registeredMachineNumber")

        account_moves = self.env["account.move"].search(
            ["&", ("mf_serial", "=", serial), ("mf_reportz", "=", False)]
        )

        number_of_last_z = data.get("_dailyClosureCounter", False)
        if False in [data, number_of_last_z]:
            _logger.info("NO SE RECUPERO EL Z DE LA MAQUINA: %s", serial)
            number_of_last_z = self._get_z_and_add_one(serial)
            _logger.info("ULTIMO Z: %s", number_of_last_z)

        for invoice in account_moves:
            invoice.write({"mf_reportz": int(number_of_last_z) + 1})
        return number_of_last_z

    def _get_z_and_add_one(self, serial):
        account_move = self.env["account.move"].search(
            ["&", ("mf_serial", "=", serial), ("mf_reportz", "!=", False)],
            order="mf_reportz desc",
            limit=1,
        )
        if not account_move:
            return 0
        return account_move.mf_reportz

    @api.onchange("is_credit")
    def _onchange_is_credit(self):
        for i in self:
            if i.mf_invoice_number:
                raise ValidationError(_("You can't edit a paper invoice"))
            if i.is_credit:
                if i.amount_residual != i.amount_total:
                    raise ValidationError(
                        _("You cannot convert an invoice to credit if it has associated payments")
                    )

    def _mf_persist_vals(self, result_data):
        """Construye los vals fiscales a persistir tras una impresión Web Serial.

        Incluye mf_invoice_number, mf_serial y mf_reportz (si viene).
        """
        self.ensure_one()
        vals = {
            "mf_invoice_number": result_data.get("sequence"),
            "mf_serial": result_data.get("serial_machine"),
        }
        if result_data.get("mf_reportz"):
            vals["mf_reportz"] = result_data["mf_reportz"]
        return vals

    def log_mf_print_failure(self, action=None, reason=None):
        """Deja constancia en el chatter de un intento fallido de impresión fiscal.

        Llamado desde el frontend Web Serial cuando no hay conexión con la
        máquina fiscal o el driver reporta un error.
        """
        action_labels = {
            "print_out_invoice": _("Factura"),
            "print_out_refund": _("Nota de crédito"),
            "print_debit_note": _("Nota de débito"),
            "reprint_document": _("Reimpresión"),
        }
        label = action_labels.get(action, action or _("Documento fiscal"))
        body = _(
            "No se ha impreso en máquina fiscal (%(label)s) porque no hay "
            "máquina fiscal conectada.",
            label=label,
        )
        if reason:
            body += _(" Detalle: %(reason)s", reason=reason)
        for move in self:
            move.message_post(body=body)
        return True

    def _get_mf_flag21(self):
        """Flag 21 (formato numérico TFHKA) para impresión Web Serial."""
        self.ensure_one()
        return self.company_id.mf_flag_21 or "00"

    def _mf_in_other_currency(self):
        """Factura en una moneda distinta a la de la compañía (compañía en Bs,
        factura en USD): la máquina fiscal trabaja en la moneda de la compañía
        y los montos del documento hay que llevarlos a ella."""
        self.ensure_one()
        return bool(self.currency_id) and self.currency_id != self.company_currency_id

    def _mf_company_rate(self):
        """Tasa moneda de la factura → moneda de la compañía con la que quedó
        contabilizada (multiplicador)."""
        self.ensure_one()
        if self.amount_total:
            return abs(self.amount_total_signed) / self.amount_total
        return 1 / self.invoice_currency_rate if self.invoice_currency_rate else 0.0

    @api.model
    def _mf_company_item(self, amount, quantity, rounding=0.01):
        """Unitario y descuento por monto (`q-`) de un ítem cuyo monto en la
        moneda de la compañía es `amount` y su cantidad `quantity` (magnitudes).

        La MF arma el ítem como unitario (2 decimales) × cantidad; el asiento
        valora la línea sin redondear el unitario. El unitario se redondea
        hacia ARRIBA al céntimo y el exceso se descuenta sobre el ítem, para
        que la MF imprima el mismo monto que el asiento
        (5 × $ 2,32 a 803,34 = 9.318,74 → 5 × 1.863,75 − 0,01).

        KEEP IN SYNC WITH: binaural_pos_multicurrency_mf (integra-addons)
        static/src/utils/mf_company_amounts.js :: mfCompanyItem
        """
        amount = float_round(amount or 0.0, precision_rounding=rounding)
        quantity = quantity or 0.0
        if amount <= 0 or quantity <= 0:
            return {"price_unit": 0.0, "discount_amount": 0.0}
        # Se quita el ruido de coma flotante antes de subir al céntimo.
        steps = float_round(
            float_round(amount / quantity / rounding, precision_digits=6),
            precision_digits=0,
            rounding_method="UP",
        )
        price_unit = float_round(max(steps, 1) * rounding, precision_rounding=rounding)
        item_amount = float_round(price_unit * quantity, precision_rounding=rounding)
        discount = float_round(item_amount - amount, precision_rounding=rounding)
        return {"price_unit": price_unit, "discount_amount": max(discount, 0.0)}

    def _mf_build_payment_lines(self, absolute=False):
        """Construye las líneas de pago para la máquina fiscal desde el
        widget de pagos de la factura.

        :param absolute: usar valor absoluto de los montos (NC)
        """
        self.ensure_one()
        payment_lines = []
        payments = self.invoice_payments_widget

        if not payments:
            payment_lines.append({"amount": 0, "payment_method": "01"})
            return payment_lines

        if self._mf_in_other_currency():
            return self._mf_build_company_payment_lines(payments["content"], absolute=absolute)

        for payment in payments["content"]:
            journal_id = self.env["account.journal"].search(
                [("name", "=", payment["journal_name"])], limit=1
            )
            amount = abs(payment["amount"]) if absolute else payment["amount"]
            new_payment = {
                "amount": amount,
                "payment_method": journal_id["payment_method"] or "01",
            }
            if payment["currency_id"] != self.env.ref("base.VEF").id:
                new_payment["amount"] = amount * self.foreign_inverse_rate

            payment_lines.append(new_payment)

        return payment_lines

    def _mf_build_company_payment_lines(self, content, absolute=False):
        """Pagos de una factura en otra moneda, en la moneda de la compañía.

        El widget trae lo conciliado en la moneda de la factura: se lleva a la
        compañía a la tasa de la factura, la misma de las líneas del documento
        fiscal. La diferencia en cambio no es un pago y no se envía. Si la
        factura quedó pagada completa, el último pago absorbe el redondeo para
        que la suma sea el total de la factura en la moneda de la compañía.
        """
        self.ensure_one()
        company_currency = self.company_currency_id
        rate = self._mf_company_rate()
        payment_lines = []
        paid_currency = 0.0
        for payment in content:
            if payment.get("is_exchange"):
                continue
            journal = self.env["account.journal"].search(
                [("name", "=", payment["journal_name"])], limit=1
            )
            amount_currency = payment["amount"]
            paid_currency += amount_currency
            amount = company_currency.round(amount_currency * rate)
            payment_lines.append(
                {
                    "amount": abs(amount) if absolute else amount,
                    "payment_method": journal["payment_method"] or "01",
                }
            )
        if not payment_lines:
            return [{"amount": 0, "payment_method": "01"}]
        if self.currency_id.is_zero(paid_currency - self.amount_total):
            total = abs(self.amount_total_signed)
            others = sum(abs(line["amount"]) for line in payment_lines[:-1])
            last = payment_lines[-1]
            sign = -1 if last["amount"] < 0 else 1
            last["amount"] = sign * company_currency.round(total - others)
        return payment_lines

    def _mf_build_invoice_lines(self):
        """Construye las líneas de producto para la máquina fiscal.

        El precio se expresa en VEF (usa foreign_price si la compañía opera
        en otra moneda) con el descuento % de línea ya aplicado; el
        formateo/redondeo final lo hace el driver Web Serial.
        """
        self.ensure_one()
        if self._mf_in_other_currency():
            return self._mf_build_company_invoice_lines()

        invoice_lines = []
        vef_id = self.env.ref("base.VEF").id

        for line in self.invoice_line_ids:
            price_vef = line.price_unit
            if self.company_id.currency_id.id != vef_id:
                price_vef = line.foreign_price
            if line.discount:
                price_vef = price_vef * (1 - line.discount / 100.0)
            invoice_lines.append(
                {
                    "tax": line.tax_ids[0].fiscal_code if line.tax_ids else 0,
                    "price_unit": price_vef,
                    "quantity": line.quantity,
                    "code": False,
                    "name": self._mf_line_name(line),
                }
            )

        return invoice_lines

    def _mf_line_name(self, line):
        if line.product_id:
            return (
                f"[{line.product_id.default_code}] "
                f"{self._normalize_product_name(line.product_id.name)}"
            )
        return self._normalize_product_name(line.name)

    def _mf_build_company_invoice_lines(self):
        """Líneas de una factura en otra moneda, en la moneda de la compañía.

        Igual que con las facturas en Bs (que mandan `price_unit` tal cual), el
        precio lleva o no el IVA según el impuesto, que se configura alineado
        con el tipo de tasa de la MF: con impuesto excluido va la base de la
        línea (su `balance` del asiento) y la MF le suma el IVA; con impuesto
        incluido va el total con IVA y la MF lo separa. El descuento % ya está
        en esos montos.
        """
        self.ensure_one()
        company_currency = self.company_currency_id
        rounding = company_currency.rounding
        rate = self._mf_company_rate()
        invoice_lines = []
        excluded_tax = False
        for line in self.invoice_line_ids:
            tax = line.tax_ids[:1]
            if tax.price_include:
                amount = company_currency.round(abs(line.price_total) * rate)
            else:
                amount = abs(line.balance)
                excluded_tax = excluded_tax or bool(tax)
            invoice_lines.append(
                {
                    "tax": tax.fiscal_code if tax else 0,
                    "quantity": line.quantity,
                    "code": False,
                    "name": self._mf_line_name(line),
                    "_amount": amount,
                    "_negative": line.price_subtotal < 0,
                }
            )

        # Con todos los impuestos incluidos, la suma de los ítems es el total
        # del documento: la última línea absorbe el redondeo de convertir cada
        # total por separado.
        positive = [vals for vals in invoice_lines if vals["_amount"] and not vals["_negative"]]
        if positive and not excluded_tax and not any(v["_negative"] for v in invoice_lines):
            diff = company_currency.round(
                abs(self.amount_total_signed) - sum(v["_amount"] for v in positive)
            )
            if diff and positive[-1]["_amount"] + diff > 0:
                positive[-1]["_amount"] = company_currency.round(positive[-1]["_amount"] + diff)

        for vals in invoice_lines:
            amount = vals.pop("_amount")
            negative = vals.pop("_negative")
            quantity = abs(vals["quantity"] or 0.0)
            if negative:
                item = self._mf_company_item(amount, 1, rounding)
                vals["price_unit"] = -item["price_unit"] / quantity if quantity else 0.0
                continue
            item = self._mf_company_item(amount, quantity, rounding)
            vals["price_unit"] = item["price_unit"]
            if item["discount_amount"]:
                vals["discount_amount"] = item["discount_amount"]
        return invoice_lines

    def _mf_build_base_payload(self):
        """Bloques comunes del payload para el driver Web Serial."""
        self.ensure_one()
        return {
            "flag_21": self._get_mf_flag21(),
            "company_id": {"name": self.company_id.name},
            "partner_id": {
                "name": self._normalize_product_name(self.partner_id.name),
                "vat": f"{self.partner_id.prefix_vat}-{self.partner_id.vat}",
                "address": self.partner_id.street or False,
                "phone": self.partner_id.phone or False,
            },
        }

    def check_reprint(self):
        """Valida y devuelve los datos para reimprimir el documento actual."""
        if not self.mf_invoice_number:
            raise ValidationError(_("The invoice has not already been printed"))

        if not self.invoice_line_ids:
            return {"valid": False, "message": "La factura no tiene lineas"}

        return {
            "type": self.move_type,
            "mf_number": self.mf_invoice_number,
            "is_debit_note": self.is_debit_journal,
        }

    def check_print_out_invoice(self):
        """Valida la factura y construye el payload de impresión fiscal."""
        if self.mf_invoice_number:
            raise ValidationError(_("The invoice has already been printed"))
        if self.state in ["draft", "cancel"]:
            raise ValidationError(_("Cannot print an invoice without validation"))
        if self.invoice_date != fields.Date.context_today(self):
            raise ValidationError(_("Cannot print an invoice with a future date"))
        if self.is_credit and self.amount_residual != self.amount_total:
            raise ValidationError(_("You cannot print a credit invoice with associated payments"))

        if not self.invoice_line_ids:
            return {"valid": False, "message": "La factura no tiene lineas"}

        payload = self._mf_build_base_payload()
        payload["invoice_lines"] = self._mf_build_invoice_lines()
        payload["payment_lines"] = self._mf_build_payment_lines()
        return payload

    def print_out_invoice(self, values):
        """Persiste los datos fiscales tras imprimir la factura."""
        _logger.info("MF print_out_invoice values: %s", values)
        result_data = values.get("data", {})
        sequence = result_data.get("sequence")

        self.write(self._mf_persist_vals(result_data))

        if self.has_printed(sequence):
            warning = _(
                "Ya existe otra factura con el mismo número fiscal %(sequence)s. "
                "Revisa las facturas anteriores.",
                sequence=sequence,
            )
            self.message_post(body=warning)
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Advertencia"),
                    "message": warning,
                    "type": "warning",
                    "sticky": True,
                },
            }

    def check_print_out_refund(self):
        """Valida la NC y construye el payload de impresión fiscal."""
        if self.mf_invoice_number:
            raise ValidationError(_("The invoice has already been printed"))
        if self.invoice_date != fields.Date.context_today(self):
            raise ValidationError(_("The credit note must be made on the same day"))
        if self.state in ["draft", "cancel"]:
            raise ValidationError(_("Cannot print an invoice without validation"))
        if not self.reversed_entry_id or not self.reversed_entry_id.mf_invoice_number:
            raise ValidationError(
                _("The original invoice has no fiscal machine number (mf_invoice_number)")
            )

        if not self.invoice_line_ids:
            return {"valid": False, "message": "La factura no tiene lineas"}

        payment_lines = []

        # En NC de POS, usar pagos reales de la orden para no perder la
        # separación por método fiscal (el widget puede agrupar). Buscar por
        # el move actual y por la factura afectada.
        candidate_move_ids = [self.id]
        if self.reversed_entry_id:
            candidate_move_ids.append(self.reversed_entry_id.id)

        pos_order = (
            self.env["pos.order"].search(
                [("account_move", "in", candidate_move_ids)],
                order="id desc",
                limit=1,
            )
            if "pos.order" in self.env
            else False
        )

        if pos_order and pos_order.payment_ids:
            for payment in pos_order.payment_ids:
                fiscal_method = (
                    getattr(payment.payment_method_id, "code_fiscal_printer", False)
                    or payment.payment_method_id.journal_id.payment_method
                    or "01"
                )
                payment_lines.append(
                    {
                        "amount": abs(payment.amount or 0.0),
                        "payment_method": fiscal_method,
                    }
                )
        else:
            payment_lines = self._mf_build_payment_lines(absolute=True)

        payload = self._mf_build_base_payload()
        payload["invoice_affected"] = {
            "number": self.reversed_entry_id.mf_invoice_number,
            "serial_machine": self.reversed_entry_id.mf_serial,
            "date": self.reversed_entry_id.invoice_date.strftime("%d/%m/%Y"),
        }
        payload["invoice_lines"] = self._mf_build_invoice_lines()
        payload["payment_lines"] = payment_lines
        return payload

    def print_out_refund(self, values):
        """Persiste los datos fiscales tras imprimir la NC."""
        _logger.info("MF print_out_refund values: %s", values)
        result_data = values.get("data", {})
        self.write(self._mf_persist_vals(result_data))

    def check_print_debit_note(self):
        """Valida la ND y construye el payload de impresión fiscal."""
        if self.mf_invoice_number:
            raise ValidationError(_("The invoice has already been printed"))
        if self.invoice_date != fields.Date.context_today(self):
            raise ValidationError(_("The debit note must be made on the same day"))
        if self.state in ["draft", "cancel"]:
            raise ValidationError(_("Cannot print an invoice without validation"))
        if not self.debit_origin_id or not self.debit_origin_id.mf_invoice_number:
            raise ValidationError(
                _("The original invoice has no fiscal machine number (mf_invoice_number)")
            )

        if not self.invoice_line_ids:
            return {"valid": False, "message": "La factura no tiene lineas"}

        payload = self._mf_build_base_payload()
        payload["invoice_affected"] = {
            "number": self.debit_origin_id.mf_invoice_number,
            "serial_machine": self.debit_origin_id.mf_serial,
            "date": self.debit_origin_id.invoice_date.strftime("%d/%m/%Y"),
        }
        payload["invoice_lines"] = self._mf_build_invoice_lines()
        payload["payment_lines"] = self._mf_build_payment_lines()
        return payload

    def print_debit_note(self, values):
        """Persiste los datos fiscales tras imprimir la ND."""
        _logger.info("MF print_debit_note values: %s", values)
        result_data = values.get("data", {})
        self.write(self._mf_persist_vals(result_data))

    def _normalize_product_name(self, name):
        if not name:
            return ""

        normalized = unicodedata.normalize("NFKD", str(name))
        no_accents = "".join(c for c in normalized if not unicodedata.combining(c))
        cleaned = re.sub(r"[^\w\s]", " ", no_accents)
        final_name = re.sub(r"\s+", " ", cleaned).strip()

        return final_name
