from odoo import models, api, exceptions, fields, _


class AccountMove(models.Model):
    _inherit = "account.move"

    def check_print_out_invoice(self):
        res = super().check_print_out_invoice()
        data = self
        if data.partner_id.action_number:
            res["info"] = [f"ACCION: {data.partner_id.action_number.number}"]

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
                    "name": f"[{line.product_id.default_code}] {line.product_id.name} {line.name}"
                    if line.product_id
                    else line.name,
                }
            )
        res["invoice_lines"] = _invoice_lines
        return res

    def check_print_out_refund(self):
        res = super().check_print_out_refund()
        if self.partner_id.action_number:
            res["info"] = [f"ACCION: {self.partner_id.action_number.number}"]

        _invoice_lines = []
        for line in self.invoice_line_ids:
            price_vef = line.price_unit
            if self.company_id.currency_id.id != self.env.ref("base.VEF").id:
                price_vef = line.foreign_price
            _invoice_lines.append(
                {
                    "tax": line.tax_ids[0].fiscal_code if line.tax_ids else 0,
                    "price_unit": price_vef,
                    "quantity": line.quantity,
                    "code": False,
                    "name": f"[{line.product_id.default_code}] {line.product_id.name} {line.name}"
                    if line.product_id
                    else line.name,
                }
            )
        res["invoice_lines"] = _invoice_lines
        return res
