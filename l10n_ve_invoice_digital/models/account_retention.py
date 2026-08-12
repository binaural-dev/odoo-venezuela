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

    def action_annul_tfhka(self):
        # Opens the wizard that captures the annulment reason (automatic date/time).
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Cancel in The Factory HKA",
            "res_model": "tfhka.annul.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_retention_id": self.id},
        }

    @api.depends('state', 'is_digitalized')
    def _compute_visibility_button(self):
        for record in self:
            record.show_digital_retention_iva = True
            record.show_digital_retention_islr = True
            if record.state == 'emitted' and not record.is_digitalized and record.company_id.invoice_digital_tfhka:
                record.show_digital_retention_iva = False
                record.show_digital_retention_islr = False
