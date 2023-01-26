from odoo import api, fields, models, _
import logging
from lxml import etree

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    def default_alternate_currency(self):
        """
        This method is used to get the foreign currency of the company and set it as the default value of the foreign currency field

        Returns
        -------
        type = int
            The id of the foreign currency of the company

        """
        alternate_currency = self.env.company.currency_foreign_id.id
        if alternate_currency:
            return alternate_currency
        return False

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

    tax = fields.Float(help="Tax of the line", compute="_compute_tax", digits="Tasa", default=0.0)

    foreign_taxable_income = fields.Monetary(
        help="Foreign Taxable Income of the invoice",
        compute="_compute_foreign_taxable_income",
        currency_field="foreign_currency_id",
    )
    total_taxed = fields.Many2one(
        "account.tax",
        help="Total Taxed of the invoice",
    )

    foreign_tax = fields.Float(
        help="Foreign Tax of the line",
        # compute="_compute_foreign_tax",
        digits="Tasa",
    )

    foreign_discount = fields.Monetary(
        help="Foreign Discount of the line",
        # compute="_compute_foreign_discount",
        currency_field="foreign_currency_id",
    )

    foreign_total_billed = fields.Monetary(
        help="Foreign Total Billed of the invoice",
        compute="_compute_foreign_total_billed",
        currency_field="foreign_currency_id",
    )

    foreign_total_due = fields.Monetary(
        help="Foreign Total Due of the invoice",
        compute="_compute_foreign_total_due",
        currency_field="foreign_currency_id",
    )

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        """
        This method is used to get the view of the account move form and add the foreign currency symbol to the page title

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
                    "binaural_invoice.view_account_move_form_binaural_invoice"
                ).id
                doc = etree.XML(res["arch"])
                page = doc.xpath("//page[@name='foreign_currency']")
                if page:
                    page[0].set("string", _("Foreign Currency (%s)") % foreign_currency_symbol)
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

    @api.depends("invoice_date")
    def _compute_tax(self):
        """
        Compute the tax of the line.

        if current_currency is equal to 2 "USD" compute the company rate

        else thats compute the inverse rate

        """
        current_currency = self.env.company.currency_id.id
        foreign_currency = self.env["res.currency"].search([("active", "=", True)])
        for currency in foreign_currency:
            if currency.id != current_currency:
                for tax in currency.rate_ids:
                    if current_currency == 2:
                        if tax.name == self.invoice_date:
                            self.tax = tax.company_rate
                            break
                        self.tax = tax[-1].company_rate
                    else:
                        if tax.name == self.invoice_date:

                            self.tax = tax.inverse_company_rate
                            break
                        self.tax = tax[-1].inverse_company_rate

    @api.depends("foreign_currency_id", "amount_total", "tax")
    def _compute_foreign_taxable_income(self):
        """
        Compute the foreign taxable income of the invoice

        """
        for rec in self:
            rec.foreign_taxable_income = rec.amount_untaxed * rec.tax

    @api.depends("foreign_currency_id", "amount_total", "tax")
    def _compute_foreign_total_billed(self):
        """
        Compute the foreign total billed of the invoice

        """
        for rec in self:
            rec.foreign_total_billed = rec.amount_total * rec.tax

    @api.depends("foreign_currency_id", "amount_residual", "tax")
    def _compute_foreign_total_due(self):
        """
        Compute the foreign total due of the invoice

        """
        for rec in self:
            rec.foreign_total_due = rec.amount_residual * rec.tax

    @api.depends(
        "invoice_line_ids.currency_rate",
        "invoice_line_ids.tax_base_amount",
        "invoice_line_ids.tax_line_id",
        "invoice_line_ids.price_total",
        "invoice_line_ids.price_subtotal",
        "invoice_payment_term_id",
        "partner_id",
        "currency_id",
    )
    def _compute_tax_totals(self):
        res = super()._compute_tax_totals()
        for rec in self:
            _logger.warning("Se ejecutó el método _compute_tax_totals %s" % rec.tax_totals)
        return res
