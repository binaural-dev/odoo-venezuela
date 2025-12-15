from odoo import fields, models, _ , api


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _check_igtf_apply_improved(self, partner, invoice_type):
        company_taxpayer_type = partner.company_id.taxpayer_type
        
        # 2. Manejo de Ventas (out_invoice)
        if invoice_type == "out_invoice":
            return company_taxpayer_type == 'special'
            
        # 3. Manejo de Compras (in_invoice)
        elif invoice_type == "in_invoice":
            partner_taxpayer_type = partner.taxpayer_type
            
            return partner_taxpayer_type == 'special'
            
        return False
