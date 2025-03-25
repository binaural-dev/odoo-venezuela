from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


class AccountMoveInh(models.Model):
    _inherit = "account.move"

    def default_fiscal_machine(self):
        """
        Return unique fiscal machine on IoT Box
        """
        return self.env["iot.device"].search([("type", "=", "fiscal_data_module")], limit=1).id

    is_credit = fields.Boolean(default=False)
    iot_mf = fields.Many2one(
        "iot.device",
        string="Fiscal Machine",
        default=default_fiscal_machine,
        copy=False,
        domain=[("serial_machine", "!=", False)],
    )
    iot_box = fields.Many2one(
        "iot.box", string="IoT Box", related="iot_mf.iot_id", default=False, copy=False
    )
    mf_serial = fields.Char(
        string="Fiscal machine serial", default=False, copy=False, tracking=True
    )
    mf_invoice_number = fields.Char(
        string="Sequence number", default=False, copy=False, tracking=True
    )
    mf_reportz = fields.Char(string="Report number Z", default=False, copy=False, tracking=True)
    
    print_type = fields.Selection(
        related='company_id.invoice_print_type',
        store=True
    )

    def has_printed(self, invoice_number):
        """
        Check if the invoice sequence has already been printed
        -----------
        Return
        Recordset of account.move if exist
        """
        return (
            len(
                self.env["account.move"].search(
                    [("mf_invoice_number", "=", invoice_number)], limit=2
                )
            )
            > 1
        )

    def check_report_z(self, serial):
        account_moves = self.env["account.move"].search(
            ["&", ("mf_serial", "=", serial), ("mf_reportz", "=", False)]
        )

        return True

    def report_z(self, serial, response):
        data = response.get("data", False)

        if not response.get("valid", False):
            raise ValidationError(response.get("message", "No se pudo imprimir el reporte Z"))

        serial = data.get("_registeredMachineNumber")

        account_moves = self.env["account.move"].search(
            ["&", ("mf_serial", "=", serial), ("mf_reportz", "=", False)]
        )

        _numberOfLastZReport = data.get("_dailyClosureCounter", False)
        if False in [data, _numberOfLastZReport]:
            _logger.info("NO SE RECUPERO EL Z DE LA MAQUINA: %s", serial)
            _numberOfLastZReport = self._get_z_and_add_one(serial)
            _logger.info("ULTIMO Z: %s", _numberOfLastZReport)

        for invoice in account_moves:
            invoice.write({"mf_reportz": int(_numberOfLastZReport) + 1})
        return _numberOfLastZReport

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

    def check_reprint(self):
        if not self.mf_invoice_number:
            raise ValidationError(_("The invoice has not already been printed"))
        if not self.iot_mf:
            raise ValidationError(_("The invoice has no fiscal machine assigned"))
        data = self
        if not data:
            return {"valid": False, "message": "No se envio datos"}

        if not data.invoice_line_ids:
            return {"valid": False, "message": "La factura no tiene lineas"}

        _data = {
            "identifier": data.iot_mf.identifier,
            "iot_ip": data.iot_box.ip,
            "type": data.move_type,
            "mf_number": data.mf_invoice_number,
            "is_debit_note": data.is_debit_journal
        }
        return _data

    def check_print_out_invoice(self):
        # if not self.journal_id.fiscal:
        #     raise ValidationError(_("You cannot print an invoice with a non-fiscal journal"))
        if self.mf_invoice_number:
            raise ValidationError(_("The invoice has already been printed"))
        if not self.iot_mf:
            raise ValidationError(_("The invoice has no fiscal machine assigned"))
        if self.state in ["draft", "cancel"]:
            raise ValidationError(_("Cannot print an invoice without validation"))
        if self.invoice_date != fields.Date.today():
            raise ValidationError(_("Cannot print an invoice with a future date"))
        if self.is_credit and self.amount_residual != self.amount_total:
            raise ValidationError(_("You cannot print a credit invoice with associated payments"))

        data = self

        if not data:
            return {"valid": False, "message": "No se envio datos"}

        if not data.invoice_line_ids:
            return {"valid": False, "message": "La factura no tiene lineas"}

        payment_lines = []
        payments = data.invoice_payments_widget

        if not payments:
            payment_lines.append({"amount": 0, "payment_method": "01"})
        else:
            payments = payments["content"]
            for payment in payments:
                journal_id = self.env["account.journal"].search(
                    [("name", "=", payment["journal_name"])], limit=1
                )
                new_payment = {
                    "amount": payment["amount"],
                    "payment_method": journal_id["payment_method"] or "01",
                }
                if payment["currency_id"] != data.env.ref("base.VEF").id:
                    new_payment["amount"] = payment["amount"] * data.foreign_inverse_rate

                payment_lines.append(new_payment)

        _invoice_lines = []
        for line in data.invoice_line_ids:
            price_vef = line.price_unit
            if data.company_id.currency_id.id != data.env.ref("base.VEF").id:
                price_vef = line.foreign_price
            _invoice_lines.append(
                {
                    "tax": line.tax_ids[0].fiscal_code if line.tax_ids else 0,
                    "price_unit": price_vef,
                    "quantity": line.quantity,
                    "code": False,
                    "name": f"[{line.product_id.default_code}] {line.product_id.name}"
                    if line.product_id
                    else line.name,
                }
            )

        _data = {
            "flag_21": data.iot_mf.flag_21,
            "identifier": data.iot_mf.identifier,
            "iot_ip": data.iot_box.ip,
            "company_id": {"name": data.company_id.name},
            "partner_id": {
                "name": data.partner_id.name,
                "vat": f"{data.partner_id.prefix_vat}-{data.partner_id.vat}",
                "address": data.partner_id.street or False,
                "phone": data.partner_id.phone or False,
            },
            "invoice_lines": _invoice_lines,
            "payment_lines": payment_lines,
        }
        return _data

    def print_out_invoice(self, values):
        self.write(
            {
                "mf_invoice_number": values["sequence"],
                "mf_serial": values["serial_machine"],
            }
        )

        if self.has_printed(values["sequence"]):
            context = dict(self._context or {})
            context[
                "message"
            ] = f"""
            An invoice with the same sequence number {values["sequence"]}
            Please review previous invoices
            """

            return {
                "name": f"Warning",
                "type": "ir.actions.act_window",
                "view_mode": "form",
                "res_model": "sh.message.wizard",
                "target": "new",
                "context": context,
            }
            
    def check_print_out_refund(self):
        """
        Print out refund in fiscal machine
        """
        if not self.iot_mf:
            raise ValidationError(_("The invoice has no fiscal machine assigned"))
        # if self.iot_mf.serial_machine != self.reversed_entry_id.mf_serial:
        #     raise ValidationError(_("The credit note must be made in the same fiscal machine"))
        if self.invoice_date != fields.Date.today():
            raise ValidationError(_("The credit note must be made on the same day"))
        if self.state in ["draft", "cancel"]:
            raise ValidationError(_("Cannot print an invoice without validation"))

        data = self

        if not data:
            return {"valid": False, "message": "No se envio datos"}

        if not data.invoice_line_ids:
            return {"valid": False, "message": "La factura no tiene lineas"}

        payment_lines = []
        payments = data.invoice_payments_widget

        if not payments:
            payment_lines.append({"amount": 0, "payment_method": "01"})
        else:
            payments = payments["content"]
            for payment in payments:
                journal_id = self.env["account.journal"].search(
                    [("name", "=", payment["journal_name"])], limit=1
                )
                new_payment = {
                    "amount": payment["amount"],
                    "payment_method": journal_id["payment_method"] or "01",
                }
                if payment["currency_id"] != data.env.ref("base.VEF").id:
                    new_payment["amount"] = payment["amount"] * data.foreign_inverse_rate

                payment_lines.append(new_payment)

        _invoice_lines = []
        for line in data.invoice_line_ids:
            price_vef = line.price_unit
            if data.company_id.currency_id.id != data.env.ref("base.VEF").id:
                price_vef = line.foreign_price
            _invoice_lines.append(
                {
                    "tax": line.tax_ids[0].fiscal_code if line.tax_ids else 0,
                    "price_unit": price_vef,
                    "quantity": line.quantity,
                    "code": False,
                    "name": f"[{line.product_id.default_code}] {line.product_id.name}"
                    if line.product_id
                    else line.name,
                }
            )

        _data = {
            "flag_21": data.iot_mf.flag_21,
            "identifier": data.iot_mf.identifier,
            "iot_ip": data.iot_box.ip,
            "company_id": {"name": data.company_id.name},
            "partner_id": {
                "name": data.partner_id.name,
                "vat": f"{data.partner_id.prefix_vat}-{data.partner_id.vat}",
                "address": data.partner_id.street or False,
                "phone": data.partner_id.phone or False,
            },
            "invoice_affected": {
                "number": data.reversed_entry_id.mf_invoice_number,
                "serial_machine": data.reversed_entry_id.mf_serial,
                "date": data.reversed_entry_id.invoice_date.strftime("%d/%m/%Y"),
            },
            "invoice_lines": _invoice_lines,
            "payment_lines": payment_lines,
        }

        return _data

    def print_out_refund(self, values):
        self.write({"mf_invoice_number": values["sequence"], "mf_serial": values["serial_machine"]})

    def _get_reconciled_info_JSON_values(self):
        res = super()._get_reconciled_info_JSON_values()
        reconciled_vals = []
        for payment in res:
            payment_id = self.env["account.payment"].search(
                [("id", "=", payment["account_payment_id"])]
            )
            payment["mf_payment_method"] = payment_id.journal_id.payment_method
            reconciled_vals.append(payment)
        return reconciled_vals

        
    def check_print_debit_note(self):
        """
        Print debit note in fiscal machine
        """
        if not self.iot_mf:
            raise ValidationError(_("The invoice has no fiscal machine assigned"))
        # if self.iot_mf.serial_machine != self.debit_origin_id.mf_serial:
        #     raise ValidationError(_("The debit note must be made in the same fiscal machine"))
        if self.invoice_date != fields.Date.today():
            raise ValidationError(_("The debit note must be made on the same day"))
        if self.state in ["draft", "cancel"]:
            raise ValidationError(_("Cannot print an invoice without validation"))

        data = self

        if not data:
            return {"valid": False, "message": "No se envio datos"}

        if not data.invoice_line_ids:
            return {"valid": False, "message": "La factura no tiene lineas"}

        payment_lines = []
        payments = data.invoice_payments_widget

        if not payments:
            payment_lines.append({"amount": 0, "payment_method": "01"})
        else:
            payments = payments["content"]
            for payment in payments:
                journal_id = self.env["account.journal"].search(
                    [("name", "=", payment["journal_name"])], limit=1
                )
                new_payment = {
                    "amount": payment["amount"],
                    "payment_method": journal_id["payment_method"] or "01",
                }
                if payment["currency_id"] != data.env.ref("base.VEF").id:
                    new_payment["amount"] = payment["amount"] * data.foreign_inverse_rate

                payment_lines.append(new_payment)

        _invoice_lines = []
        for line in data.invoice_line_ids:
            price_vef = line.price_unit
            if data.company_id.currency_id.id != data.env.ref("base.VEF").id:
                price_vef = line.foreign_price
            _invoice_lines.append(
                {
                    "tax": line.tax_ids[0].fiscal_code if line.tax_ids else 0,
                    "price_unit": price_vef,
                    "quantity": line.quantity,
                    "code": False,
                    "name": f"[{line.product_id.default_code}] {line.product_id.name}"
                    if line.product_id
                    else line.name,
                }
            )

        _data = {
            "flag_21": data.iot_mf.flag_21,
            "identifier": data.iot_mf.identifier,
            "iot_ip": data.iot_box.ip,
            "company_id": {"name": data.company_id.name},
            "partner_id": {
                "name": data.partner_id.name,
                "vat": f"{data.partner_id.prefix_vat}-{data.partner_id.vat}",
                "address": data.partner_id.street or False,
                "phone": data.partner_id.phone or False,
            },
            "invoice_affected": {
                "number": data.debit_origin_id.mf_invoice_number,
                "serial_machine": data.debit_origin_id.mf_serial,
                "date": data.debit_origin_id.invoice_date.strftime("%d/%m/%Y"),
            },
            "invoice_lines": _invoice_lines,
            "payment_lines": payment_lines,
        }

        return _data
    
    def print_debit_note(self, values):
        self.write({"mf_invoice_number": values["sequence"], "mf_serial": values["serial_machine"]})