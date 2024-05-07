from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    commission_product_id = fields.Many2one(
        "product.product",
        related="company_id.commission_product_id",
        readonly=False,
        default=lambda self: self.env["ir.model.data"]._xmlid_to_res_id(
            "binaural_commissions.product_product_commission_payment"
        ),
    )
    commission_journal_id = fields.Many2one(
        "account.journal", related="company_id.commission_journal_id", readonly=False
    )
    commission_invoice_date_field = fields.Selection(
        related="company_id.commission_invoice_date_field",
        readonly=False,
    )
    compute_commission_when = fields.Selection(
        related="company_id.compute_commission_when", readonly=False
    )
    commission_payment_through = fields.Selection(
        related="company_id.commission_payment_through", readonly=False
    )
    in_invoice_status_commission = fields.Selection(
        related="company_id.in_invoice_status_commission", readonly=False
    )

    def action_edit_commission_policy_type_order(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Commission Policy Types"),
            "res_model": "commission.policy.type",
            "view_mode": "tree",
            "view_id": self.env.ref("binaural_commissions.commission_policy_type_tree_view").id,
        }
