from odoo import fields, models, api


class StockMove(models.Model):
    _inherit = "stock.move"

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


    @api.depends("location_id")
    def _compute_subsidiary_location_id(self):
        for move in self:
            warehouse_id = move.location_id.warehouse_id
            move.subsidiary_origin_id = warehouse_id.subsidiary_id


    @api.depends("location_dest_id")
    def _compute_subsidiary_location_dest_id(self):
        for move in self:
            warehouse_id = move.location_dest_id.warehouse_id
            move.subsidiary_dest_id = warehouse_id.subsidiary_id

    def _account_entry_move(self, qty, description, svl_id, cost):
        """
        Ensures the valuation move is created even when the move is not an in or an out, as long
        as it comes from a picking and if it is an internal transfer.
        """
        res = super()._account_entry_move(qty, description, svl_id, cost)
        if not self._is_internal():
            return res
        am_vals = []
        journal_id, acc_src, acc_dest, acc_valuation = self._get_accounting_data_for_valuation()

        am_vals.append(
            self.with_company(self.env.company)._prepare_account_move_vals(
                acc_src, acc_dest, journal_id, qty, description, svl_id, cost
            )
        )
        return am_vals

    def _get_src_account(self, accounts_data):
        if self._is_internal() and self.company_id.subsidiary:
            return self.location_id.warehouse_id.inventory_account_id.id
        return super()._get_src_account(accounts_data)

    def _get_dest_account(self, accounts_data):
        if self._is_internal() and self.company_id.subsidiary:
            return self.location_dest_id.warehouse_id.inventory_account_id.id
        return super()._get_dest_account(accounts_data)

    def _is_internal(self):
        self.ensure_one()
        return self.picking_id and self.picking_id.picking_type_id.code == "internal"

    def _generate_valuation_lines_data(
        self,
        partner_id,
        qty,
        debit_value,
        credit_value,
        debit_account_id,
        credit_account_id,
        svl_id,
        description,
    ):
        """
        Ensures the origin and destination subsidiary is setted on its corresponding move line, we
        use context for passing the values so we don't have to override the original methods that
        goes from the _account_entry_move method to this one.
        """
        res = super()._generate_valuation_lines_data(
            partner_id,
            qty,
            debit_value,
            credit_value,
            debit_account_id,
            credit_account_id,
            svl_id,
            description,
        )

        subsidiaries = (
            self.env.context.get("subsidiary_origin_id", False),
            self.env.context.get("subsidiary_dest_id", False),
        )

        if not all(subsidiaries):
            return res

        res["credit_line_vals"]["analytic_distribution"] = {str(subsidiaries[0]): 100}
        res["debit_line_vals"]["analytic_distribution"] = {str(subsidiaries[1]): 100}

        return res
