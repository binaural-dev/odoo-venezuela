from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError


class PaymentConceptLine(models.Model):
    _name = "payment.concept.line"
    _description = "Payment Concept Line"

    _sql_constraints = [("unique_code", "UNIQUE(code)", "The concept code already exists")]

    pay_from = fields.Float(string="Payments greater than:")
    type_person_id = fields.Many2one(
        "type.person", string="Type person",store=True, required=True, domain=[("state", "=", True)]
    )
    payment_concept_id = fields.Many2one(
        "payment.concept",
        string="Associated Payment Concept",
        required=True,
        domain=[("status", "=", True)],
        ondelete="cascade",
    )
    percentage_tax_base = fields.Float(string="Percentage Taxable Base")
    tariff_id = fields.Many2one("fees.retention", string="Tariff", domain=[("status", "=", True)])
    code = fields.Char(string="Concept code", required=True)

    @api.onchange("percentage_tax_base")
    def check_value_percentage(self):
        if self.percentage_tax_base > 100:
            return {
                "warning": {
                    "title": _("Error in taxable base percentage field"),
                    "message": _("the percentage may not exceed 100% on the payment concept line"),
                },
                "value": {"percentage_tax_base": 0},
            }
