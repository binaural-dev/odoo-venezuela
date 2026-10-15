from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    tax_calculation_rounding_method = fields.Selection(default="round_per_line")

    tax_totals_edit_tolerance = fields.Float(
        string="Tax Amount Edit Tolerance",
        default=0.03,
        help="Maximum amount (in the document's currency) that the "
        "tax_totals pencil-edit may move a tax group's amount away from "
        "its computed value, in either direction. Only enforced for users "
        "in the 'Fiscal Config Support' group -- everyone else can't edit "
        "the field at all.",
    )

    @api.constrains('tax_totals_edit_tolerance')
    def _check_tax_totals_edit_tolerance(self):
        for company in self:
            if not 0.0 <= company.tax_totals_edit_tolerance <= 1.0:
                raise ValidationError(_("The tax amount edit tolerance must be between 0 and 1."))

    taxpayer_type = fields.Selection(
        [
            ("formal", "Formal"),
            ("special", "Special"),
            ("ordinary", "Ordinary"),
        ],
        default="special",
        tracking=True,
    )

    vat = fields.Char(
        string="RIF",
        tracking=True,
    )

    street = fields.Char(tracking=True)

    country_id = fields.Many2one(
        tracking=True,
        default=lambda self: self.env["res.country"].search([("code", "=", "VE")], limit=1),
    )

    unique_tax = fields.Boolean()
    show_discount_on_moves = fields.Boolean()

    exent_aliquot_sale = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "sale")])
    general_aliquot_sale = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "sale")])
    reduced_aliquot_sale = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "sale")])
    extend_aliquot_sale = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "sale")])
    not_show_reduced_aliquot_sale = fields.Boolean()
    not_show_extend_aliquot_sale = fields.Boolean()

    exent_aliquot_purchase = fields.Many2one(
        "account.tax", domain=[("type_tax_use", "=", "purchase")]
    )
    general_aliquot_purchase = fields.Many2one(
        "account.tax", domain=[("type_tax_use", "=", "purchase")]
    )
    reduced_aliquot_purchase = fields.Many2one(
        "account.tax", domain=[("type_tax_use", "=", "purchase")]
    )
    extend_aliquot_purchase = fields.Many2one(
        "account.tax", domain=[("type_tax_use", "=", "purchase")]
    )
    not_show_reduced_aliquot_purchase = fields.Boolean()
    not_show_extend_aliquot_purchase = fields.Boolean()

    config_deductible_tax = fields.Boolean()

    no_deductible_general_aliquot_purchase = fields.Many2one(
        "account.tax", domain=[("type_tax_use", "=", "purchase")]
    )
    no_deductible_reduced_aliquot_purchase = fields.Many2one(
        "account.tax", domain=[("type_tax_use", "=", "purchase")]
    )
    no_deductible_extend_aliquot_purchase = fields.Many2one(
        "account.tax", domain=[("type_tax_use", "=", "purchase")]
    )

    exent_aliquot_purchase_international = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "purchase")])
    general_aliquot_purchase_international = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "purchase")])
    reduced_aliquot_purchase_international = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "purchase")])
    extend_aliquot_purchase_international = fields.Many2one("account.tax", domain=[("type_tax_use", "=", "purchase")])

    not_show_general_aliquot_purchase_international = fields.Boolean()

    not_show_reduced_aliquot_purchase_international = fields.Boolean()

    not_show_extend_aliquot_purchase_international = fields.Boolean()

    not_show_total_purchases_with_international_iva = fields.Boolean()

    not_show_exempt_total_purchases = fields.Boolean()

    not_show_total_purchases_international = fields.Boolean()

    index_payment_in_wizard = fields.Boolean('index_payment_in_wizard',default=True,help='Apply Indexacion to payment from wizard of invoice')

    indexaxion_payment_mode = fields.Selection([
        ('indexed', 'Indexed (Payment Date Rate)'),
        ('not_indexed', 'Non-Indexed (Invoice Date Rate)'),
        ('to_agreed', 'To be Agreed (Mutual Agreement)'),
    ], string='Type indexacion', default='indexed', help='Defines the exchange rate criteria applied at the time of payment wizard.')

    indexed_default = fields.Boolean('Default indexacion',default=True)

    # ── Alternate-currency exchange difference ──
    # See `account.move.line._inject_foreign_exchange_amounts` /
    # `_create_standalone_foreign_exchange_difference_entry`. Deliberately
    # NO dedicated accounts here: the alternate amount is added to the
    # SAME lines/accounts Odoo's native exchange difference already uses
    # (`income_currency_exchange_account_id`/`expense_currency_exchange_account_id`,
    # `currency_exchange_journal_id`) -- one asiento, both currencies.
    l10n_ve_use_foreign_exchange_diff = fields.Boolean(
        string='Use Alternate Currency Exchange Difference',
        default=True,
        help="Adds the alternate currency amount to Odoo's own exchange "
             "difference entry, or creates one just for it if company "
             "currency matched exactly.",
    )

    def _l10n_ve_foreign_exchange_diff_missing_config(self):
        """Names of the exchange difference settings this company lacks."""
        self.ensure_one()
        missing = []
        if not self.currency_exchange_journal_id:
            missing.append(_("Exchange Gain or Loss Journal"))
        if not self.income_currency_exchange_account_id:
            missing.append(_("Gain Exchange Rate Account"))
        if not self.expense_currency_exchange_account_id:
            missing.append(_("Loss Exchange Rate Account"))
        return missing

    @api.model_create_multi
    def create(self, vals_list):
        # Enabled by default: a company just created cannot have the
        # exchange journal/accounts yet (the chart of accounts creates them
        # later), so the default alone is not validated. An explicit
        # activation (flag in vals) is.
        if any('l10n_ve_use_foreign_exchange_diff' not in vals for vals in vals_list):
            companies = super(ResCompany, self.with_context(l10n_ve_skip_exchange_diff_check=True)).create(vals_list)
            # Back to the caller's context: the skip only covers the creation.
            return companies.with_env(self.env)
        return super().create(vals_list)

    @api.constrains(
        'l10n_ve_use_foreign_exchange_diff', 'currency_exchange_journal_id',
        'income_currency_exchange_account_id', 'expense_currency_exchange_account_id',
    )
    def _check_l10n_ve_use_foreign_exchange_diff_requires_config(self):
        # Loading a chart of accounts writes the exchange journal and the
        # gain/loss accounts in separate steps: the config is incomplete
        # until it finishes, so it can't be validated in the middle of it
        # (`account.chart.template._load` revalidates it at the end).
        if self.env.context.get('chart_template_load') or self.env.context.get('l10n_ve_skip_exchange_diff_check'):
            return
        for company in self:
            if not company.l10n_ve_use_foreign_exchange_diff:
                continue
            missing = company._l10n_ve_foreign_exchange_diff_missing_config()
            if missing:
                raise ValidationError(_(
                    "With 'Use Alternate Currency Exchange Difference' "
                    "enabled, configure the following (Accounting Settings "
                    "> Default Accounts): %(missing)s.",
                    missing=", ".join(missing),
                ))


