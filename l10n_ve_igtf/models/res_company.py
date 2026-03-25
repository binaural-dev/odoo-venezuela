from odoo import fields, models, api, _
from odoo.exceptions import UserError

class ResCompany(models.Model):
    _inherit = "res.company"

    customer_account_igtf_id = fields.Many2one(
        "account.account", domain=[("account_type", "=", "liability_current"),], copy=False
    )
    supplier_account_igtf_id = fields.Many2one(
        "account.account", domain=[("account_type", "=", "expense")],copy=False
    )
    igtf_percentage = fields.Float(string="IGTF Percentage", default=3.00,copy=False)

    show_igtf_suggested_account_move = fields.Boolean(default=False,copy=False)
    show_igtf_suggested_sale_order = fields.Boolean(default=False,copy=False)

    advance_payment_igtf_journal_id = fields.Many2one(
        "account.journal",
        string="Advance Payment IGTF Journal",
        help="Journal used for advance payments with IGTF",copy=False
    )

    advance_customer_account_id = fields.Many2one(
        "account.account",
        string="Advance Customer Account",
        domain = [ ('account_type', '=', 'liability_current'),("is_advance_account", "=", True),('reconcile','=',True)],
        help="Account used for advance payments from customers",copy=False
    )

    advance_supplier_account_id = fields.Many2one(
        "account.account",
        string="Advance Supplier Account",
        domain = [('account_type', '=', 'asset_current'),("is_advance_account", "=", True),('reconcile','=',True)],
        help="Account used for advance payments to suppliers",copy=False
    )

    revalorize_payments_vef = fields.Boolean(copy=False, default = False
    )

    @api.onchange('advance_customer_account_id','advance_supplier_account_id')
    def _onchange_default_igtf_account(self):
        for rec in self:

            if self.env.context.get('install_mode') or self.env.context.get('skip_check'):
                return
            if rec.advance_customer_account_id and not rec.advance_customer_account_id.is_advance_account:
                raise UserError(_("The account for Advance Customer Account must be type liability_current, is_advance_account and reconciliable"))
            
            if rec.advance_supplier_account_id and not rec.advance_supplier_account_id.is_advance_account:
                raise UserError(_("The account for Advance Supplier Account must be type asset_current, is_advance_account and reconciliable"))

    