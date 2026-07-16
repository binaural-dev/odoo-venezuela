from odoo import models, fields, api, _


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    is_foreign_currency = fields.Boolean(default=False)

    cross_account_journal = fields.Many2one("account.journal", domain=[("type", "=", "general")])

    cross_journal = fields.Many2one("account.journal", domain=[("type", "in", ("bank", "cash"))])

    apply_one_cross_move = fields.Boolean(
        string="Enable Automatic Cross-Account Clearing",
        default=False,
        help="When enabled, closing a PoS session creates a draft journal "
        "entry that clears this payment method's outstanding (transitory) "
        "account into the real bank account set in 'Cross Journal', "
        "recorded in the 'Cross Account Journal'. One entry is created per "
        "payment for split payment methods, or one per session for "
        "combined payment methods. The entry is created in draft state and "
        "has no effect on account balances until it is reviewed and posted "
        "manually.",
    )
    
    @api.model
    def _load_pos_data_fields(self, config_id):
        res = super()._load_pos_data_fields(config_id)
        res += ['is_foreign_currency', 'cross_account_journal', 'cross_journal', 'apply_one_cross_move']
        return res