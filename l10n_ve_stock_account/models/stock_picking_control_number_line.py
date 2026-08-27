from odoo import fields, models


class StockPickingControlNumberLine(models.Model):
    """One reserved control number per printed sheet of a dispatch guide.

    The control number is pre-printed on the physical paper the dispatch
    guide is issued on (a SENIAT-compliant numbering method alternative to
    the digital control number issued by an authorized provider). The
    system does not generate or print it, it only records it for
    traceability. When a guide has more lines than fit on a single sheet,
    one consecutive number is reserved per sheet.
    """

    _name = "stock.picking.control.number.line"
    _description = "Línea de Número de Control de la Guía de Despacho"
    _order = "picking_id, sheet_number"

    picking_id = fields.Many2one(
        comodel_name="stock.picking",
        string="Transferencia",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="picking_id.company_id",
        store=True,
        index=True,
    )
    sheet_number = fields.Integer(string="Hoja", required=True)
    number = fields.Char(string="Número de Control", required=True, copy=False)
