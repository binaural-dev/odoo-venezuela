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

    tax = fields.Float(help="Tax of the line", compute="_compute_tax", digits="Tasa")

    foreign_taxable_income = fields.Monetary(
        help="Foreign Taxable Income of the line",
        # compute="_compute_foreign_taxable_income",
        digits="Tasa",
        currency_field="foreign_currency_id",
    )
    total_taxed = fields.Many2one(
        "account.tax",
        help="Total Taxed of the line",
    )

    foreign_tax = fields.Float(
        help="Foreign Tax of the line", 
        # compute="_compute_foreign_tax",
        digits="Tasa"
    )

    foreign_discount = fields.Monetary(
        help="Foreign Discount of the line",
        # compute="_compute_foreign_discount",
        digits="Tasa",
        currency_field="foreign_currency_id",
    )

    foreign_total_due = fields.Monetary(
        help="Foreign Total Due of the line",
        # compute="_compute_foreign_total_due",
        digits="Tasa",
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
                view_id = self.env.ref("binaural_account.view_account_move_form_binaural").id
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

    # @api.depends("foreign_currency_id")
    def _compute_tax(self):
        """
        Compute the tax of the line

        """
        current_currency = self.env.company.currency_id.id
        foreign_currency = self.env['res.currency'].search([('active', '=', True)])
        for currency in foreign_currency:
            if currency.id != current_currency:
                for tax in currency.rate_ids:
                    self.tax = tax[1].company_rate
        
        