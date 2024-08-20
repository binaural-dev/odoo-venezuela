from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from lxml import etree
from odoo.tools.float_utils import float_is_zero
import logging
_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _name = "purchase.order"
    _inherit = ["purchase.order", "filter.partner.mixin"]

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
        default=default_alternate_currency,
    )

    vat = fields.Char(
        string="VAT",
        help="VAT of the partner",
        compute="_compute_vat",
        readonly=False,
    )

    foreign_rate = fields.Float(
        help="The rate that is gonna be always shown to the user.",
        compute="_compute_rate",
        digits="Tasa",
        default=0.0,
        store=True,
        readonly=False,
    )
    foreign_inverse_rate = fields.Float(
        help="Rate that will be used as factor to multiply of the foreign currency for this order.",
        compute="_compute_rate",
        digits=(16, 15),
        default=0.0,
        store=True,
        readonly=False,
    )

    manually_set_rate = fields.Boolean(default=False)
    last_foreign_rate = fields.Float(copy=False)

    total_taxed = fields.Many2one(
        "account.tax",
        help="Total Taxed of the order",
    )

    foreign_taxable_income = fields.Monetary(
        help="Foreign Taxable Income of the order",
        compute="_compute_foreign_taxable_income",
        currency_field="foreign_currency_id",
    )

    foreign_total_billed = fields.Monetary(
        help="Foreign Total Billed of the order",
        compute="_compute_foreign_total_billed",
        currency_field="foreign_currency_id",
        store=True,
    )

    journal_invoice_id = fields.Many2one(
        "account.journal", string="Journal Invoice", domain="[('type', '=', 'purchase')]"
    )

    @api.constrains("currency_id")
    def _check_currency_id(self):
        for move in self:
            if move.currency_id.id != self.env.company.currency_id.id:
                raise ValidationError(
                    _("You cannot place a currency other than the base of the system.")
                )

    @api.onchange("journal_invoice_id")
    def _onchange_journal_invoice_id(self):
        if not self.journal_invoice_id:
            return

        for line in self.order_line:
            if not self.journal_invoice_id.fiscal:
                line.taxes_id = self.env.company.exent_aliquot_purchase
            else:
                if not line.product_id:
                    continue
                line.taxes_id = line.product_id.supplier_taxes_id

    @api.constrains("order_line")
    def _check_taxes_id(self):
        for order in self:
            for line in order.order_line:
                if (
                    len(line.taxes_id) != 1
                    and not line.display_type
                    and self.env.company.unique_tax
                ):
                    raise ValidationError(_("All products must contain only one tax."))

    @api.depends("tax_totals")
    def _compute_foreign_taxable_income(self):
        """
        Compute the foreign taxable income of the order
        """
        for order in self:
            order.foreign_taxable_income = False
            if order.order_line:
                order.foreign_taxable_income = order.tax_totals["foreign_amount_untaxed"]

    @api.depends("tax_totals")
    def _compute_foreign_total_billed(self):
        """
        Compute the foreign total billed of the order
        """
        for order in self:
            order.foreign_total_billed = False
            if order.order_line:
                order.foreign_total_billed = order.tax_totals["foreign_amount_total"]

    @api.depends(
        "order_line.taxes_id",
        "order_line.price_subtotal",
        "amount_total",
        "amount_untaxed",
        "foreign_rate",
    )
    def _compute_tax_totals(self):
        return super()._compute_tax_totals()

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        """
        This method is used to get the view of the purchase order form and add the foreign currency
        symbol to the page title.

        Parameters
        ----------
        view_id : int
            The id of the view

        view_type : str
            The type of the view

        options : dict
            The options of the view

        Returns
        -------
        type = dict
            The view of the purchase order form with the foreign currency symbol added to the page
            title
        """
        foreign_currency_symbol = ""
        foreign_currency_id = self.env.company.currency_foreign_id

        res = super().get_view(view_id, view_type, **options)

        if foreign_currency_id:
            foreign_currency_symbol = foreign_currency_id.symbol
            if view_type == "form":
                view_id = self.env.ref(
                    "binaural_purchase.view_purchase_order_form_binaural_purchase"
                ).id
                doc = etree.XML(res["arch"])
                page = doc.xpath("//page[@name='foreign_currency']")
                if page:
                    page[0].set("string", _("Foreign Currency ") + " " + foreign_currency_symbol)
                    res["arch"] = etree.tostring(doc, encoding="unicode")
        return res

    @api.depends("partner_id")
    def _compute_vat(self):
        """
        Compute the vat of the partner and add the prefix to it if it exists in the partner record
        """
        for rec in self:
            if rec.partner_id.prefix_vat and rec.partner_id.vat:
                vat = str(rec.partner_id.prefix_vat) + str(rec.partner_id.vat)
            else:
                vat = str(rec.partner_id.vat)
            rec.vat = vat.upper()

    @api.model_create_multi
    def create(self, vals_list):
        """
        Ensure that the foreign_rate and foreign_inverse_rate are computed when the purchase order
        is created.
        """
        purchase_orders = super().create(vals_list)
        purchase_orders._compute_rate()
        return purchase_orders

    @api.onchange("name")
    def onchange_order_line(self):
        """
        Ensure the foreign_rate and foreign_inverse_rate are computed when the order is still not
        created.
        """
        self._compute_rate()

    @api.depends("date_order", "date_approve")
    def _compute_rate(self):
        """
        Compute the rate of the purchase order using the compute_rate method of the
        res.currency.rate model.
        """
        Rate = self.env["res.currency.rate"]
        ignore_rate_with_value = self.env.context.get("ignore_rate_with_value", False)

        for purchase in self:

            if ignore_rate_with_value and purchase.foreign_rate:
                continue

            if purchase.manually_set_rate:
                continue
            if (
                not self.env.company.update_purchase_order_rate_using_date_order
                and not float_is_zero(
                    purchase.foreign_rate, precision_rounding=self.env.company.currency_id.rounding
                )
            ):
                continue
            date_order = (
                purchase.date_approve.date()
                if purchase.date_approve
                else purchase.date_order.date()
            )
            rate_values = Rate.compute_rate(
                purchase.foreign_currency_id.id, date_order or fields.Date.today()
            )
            purchase.foreign_rate = rate_values.get("foreign_rate", 0)
            purchase.foreign_inverse_rate = rate_values.get("foreign_inverse_rate", 0)

    @api.onchange("foreign_rate")
    def _onchange_foreign_rate(self):
        """
        Onchange the foreign rate and compute the foreign inverse rate
        """
        for purchase in self:
            base_usd_id = self.env["ir.model.data"]._xmlid_to_res_id(
                "base.USD", raise_if_not_found=False
            )
            if not bool(purchase.foreign_rate):
                return
            purchase.foreign_inverse_rate = (
                1 / purchase.foreign_rate
                if purchase.foreign_currency_id.id == base_usd_id
                else purchase.foreign_rate
            )

    def action_create_invoice(self):
        """
        Inherits the original method to set the value of the following fields on the invoice based
        on the ones from the order:
            - filter_partner
            - manually_set_rate
            - foreign_rate
            - foreign_inverse_rate
        """
        res = super().action_create_invoice()
        if not self.env.company.use_invoice_rate_from_purchase_order:
            return res
        for order in self:
            order.invoice_ids.write(
                {
                    "filter_partner": order.filter_partner,
                    "manually_set_rate": order.manually_set_rate,
                    "foreign_rate": order.foreign_rate,
                    "foreign_inverse_rate": order.foreign_inverse_rate,
                }
            )
        return res

    def write(self, vals):
        if vals.get("foreign_rate", False):
            vals.update({"last_foreign_rate": self.foreign_rate})
        res = super().write(vals)
        if (
            vals.get("foreign_rate", False)
            and self.manually_set_rate
            and self.foreign_rate != self.last_foreign_rate
        ):
            self.message_post(
                body=_(
                    "The rate has been updated from %(last_rate)s to %(rate)s ",
                )
                % ({"rate": self.foreign_rate, "last_rate": self.last_foreign_rate})
            )
        return res

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for purchase in res:
            Rate = self.env["res.currency.rate"]
            rate_values = Rate.compute_rate(
                purchase.foreign_currency_id.id, purchase.date_order or fields.Date.today()
            )
            last_foreign_rate = rate_values.get("foreign_rate", 0)
            if purchase.manually_set_rate and purchase.foreign_rate != last_foreign_rate:
                purchase.message_post(
                    body=_(
                        "The rate has been updated from %(last_rate)s to %(rate)s ",
                    )
                    % ({"rate": purchase.foreign_rate, "last_rate": last_foreign_rate})
                )
        return res

    def read(self, fields=None, load='_classic_read'):
        self.with_context(ignore_rate_with_value=True)._compute_rate()
        return super().read(fields, load)
