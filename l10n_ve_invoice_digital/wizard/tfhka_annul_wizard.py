from odoo import _, fields, models


class TfhkaAnnulWizard(models.TransientModel):
    _name = "tfhka.annul.wizard"
    _description = "TFHKA Annul Wizard"

    retention_id = fields.Many2one(
        "account.retention", string="Retention", required=True, ondelete="cascade"
    )
    reason = fields.Char(string="Reason for annulment", required=True)

    def action_confirm(self):
        self.ensure_one()
        self.env["tfhka.retention.service"].annul_retention(
            self.retention_id, self.reason
        )
        # Boton unico de anulacion: una vez anulada en TFHKA, se encadena la
        # cancelacion nativa en Odoo (reversa pagos/conciliacion) para que
        # ambos lados queden consistentes en una sola operacion.
        self.retention_id.action_cancel()
        self.retention_id.message_post(
            body=_("Retention also cancelled in Odoo (accounting entries reversed) as part of the unified cancellation."),
        )
        return {"type": "ir.actions.act_window_close"}
