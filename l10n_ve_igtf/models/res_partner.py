from odoo import fields, models, _ , api


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _check_igtf_apply_improved(self, invoice_type):
        for rec in self:
            company = self.company_id or self.env.company
            company_taxpayer_type = company.taxpayer_type
            
            # 2. Manejo de Ventas (out_invoice)
            if invoice_type in ["out_invoice","out_refund"]:
                return company_taxpayer_type in ['special','formal']
                
            # 3. Manejo de Compras (in_invoice)
            elif invoice_type in ["in_invoice","in_refund"]:
                partner_taxpayer_type = rec.taxpayer_type
                
                return partner_taxpayer_type in ['special','formal']
                
            return False
