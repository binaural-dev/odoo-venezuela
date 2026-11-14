from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PosPaymentMethodCurrency(models.Model):
    """Settings of a payment method for one of the foreign currencies it
    accepts (``pos.payment.method.currency_ids``).

    Odoo 19 kept one payment method per currency ("Efectivo $", "Efectivo EUR")
    and flagged it ``is_foreign_currency`` with its own cross journals. Odoo 20
    has a single cash method per register that accepts several currencies, so
    what used to hang from the method hangs from the pair method + currency.

    Modules that need a per-currency setting (``l10n_ve_pos_igtf`` with
    ``apply_igtf``) extend this model and read it from the currency the
    customer paid with: ``payment_method._get_currency_settings(currency)``.
    """

    _name = "pos.payment.method.currency"
    _description = "Payment Method Currency Settings"
    _inherit = ["pos.load.mixin"]
    _order = "payment_method_id, currency_id"

    payment_method_id = fields.Many2one(
        "pos.payment.method", required=True, ondelete="cascade", index=True
    )
    currency_id = fields.Many2one("res.currency", required=True)
    company_id = fields.Many2one(
        related="payment_method_id.company_id", store=True, index=True
    )
    cross_account_journal = fields.Many2one(
        "account.journal",
        domain=[("type", "=", "general")],
        check_company=True,
        help="Journal of the cross move of the payments made in this currency.",
    )
    cross_journal = fields.Many2one(
        "account.journal",
        domain=[("type", "in", ("bank", "cash"))],
        check_company=True,
        help="Journal that receives the payments made in this currency.",
    )

    _unique_method_currency = models.Constraint(
        "unique (payment_method_id, currency_id)",
        "A payment method has only one setting per currency.",
    )

    @api.constrains("payment_method_id", "currency_id")
    def _check_currency_in_method(self):
        for setting in self:
            if setting.currency_id not in setting.payment_method_id.currency_ids:
                raise ValidationError(
                    _(
                        "%(currency)s is not a currency of the payment method %(method)s.",
                        currency=setting.currency_id.name,
                        method=setting.payment_method_id.name,
                    )
                )

    @api.model
    def _load_pos_data_domain(self, data):
        return [("payment_method_id", "in", data["pos.payment.method"].ids)]

    @api.model
    def _load_pos_data_fields(self, config):
        return ["id", "payment_method_id", "currency_id"]

    @api.model
    def _load_pos_data_dependencies(self):
        return ["pos.payment.method"]
