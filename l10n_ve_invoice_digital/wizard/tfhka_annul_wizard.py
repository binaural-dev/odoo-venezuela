from odoo import fields, models


class TfhkaAnnulWizard(models.TransientModel):
    _name = "tfhka.annul.wizard"
    _description = "TFHKA Annul Wizard"

    retention_id = fields.Many2one(
        "account.retention", string="Retention", required=True, ondelete="cascade"
    )
    motivo = fields.Char(string="Reason for annulment", required=True)

    def action_confirm(self):
        self.ensure_one()
        self.env["tfhka.retention.service"].annul_retention(
            self.retention_id, self.motivo
        )
        return {"type": "ir.actions.act_window_close"}
