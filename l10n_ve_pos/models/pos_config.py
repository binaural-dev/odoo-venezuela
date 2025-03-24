from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Integra 16 tiene varios campos con readonly=True, revisar para migrar


class PosConfig(models.Model):
    _inherit = "pos.config"

    foreign_currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_foreign_id"
    )

    foreign_inverse_rate = fields.Float(
        help="Rate that will be used as factor to multiply of the foreign currency for moves.",
        compute="_compute_rate",
        digits=(16, 15),
        default=0.0,
        readonly=False,
    )
    foreign_rate = fields.Float(
        compute="_compute_rate",
        digits="Tasa",
        default=0.0,
        readonly=False,
    )
    pos_show_free_qty = fields.Boolean(related="company_id.pos_show_free_qty")
    sell_kit_from_another_store = fields.Boolean(default=False)
    pos_show_just_products_with_available_qty = fields.Boolean(
        related="company_id.pos_show_just_products_with_available_qty"
    )
    pos_search_cne = fields.Boolean(related="company_id.pos_search_cne")
    amount_to_zero = fields.Boolean("Amount to zero")
    activate_barcode_strict_mode = fields.Boolean(
        help="Activate product entry with barcode in strict mode"
    )

    @api.depends("foreign_currency_id", "foreign_inverse_rate", "foreign_rate")
    def _compute_rate(self):
        """
        Compute the rate of the pos using the compute_rate method of the res.currency.rate model.
        """
        rate = self.env["res.currency.rate"]
        for config in self:
            rate_values = rate.compute_rate(
                config.foreign_currency_id.id, fields.Date.today()
            )
            config.update(rate_values)

    def _action_to_open_ui(self):
        res = super()._action_to_open_ui()
        if (
            not self.current_session_id.foreign_currency_id
            or not self.current_session_id.foreign_currency_id.active
        ):
            raise ValidationError(
                _("The session must have a foreign currency or active")
            )
        return res
