from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class IrSequence(models.Model):
    _inherit = "ir.sequence"

    def create(self, vals):
        self.check_sequence_exists(vals)
        return super().create(vals)
    
    def write(self, vals):
        self.check_sequence_exists(vals)
        return super().write(vals)
    
    def check_sequence_exists(self, vals):
        """"Checks if a sequence with the given code already exists for the specified company."""
        seq_code = vals.get("code", self.code)
        company_id = vals.get("company_id", self.company_id.id)
        # Realiza la validacion solo si se proporciona un company_id y un seq_code
        if company_id and seq_code:
            sequence = self.sudo().search([
                ("code", "=", seq_code), 
                ("company_id", "=", company_id),
                ("id", "!=", self.id)
            ])
            if sequence:
                raise ValidationError(_("The sequence code '%s' already exists for this company. Please check your sequences.") % seq_code)