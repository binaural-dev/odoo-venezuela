from odoo import api, fields, models


class PosPayment(models.Model):
    _inherit = "pos.payment"

    # Odoo 19 frontend `PosPayment` expects these base fields when creating/
    # mutating payment lines (e.g. setAmount -> pos_order_id.assertEditable()).
    _POS_PAYMENT_CORE_FIELDS = (
        "id",
        "name",
        "uuid",
        "amount",
        "payment_date",
        "payment_method_id",
        "payment_status",
        "ticket",
        "is_change",
        "pos_order_id",
        "currency_id",
        "foreign_currency_id",
        "amount_currency",
        # Required by core's DevicesSynchronisation.constructOrdersDomain,
        # which calls record.write_date.plus(...) on every dynamic model.
        "write_date",
    )

    foreign_rate = fields.Float(
        help="The rate that is gonna be always shown to the user.",
        default=0.0,
        readonly=False,
    )
    foreign_amount = fields.Float(readonly=True, digits=(16, 2))
    foreign_amount_currency_id = fields.Many2one(
        "res.currency",
        related="pos_order_id.foreign_currency_id",
        string="Foreign Amount Currency",
    )

    payment_currency_id = fields.Many2one(
        "res.currency",
        compute="_compute_payment_currency",
        string="Payment Currency",
        help="Currency the customer handed over: the foreign currency of the "
        "payment, or the currency of the order when it was paid in it.",
    )
    is_foreign_currency = fields.Boolean(
        compute="_compute_payment_currency",
        string="Paid in Foreign Currency",
        help="The payment was made in a currency other than the one of the order.",
    )

    @api.depends("foreign_currency_id", "currency_id")
    def _compute_payment_currency(self):
        for payment in self:
            foreign = payment.foreign_currency_id
            is_foreign = bool(foreign) and foreign != payment.currency_id
            payment.is_foreign_currency = is_foreign
            payment.payment_currency_id = foreign if is_foreign else payment.currency_id

    def _get_currency_settings(self):
        """Settings of the payment method for the currency of this payment
        (cross journals, IGTF): the hook to decide anything per currency."""
        self.ensure_one()
        return self.payment_method_id._get_currency_settings(self.payment_currency_id)

    @api.model
    def _load_pos_data_fields(self, config):
        """Keep Odoo 19 core payment contract and extend it with Venezuelan
        foreign-currency fields.

        Important: `pos.load.mixin._load_pos_data_fields` returns `[]` for
        pos.payment in core, which is a special value meaning "load every
        field" (see `_load_pos_data_read`: `records.read(fields, ...)` with
        an empty list reads all fields). Turning that `[]` into an explicit
        whitelist — even one padded with our own required fields — silently
        breaks every OTHER module's pos.payment field (e.g. an analytic
        account added by a subsidiary/cost-center module): anything not in
        this hardcoded list stops reaching the frontend, and the client's
        `related_models` engine rejects it with "field does not exist" the
        moment something tries to set it. Only build the whitelist if some
        ancestor already narrowed it; otherwise, keep passing "all fields"
        through untouched.
        """
        res = super()._load_pos_data_fields(config)
        if not res:
            return res
        required = list(self._POS_PAYMENT_CORE_FIELDS) + [
            "foreign_rate",
            "foreign_amount",
            "foreign_amount_currency_id",
        ]
        for name in required:
            if name not in res:
                res.append(name)
        return res
