from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError

import logging
_logger = logging.getLogger(__name__)
class PaymentConcept(models.Model):
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
                    continue
                    # raise UserError(_("The type of person cannot be repeated."))
                else:
                    type_person_id.append(line.type_person_id.id)

    @api.model
    def _handle_payment_concept_one(self):
        id_concept = 'l10n_ve_payment_extension.payment_concept_one_l10n_ve_payment_extension'
        name_concept = 'Honorarios Profesionales Pagados a'
        
        concept_lines = [
            {
                'code': 2,
                'pay_from': 0.13,
                'percentage_tax_base': 100,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_substrat_l10n_ve_payment_extension').id,
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_l10n_ve_payment_extension').id
            },
            {
                'code': 4,
                'pay_from': 0.00,
                'percentage_tax_base': 100,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_percentage_one_l10n_ve_payment_extension').id,
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_three_l10n_ve_payment_extension').id
            },
            {
                'code': 3,
                'pay_from': 0.00,
                'percentage_tax_base': 90,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_percentage_two_l10n_ve_payment_extension').id,
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_two_l10n_ve_payment_extension').id
            },
            {
                'code': 5,
                'pay_from': 0.00,
                'percentage_tax_base': 90,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_percentage_five_l10n_ve_payment_extension').id,
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_four_l10n_ve_payment_extension').id
            }
        ]
        
        new_concept_lines = self.validate_concept_lines(concept_lines) 

        if not new_concept_lines:
            return

        self.create_concept_line(id_concept, name_concept, new_concept_lines)

    @api.model
    def _handle_payment_concept_two(self):
        id_concept = 'l10n_ve_payment_extension.payment_concept_two_l10n_ve_payment_extension'
        name_concept = 'Gastos de Transporte (Fletes) Pagados a'
        
        concept_lines = [
            {
                'code': 71,
                'pay_from': 0.13,
                'percentage_tax_base': 100,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_substrat_second_l10n_ve_payment_extension').id,
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_l10n_ve_payment_extension').id
            },
            {
                'code': 72,
                'pay_from': 0.00,
                'percentage_tax_base': 100,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_percentage_four_l10n_ve_payment_extension').id,
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_three_l10n_ve_payment_extension').id
            }
        ]
        
        new_concept_lines = self.validate_concept_lines(concept_lines) 

        if not new_concept_lines:
            return

        self.create_concept_line(id_concept, name_concept, new_concept_lines)
        
    @api.model
    def _handle_payment_concept_three(self):
        id_concept = 'l10n_ve_payment_extension.payment_concept_three_l10n_ve_payment_extension'
        name_concept = '(Contratista) Ejecución de obras y prestación de servicios en Venezuela pagadas a:'
        
        concept_lines = [
            {
                'code': 53,
                'pay_from': 0.13,
                'percentage_tax_base': 100,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_substrat_second_l10n_ve_payment_extension').id,
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_l10n_ve_payment_extension').id 
            },
            {
                'code': 55,
                'pay_from': 0.00,
                'percentage_tax_base': 100,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_l10n_ve_percentage_three_payment_extension').id,
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_three_l10n_ve_payment_extension').id
            },
            {
                'code': 54,
                'pay_from': 0.00,
                'percentage_tax_base': 100,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_percentage_two_l10n_ve_payment_extension').id,
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_two_l10n_ve_payment_extension').id
            },
            {
                'code': 56,
                'pay_from': 0.00,
                'percentage_tax_base': 100,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_percentage_five_l10n_ve_payment_extension').id,
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_four_l10n_ve_payment_extension').id
            }      
        ]
        
        new_concept_lines = self.validate_concept_lines(concept_lines) 

        if not new_concept_lines:
            return

        self.create_concept_line(id_concept, name_concept, new_concept_lines)
        
    @api.model
    def _handle_payment_concept_four(self):
        id_concept = 'l10n_ve_payment_extension.payment_concept_four_l10n_ve_payment_extension'
        name_concept = 'Arrendamiento de bienes muebles pagado a:'
        
        concept_lines = [
            {
                'code': 61,
                'pay_from': 0.13,
                'percentage_tax_base': 100,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_substrat_l10n_ve_payment_extension').id,
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_l10n_ve_payment_extension').id 
            },
            {
                'code': 63,
                'pay_from': 0.00,
                'percentage_tax_base': 100,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_percentage_one_l10n_ve_payment_extension').id,
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_three_l10n_ve_payment_extension').id
            },
            {
                'code': 62,
                'pay_from': 0.00,
                'percentage_tax_base': 100,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_percentage_two_l10n_ve_payment_extension').id,
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_two_l10n_ve_payment_extension').id
            },
            {
                'code': 64,
                'pay_from': 0.00,
                'percentage_tax_base': 100,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_percentage_one_l10n_ve_payment_extension').id,
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_four_l10n_ve_payment_extension').id
            } 
        ]
        
        new_concept_lines = self.validate_concept_lines(concept_lines) 

        if not new_concept_lines:
            return

        self.create_concept_line(id_concept, name_concept, new_concept_lines)

    @api.model
    def _handle_payment_concept_five(self):
        id_concept = 'l10n_ve_payment_extension.payment_concept_five_l10n_ve_payment_extension'
        name_concept = 'Arrendamiento o cesión de uso de bienes inmuebles, pagados al arrendador por personas jurídicas, comunidades o los administradores:'
        
        concept_lines = [
            {
                'code': 57,
                'pay_from': 0.13,
                'percentage_tax_base': 100,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_substrat_l10n_ve_payment_extension').id,
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_l10n_ve_payment_extension').id 
            },
            {
                'code': 59,
                'pay_from': 0.00,
                'percentage_tax_base': 100,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_percentage_one_l10n_ve_payment_extension').id,
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_three_l10n_ve_payment_extension').id
            },
            {
                'code': 58,
                'pay_from': 0.00,
                'percentage_tax_base': 100,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_percentage_two_l10n_ve_payment_extension').id,
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_two_l10n_ve_payment_extension').id
            },
            {
                'code': 60,
                'pay_from': 0.00,
                'percentage_tax_base': 100,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_percentage_five_l10n_ve_payment_extension').id,
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_four_l10n_ve_payment_extension').id
            }
        ]
        
        new_concept_lines = self.validate_concept_lines(concept_lines) 

        if not new_concept_lines:
            return

        self.create_concept_line(id_concept, name_concept, new_concept_lines)

    @api.model
    def _handle_payment_concept_six(self):
        id_concept = 'l10n_ve_payment_extension.payment_concept_six_l10n_ve_payment_extension'
        name_concept = 'Publicidad, propaganda y venta de espacios pagadas a'
        
        concept_lines = [
            {
                'code': 83,
                'pay_from': 0.13,
                'percentage_tax_base': 100,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_substrat_l10n_ve_payment_extension').id,
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_l10n_ve_payment_extension').id 
            },
            {
                'code': 84,
                'pay_from': 0.00,
                'percentage_tax_base': 100,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_percentage_one_l10n_ve_payment_extension').id,
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_three_l10n_ve_payment_extension').id
            },
            {
                'code': 85,
                'pay_from': 0.00,
                'percentage_tax_base': 100,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_percentage_one_l10n_ve_payment_extension').id,
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_four_l10n_ve_payment_extension').id
            },
            {
                'code': 86,
                'pay_from': 0.00,
                'percentage_tax_base': 100,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_percentage_four_l10n_ve_payment_extension').id,
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_seven_l10n_ve_payment_extension').id
            }
        ]
        
        new_concept_lines = self.validate_concept_lines(concept_lines) 

        if not new_concept_lines:
            return

        self.create_concept_line(id_concept, name_concept, new_concept_lines)      

    @api.model
    def _handle_payment_concept_seven(self):
        id_concept = 'l10n_ve_payment_extension.payment_concept_seven_l10n_ve_payment_extension'
        name_concept = 'Comisiones pagadas a'
        
        concept_lines = [
            {
                'code': 14,
                'pay_from': 0.13,
                'percentage_tax_base': 100,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_substrat_l10n_ve_payment_extension').id,
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_l10n_ve_payment_extension').id 
            },
            {
                'code': 16,
                'pay_from': 0.00,
                'percentage_tax_base': 100,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_percentage_one_l10n_ve_payment_extension').id,
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_three_l10n_ve_payment_extension').id
            },
            {
                'code': 15,
                'pay_from': 0.00,
                'percentage_tax_base': 100,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_percentage_two_l10n_ve_payment_extension').id,
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_two_l10n_ve_payment_extension').id
            },
            {
                'code': 17,
                'pay_from': 0.00,
                'percentage_tax_base': 100,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_percentage_one_l10n_ve_payment_extension').id,
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_four_l10n_ve_payment_extension').id
            }
        ]
        
        new_concept_lines = self.validate_concept_lines(concept_lines) 

        if not new_concept_lines:
            return

        self.create_concept_line(id_concept, name_concept, new_concept_lines)  

        
    def create_concept_line(self, id_concept, name_concept, new_concept_lines):
        concept = self.env.ref(id_concept, raise_if_not_found=False)
        
        if not concept:
            concept = self.env['payment.concept'].create({
                'name': name_concept,
                'status': True,
                'line_payment_concept_ids': [(0, 0, line) for line in new_concept_lines]
            })
        else:
            concept.write({
                'line_payment_concept_ids': [(0, 0, line) for line in new_concept_lines]
            })

        return
    
    def validate_concept_lines(self, concept_lines):
        existing_codes = self.env['payment.concept.line'].search([]).mapped('code')
        return [line for line in concept_lines if str(line['code']) not in existing_codes]