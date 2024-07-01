import copy

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import date_utils


class WizardInvoiceBatch(models.TransientModel):
    _name = "invoice.batch"
    _description = "Create batch invoices for fixed concepts"
    _rec_name = "comment"

    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.user.company_id
    )

    subscription_product_line_ids = fields.One2many(
        "invoice.batch.line",
        "subscription_product_line_id",
        required=True,
    )
    partners_ids = fields.Many2many(
        "res.partner", required=True, domain=[("active", "=", True)]
    )

    sub_amount_untaxed = fields.Monetary(
        compute="_compute_subscription_product_amounts"
    )
    sub_amount_tax = fields.Monetary(compute="_compute_subscription_product_amounts")
    sub_amount_total = fields.Monetary(compute="_compute_subscription_product_amounts")
    comment = fields.Text()
    fee_period = fields.Date()

    def set_default_pricelist(self):
        product_pricelist_id = (
            self.env["product.pricelist"].search([("active", "=", True)], limit=1).id
        )
        return product_pricelist_id

    pricelist_id = fields.Many2one("product.pricelist", default=set_default_pricelist)

    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.user.company_id.currency_id,
    )

    def generate_invoice_batch(self):
        batchs_journal_id = self.company_id.batchs_journal_id
        if not batchs_journal_id:
            raise UserError(
                _(
                    "There's no journal configured for batch invoicing, "
                    "please contact the administrator."
                )
            )
        invoice_vals = {
            "journal_id": batchs_journal_id.id,
            "invoice_date": fields.Date.today(),
            "company_id": self.company_id.id,
            "narration": self.comment,
            "move_type": "out_invoice",
            "fee_period": self.fee_period,
        }
        lines_vals = [
            (
                0,
                0,
                {
                    "name": line.name,
                    "account_id": batchs_journal_id.default_account_id.id,
                    "price_unit": line.price_unit or 0.0,
                    "quantity": line.quantity,
                    "product_id": line.product_id.id,
                    "tax_ids": [(6, 0, line.tax_ids.ids)],
                },
            )
            for line in self.subscription_product_line_ids
        ]
        invoice_vals["invoice_line_ids"] = lines_vals

        invoice_vals_for_all_valid_partners = (
            self._get_invoice_vals_for_all_valid_partners(invoice_vals)
        )
        self.env["account.move"].create(invoice_vals_for_all_valid_partners)
        return

    def _get_invoice_vals_for_all_valid_partners(self, invoice_vals):
        AccountMove = self.env["account.move"]
        vals_list = []
        period_start = date_utils.start_of(self.fee_period, "month")
        period_end = date_utils.end_of(self.fee_period, "month")

        for partner in self.partners_ids:
            partner_invoices_for_period = AccountMove.search(
                [
                    ("partner_id", "=", partner.id),
                    ("move_type", "=", "out_invoice"),
                    ("fee_period", ">=", period_start),
                    ("fee_period", "<=", period_end),
                ]
            )
            if partner_invoices_for_period.filtered(
                lambda i: any(
                    line.product_id.fixed_concept for line in i.invoice_line_ids
                )
            ):
                continue
            fiscal_position_id = self.env[
                "account.fiscal.position"
            ]._get_fiscal_position(partner)
            new_vals = {
                "partner_id": partner.id,
                "fiscal_position_id": fiscal_position_id,
                "invoice_payment_term_id": partner.property_payment_term_id.id,
                **copy.deepcopy(invoice_vals),
            }
            vals_list.append(new_vals)

        return vals_list

    @api.depends("subscription_product_line_ids.price_total")
    def _compute_subscription_product_amounts(self):
        for rec in self:
            sub_amount_untaxed = sub_amount_tax = 0.0
            for line in rec.subscription_product_line_ids:
                sub_amount_untaxed += line.price_subtotal
                if rec.company_id.tax_calculation_rounding_method == "round_globally":
                    price = line.price_unit
                    taxes = line.tax_ids.compute_all(
                        price,
                        line.subscription_product_line_id.currency_id,
                        line.quantity,
                        product=line.product_id,
                        partner=line.subscription_product_line_id.partner_id,
                    )
                    sub_amount_tax += sum(
                        t.get("amount", 0.0) for t in taxes.get("taxes", [])
                    )
                else:
                    sub_amount_tax += line.price_tax
            rec.update(
                {
                    "sub_amount_untaxed": rec.company_id.currency_id.round(
                        sub_amount_untaxed
                    ),
                    "sub_amount_tax": rec.company_id.currency_id.round(sub_amount_tax),
                    "sub_amount_total": sub_amount_untaxed + sub_amount_tax,
                }
            )


class InvoiceBatchLine(models.TransientModel):
    _name = "invoice.batch.line"
    _description = "Batch invoices lines"

    @api.depends("product_id")
    def _compute_product_name(self):
        for rec in self:
            if rec.product_id.description:
                rec.name = rec.product_id.description
            else:
                rec.name = rec.product_id.name

    name = fields.Text(default=_compute_product_name, store=True)
    product_id = fields.Many2one(
        "product.product", required=True, domain=[("fixed_concept", "=", True)]
    )
    quantity = fields.Float(default=1.0, required=True)
    product_uom = fields.Many2one("uom.uom", related="product_id.uom_id", required=True)

    price_unit = fields.Float(default=0.0)
    tax_ids = fields.Many2many(
        "account.tax",
        domain=[("active", "=", True), ("type_tax_use", "=", "sale")],
    )

    subscription_product_line_id = fields.Many2one(
        "invoice.batch",
        string="Contract Product Lines",
    )
    price_subtotal = fields.Float(compute="_compute_amount", readonly=True, store=True)
    price_tax = fields.Float(compute="_compute_amount", readonly=True, store=True)
    price_total = fields.Float(
        compute="_compute_amount", string="Total", readonly=True, store=True
    )

    product_no_variant_attribute_value_ids = fields.Many2many(
        "product.template.attribute.value",
        string="Product attribute values that do not create variants",
    )
    currency_id = fields.Many2one("res.currency")

    @api.depends("quantity", "price_unit", "tax_ids")
    def _compute_amount(self):
        for line in self:
            price = line.price_unit
            taxes = line.tax_ids.compute_all(
                price,
                line.subscription_product_line_id.currency_id,
                line.quantity,
                product=line.product_id,
                partner=None,
            )
            line.update(
                {
                    "price_tax": taxes["total_included"] - taxes["total_excluded"],
                    "price_total": taxes["total_included"],
                    "price_subtotal": taxes["total_excluded"],
                }
            )

    def _get_display_price(self, product):
        # it is possible that a no_variant attribute is still in a variant if
        # the type of the attribute has been changed after creation.
        no_variant_attributes_price_extra = [
            ptav.price_extra
            for ptav in self.product_no_variant_attribute_value_ids.filtered(
                lambda ptav: ptav.price_extra
                and ptav not in product.product_template_attribute_value_ids
            )
        ]
        if no_variant_attributes_price_extra:
            product = product.with_context(
                no_variant_attributes_price_extra=no_variant_attributes_price_extra
            )

        if (
            self.subscription_product_line_id.pricelist_id.discount_policy
            == "with_discount"
        ):
            return product.with_context(
                pricelist=self.subscription_product_line_id.pricelist_id.id
            ).list_price
        product_context = dict(
            partner_id=self.subscription_product_line_id.partner_id.id,
            date=self.subscription_product_line_id.date_order,
            uom=self.product_uom.id,
        )

        (
            final_price,
            rule_id,
        ) = self.subscription_product_line_id.pricelist_id.with_context(
            **product_context
        ).get_product_price_rule(
            self.product_id,
            self.quantity or 1.0,
            self.subscription_product_line_id.partner_id,
        )
        base_price, currency = self.with_context(
            **product_context
        )._get_real_price_currency(
            product,
            rule_id,
            self.quantity,
            self.product_uom,
            self.subscription_product_line_id.pricelist_id.id,
        )
        if currency != self.subscription_product_line_id.pricelist_id.currency_id:
            base_price = currency._convert(
                base_price,
                self.subscription_product_line_id.pricelist_id.currency_id,
                self.subscription_product_line_id.company_id
                or self.env.user.company_id,
                fields.Date.today(),
            )
        return max(base_price, final_price)

    def _compute_tax_id(self):
        for line in self:
            taxes = line.product_id.taxes_id.filtered(
                lambda r: not line.subscription_product_line_id.company_id
                or r.company_id == line.subscription_product_line_id.company_id
            )
            line.tax_ids = taxes

    @api.onchange("product_id")
    def product_id_change_p(self):
        if not self.product_id or not self.subscription_product_line_id.pricelist_id:
            return {"domain": {"product_uom": []}}
        vals = {}
        domain = {
            "product_uom": [("category_id", "=", self.product_id.uom_id.category_id.id)]
        }
        if not self.product_uom or (self.product_id.uom_id.id != self.product_uom.id):
            vals["product_uom"] = self.product_id.uom_id
            vals["quantity"] = self.quantity or 1.0

        product = self.product_id.with_context(
            lang=None,
            partner=None,
            quantity=vals.get("quantity") or self.quantity,
            date=fields.date.today(),
            pricelist=self.subscription_product_line_id.pricelist_id.id,
            uom=self.product_uom.id,
        )

        result = {"domain": domain}

        name = self.product_id.name

        vals.update(name=name)

        self.tax_ids = product.taxes_id
        if self.subscription_product_line_id.pricelist_id:
            vals["price_unit"] = self.env[
                "account.tax"
            ]._fix_tax_included_price_company(
                self._get_display_price(product),
                product.taxes_id,
                self.tax_ids,
                self.subscription_product_line_id.company_id,
            )
        self.update(vals)

        return result
