from odoo import models, fields,api

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    transport_number = fields.Char(
        string = "Transport Number"
        )
    name_company = fields.Many2one(
        string = "Company",
        related = "purchase_id.name_company",
        store = True,
        readonly = True
        )
    type_company = fields.Selection(
        [
            ("sea", "Sea"),
            ("air", "Air"),
            ("land", "Land"),
        ],
        default = "",
        related = "purchase_id.type_company",
        store = True
    )
    incoterm = fields.Selection(
        [
            ("fob", "FOB"),
            ("cif", "CIF"),
            ("cfr", "CFR"),
            ("na", "N/A"),
        ],
        default = "",
        related = "purchase_id.incoterm",
        store = True
    )
    bl = fields.Char(
        string = "B/L",
        related = "purchase_id.bl",
    )
    wl = fields.Char(
        string = "W/L",
        related = "purchase_id.wl",
    )
    date_in_store = fields.Date(
        related = "purchase_id.date_in_store"
    )
    order_in_transit = fields.Boolean(
        related = "purchase_id.order_in_transit"
    )
    exit_etd = fields.Date(
        related = "purchase_id.exit_etd"
    )
    inlay_port = fields.Date(
        related = "purchase_id.inlay_port"
    )
    aduana_agent = fields.Many2one(
        related = "purchase_id.aduana_agent",
        store = True,
        readonly = True
    )
    sequence_code = fields.Char(
        related = 'picking_type_id.sequence_code'
    )
    packing_factor = fields.Integer(
    )

    weight_factor = fields.Float(string='Total Weight', compute='_compute_weight_factor')

    @api.depends('weight', 'packing_factor')
    def _compute_weight_factor(self):
        for record in self:
            record.weight_factor = (record.weight * record.packing_factor)/100 + record.weight