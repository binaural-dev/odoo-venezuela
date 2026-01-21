# -*- coding: utf-8 -*-
from odoo import fields,models
from odoo.exceptions import ValidationError
from odoo import _

class StockScrap(models.Model):
    _inherit = "stock.scrap"
    
    def action_validate(self):
        """Validate the scrap operation, ensuring that the scrap quantity does not exceed the quantity produced
        in the production order (if the scrap has one)."""

        if not self.env.company.allow_scrap_more_than_available:
            if not self.check_available_qty():
                raise ValidationError(_("You cannot scrap more than the available product quantity in this location."))
            
        if not self.env.company.not_allow_scrap_more_than_what_was_manufactured:
            return super(StockScrap,self).action_validate()

        if self.production_id:
            count = 0
            if self.production_id.scrap_ids:
                for scrap in self.production_id.scrap_ids.filtered(
                    lambda scrap: scrap.state == "done"
                ):
                    count += scrap.scrap_qty
                if (
                    count >= self.production_id.qty_produced
                    or (self.scrap_qty + count) > self.production_id.qty_produced
                    or self.scrap_qty > self.production_id.qty_produced
                ):
                    raise ValidationError(
                        _(
                            "No more than what is manufactured can be discarded in this operation."
                        )
                    )
            
        return super(StockScrap, self).action_validate()