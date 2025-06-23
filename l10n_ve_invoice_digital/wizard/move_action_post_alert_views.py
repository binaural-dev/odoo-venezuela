from odoo import models, _
from odoo.exceptions import UserError, ValidationError

class MoveActionPostAlertWizard(models.TransientModel):
    _inherit = 'move.action.post.alert.wizard'

    def action_confirm(self):
        res = super(MoveActionPostAlertWizard, self).action_confirm()
        if self.move_id and self.env.company.invoice_digital_tfhka:
            for record in self.move_id :
                if record.move_type == "out_invoice":
                    if record.sequence_number > 1:
                        previous_invoice = self.env["account.move"].search(
                            [
                                ("company_id", "=", record.company_id.id),
                                ("move_type", "=", "out_invoice"),
                                ("sequence_number", "!=", record.sequence_number),
                                ("is_digitalized", "=", False),
                                ("state", "=", "posted"),
                                ("journal_id", "=", record.journal_id.id),
                            ], order="sequence_number asc", limit=1, 
                        )
                        if previous_invoice and not previous_invoice.is_digitalized:
                            raise UserError(_("The invoice %s has not been digitized") % (previous_invoice.name))
                else:
                    record.generate_document_digital()
        return res

