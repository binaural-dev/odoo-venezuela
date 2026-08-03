import logging
import re
import unicodedata

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

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

    def _mf_build_invoice_lines(self):
        """Construye las líneas de producto para la máquina fiscal.

        El precio se expresa en VEF (usa foreign_price si la compañía opera
        en otra moneda) con el descuento % de línea ya aplicado; el
        formateo/redondeo final lo hace el driver Web Serial.
        """
        self.ensure_one()
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
                    "name": f"[{line.product_id.default_code}] {self._normalize_product_name(line.product_id.name)}"
                    if line.product_id
                    else self._normalize_product_name(line.name),
                }
            )

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
