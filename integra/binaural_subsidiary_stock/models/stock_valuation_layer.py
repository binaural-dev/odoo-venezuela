from odoo import api, fields, models


class StockValuationLayer(models.Model):
    _inherit = "stock.valuation.layer"

    subsidiary_id = fields.Many2one(
        "account.analytic.account",
        string="Subsidiary",
        compute="_compute_subsidiary_id",
        store=True,
    )

    @api.depends("stock_move_id")
    def _compute_subsidiary_id(self):
        for svl in self:
            move = svl.stock_move_id or svl.stock_valuation_layer_id.stock_move_id
            if not move:
                continue
            if move._is_in():
                svl.subsidiary_id = move.subsidiary_dest_id
            if move._is_out():
                svl.subsidiary_id = move.subsidiary_origin_id

    def _validate_accounting_entries(self):
        res = super()._validate_accounting_entries()
        for svl in self:
            svl.account_move_id.account_analytic_id = svl.subsidiary_id.id
        return res
