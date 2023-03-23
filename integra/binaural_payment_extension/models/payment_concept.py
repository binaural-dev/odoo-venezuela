from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError


class PaymentConceptBinaural(models.Model):
    _name = "payment.concept"
    _description = "Payment Concept"

    name = fields.Char(string="Description", required=True, store=True)
    line_payment_concept_ids = fields.One2many(
        "payment.concept.line", "payment_concept_id", "Payment Concept Line", 
        store=True
    )
    status = fields.Boolean(default=True, string="Active?", store=True)

    @api.constrains("line_payment_concept_ids")
    def _constraint_line_payment_concept_ids(self):
        for record in self:
            type_person_id = []
            for line in record.line_payment_concept_ids:
                if line.type_person_id.id in type_person_id:
                    raise UserError(_("The type of person cannot be repeated."))
                else:
                    type_person_id.append(line.type_person_id.id)
