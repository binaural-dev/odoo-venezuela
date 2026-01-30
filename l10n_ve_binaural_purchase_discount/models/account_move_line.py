from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.onchange("price_unit")
    def _onchange_price_unit(self):
        for rec in self:
            if rec.product_id and rec.move_type == "in_invoice":
                if rec.price_unit <= 0 and rec.display_type not in ("line_section","line_note"):
                    if (
                        'purchase_discount_product_id' in self.env.company._fields
                        and self.env.company.purchase_discount_product_id
                        and rec.product_id == self.env.company.purchase_discount_product_id
                    ):
                        continue

                
                    raise ValidationError(_("The price entered cannot be negative"))
            
            if rec.product_id and rec.move_type == "out_invoice":
                if rec.price_unit <= 0 and rec.display_type not in ("line_section","line_note"):
                   
                    raise ValidationError(_("The price entered cannot be positive"))