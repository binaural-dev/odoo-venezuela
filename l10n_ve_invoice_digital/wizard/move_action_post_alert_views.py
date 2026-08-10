from odoo import models, _
from odoo.exceptions import UserError, ValidationError

class MoveActionPostAlertWizard(models.TransientModel):
    _inherit = 'move.action.post.alert.wizard'

    def action_confirm(self):
        res = super(MoveActionPostAlertWizard, self).action_confirm()
        
        if self.move_id and self.env.company.invoice_digital_tfhka:
            for record in self.move_id:
                # 1. Validar que la factura pertenezca a un diario digital antes de procesar lógicas de TFHKA
                if not record.journal_id.digital_invoice:
                    continue
                    
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
                            raise UserError(_("The invoice %(name)s has not been digitized", name=previous_invoice.name))
                        if move_type == "out_invoice" and previous_invoice.debit_origin_id:
                            raise UserError(_("The debit note %(name)s has not been digitized", name=previous_invoice.name))
                        if move_type == "out_refund":
                            raise UserError(_("The credit note %(name)s has not been digitized", name=previous_invoice.name))
                        
                if not record.company_id.digitalization_with_payment_tfhka:
                    record.generate_document_digital()

        return res

