from odoo import api, fields, models

class PurchaseOrderZmart(models.Model):
    _inherit = "purchase.order"

    name_company = fields.Many2one(
        'purchase.company'
    )
    type_company = fields.Selection(
        [
            ("sea", "Sea"),
            ("air", "Air"),
            ("land", "Land"),
        ],
        default="",
        store=True,
        required=True
    )
    incoterm = fields.Selection(
        [
            ("fob", "FOB"),
            ("cif", "CIF"),
            ("cfr", "CFR"),
            ("na", "N/A"),
        ],
        default="",
        store=True,
        required=True
    )
    bl = fields.Char(
        string="B/L"
    )
    wl = fields.Char(
        string="W/L"
    )
    date_in_store = fields.Date()
    order_in_transit = fields.Boolean()
    exit_etd = fields.Date()
    inlay_port = fields.Date()
    aduana_agent = fields.Many2one(
        'purchase.aduana.agent'
    )
    
    def button_report_purchase_order(self):
        return self.env.ref('purchase.action_report_purchase_order').report_action(self)
    
    def button_report_purchase_quotation(self):
        return self.env.ref('purchase.report_purchase_quotation').report_action(self)