from odoo import models, api, fields


class AccountRetention(models.Model):
    _inherit = "account.retention"

    is_digitalized = fields.Boolean(string="Digitized", default=False, copy=False, tracking=True)
    show_digital_retention_iva = fields.Boolean(string="Show Digital Retention", compute="_compute_visibility_button", copy=False)
    show_digital_retention_islr = fields.Boolean(string="Show Digital Retention", compute="_compute_visibility_button", copy=False)
    control_number_tfhka = fields.Char(string="Control Number", copy=False)

    def generate_document_digital(self):
        # Toda la lógica vive en la capa de servicios (tfhka.retention.service),
        # incluido el flujo del wizard de alerta de secuencia.
        return self.env["tfhka.retention.service"].send_retention(self)

    @api.depends('state', 'is_digitalized')
    def _compute_visibility_button(self):
        for record in self:
            record.show_digital_retention_iva = True
            record.show_digital_retention_islr = True
            if record.state == 'emitted' and not record.is_digitalized and record.company_id.invoice_digital_tfhka:
                record.show_digital_retention_iva = False
                record.show_digital_retention_islr = False
