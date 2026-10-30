from odoo import models, api, fields


class AccountRetention(models.Model):
    _inherit = "account.retention"

    is_digitalized = fields.Boolean(string="Digitized", default=False, copy=False, tracking=True)
    show_digital_retention_iva = fields.Boolean(string="Show Digital Retention", compute="_compute_visibility_button", copy=False)
    show_digital_retention_islr = fields.Boolean(string="Show Digital Retention", compute="_compute_visibility_button", copy=False)
    control_number_tfhka = fields.Char(string="Control Number", copy=False)
    document_number_tfhka = fields.Char(string="Document Number TFHKA", copy=False)
    annulled_tfhka = fields.Boolean(string="Annulled in TFHKA", default=False, copy=False, tracking=True)

    def generate_document_digital(self):
        # All logic lives in the service layer (tfhka.retention.service),
        # including the sequence alert wizard flow.
        return self.env["tfhka.retention.service"].send_retention(self)

    def action_post(self):
        res = super().action_post()
        for retention in self:
            if (
                retention.type_retention in ("iva", "islr")
                and retention.type == "in_invoice"
                and retention.company_id.invoice_digital_tfhka
                and not retention.is_digitalized
                and retention.env.context.get("l10n_ve_invoice_digital_auto_retention")
            ):
                document_type = "05" if retention.type_retention == "iva" else "06"
                # account_retention_alert=True: equivalente a "confirmar y
                # continuar" del wizard de alerta de secuencia. En el flujo
                # automatico no hay nadie para responder ese wizard, asi que
                # se adopta el correlativo igual que haria un usuario al
                # confirmar la alerta manualmente.
                retention.with_context(
                    document_type=document_type, account_retention_alert=True
                ).generate_document_digital()
        return res

    def action_cancel_retention(self):
        """Boton unico de anulacion: si esta digitalizada en TFHKA y no
        anulada, primero pide el motivo y anula alla (el wizard encadena
        despues la cancelacion nativa); si no, cancela directo en Odoo."""
        self.ensure_one()
        if self.is_digitalized and not self.annulled_tfhka:
            return {
                "type": "ir.actions.act_window",
                "name": "Cancel in The Factory HKA",
                "res_model": "tfhka.annul.wizard",
                "view_mode": "form",
                "target": "new",
                "context": {"default_retention_id": self.id},
            }
        return self.action_cancel()

    @api.depends('state', 'is_digitalized')
    def _compute_visibility_button(self):
        for record in self:
            record.show_digital_retention_iva = True
            record.show_digital_retention_islr = True
            if record.state == 'emitted' and not record.is_digitalized and record.company_id.invoice_digital_tfhka:
                record.show_digital_retention_iva = False
                record.show_digital_retention_islr = False
