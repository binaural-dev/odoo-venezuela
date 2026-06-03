from odoo import _, api, models, fields
import logging

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"


    @api.model_create_multi
    def create(self, vals_list):
        records = super(ProductTemplate, self).create(vals_list)
        records._enforce_single_tax()
        return records

    def write(self, vals):
        res = super(ProductTemplate, self).write(vals)
        self._enforce_single_tax()
        return res

    def _enforce_single_tax(self):
        for rec in self:
            # Sales Taxes logic
            if not rec.taxes_id:
                sale_tax = self.env.company.account_sale_tax_id or self.env.company.root_id.sudo().account_sale_tax_id
                rec.taxes_id = [(6, 0, [sale_tax.id])]
            # Purchase Taxes logic
            if not rec.supplier_taxes_id:
                purchase_tax = self.env.company.account_purchase_tax_id or self.env.company.root_id.sudo().account_purchase_tax_id
                rec.supplier_taxes_id = [(6, 0, [purchase_tax.id])]