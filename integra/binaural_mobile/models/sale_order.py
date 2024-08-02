import logging
import copy
from bs4 import BeautifulSoup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
JOURNAL_DOMAIN = [
    ("active", "=", True),
    ("type", "=", "sale"),
]


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for record in res:
            record.manage_note_app()
        return res

    def manage_note_app(self):
        for record in self:
            line_note = record.order_line.filtered(lambda line: line.display_type == "line_note")
            if not record.note and line_note:
                line_note.unlink()
                continue

            if not record.note:
                continue

            note = BeautifulSoup(record.note).get_text()
            if line_note and note == "":
                line_note.unlink()
                continue
            if record.note:
                if line_note:
                    line_note.write({"name": note})

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

    company_mobile = fields.Boolean(
        related="company_id.company_mobile",
    )

    def write(self, vals):
        if "note" in vals:
            self.manage_note_app()
        if (
            "order_line" in vals
            and self.env.user.employee_id.is_seller
            and self.state in ["sale", "done"]
        ):
            raise UserError(_("You can't modify this order, beceause it isn't in draft."))
        res = super().write(vals)
        return res

    def _create_invoices(self, grouped=False, final=False, date=None):
        res = super()._create_invoices(grouped, final, date)  # contingence?
        for invoice in res:
            if invoice.state == "draft":
                invoice.journal_id = self.journal_id.id if self.company_mobile else False
                invoice.invoice_user_id = self.user_id.id

        return res

    def _get_journal_id(self):
        self.ensure_one()

        if self.tax_included:
            return self.env.company.dairy_fiscal

        return self.env.company.dairy_no_fiscal

    @api.depends("tax_included")
    def _compute_journal_id(self):
        for sale in self:
            journal_id = sale._get_journal_id()

            sale.journal_id = journal_id.id if self.company_mobile else False

            for invoice in sale.invoice_ids:
                if invoice.state != "draft":
                    continue

                invoice.journal_id = journal_id.id if self.company_mobile else False

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

    @api.onchange("tax_included")
    def _onchange_tax_included(self):
        self.set_tax_lines()

    def set_tax_lines(self):
        if self.order_line:
            with_out_tax = self.env["account.tax"].search(
                [
                    ("active", "=", True),
                    ("company_id", "in", [self.company_id.id, False]),
                    ("type_tax_use", "=", "sale"),
                    ("amount", "=", 0),
                ],
                limit=1,
            )
            for line in self.order_line:
                if not line.display_type:
                    if line.product_template_id.taxes_id:
                        line.update(
                            {
                                "tax_id": [
                                    (
                                        6,
                                        0,
                                        [
                                            (
                                                line.product_template_id.taxes_id[0].id
                                                if self.tax_included
                                                else with_out_tax.id
                                            )
                                        ],
                                    )
                                ]
                            }
                        )


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    price_unit_with_tax = fields.Float(compute="_compute_price_unit_with_tax", store=True)

    @api.depends("price_unit", "tax_id")
    def _compute_price_unit_with_tax(self):
        for line in self:
            price_unit = line.price_unit
            taxes = line.tax_id.compute_all(
                price_unit,
                line.order_id.currency_id,
                1,
                product=line.product_id,
            )
            line.price_unit_with_tax = taxes["total_included"]

    @api.onchange("product_id")
    def _onchange_product_id_warning(self):
        res = super()._compute_tax_id()
        self.order_id.set_tax_lines()
        return res
