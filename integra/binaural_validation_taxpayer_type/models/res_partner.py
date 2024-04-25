from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = "res.partner"

    company_taxpayer_type = fields.Selection(
        related='company_id.taxpayer_type'
    )

    is_required_withholding_type_id = fields.Boolean(
        compute='_compute_is_required_withholding_type_id'
    )

    @api.onchange('company_id')
    def _compute_is_required_withholding_type_id(self):
        for record in self:
            exist_ordinary_taxpayer_company = record.company_id.taxpayer_type == "ordinary"

            if not record.company_id:
                company_ids = self.env["res.company"].search(
                    [("taxpayer_type", "=", "ordinary")], 
                    limit=1
                )

                exist_ordinary_taxpayer_company = any(company_ids)

            record.is_required_withholding_type_id = record.supplier_rank > 0 and not exist_ordinary_taxpayer_company
