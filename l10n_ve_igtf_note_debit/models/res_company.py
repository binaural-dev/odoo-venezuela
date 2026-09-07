from odoo import fields, models, api, _
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = "res.company"


    igtf_note_debit_mode = fields.Selection(
        [
            ("inline", "Line in the same journal entry (current flow)"),
            ("debit_note", "Automatic Fiscal Debit Note (new flow)"),
        ],
        string="IGTF Perception Mode",
        default="inline",
        required=True,
        copy=False,
        help="Determines how the IGTF perception is recorded:\n"
             "- Line in the same journal entry: l10n_ve_igtf's historical behavior.\n"
             "- Automatic Fiscal Debit Note: generates an independent fiscal "
             "document (Debit Note) linked to the source invoice, in "
             "accordance with SENIAT Providencias 0071/0102.",
    )


    igtf_note_debit_product_id = fields.Many2one(
        "product.product",
        string="IGTF Perception Product",
        copy=False,
        help="Product used as the single line of the IGTF Debit Note. It "
             "must have the Exempt/Not Subject sale and purchase tax "
             "assigned ('exent_aliquot_sale' / 'exent_aliquot_purchase' "
             "fields from l10n_ve_accountant) -- IGTF is not a VAT base, but "
             "l10n_ve_accountant requires every product to have exactly one "
             "sale tax and one purchase tax assigned.",
    )

    igtf_note_debit_include_in_payment_default = fields.Boolean(
        string="Include IGTF in Payment by Default",
        default=True,
        copy=False,
        help="Default value of the 'Include IGTF in Payment' checkbox in "
             "the payment register wizard, when 'IGTF Perception Mode' is "
             "'Automatic Fiscal Debit Note'. The user can check or uncheck "
             "it on each individual payment; this only defines the "
             "starting value.",
    )

    igtf_note_debit_vef_journal_id = fields.Many2one(
        "account.journal",
        string="VEF Journal for IGTF Collection",
        copy=False,
        help="Journal in Bolivares (VEF) used to register the separate "
             "IGTF payment when the 'Include IGTF in Payment' checkbox is "
             "UNCHECKED in the payment register wizard (the source payment "
             "only covers the invoice, and the IGTF Debit Note is collected "
             "with a second, independent payment). If not configured, the "
             "first bank/cash journal in VEF not marked as IGTF is "
             "searched automatically.",
    )

    igtf_note_debit_valid_journal_ids = fields.Json(
        string="Valid VEF Journal IDs for IGTF",
        compute="_compute_igtf_note_debit_valid_journal_ids",
        help="List (JSON) of the account.journal IDs that meet the "
             "requirements to be the VEF journal for IGTF collection: "
             "bank/cash type, not marked as an IGTF journal, and in "
             "Bolivares (VEF) currency -- either explicit or implicit "
             "(no own currency, when the company currency is VEF).",
    )

    @api.depends("currency_id")
    def _compute_igtf_note_debit_valid_journal_ids(self):
        Journal = self.env["account.journal"]
        vef = self.env.ref("base.VEF")
        for company in self:
            domain = [
                ("company_id", "=", company.id),
                ("type", "in", ("bank", "cash")),
                ("is_igtf", "!=", True),
            ]
            if company.currency_id == vef:
                domain += ["|", ("currency_id", "=", vef.id), ("currency_id", "=", False)]
            else:
                domain += [("currency_id", "=", vef.id)]
            journals = Journal.search(domain)
            company.igtf_note_debit_valid_journal_ids = journals.ids

    igtf_note_debit_valid_product_ids = fields.Json(
        string="Valid Product IDs for IGTF",
        compute="_compute_igtf_note_debit_valid_product_ids",
        help="List (JSON) of the product.product IDs that meet the "
             "requirements to be the IGTF Perception Product: Service "
             "type, income/expense account equal to the customer/supplier "
             "IGTF account configured in Settings > Accounting > IGTF, "
             "and sale/purchase tax equal to the Exempt tax configured in "
             "Settings > Accounting > Fiscal Regime (exent_aliquot_sale / "
             "exent_aliquot_purchase).",
    )

    @api.depends(
        "customer_account_igtf_id",
        "supplier_account_igtf_id",
        "exent_aliquot_sale",
        "exent_aliquot_purchase",
    )
    def _compute_igtf_note_debit_valid_product_ids(self):
        Product = self.env["product.product"]
        for company in self:
            if not (
                company.customer_account_igtf_id
                and company.supplier_account_igtf_id
                and company.exent_aliquot_sale
                and company.exent_aliquot_purchase
            ):
                company.igtf_note_debit_valid_product_ids = []
                continue
            domain = [
                ("type", "=", "service"),
                ("property_account_income_id", "=", company.customer_account_igtf_id.id),
                ("property_account_expense_id", "=", company.supplier_account_igtf_id.id),
                ("taxes_id", "in", company.exent_aliquot_sale.id),
                ("supplier_taxes_id", "in", company.exent_aliquot_purchase.id),
                ("company_id", "in", (company.id, False)),
            ]
            products = Product.search(domain)
            company.igtf_note_debit_valid_product_ids = products.ids

    @api.constrains("igtf_note_debit_mode", "igtf_note_debit_product_id")
    def _check_igtf_note_debit_config(self):
        for company in self:
            if self.env.context.get("install_mode") or self.env.context.get("skip_check"):
                continue
            if company.igtf_note_debit_mode == "debit_note" and not company.igtf_note_debit_product_id:
                raise UserError(_(
                    "To use the 'Automatic Fiscal Debit Note' mode you must "
                    "configure the IGTF Perception product in Settings > "
                    "Accounting > IGTF."
                ))
