from odoo import models, fields


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    is_digitalized = fields.Boolean(string="Digitized", default=False, copy=False, tracking=True)
    show_digital_dispatch_guide = fields.Boolean(string="Show Digital Dispatch Guide", compute="_compute_visibility_button", copy=False)
    control_number_tfhka = fields.Char(string="Control Number", copy=False)

    def button_validate(self):
        res = super(StockPicking, self).button_validate()
        for record in self:
            if record.state == 'done' and record.company_id.dispatch_guide_digital_tfhka and not record.is_digitalized and record.is_dispatch_guide and record.picking_type_id.code != "incoming":
                record.generate_document_digital()
        return res

    def generate_document_digital(self):
        return self.env["tfhka.dispatch.guide.service"].send_document(self)

    def _compute_visibility_button(self):
        for record in self:
            record.show_digital_dispatch_guide = True
            if record.company_id.dispatch_guide_digital_tfhka:
                record.show_digital_dispatch_guide = False

    def _set_guide_number(self):
        for picking in self:
            if picking.dispatch_guide_controls:
                if not picking.company_id.dispatch_guide_digital_tfhka:
                    picking.guide_number = picking.get_sequence_guide_num()
                elif picking.is_digitalized:
                    picking.guide_number = picking.get_sequence_guide_num()
