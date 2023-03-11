from odoo import models, fields, api, _


class AccountMoveRetention(models.Model):
    _inherit = "account.move"

    apply_islr_retention = fields.Boolean(
        string="Apply ISLR Retention?",
        default=False,
        track_visibility="onchange",
    )

    apply_iva_retention = fields.Boolean(
        string="Apply IVA Retention?",
        default=False,
        track_visibility="onchange",
    )

    islr_voucher_number = fields.Char(
        string="ISLR Voucher Number",
        track_visibility="onchange",
    )

    iva_voucher_number = fields.Char(
        string="IVA Voucher Number",
        track_visibility="onchange",
    )

    retention_islr_line_ids = fields.One2many(
        "account.retention.line",
        "invoice_id",
        string="ISLR Retention Lines",
    )

    retention_iva_line_ids = fields.One2many(
        "account.retention.line",
        "invoice_id",
        string="IVA Retention Lines",
    )

    generate_iva_retention = fields.Boolean(
        string="Generate IVA Retention?",
        default=False,
        track_visibility="onchange",
    )

    def action_register_payment(self):
        """
        Override the action_register_payment method to add the invoice lines to the payment register.
        """
        res = super().action_register_payment()
        if self.move_type in ["out_invoice", "out_refund", "in_invoice", "in_refund"]:
            res["context"]["default_retention_line_ids"] = self.invoice_line_ids if self.invoice_line_ids.filtered(lambda x: x.tax_ids.filtered(lambda y: y.tax_group_id.name == "IVA")) else False
            # res["context"]["default_invoice_line_ids"] = self.invoice_line_ids
            res["context"]["default_retention_type"] = self.move_type
        return res

