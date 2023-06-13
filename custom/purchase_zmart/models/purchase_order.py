from odoo import api, fields, models

class PurchaseOrderZmart(models.Model):
    _inherit = "purchase.order"
    
    transport_number = fields.Char(string="Transport Number")
    name_company = fields.Many2one('purchase.company', string="Company")
    vl_number = fields.Char(string="VL Number")
    date_in_store = fields.Date()
    
    def button_report_purchase_order(self):
        return self.env.ref('purchase.action_report_purchase_order').report_action(self)
    
    def button_report_purchase_quotation(self):
        return self.env.ref('purchase.report_purchase_quotation').report_action(self)