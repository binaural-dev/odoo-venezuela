import datetime
import logging

from lxml import etree
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_is_zero

_logger = logging.getLogger(__name__)


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
        return self.env.company.foreign_currency_id.id or False

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
        tracking=True,
    )
    foreign_inverse_rate = fields.Float(
        help="Rate that will be used as factor to multiply of the foreign currency for this move.",
        compute="_compute_rate",
        digits=(16, 15),
        default=0.0,
        store=True,
        readonly=False,
    )

    last_foreign_rate = fields.Float(copy=False)
    manually_set_rate = fields.Boolean(default=False)

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

    pricelist_id = fields.Many2one(
        domain=lambda self: (
            "[('company_id', 'in', (company_id, False)),"
            f"('currency_id', '=', {self.env.company.currency_id.id})]"
        )
    )

    address = fields.Char(related="partner_id.street")

    mobile = fields.Char(related="partner_id.mobile")

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None, **kwargs):
        if 'load' in kwargs:
            del kwargs['load']
        context = self.with_context(active_test=False)
        return super(SaleOrder, context).search_read(
            domain, fields, offset, limit, order
        )

    @api.constrains("order_line")
    def _check_taxes_id(self):
        for order in self:
            for line in order.order_line:
                if (
                    len(line.tax_id) != 1
                    and not line.display_type
                    and self.env.company.unique_tax
                ):
                    raise ValidationError(_("All products must contain only one tax."))

    @api.constrains("order_line", "state")
    def _check_lines_maximum_limit(self):
        are_sale_lines_limited = self.env.company.are_sale_lines_limited

        if not are_sale_lines_limited:
            return

        maximum_sales_line_limit = self.env.company.maximum_sales_line_limit

        if not maximum_sales_line_limit:
            return

        for order in self:

            if order.state in ["draft", "cancel"]:
                continue

            if len(order.order_line) <= maximum_sales_line_limit:
                continue

            raise UserError(
                _("The order line limit must not exceed %s.", maximum_sales_line_limit)
            )

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
                move.foreign_total_billed = move.tax_totals.get("total_amount_foreign_currency")

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
        foreign_currency_id = self.env.company.foreign_currency_id
        res = super().get_view(view_id, view_type, **options)

        if foreign_currency_id:
            foreign_currency_symbol = foreign_currency_id.symbol
            if view_type == "form":
                view_id = self.env.ref(
                    "l10n_ve_sale.view_sale_order_form_l10n_ve_sales"
                ).id
                doc = etree.XML(res["arch"])
                page = doc.xpath("//page[@name='foreign_currency']")
                if page:
                    page[0].set(
                        "string", _("Foreign Currency ") + foreign_currency_symbol
                    )
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
        # Adaptar el contexto para que el método de impuestos pueda recuperar el registro de la orden
        for order in self:
            ctx = self.env.context.copy()
            ctx.update({'active_id': order.id, 'active_model': order._name})
            order.with_context(ctx)._compute_tax_totals_base()

    def _compute_tax_totals_base(self):
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

    @api.depends("foreign_currency_id", "date_order")
    def _compute_rate(self):
        """
        Compute the rate of the sale order using the compute_rate method of the res.currency.rate
        model.
        """
        Rate = self.env["res.currency.rate"]
        # If the user doesn't want to update the foreign rate using the date order, then don't
        # compute the rate when it is not zero.
        for sale in self:
            if (
                sale.manually_set_rate
                or "website_id" in sale._fields
                and sale.website_id
            ):
                continue
            if (
                not self.env.company.update_sale_order_rate_using_date_order
                and not float_is_zero(
                    sale.foreign_rate,
                    precision_rounding=self.env.company.currency_id.rounding,
                )
            ):
                continue
            rate_values = Rate.compute_rate(
                sale.foreign_currency_id.id,
                sale.date_order.date() or fields.Date.today(),
            )
            sale.foreign_rate = rate_values.get("foreign_rate", 0)
            sale.foreign_inverse_rate = rate_values.get("foreign_inverse_rate", 0)

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

    def _get_invoiceable_lines(self, final=False):
        if self._context.get("ignore_limit", False):
            return super()._get_invoiceable_lines(final)

        res = super()._get_invoiceable_lines(final)
        limit = self.company_id.max_product_invoice

        if len(res) <= limit:
            return res
        return res[:limit]

    def _create_invoices(self, grouped=False, final=False, date=None):
        """
        This function creates the invoice associated to the order,
        but with this inheritance it creates multiple invoices if
        it exceeds the configuration limit.

        It also sends the custom rate of the order to the invoice
        """
        invoices = self.env["account.move"]
        for order in self:
            invoiceable_lines = order._get_invoiceable_lines(final)
            while len(invoiceable_lines) != 0:
                invoices |= super()._create_invoices(grouped, final, date)
                invoiceable_lines = order._get_invoiceable_lines(final)

        return invoices

    def _prepare_invoice(self):
        invoice_vals = super()._prepare_invoice()
        invoice_vals["manually_set_rate"] = (
            self.manually_set_rate or self.env.company.use_invoice_rate_from_sale_order
        )
        invoice_vals["foreign_rate"] = self.foreign_rate
        invoice_vals["foreign_inverse_rate"] = self.foreign_inverse_rate
        return invoice_vals

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

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for sale in res:
            Rate = self.env["res.currency.rate"]
            rate_values = Rate.compute_rate(
                sale.foreign_currency_id.id, sale.date_order or fields.Date.today()
            )
            last_foreign_rate = rate_values.get("foreign_rate", 0)
            if sale.manually_set_rate and sale.foreign_rate != last_foreign_rate:
                sale.message_post(
                    body=_(
                        "The rate has been updated from %(last_rate)s to %(rate)s ",
                    )
                    % ({"rate": sale.foreign_rate, "last_rate": last_foreign_rate})
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

    @api.onchange("pricelist_id")
    def _onchange_pricelist_id(self):
        """
        Recalculate the prices of the products in the purchase order when the rate changes.
        """
        try:
            record = self if isinstance(self.id, int) else self._origin
            record._recompute_prices()
            if self.pricelist_id:
                record.message_post(
                    body=_(
                        "Product prices have been recomputed according to pricelist %s.",
                        self.pricelist_id._get_html_link(),
                    )
                )
        except Exception:
            self._recompute_prices()

    def _block_valid_confirm(self):
        self.ensure_one()

        block_order_invoice_payment_state = (
            self.company_id.block_order_invoice_payment_state
        )
        block_order_invoice_total_amount_overdue = (
            self.company_id.block_order_invoice_total_amount_overdue
        )

        today_date = fields.Date.today()

        invoice_ids = self.env["account.move"].search(
            [
                ("partner_id", "=", self.partner_id.id),
                ("amount_total", ">", 0),
                "|",
                ("payment_state", "=", block_order_invoice_payment_state),
                ("invoice_date_due", "<", today_date),
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted")
            ]
        )

        if not any(invoice_ids):
            return None

        invoice_count_payment_state = 0
        invoice_count_date_expired = 0
        amount_total_overdue = 0
        amount_total_not_pay = 0

        for invoice_id in invoice_ids:
            if block_order_invoice_payment_state:
                if invoice_id.payment_state == block_order_invoice_payment_state:
                    invoice_count_payment_state += 1

            if invoice_id.invoice_date_due and invoice_id.invoice_date_due < today_date:
                amount_total_overdue += invoice_id.amount_total
                amount_total_not_pay += invoice_id.amount_residual
                invoice_count_date_expired += 1

        if invoice_count_payment_state:
            payment_state_labels = {
                "not_paid": _("Not Paid"),
                "in_payment": _(
                    "In Payment Process",
                ),
            }

            raise UserError(
                _("The budget cannot be confirmed. You have %s Invoices (%s).")
                % (
                    invoice_count_payment_state,
                    payment_state_labels[block_order_invoice_payment_state],
                )
            )

        if block_order_invoice_total_amount_overdue:
            if amount_total_not_pay > block_order_invoice_total_amount_overdue:
                raise UserError(
                    _(
                        "The budget cannot be confirmed. Has an overdue amount of (%.2f) that cannot be greater than %.2f %s."
                    )
                    % (
                        amount_total_not_pay,
                        block_order_invoice_total_amount_overdue,
                        invoice_id.currency_id.name,
                    )
                )

    def action_confirm(self):
        for order in self:
            if not order.order_line or all(line.display_type for line in order.order_line):
                raise UserError(_("Before confirming an order, you need to add a product."))
        skip_not_allow_sell_products_validation = self.env.context.get(
            "skip_not_allow_sell_products_validation", False
        )
        if (
            self.env.company.not_allow_sell_products
            and not skip_not_allow_sell_products_validation
        ):
            for order in self:
                for line in order.order_line:
                    if (
                        line.product_id.detailed_type == "product"
                        and line.product_id.qty_available < line.product_uom_qty
                    ):
                        msg = _("Does not have enough units available for the product ")
                        msg += _("{}. Only has {} units of the {} demanded.").format(
                            line.product_id.name,
                            line.product_id.qty_available,
                            line.product_uom_qty,
                        )
                        raise ValidationError(msg)

            if (
                order.company_id.account_use_credit_limit
                and order.partner_id.use_partner_credit_limit_order
            ):
                total_pay = order.partner_id.credit + order.amount_total
                if total_pay > order.partner_id.credit_limit:
                    decimal_places = order.currency_id.decimal_places
                    raise ValidationError(
                        _(
                            "No se ha confirmado el presupuesto. Límite de crédito excedido. La cuenta por cobrar del cliente es de %s más %s en presupuesto da un total de %s superando el límite de ventas de %s. Por favor cancele el presupuesto o comuníquese con el administrador para aumentar el límite de crédito del cliente.",
                            round(order.partner_id.credit, decimal_places),
                            round(order.amount_total, decimal_places),
                            round(total_pay, decimal_places),
                            round(order.partner_id.credit_limit, decimal_places),
                        )
                    )

        self._block_valid_confirm()


        res = super().action_confirm()
        product_limit = self.env.company.limit_product_qty_out
        for sale in self:
            picking = sale.picking_ids
            if product_limit > 0:
                picking_moves = picking.move_ids_without_package
                picking_vals = picking.read(['location_dest_id', 'location_id', 'move_type', 'picking_type_id']) 
                picking_vals = {
                    key: (value[0] if isinstance(value, tuple) else value)
                    for key, value in picking_vals[0].items()
                }
                picking_vals['origin'] = picking.origin
                picking_vals['partner_id'] = picking.partner_id.id
                picking_vals['user_id'] = picking.user_id.id
                
                list_pickings_moves = [picking_moves[i:i + product_limit] for i in range(0, len(picking_moves), product_limit)]
                picking.move_ids_without_package = list_pickings_moves[0]
                
                for list_moves in list_pickings_moves[1:]:
                    picking_vals["move_ids_without_package"] = list_moves
                    new_picking = self.env['stock.picking'].create(picking_vals)
                

                
        return res

    def cancel_order_after_date(self):
        orders = self.search(
            [
                ("create_date", "<", fields.Date.today() - datetime.timedelta(days=1)),
                ("state", "not in", ["sale", "done", "cancel"]),
            ]
        )
        for order in orders:
            order.action_cancel()

    @api.depends('order_line.price_subtotal', 'currency_id', 'company_id', 'payment_term_id')
    def _compute_amounts(self):
        for order in self:
            order.amount_untaxed = order.tax_totals['base_amount_currency']
            order.amount_tax = order.tax_totals['tax_amount_currency']
            order.amount_total = order.tax_totals['total_amount_currency']