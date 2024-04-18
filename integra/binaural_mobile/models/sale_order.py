import logging
import copy

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
JOURNAL_DOMAIN = [("active", "=", True), ("type", "=", "sale"),]

class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _get_default_journal(self):
        domain = copy.deepcopy(JOURNAL_DOMAIN)
        domain.append(("fiscal", "=", False))
        journal = self.env["account.journal"].search(domain, limit=1)

        return journal.id

    state_seller = fields.Char(
        "Seller State",
        compute="_compute_state_seller",
        help="Track the actual order state to display in-app.",
    )
    tax_included = fields.Boolean(
        tracking=True, help="Indicates if a sale order was includes taxes."
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Sales Journal",
        compute="_compute_journal_id",
        default=_get_default_journal,
        help="Journal used when a invoice is generated with or without taxes.",
    )

    def write(self, vals):
        if "order_line" in vals and self.env.user.employee_id.is_seller and self.state in ["sale","done"]:
            raise UserError(_("You can't modify this order, beceause it isn't in draft."))
        res = super().write(vals)
        return res


    def _create_invoices(self, grouped=False, final=False, date=None):
        res = super()._create_invoices(grouped, final, date) #contingence?
        for invoice in res:
            if invoice.state == "draft":
                invoice.journal_id = self.journal_id.id
                invoice.invoice_user_id = self.user_id.id

        return res

    @api.depends("tax_included")
    def _compute_journal_id(self):
        for sale in self:
            if sale.tax_included:
                journal = sale.env.company.dairy_fiscal
            else:
                journal = sale.env.company.dairy_no_fiscal
                
            if sale.invoice_ids:
                for invoice in sale.invoice_ids:
                    if invoice.state == "draft":
                        invoice.journal_id = journal.id
            sale.journal_id = journal.id


    @api.depends("state", "invoice_ids")
    def _compute_state_seller(self):
        for sale in self:
            state_seller = ""
            if sale.state in ["draft", "sent"]:
                state_seller = _("Draft")
            elif sale.state == "cancel":
                state_seller = _("Cancel")
            elif sale.invoice_ids:
                state_seller = _("Invoice")
            else:
                state_seller = _("Sale Order")

            sale.state_seller = state_seller
