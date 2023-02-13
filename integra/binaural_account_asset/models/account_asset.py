from odoo import api, fields, models, _


class AccountAsset(models.Model):
    _inherit = "account.asset"

    def default_alternate_currency(self):
        """
        This method is used to get the foreign currency of the company and set it as the default
        value of the foreign currency field.

        Returns
        -------
        type = int
            The id of the foreign currency of the company
        """
        return self.env.company.currency_foreign_id.id or False

    foreign_currency_id = fields.Many2one(
        "res.currency",
        string="Foreign Currency",
        default=default_alternate_currency,
    )
    foreign_rate = fields.Float(
        help="The rate of the asset.",
        digits="Tasa",
        compute="_compute_rate",
        store=True,
        readonly=False,
    )
    foreign_inverse_rate = fields.Float(
        help="The inverse rate of the asset.",
        digits=(12, 6),
        compute="_compute_rate",
        store=True,
        readonly=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        """
        Ensure that the foreign_rate and foreign_inverse_rate are computed when the asset is created.
        """
        assets = super().create(vals_list)
        assets._compute_rate()
        return assets

    @api.depends("original_move_line_ids")
    def _compute_rate(self):
        """
        This method is used to compute the rate and inverse rate of the foreign currency.
        It gets the values from the first line of the original move lines.
        """
        for asset in self.filtered("original_move_line_ids"):
            asset.foreign_rate = asset.original_move_line_ids[0].move_id.foreign_rate
            asset.foreign_inverse_rate = asset.original_move_line_ids[
                0
            ].move_id.foreign_inverse_rate

    def compute_depreciation_board(self):
        """
        Ensures that the foreign rate and inverse rate are written in the depreciation moves whenever
        the depreciation board is computed.
        """
        res = super().compute_depreciation_board()
        for asset in self:
            self.depreciation_move_ids.write(
                {
                    "foreign_rate": asset.foreign_rate,
                    "foreign_inverse_rate": asset.foreign_inverse_rate,
                }
            )
        return res
