from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = "account.move"

    guide_number = fields.Char(compute='_compute_guide_number', string="Guide Number", store=True)
    transfer_ids = fields.Many2many("stock.picking", string="Transfers")
    picking_ids = fields.Many2many("stock.picking", column1='account_move_id', column2= 'stock_picking_id', relation='pickings_invoice_rel')
    from_picking = fields.Boolean(string="From Picking", default=False)

    

    @api.depends("picking_ids")
    def _compute_guide_number(self):
        for record in self:
            list_guide_number = [picking.guide_number for picking in record.picking_ids]
            record.guide_number = "/".join(list_guide_number)

    def _get_tax_grouped_lines(self):
        """
        Agrupa las líneas de factura por el conjunto de impuestos que tienen aplicados.
        Retorna un diccionario: { tuple(ids_impuestos): {'base': suma_base, 'taxes': recordset_impuestos} }
        """
        self.ensure_one()
        tax_groups = {}
        for line in self.invoice_line_ids:
            tax_ids = line.tax_ids.ids
            tax_key = tuple(sorted(tax_ids))

            if tax_key not in tax_groups:
                tax_groups[tax_key] = {
                    'base_amount': 0.0,
                    'taxes': line.tax_ids,
                }
            tax_groups[tax_key]['base_amount'] += line.price_subtotal
        return tax_groups
