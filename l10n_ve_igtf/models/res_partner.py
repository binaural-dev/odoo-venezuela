from odoo import fields, models, _ , api


class ResPartner(models.Model):
    _inherit = "res.partner"

    default_advance_customer_account_id= fields.Many2one(
        "account.account", 
        domain=[("account_type", "=", "liability_current"), ("is_advance_account", "=", True),('reconcile','=',True)], 
        copy=False, 
        required=True,
        default=lambda self: self.env.company.advance_customer_account_id,
    )

    default_advance_supplier_account_id= fields.Many2one(
        "account.account", 
        domain=[("account_type", "=", "asset_current"),("is_advance_account", "=", True),('reconcile','=',True)], 
        copy=False, 
        required=True, 
        default=lambda self: self.env.company.advance_supplier_account_id,
    )

    def _check_igtf_apply_improved(self, invoice_type):
        for rec in self:
            company = self.company_id or self.env.company
            company_taxpayer_type = company.taxpayer_type
            
            # 2. Manejo de Ventas (out_invoice)
            if invoice_type in ["out_invoice","out_refund"] and rec.default_advance_customer_account_id:
                return company_taxpayer_type in ['special','formal']
                
            # 3. Manejo de Compras (in_invoice)
            elif invoice_type in ["in_invoice","in_refund"] and rec.default_advance_supplier_account_id:
                partner_taxpayer_type = rec.taxpayer_type
                
                return partner_taxpayer_type in ['special','formal']
                
            return False