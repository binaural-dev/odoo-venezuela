from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    def unlink(self):
        for record in self:
            invoice = record.env["account.move"]
            if record.debit_move_id.move_type == "out_invoice":
                invoice = record.debit_move_id.move_id
            if record.credit_move_id.move_type == "out_invoice":
                invoice = record.credit_move_id.move_id
            if invoice and invoice.commission_payment_state != "not_paid":
                raise ValidationError(
                    _("You can't remove a payment with invoice commmission in progress or paid.")
                )

        return super().unlink()

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for record in res:
            invoice = record.env["account.move"]
            if record.debit_move_id.move_type == "out_invoice":
                invoice = record.debit_move_id.move_id
            if record.credit_move_id.move_type == "out_invoice":
                invoice = record.credit_move_id.move_id
            if (
                invoice
                and invoice.commission_invoice_date_field == "invoice_reception_date"
                and invoice.invoice_reception_date == False
            ):
                raise ValidationError(
                    _("You can't add a payment to an invoice without reception date.")
                )
        return res
