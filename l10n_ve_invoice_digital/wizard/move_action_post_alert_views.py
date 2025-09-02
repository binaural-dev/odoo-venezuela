from odoo import models, _
from odoo.exceptions import UserError, ValidationError

class MoveActionPostAlertWizard(models.TransientModel):
    _inherit = 'move.action.post.alert.wizard'

    def action_confirm(self):
        res = super(MoveActionPostAlertWizard, self).action_confirm()
        if self.move_id and self.env.company.invoice_digital_tfhka:
            for record in self.move_id :
                if record.sequence_number > 1:
                    previous_invoice = self.env["account.move"].search(
                        [
                            ("company_id", "=", record.company_id.id),
                            ("move_type", "=", record.move_type),
                            ("sequence_number", "!=", record.sequence_number),
                            ("is_digitalized", "=", False),
                            ("state", "=", "posted"),
                            ("journal_id", "=", record.journal_id.id),
                        ], order="sequence_number asc", limit=1, 
                    )
                    if previous_invoice and not previous_invoice.is_digitalized:
                        move_type = previous_invoice.move_type
                        if move_type == "out_invoice" and not previous_invoice.debit_origin_id:
                            raise UserError(_("The invoice %s has not been digitized") % (previous_invoice.name))
                        if move_type == "out_invoice" and previous_invoice.debit_origin_id:
                            raise UserError(_("The debit note %s has not been digitized") % (previous_invoice.name))
                        if move_type == "out_refund":
                            raise UserError(_("The credit note %s has not been digitized") % (previous_invoice.name))
                        
        return res

