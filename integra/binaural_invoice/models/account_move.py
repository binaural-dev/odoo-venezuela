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

    foreign_tax_totals = fields.Binary(
        help="Foreign Tax Totals of the invoice",
        compute="_compute_foreign_tax_totals",
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

    @api.depends("invoice_date",
        "invoice_line_ids.currency_rate",
        "invoice_line_ids.tax_base_amount",
        "invoice_line_ids.tax_line_id",
        "invoice_line_ids.price_total")
    def _compute_tax(self):
        """
        Compute the tax of the line.

        if current_currency is equal to 2 "USD" compute the company rate

        else thats compute the inverse rate of the company wich is 3 "VEF"

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

    def action_register_payment(self):

        res = super().action_register_payment()
        res["context"]["default_foreign_currency_rate"] = self.tax
        return res

    
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
    def _compute_foreign_tax_totals(self):
        """ Computed field used for custom widget's rendering.
            Only set on invoices.
        """
        for move in self:
            if move.is_invoice(include_receipts=True):
                base_lines = move.invoice_line_ids.filtered(lambda line: line.display_type == 'product')
                base_line_values_list = [line._convert_to_tax_base_line_dict() for line in base_lines]

                if move.id:
                    # The invoice is stored so we can add the early payment discount lines directly to reduce the
                    # tax amount without touching the untaxed amount.
                    sign = -1 if move.is_inbound(include_receipts=True) else 1
                    base_line_values_list += [
                        {
                            **line._convert_to_tax_base_line_dict(),
                            'handle_price_include': False,
                            'quantity': 1.0,
                            'price_unit': sign * line.amount_currency,
                        }
                        for line in move.line_ids.filtered(lambda line: line.display_type == 'epd')
                    ]

                kwargs = {
                    'base_lines': base_line_values_list,
                    'currency': move.currency_id,
                }

                if move.id:
                    kwargs['tax_lines'] = [
                        line._convert_to_tax_line_dict()
                        for line in move.line_ids.filtered(lambda line: line.display_type == 'tax')
                    ]
                else:
                    # In case the invoice isn't yet stored, the early payment discount lines are not there. Then,
                    # we need to simulate them.
                    epd_aggregated_values = {}
                    for base_line in base_lines:
                        if not base_line.epd_needed:
                            continue
                        for grouping_dict, values in base_line.epd_needed.items():
                            epd_values = epd_aggregated_values.setdefault(grouping_dict, {'price_subtotal': 0.0})
                            epd_values['price_subtotal'] += values['price_subtotal']

                    for grouping_dict, values in epd_aggregated_values.items():
                        taxes = None
                        if grouping_dict.get('tax_ids'):
                            taxes = self.env['account.tax'].browse(grouping_dict['tax_ids'][0][2])

                        kwargs['base_lines'].append(self.env['account.tax']._convert_to_tax_base_line_dict(
                            None,
                            partner=move.partner_id,
                            currency=move.currency_id,
                            taxes=taxes,
                            price_unit=values['price_subtotal'],
                            quantity=1.0,
                            account=self.env['account.account'].browse(grouping_dict['account_id']),
                            analytic_distribution=values.get('analytic_distribution'),
                            price_subtotal=values['price_subtotal'],
                            is_refund=move.move_type in ('out_refund', 'in_refund'),
                            handle_price_include=False,
                        ))
                move.tax_totals = self.env['account.tax']._prepare_foreign_tax_totals(**kwargs)
                _logger.warning('CONCHALE %s', move.tax_totals)
            else:
                # Non-invoice moves don't support that field (because of multicurrency: all lines of the invoice share the same currency)
                move.tax_totals = None