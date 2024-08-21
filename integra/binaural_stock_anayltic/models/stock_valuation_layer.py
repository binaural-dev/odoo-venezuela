from odoo import api, models


class StockValuationLayer(models.Model):
    _inherit = "stock.valuation.layer"

    def _validate_accounting_entries(self):
        super()._validate_accounting_entries()

        for svl in self:
            lines = svl.account_move_id.line_ids
            for line in lines:
                account = svl._get_stock_analytic_account(line)
                line.account_analytic_id = account

    @api.model
    def _get_stock_analytic_account(self, line):
        """Obtain the Analytic Account that comes from the picking.
        It performs several checks to know if the product category
        satisfy the requirements and the debit account is a expense
        type.

        Parameters
        ----------
        line: account.move.line
            The expense account id

        Returns
        -------
        account.analytic.account
            The analytic account id that comes from the picking, or False
            if it does not exist/does not satisfy the requirements.
        """
        self.ensure_one()

        analytic_account_id = self.env["account.analytic.account"]
        category = self.product_id.categ_id
        picking = self.stock_move_id.picking_id

        if line.check_account_type("expense") and category.is_analytic_category():
            analytic_account_id = picking.analytic_account_id

        return analytic_account_id
