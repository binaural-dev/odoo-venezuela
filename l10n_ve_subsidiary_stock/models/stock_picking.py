from odoo import fields, models, api


class StockPicking(models.Model):
    _inherit = "stock.picking"

    subsidiary_origin_id = fields.Many2one(
        "account.analytic.account",
        string="Origin Subsidiary",
        compute="_compute_subsidiary_location_id",
        store=True,
    )

    subsidiary_dest_id = fields.Many2one(
        "account.analytic.account",
        string="Destination Subsidiary",
        compute="_compute_subsidiary_location_dest_id",
        store=True,
    )

    location_id = fields.Many2one(
        domain=lambda self: (
            "[('company_id', 'in', (company_id, False)),"
            f"('warehouse_id.subsidiary_id', 'in', {self.env.user.subsidiary_ids.ids})]"
        )
    )

    location_dest_id = fields.Many2one(
        domain=lambda self: (
            "[('company_id', 'in', (company_id, False)),"
            f"('warehouse_id.subsidiary_id', 'in', {self.env.user.subsidiary_ids.ids})]"
        )
    )

    @api.depends("location_id")
    def _compute_subsidiary_location_id(self):
        for picking in self:
            warehouse_id = picking.location_id.warehouse_id
            picking.subsidiary_origin_id = warehouse_id.subsidiary_id


    @api.depends("location_dest_id")
    def _compute_subsidiary_location_dest_id(self):
        for picking in self:
            warehouse_id = picking.location_dest_id.warehouse_id
            picking.subsidiary_dest_id = warehouse_id.subsidiary_id

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


    def _action_done(self):
        """
        Creates and posts the valuation move when the picking is an internal transfer,
        after the picking is validated.
        """
        res = super()._action_done()

        # The context is used to tell the create method of the account move that the
        # subsidiaries do not require to be setted on the move lines as the
        # _generate_valuation_lines_data method of the stock move sets them already and
        # it can lead to conflicts.
        AccountMove = (
            self.env["account.move"].sudo().with_context(skip_subsidiaries_setting=True)
        )
        for move in self.filtered(
            lambda p: p.picking_type_id.code == "internal"
        ).mapped("move_ids_without_package"):
            standard_price = move.product_id.standard_price
            if self.env.company.currency_id.is_zero(standard_price):
                continue

            reference = (
                move.reference
                and "%s - %s" % (move.reference, move.product_id.name)
                or move.product_id.name
            )
            cost = standard_price * move.quantity
            am_vals = (
                move.with_company(self.env.company)
                .with_context(
                    subsidiary_origin_id=move.subsidiary_origin_id.id,
                    subsidiary_dest_id=move.subsidiary_dest_id.id,
                )
                ._account_entry_move(move.quantity, reference, False, cost)
            )
            for val in am_vals:
                del val["stock_valuation_layer_ids"]
            moves = AccountMove.create(am_vals)
            moves._post()
        return res
