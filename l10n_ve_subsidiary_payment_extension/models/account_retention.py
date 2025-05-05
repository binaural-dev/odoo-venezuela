from odoo import api, fields, models


class AccountRetention(models.Model):
    _inherit = "account.retention"

    account_analytic_id = fields.Many2one(
        "account.analytic.account",
        string="Subsidiary",
        compute="_compute_account_analytic_id",
        store=True,
    )

    @api.depends("retention_line_ids")
    def _compute_account_analytic_id(self):
        for retention in self:
            if not retention.retention_line_ids:
                continue
            retention.account_analytic_id = retention.retention_line_ids[0].account_analytic_id

    def action_post(self):
        res = super().action_post()
        for line in self.mapped("retention_line_ids"):
            line.payment_id.write({"account_analytic_id": line.move_id.account_analytic_id.id})
        return res

    def get_sequence_municipal_retention(self):
        """
        We assume that all the retention lines of the same retention will have the same subsidiary
        so we use the one of the first retention line we find.
        """
        subsidiary_municipal_supplier_retencion_sequence = self.retention_line_ids[
            0
        ].move_id.account_analytic_id.municipal_supplier_retentions_sequence_id
        if not subsidiary_municipal_supplier_retencion_sequence:
            return super().get_sequence_municipal_retention()
        return subsidiary_municipal_supplier_retencion_sequence
