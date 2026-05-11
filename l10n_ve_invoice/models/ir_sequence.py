from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class IrSequence(models.Model):
    _inherit = "ir.sequence"

    code = fields.Char(copy=False)

    _UNIQUE_CODE_BY_COMPANY = {
        "invoice.correlative",
    }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self.check_sequence_exists(vals)
        return super().create(vals_list)
    
    def write(self, vals):
        for record in self:
            record.check_sequence_exists(vals)
        return super().write(vals)
    
    def check_sequence_exists(self, vals):
        """"Checks if a sequence with the given code already exists for the specified company."""
        seq_code = vals.get("code", self.code)
        company_id = vals.get("company_id", self.company_id.id)
        if seq_code and seq_code not in self._UNIQUE_CODE_BY_COMPANY:
            return
        if company_id and seq_code:
            domain = [
                ("code", "=", seq_code), 
                ("company_id", "=", company_id),
                ("active", "=", True),
            ]
            if self.ids:
                domain.append(("id", "not in", self.ids))
            sequence = self.sudo().search(domain, limit=1)
            if sequence:
                raise ValidationError(_("The sequence code '%s' already exists for this company. Please check your sequences.") % seq_code)