from odoo import models, fields, api, _


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    is_foreign_currency = fields.Boolean(default=False)

    cross_account_journal = fields.Many2one("account.journal", domain=[("type", "=", "general")])

    cross_journal = fields.Many2one("account.journal", domain=[("type", "in", ("bank", "cash"))])

    apply_one_cross_move = fields.Boolean(default=False)
    
    @api.model
    def _load_pos_data_fields(self, config_id):
        res = super()._load_pos_data_fields(config_id)
        res += ['is_foreign_currency', 'cross_account_journal', 'cross_journal', 'apply_one_cross_move']
        return res