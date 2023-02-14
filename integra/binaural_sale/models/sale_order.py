from odoo import models, fields, api, _
from lxml import etree
import dateutil.parser


class SaleOrder(models.Model):
    _inherit = 'sale.order'

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

    foreign_taxable_income = fields.Monetary(
        help="Foreign Taxable Income of the invoice",
        compute="_compute_foreign_taxable_income",
        currency_field="foreign_currency_id",
    )
    total_taxed = fields.Many2one(
        "account.tax",
        help="Total Taxed of the invoice",
    )
    foreign_total_billed = fields.Monetary(
        help="Foreign Total Billed of the invoice",
        compute="_compute_foreign_total_billed",
        currency_field="foreign_currency_id",
        store=True,
    )

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
        foreign_currency_id = self.env.company.currency_foreign_id.id

        res = super().get_view(view_id, view_type, **options)

        if foreign_currency_id:
            foreign_currency_record = self.env["res.currency"].search(
                [("id", "=", int(foreign_currency_id))]
            )
            foreign_currency_symbol = foreign_currency_record.symbol
            if view_type == "form":
                view_id = self.env.ref(
                    "binaural_sale.view_sale_order_form_binaural_sales"
                ).id
                doc = etree.XML(res["arch"])
                page = doc.xpath("//page[@name='foreign_currency']")
                if page:
                    page[0].set("string", _("Foreign Currency ") + " " + foreign_currency_symbol)
                    res["arch"] = etree.tostring(doc, encoding="unicode")
        return res

    @api.depends('partner_id')
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
        Ensure that the foreign_rate and foreign_inverse_rate are computed when the invoice is created.
        """
        moves = super().create(vals_list)
        moves._compute_rate()
        return moves

    @api.depends("date_order")
    def _compute_rate(self):
        """
        Compute the rate of the invoice using the compute_rate method of the res.currency.rate model.
        """
        Rate = self.env["res.currency.rate"]
        for move in self:
            date_order = dateutil.parser.parse(str(move.date_order)).date()
            rate_values = Rate.compute_rate(
                move.foreign_currency_id.id, date_order or fields.Date.today()
            )
            move.update(rate_values)

    @api.depends("foreign_currency_id", "amount_total", "foreign_rate")
    def _compute_foreign_taxable_income(self):
        """ 
        Compute the foreign taxable income of the invoice
        """
        for move in self:
            move.foreign_taxable_income = move.amount_untaxed * move.foreign_inverse_rate

    @api.depends("foreign_currency_id", "amount_total", "foreign_rate")
    def _compute_foreign_total_billed(self):
        """
        Compute the foreign total billed of the invoice
        """
        for move in self:
            move.foreign_total_billed = move.amount_total * move.foreign_inverse_rate


    @api.onchange("foreign_rate")
    def _onchange_foreign_rate(self):
        """
        Onchange the foreign rate and compute the foreign inverse rate
        """
        for move in self:
            base_usd_id = self.env["ir.model.data"]._xmlid_to_res_id(
                "base.USD", raise_if_not_found=False
            )
            if not bool(move.foreign_rate):
                return
            move.foreign_inverse_rate = (
                1 / move.foreign_rate
                if move.foreign_currency_id.id == base_usd_id
                else move.foreign_rate
            )



