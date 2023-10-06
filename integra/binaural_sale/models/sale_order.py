from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from lxml import etree
from odoo.tools.float_utils import float_is_zero


class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = ["sale.order", "filter.partner.mixin"]

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
        help="Rate that will be used as factor to multiply of the foreign currency for this move.",
        compute="_compute_rate",
        digits=(16, 15),
        default=0.0,
        store=True,
        readonly=False,
    )

    total_taxed = fields.Many2one(
        "account.tax",
        help="Total Taxed of the invoice",
    )

    foreign_taxable_income = fields.Monetary(
        help="Foreign Taxable Income of the invoice",
        compute="_compute_foreign_taxable_income",
        currency_field="foreign_currency_id",
    )

    foreign_total_billed = fields.Monetary(
        help="Foreign Total Billed of the invoice",
        compute="_compute_foreign_total_billed",
        currency_field="foreign_currency_id",
        store=True,
    )

    @api.constrains("order_line")
    def _check_taxes_id(self):
        for order in self:
            for line in order.order_line:
                if len(line.tax_id) != 1 and not line.display_type and self.env.company.unique_tax:
                    raise ValidationError(_("All products must contain only one tax."))

    @api.depends("tax_totals")
    def _compute_foreign_taxable_income(self):
        """
        Compute the foreign taxable income of the order
        """
        for move in self:
            move.foreign_taxable_income = False
            if move.order_line:
                move.foreign_taxable_income = move.tax_totals["foreign_amount_untaxed"]

    @api.depends("tax_totals")
    def _compute_foreign_total_billed(self):
        """
        Compute the foreign total billed of the order
        """
        for move in self:
            move.foreign_total_billed = False
            if move.order_line:
                move.foreign_total_billed = move.tax_totals["foreign_amount_total"]

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        """
        This method is used to get the view of the account move form and add the foreign currency
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
            The view of the account move form with the foreign currency symbol added to the page title
        """
        foreign_currency_symbol = ""
        foreign_currency_id = self.env.company.currency_foreign_id
        res = super().get_view(view_id, view_type, **options)

        if foreign_currency_id:
            foreign_currency_symbol = foreign_currency_id.symbol
            if view_type == "form":
                view_id = self.env.ref("binaural_sale.view_sale_order_form_binaural_sales").id
                doc = etree.XML(res["arch"])
                page = doc.xpath("//page[@name='foreign_currency']")
                if page:
                    page[0].set("string", _("Foreign Currency ") + foreign_currency_symbol)
                    res["arch"] = etree.tostring(doc, encoding="unicode")
        return res

    @api.depends(
        "order_line.tax_id",
        "order_line.price_unit",
        "amount_total",
        "amount_untaxed",
        "currency_id",
        "foreign_rate",
    )
    def _compute_tax_totals(self):
        return super()._compute_tax_totals()

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

    @api.onchange("name")
    def _onchange_name(self):
        """
        Ensure the foreign_rate and foreign_inverse_rate are computed when the order is still not
        created.
        """
        self._compute_rate()

    @api.depends("date_order")
    def _compute_rate(self):
        """
        Compute the rate of the sale order using the compute_rate method of the res.currency.rate
        model.
        """
        Rate = self.env["res.currency.rate"]
        # If the user doesn't want to update the foreign rate using the date order, then don't
        # compute the rate when it is not zero.
        for sale in self:
            if not self.env.company.update_sale_order_rate_using_date_order and not float_is_zero(
                sale.foreign_rate, precision_rounding=self.env.company.currency_id.rounding
            ):
                continue
            rate_values = Rate.compute_rate(
                sale.foreign_currency_id.id, sale.date_order.date() or fields.Date.today()
            )
            sale.update(rate_values)

    @api.onchange("foreign_rate")
    def _onchange_foreign_rate(self):
        """
        Onchange the foreign rate and compute the foreign inverse rate
        """
        for sale in self:
            base_usd_id = self.env["ir.model.data"]._xmlid_to_res_id(
                "base.USD", raise_if_not_found=False
            )
            if not bool(sale.foreign_rate):
                return
            sale.foreign_inverse_rate = (
                1 / sale.foreign_rate
                if sale.foreign_currency_id.id == base_usd_id
                else sale.foreign_rate
            )

    def _create_invoices(self, grouped=False, final=False, date=None):
        """
        This function creates the invoice associated to the order,
        but with this inheritance it creates multiple invoices if
        it exceeds the configuration limit.

        It also sends the custom rate of the order to the invoice
        """
        limit = self.company_id.max_product_invoice
        group = len(self._get_invoiceable_lines(final)) / limit
        invoices = self.env["account.move"]
        invoice_vals = self._prepare_invoice()

        if group % 1 != 0:
            group = int(group) + 1

        if group == 1:
            res = super()._create_invoices(grouped, final, date)
            self._update_invoices_rate()
            return res

        res = super()._create_invoices(grouped, final, date)

        invoices |= res
        _move_lines = self.env["account.move.line"]

        for i in range(group - len(res)):
            _move_lines = res.invoice_line_ids[limit : limit + limit]
            move = (
                self.env["account.move"]
                .sudo()
                .with_context(default_move_type="out_invoice")
                .create(invoice_vals)
            )

            for line in _move_lines:
                line_qty = line.quantity
                line.sudo().write({"move_id": move.id})
                line.sudo().write({"quantity": line_qty})

            move.message_post_with_view(
                "mail.message_origin_link",
                values={"self": move, "origin": move.line_ids.sale_line_ids.order_id},
                subtype_id=self.env["ir.model.data"]._xmlid_to_res_id("mail.mt_note"),
            )
            invoices |= move

        self._update_invoices_rate()
        for invoice in invoices:
            invoice.compute_line_ids_foreign_debit_and_credit()
        return invoices

    def _update_invoices_rate(self):
        """
        Syncs the rates of the invoices with the rates of the order.
        """
        if not self.env.company.use_invoice_rate_from_sale_order:
            return
        for sale in self:
            sale.invoice_ids.write(
                {
                    "foreign_rate": sale.foreign_rate,
                    "foreign_inverse_rate": sale.foreign_inverse_rate,
                }
            )

    @api.onchange("pricelist_id")
    def _onchange_pricelist_id(self):
        """
        Recalculate the prices of the products in the purchase order when the rate changes.
        """
        try:
            sale_order_id = int(str(self.id)[6:])
            sale_order = self.env["sale.order"].browse(sale_order_id)

            sale_order._recompute_prices()
            sale_order.message_post(
                body=_(
                    "Product prices have been recomputed according to pricelist %s.",
                    self.pricelist_id._get_html_link(),
                )
            )

        except:
            self._recompute_prices()
