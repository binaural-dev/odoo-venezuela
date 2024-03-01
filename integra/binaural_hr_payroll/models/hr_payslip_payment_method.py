from io import BytesIO
from odoo import models, fields, api


class HrPayslipPaymentMethods(models.Model):
    _name = "hr.payslip.payment.methods"
    _description = "Show a report of the payment methods used on the payslips"

    name = fields.Char(related="bank_id.name", string="Bank Name")
    bank_id = fields.Many2one("res.bank", string="Bank")
    date_from = fields.Date()
    date_to = fields.Date()
    total = fields.Float(compute="_compute_total")

    payslip_ids = fields.Many2many(
        "hr.payslip", string="Payslips", compute="_compute_payslip_ids", store=True
    )

    def download_bnc_txt(self):
        self.ensure_one()
        url = f"/web/binary/download_bnc_txt?payment_method_id={self.id}"
        return {"type": "ir.actions.act_url", "url": url, "target": "self"}

    def generate_bnc_txt(self):
        self.ensure_one()
        txt = {}
        with BytesIO() as f:
            for payslip in self.payslip_ids:
                amount_without_decimals = str(payslip.net_wage).split(".")
                if len(amount_without_decimals[1]) < 2:
                    amount_without_decimals[1] = amount_without_decimals[1] + "0"
                amount_without_decimals = amount_without_decimals[0] + amount_without_decimals[1]

                f.write(b"NC ")
                f.write(b"%s" % (payslip.employee_id.bank_account_id.acc_number.encode("utf-8")))
                f.write(b"%s" % (amount_without_decimals.encode("utf-8")))
                f.write(b"%s" % (payslip.employee_id.prefix_vat.encode("utf-8")))
                f.write(b"%s\n" % (payslip.employee_id.vat.encode("utf-8")))
            txt["file"] = f.getvalue()
            txt[
                "filename"
            ] = f"BNC_TXT_{self.date_from.strftime('%d%m%Y')}_TO_{self.date_to.strftime('%d%m%Y')}.txt"
        return txt

    @api.depends("date_from", "date_to", "bank_id")
    def _compute_payslip_ids(self):
        self.payslip_ids = []
        for payment_method in self:
            payslip_ids = self.env["hr.payslip"].search(
                [
                    ("date_from", ">=", payment_method.date_from),
                    ("date_to", "<=", payment_method.date_to),
                    ("struct_category", "!=", "provision"),
                    ("employee_id.bank_account_id.bank_id", "=", payment_method.bank_id.id),
                    ("state", "=", "done"),
                ]
            )

            payment_method.payslip_ids = payslip_ids

    @api.depends("payslip_ids")
    def _compute_total(self):
        for payment_method in self:
            payment_method.total = sum(slip.net_wage for slip in payment_method.payslip_ids)
