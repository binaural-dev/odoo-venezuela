from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class AccountMove(models.Model):
    _name = "account.move"
    _inherit = "account.move"

                
    @api.constrains("invoice_line_ids")
    def _check_price_in_zero(self):
        from_pos = self.env.context.get('from_pos', False)
        for line in self.filtered(lambda m: m.is_invoice()).mapped("invoice_line_ids"):
            if line.price_unit <= 0 and line.display_type not in ("line_section","line_note") and line.move_type == "in_invoice":
                if (
                    'purchase_discount_product_id' in self.env.company._fields
                    and self.env.company.purchase_discount_product_id
                    and line.product_id == self.env.company.purchase_discount_product_id
                ):
                    continue

                if not from_pos:
                    raise ValidationError(_("An invoice cannot have a line with a price of zero"))
                

    

   