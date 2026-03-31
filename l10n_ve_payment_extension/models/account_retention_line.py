from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)


class AccountRetentionLine(models.Model):
    _name = "account.retention.line"
    _description = "Retention Line"
    _rec_name = 'name'

    check_company = True

    name = fields.Char(
        string="Description", compute="_compute_name", store=True, readonly=False
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    state = fields.Selection(related="retention_id.state")
    company_currency_id = fields.Many2one(related="retention_id.company_currency_id")
    foreign_currency_id = fields.Many2one(related="retention_id.foreign_currency_id")
    retention_id = fields.Many2one("account.retention", string="Retention", ondelete="cascade")
    invoice_type = fields.Selection(
        selection=[
            ("out_invoice", "Out invoice"),
            ("in_invoice", "In invoice"),
            ("out_refund", "Out refund"),
            ("in_refund", "In refund"),
            ("out_debit", "Out debit"),
            ("in_debit", "In debit"),
        ],
    )
    date_accounting = fields.Date(related="retention_id.date_accounting", store=True)
    aliquot = fields.Float(digits=(16, 2))
    amount_tax_ret = fields.Float(string="Retained tax", digits=(16, 2))
    base_ret = fields.Float("Retained base", digits=(16, 2))
    imp_ret = fields.Float(string="tax incurred", digits=(16, 2))
    retention_rate = fields.Float(store=True, digits="Tasa")
    move_id = fields.Many2one("account.move", "move", ondelete="cascade", store=True)
    is_retention_client = fields.Boolean(default=True)
    display_invoice_number = fields.Char(
        string="Invoice Number", compute="_compute_display_invoice_number", store=True
    )
    invoice_amount = fields.Float(
        string="Taxable income",
        digits="Tasa",
        compute="_compute_amounts",
        store=True,
        readonly=False,
    )
    invoice_total = fields.Float(string="Total invoiced", digits="Tasa", store=True)
    iva_amount = fields.Float(string="IVA", digits=(16, 2))

    retention_amount = fields.Float(
        digits="Tasa", compute="_compute_retention_amount", store=True, readonly=False
    )
    foreign_retention_amount = fields.Float(
        digits="Tasa", compute="_compute_retention_amount", store=True, readonly=False
    )

    payment_concept_id = fields.Many2one(
        "payment.concept", "Payment concept", ondelete="cascade", index=True
    )
    code = fields.Char(
        related="payment_concept_id.line_payment_concept_ids.code"
    )
    code_visible=fields.Boolean(
        related='company_id.code_visible')
    economic_activity_id = fields.Many2one(
        "economic.activity",
        ondelete="cascade",
        compute="_compute_economic_activity_id",
        readonly=False,
        store=True,
        index=True,
    )

    payment_id = fields.Many2one("account.payment", "Payment", index=True)

    payment_date = fields.Date(related="payment_id.date", store=True)

    payment_journal_id = fields.Many2one(
        "account.journal",
        "Payment journal",
        ondelete="cascade",
        index=True,
        related="payment_id.journal_id",
    )

    related_pay_from = fields.Float(
        string="Pays from",
        compute="_compute_related_fields",
        store=True,
    )

    related_percentage_tax_base = fields.Float(
        string="% tax base",
        compute="_compute_related_fields",
        store=True,
        readonly=False,
    )

    related_percentage_fees = fields.Float(
        string="% tariffs",
        compute="_compute_related_fields",
        store=True,
    )

    related_amount_subtract_fees = fields.Float(
        string="Amount subtract tariffs",
        compute="_compute_related_fields",
        store=True,
    )

    # foreign currency
    foreign_invoice_amount = fields.Float(
        string="Foreign taxable income", compute="_compute_amounts", store=True, readonly=False
    )
    foreign_invoice_total = fields.Float(string="Foreign total invoiced")
    foreign_iva_amount = fields.Float(string="Foreign IVA")
    foreign_retention_amount = fields.Float()
    foreign_currency_rate = fields.Float(string="Rate")

    @api.onchange("move_id")
    def _onchange_move_id(self):
        """
        Calcula y actualiza los campos de la línea de retención cuando cambia la factura.
        """
        for record in self:
            if not record.move_id:
                return {}

            if record.retention_id and record.retention_id.type_retention != 'iva' or not record.retention_id:
                return

            invoice_id = record.move_id

            # Use the retention's partner for third-party billing, otherwise the invoice's partner
            withholding_partner = (
                record.retention_id.partner_id
                if record.retention_id and record.retention_id.partner_id
                else invoice_id.partner_id
            )
            withholding_amount = (
                withholding_partner.withholding_type_id.value
                if withholding_partner and withholding_partner.withholding_type_id
                else 0
            )

            # Aquí va la lógica de tu método original
            tax_ids = invoice_id.invoice_line_ids.filtered(
                lambda l: l.tax_ids and l.tax_ids[0].amount > 0
            ).mapped("tax_ids")

            if not any(tax_ids):

                return {
                    "warning": {
                        "title": _("Atención"),
                        "message": _("The invoice has no tax."),
                    }
                }

            tax_groups = invoice_id.tax_totals["subtotals"][0]["tax_groups"]

            for tax_group in tax_groups:
                taxes = tax_ids.filtered(lambda l: l.tax_group_id.id == tax_group["id"])
                if not taxes:
                    continue

                tax = taxes[0]
                retention_amount = tax_group["tax_amount"] * (withholding_amount / 100)
                record.name = _("Iva Retention")
                record.invoice_type = invoice_id.move_type
                record.move_id = invoice_id.id
                record.aliquot = tax.amount
                record.iva_amount = tax_group["tax_amount"]
                record.invoice_total = invoice_id.tax_totals["total_amount"]
                record.related_percentage_tax_base = withholding_amount
                record.invoice_amount = tax_group["base_amount"]
                record.foreign_currency_rate = invoice_id.foreign_rate
                record.foreign_invoice_amount = tax_group["base_amount_foreign_currency"]
                record.foreign_iva_amount = tax_group["tax_amount_foreign_currency"]
                record.foreign_invoice_total = invoice_id.tax_totals["total_amount_foreign_currency"]

                if invoice_id.move_type == "out_invoice":
                    record.retention_amount = 0.0
                    record.foreign_retention_amount = 0.0
                else:
                    record.retention_amount = retention_amount
                    record.foreign_retention_amount = record.foreign_iva_amount * (withholding_amount / 100)

                break

    @api.depends("retention_id.type_retention", "move_id")
    def _compute_name(self):
        for record in self:
            if record.name:
                continue
            names = {
                "islr": _("ISLR Retention"),
                "iva": _("IVA Retention"),
                "municipal": _("Municipal Retention"),
            }
            type_retention = record.retention_id.type_retention or self.env.context.get("type")
            record.name = names.get(type_retention, _("Retention"))

    @api.depends("retention_id", "move_id")
    def _compute_economic_activity_id(self):
        for line in self:
            if line.economic_activity_id:
                continue
            if line.retention_id and line.retention_id.type_retention == "municipal":
                line.economic_activity_id = line.retention_id.partner_id.economic_activity_id
            if line.move_id and line.id in line.move_id.retention_municipal_line_ids.ids:
                line.economic_activity_id = line.move_id.partner_id.economic_activity_id

    def unlink(self):
        for record in self:
            if record.payment_id:
                record.payment_id.unlink()
        return super().unlink()

    def _get_islr_type_person_id(self):
        """Return the type person used to match ISLR concept lines.

        For customer retentions (out_invoice), use the company partner type person.
        For other flows, keep the existing partner-based behavior.
        """
        self.ensure_one()

        if (
            self.retention_id
            and self.retention_id.type_retention == "islr"
            and self.retention_id.type == "out_invoice"
        ):
            return self.company_id.partner_id.type_person_id

        if self.retention_id and self.retention_id.partner_id:
            return self.retention_id.partner_id.type_person_id

        if self.move_id and self.move_id.partner_id:
            return self.move_id.partner_id.type_person_id

        return self.env["type.person"]

    @api.depends("payment_concept_id", "move_id")
    def _compute_related_fields(self):
        """
        This compute is used to get the related fields from the payment concept of the partner
        to generate the ISLR retention line
        """
        lines_from_islr_retention = self.filtered(
            lambda l: l.payment_concept_id
            and (not l.retention_id or l.retention_id.type_retention == "islr")
        )
        for record in lines_from_islr_retention:
            # Use the retention's partner for third-party billing, otherwise the invoice's partner
            calc_partner = (
                record.retention_id.partner_id
                if record.retention_id and record.retention_id.partner_id
                else record.move_id.partner_id
            )
            type_person = record._get_islr_type_person_id()
            # Payment concept of the line
            payment_concept = record.payment_concept_id.line_payment_concept_ids
            for line in payment_concept:
                if type_person.id == line.type_person_id.id:
                    move = record.move_id._origin or record.move_id
                    islr_retention_lines = len(move.retention_islr_line_ids)
                    if not line.tariff_id.accumulated_rate:
                        # compare the type_person_id of the partner with the type_person_id of the
                        # payment concept and set the related fields.
                        record.invoice_total = move.tax_totals["total_amount"]
                        record.foreign_invoice_total = move.tax_totals["total_amount_foreign_currency"]
                        record.related_pay_from = line.pay_from
                        record.related_percentage_tax_base = line.percentage_tax_base
                        record.related_percentage_fees = line.tariff_id.percentage
                        record.related_amount_subtract_fees = line.tariff_id.amount_subtract
                        record.foreign_currency_rate = move.foreign_rate

                        if not record.retention_id or record.retention_id.type == "in_invoice":
                            # We don't want this fields to be computed when the retention is
                            # created from a customer invoice since they are filled by the user.
                            if islr_retention_lines <= 1:
                                record.invoice_amount = move.tax_totals["base_amount"]
                                record.foreign_invoice_amount = move.tax_totals[
                                "base_amount_foreign_currency"
                                ]
                            else:
                                record.invoice_amount = record.invoice_amount or 0
                                record.foreign_invoice_amount = record.foreign_invoice_amount or 0
                    else:
                        invoice_date = record.move_id.invoice_date_display or fields.Date.today()

                        fiscalyear_last_day = int(record.company_id.fiscalyear_last_day)
                        fiscalyear_last_month = int(record.company_id.fiscalyear_last_month)

                        # Fiscal year start calculation (handles 12/31 fiscal close correctly)
                        if fiscalyear_last_month == 12 and fiscalyear_last_day == 31:
                            fiscalyear_start = fields.Date.from_string('%s-01-01' % invoice_date.year)
                        else:
                            if invoice_date.month > fiscalyear_last_month or (invoice_date.month == fiscalyear_last_month and invoice_date.day > fiscalyear_last_day):
                                fiscalyear_start = fields.Date.from_string('%s-%02d-%02d' % (invoice_date.year, fiscalyear_last_month + 1 if fiscalyear_last_month < 12 else 1, 1))
                            else:
                                fiscalyear_start = fields.Date.from_string('%s-%02d-%02d' % (invoice_date.year - 1, fiscalyear_last_month + 1 if fiscalyear_last_month < 12 else 1, 1))
                        
                        current_ut = line.tariff_id.tax_unit_ids

                        if not current_ut:
                            raise UserError(_("The tariff does not have a valid tax unit."))
                        
                        previous_invoices = self.env['account.move'].search([
                            ('partner_id', '=', calc_partner.id),
                            ('move_type', '=', 'in_invoice'),
                            ('state', '=', 'posted'),
                            ('invoice_date_display', '>=', fiscalyear_start),
                            ('invoice_date_display', '<', invoice_date),
                            ('company_id', '=', record.company_id.id),
                        ])
                        previous_invoices = previous_invoices.filtered(
                            lambda inv: bool(inv.retention_islr_line_ids)
                        )

                        sum_total_taxable_foreign = 0.0
                        total_taxable_base = 0.0
                        if record.company_id.currency_id == self.env.ref("base.USD"):
                            for invoice in previous_invoices:
                                tax_totals = invoice.tax_totals
                                groups_by_subtotal = tax_totals.get("groups_by_foreign_subtotal", {})
                                for subtotal in tax_totals.get("subtotals", []):
                                    for group in groups_by_subtotal.get(subtotal.get("name"), []):
                                        amount = float(group.get("tax_group_base_amount", 0.0))
                                        sum_total_taxable_foreign += amount
                            
                            current_tax_totals = record.move_id.tax_totals
                            groups_by_subtotal = current_tax_totals.get("groups_by_foreign_subtotal", {})
                            for subtotal in current_tax_totals.get("subtotals", []):
                                for group in groups_by_subtotal.get(subtotal.get("name"), []):
                                    sum_total_taxable_foreign += float(group.get("tax_group_base_amount", 0.0))

                            total_taxable_base = sum_total_taxable_foreign / current_ut.value
                        else:
                            total_taxable_base = (sum(previous_invoices.mapped('amount_untaxed'), record.move_id.amount_untaxed) or 0.0) / current_ut.value

                        total_taxable_base = total_taxable_base * (line.percentage_tax_base / 100.0)

                        rates = sorted(line.tariff_id.accumulated_rate_ids, key=lambda r: r.start)

                        selected_rate = None
                        for rate in rates:
                            is_infinity_tier = (rate.stop == 0)
                            if not is_infinity_tier:
                                if rate.start <= total_taxable_base <= rate.stop:
                                    selected_rate = rate
                                    break 
                            else:
                                if total_taxable_base >= rate.start:
                                    selected_rate = rate
                                    break

                        if selected_rate:
                            record.invoice_total = record.move_id.tax_totals["total_amount"]
                            record.foreign_invoice_total = record.move_id.tax_totals["total_amount_foreign_currency"]
                            record.related_pay_from = line.pay_from
                            record.related_percentage_tax_base = line.percentage_tax_base
                            record.related_percentage_fees = selected_rate.percentage  
                            record.related_amount_subtract_fees = selected_rate.subtract_ut * current_ut.value
                            record.foreign_currency_rate = record.move_id.foreign_rate
                        else:
                            record.related_pay_from = 0.0
                            record.related_percentage_tax_base = 0.0
                            record.related_percentage_fees = 0.0
                            record.related_amount_subtract_fees = 0.0
                            record.foreign_currency_rate = 0.0

                        if not record.retention_id or record.retention_id.type == "in_invoice":
                            # We don't want this fields to be computed when the retention is
                            # created from a customer invoice since they are filled by the user.
                            if islr_retention_lines <= 1:
                                record.invoice_amount = record.move_id.tax_totals["base_amount"]
                                record.foreign_invoice_amount = record.move_id.tax_totals["base_amount_foreign_currency"]
                            else:
                                record.invoice_amount = record.invoice_amount or 0
                                record.foreign_invoice_amount = record.foreign_invoice_amount or 0

    @api.depends("invoice_amount", "foreign_invoice_amount")
    def _compute_amounts(self):
        base_currency_is_vef = self.env.company.currency_id == self.env.ref("base.VEF")
        if not base_currency_is_vef:
            for line in self:
                if line.invoice_amount > 0 and line.foreign_invoice_amount > 0:
                    line.invoice_amount = line.foreign_invoice_amount * (
                        1 / line.foreign_currency_rate
                    )

    @api.onchange(
        "invoice_amount",
        "foreign_invoice_amount", 
        "related_percentage_tax_base",
        "related_percentage_fees",
        "related_amount_subtract_fees",
        "foreign_currency_rate",
    )
    @api.depends(
        "invoice_amount",
        "foreign_invoice_amount",
        "related_percentage_tax_base",
        "related_percentage_fees",
        "related_amount_subtract_fees",
        "foreign_currency_rate",
        "move_id",
    )
    def _compute_retention_amount(self):
        """
        This compute is used to get the retention amount from the payment concept of the partner
        to generate the ISLR retention line.
        """
        base_currency_is_vef = self.env.company.currency_id == self.env.ref("base.VEF")

        islr_supplier_retention_lines = self.filtered(
            lambda l: (not l.retention_id and l.payment_concept_id)
            or (l.retention_id.type_retention == "islr" and l.retention_id.type == "in_invoice")
        )
        for record in islr_supplier_retention_lines:
            foreign_rate = record.move_id.foreign_rate
            if not foreign_rate:
                foreign_rate = 1
            ut_value = 0.0
            is_accumulated = False
            # Use the retention's partner for third-party billing, otherwise the invoice's partner
            calc_partner = (
                record.retention_id.partner_id
                if record.retention_id and record.retention_id.partner_id
                else record.move_id.partner_id
            )
            if record.payment_concept_id and record.move_id and calc_partner:
                type_person = record._get_islr_type_person_id()
                concept_line = record.payment_concept_id.line_payment_concept_ids.filtered(
                    lambda l: l.type_person_id.id == type_person.id
                )
                if concept_line:
                    is_accumulated = concept_line[0].tariff_id.accumulated_rate
                    if is_accumulated and concept_line[0].tariff_id.tax_unit_ids:
                        ut_value = concept_line[0].tariff_id.tax_unit_ids.value

            if is_accumulated and ut_value:
                if not base_currency_is_vef:
                    base_vef = record.foreign_invoice_amount
                    base_ut = round(base_vef / ut_value, 2)
                    aplicable_ut = round(base_ut * (record.related_percentage_tax_base / 100.0), 2)
                    retention_ut = round(aplicable_ut * (record.related_percentage_fees / 100.0), 2)
                    subtract_ut = round(record.related_amount_subtract_fees / ut_value, 2) if ut_value else 0.0
                    final_retention_vef = (retention_ut - subtract_ut) * ut_value

                    record.foreign_retention_amount = abs(final_retention_vef)
                    record.retention_amount = final_retention_vef / foreign_rate
                else:
                    base_vef = record.invoice_amount
                    base_ut = round(base_vef / ut_value, 2)
                    aplicable_ut = round(base_ut * (record.related_percentage_tax_base / 100.0), 2)
                    retention_ut = round(aplicable_ut * (record.related_percentage_fees / 100.0), 2)
                    subtract_ut = round(record.related_amount_subtract_fees / ut_value, 2) if ut_value else 0.0
                    final_retention_vef = (retention_ut - subtract_ut) * ut_value

                    record.retention_amount = final_retention_vef
                    record.foreign_retention_amount = abs(final_retention_vef / foreign_rate) if foreign_rate else abs(final_retention_vef)
            else:
                if not base_currency_is_vef:
                    record.retention_amount = (
                        record.invoice_amount
                        * (record.related_percentage_tax_base / 100)
                        * (record.related_percentage_fees / 100)
                    ) - record.related_amount_subtract_fees / foreign_rate
                else:
                    record.retention_amount = (
                        record.invoice_amount
                        * (record.related_percentage_tax_base / 100)
                        * (record.related_percentage_fees / 100)
                    ) - record.related_amount_subtract_fees

                record.foreign_retention_amount = abs((
                    record.foreign_invoice_amount
                    * (record.related_percentage_tax_base / 100)
                    * (record.related_percentage_fees / 100)
                ) - record.related_amount_subtract_fees)

    @api.onchange("economic_activity_id", "move_id")
    def onchange_economic_activity_id(self):
        """
        Computes the aliquot of the line when the economic activity is changed for the retentions
        of municipal type.
        """
        municipal_retention_lines_with_economic_activity_and_invoice = self.filtered(
            lambda l: (not l.retention_id or (l.retention_id.type_retention == "municipal"))
            and l.economic_activity_id
            and l.move_id
        )

        for record in municipal_retention_lines_with_economic_activity_and_invoice:
            if not record.retention_id or record.retention_id.type == "in_invoice":
                # We don't want this fields to be computed when the retention is
                # created from a customer invoice since they are filled by the user.
                record.invoice_amount = record.move_id.tax_totals["base_amount"]
                record.foreign_invoice_amount = record.move_id.tax_totals["base_amount_foreign_currency"]

            record.invoice_total = record.move_id.tax_totals["total_amount"]
            record.foreign_invoice_total = record.move_id.tax_totals["total_amount_foreign_currency"]
            record.foreign_currency_rate = record.move_id.foreign_rate

            record.aliquot = record.economic_activity_id.aliquot
            record.retention_amount = record.invoice_amount * record.aliquot / 100
            record.foreign_retention_amount = record.foreign_invoice_amount * record.aliquot / 100

    @api.onchange("invoice_amount", "foreign_invoice_amount", "aliquot")
    def onchange_municipal_invoice_amount(self):
        """
        Computes the retention amount when the invoice amount or the aliquot are changed for the
        retentions of municipal type.
        """
        for record in self.filtered(
            lambda l: (not l.retention_id and l.economic_activity_id)
            or (l.retention_id and l.retention_id.type_retention == "municipal")
        ):

            record.retention_amount = record.invoice_amount * record.aliquot / 100
            record.foreign_retention_amount = record.foreign_invoice_amount * record.aliquot / 100

    @api.onchange("retention_amount", "invoice_amount")
    def onchange_retention_amount(self):
        """
        Making sure that the foreign retention amount and foreign invoice amount are updated when
        the retention amount or the invoice amount are changed on the retention line of the
        customer retentions.

        This is made to be triggered only when the foreign currency is NOT VEF, as this is the only
        case when the retention amount and the invoice amount are shown on the retention line,
        because the amounts of the retention lines are always shown in VEF.
        """
        for line in self.filtered(
            lambda l: not l.retention_id or l.retention_id.type == "out_invoice"
        ):
            if not line.retention_id or line.retention_id.type_retention in ("islr", "municipal"):
                line.update(
                    {
                        "foreign_invoice_amount": line.invoice_amount
                        * line.move_id.foreign_inverse_rate
                    }
                )
            line.update(
                {
                    "foreign_retention_amount": line.retention_amount
                    * line.move_id.foreign_inverse_rate
                }
            )

    # @api.onchange("foreign_retention_amount", "foreign_invoice_amount")
    # def onchange_foreign_retention_amount(self):
    #     """
    #     Making sure that the retention amount and the invoice amount are updated when the foreign
    #     retention amount or the foreign invoice amount are changed on the retention line of the
    #     customer retentions.

    #     This is made to be triggered only when the foreign currency is VEF, as this is the only
    #     case when the foreign retention amount and the foreign iva amount are shown on the views of
    #     the customer retentions, because the amounts of the retention lines are always shown in VEF.
    #     """
    #     _logger.warning("noonchange context: %s", self.env.context)
    #     if self.env.context.get("noonchange", False):
    #         return
    #     for line in self.filtered(
    #         lambda l: not l.retention_id or l.retention_id.type == "out_invoice"
    #     ):
    #         if not line.move_id:
    #             continue
    #         line_with_ctx = line.with_context(noonchange=True)
    #         if not line.retention_id or line.retention_id.type_retention in ("islr", "municipal"):
    #             _logger.warning("rate: %s", line.move_id.foreign_rate)
    #             _logger.warning("inverse rate: %s", line.move_id.foreign_inverse_rate)
    #             _logger.warning("move id: %s", line.move_id)
    #             line_with_ctx.update(
    #                 {
    #                     "invoice_amount": line.foreign_invoice_amount
    #                     * (1 / line.move_id.foreign_rate)
    #                 }
    #             )
    #         _logger.warning("rate: %s", line.move_id.foreign_rate)
    #         _logger.warning("inverse rate: %s", line.move_id.foreign_inverse_rate)
    #         line_with_ctx.update(
    #             {
    #                 "retention_amount": line.foreign_retention_amount
    #                 * (1 / line.move_id.foreign_rate)
    #             }
    #         )

    @api.constrains(
        "retention_amount",
        "invoice_total",
        "foreign_retention_amount",
        "invoice_amount",
        "foreign_invoice_amount",
    )
    def _constraint_amounts_in_zero(self):
        for record in self:
            # Solo validamos si la línea está vinculada a una retención real
            if not record.retention_id:
                continue
            if any(
                (
                    record.retention_amount == 0,
                    record.invoice_total == 0,
                    record.invoice_amount == 0,
                )
            ):
                raise ValidationError(
                    _("You can not create a retention with 0 amount.")
                )

    def check_retention_amount(self):
        for record in self:
            is_vef_the_base_currency = record.env.company.currency_id == record.env.ref("base.VEF")
            is_client_retention = record.retention_id and record.retention_id.type == "out_invoice"
            if (
                is_vef_the_base_currency
                and is_client_retention
                and record.move_id.payment_state not in ("in_payment", "paid")
                and abs(record.retention_amount) > abs(record.move_id.amount_residual)
            ):
                raise ValidationError(
                    _(
                        "The total amount of the retention is greater than the residual amount of"
                        " the invoice."
                    )
                )

    def write(self, vals):
        res = super().write(vals)
        if "retention_amount" in vals or "invoice_amount" in vals:
            self.check_retention_amount()
        return res

    @api.model
    def create(self, vals):
        record = super().create(vals)
        if "retention_amount" in vals or "invoice_amount" in vals:
            record.check_retention_amount()
        return record

    def get_invoice_paid_amount_not_related_with_retentions(self):
        """
        Returns the amount paid on the invoice that is not related with the retentions for the ISLR
        supplier retention lines. """
        # We need to get the lines without duplicate invoices because the invoice can have more
        # than one retention line.
        lines_without_duplicate_invoices = self.env[self._name]
        for line in self.filtered(
            lambda l: l.retention_id and l.retention_id.type_retention == "islr"
        ):
            if line.move_id in lines_without_duplicate_invoices.mapped("move_id"):
                continue
            lines_without_duplicate_invoices |= line

        for line in lines_without_duplicate_invoices:
            partials = self.env["account.partial.reconcile"].search(
                [
                    (
                        "credit_move_id",
                        "=",
                        line.move_id.line_ids.filtered(
                            lambda l: l.account_id.account_type == "liability_payable"
                            and l.credit > 0
                        )[0].id,
                    )
                ]
            )
            retention_payments = self.env["account.payment"].search(
                [
                    ("move_id.line_ids", "in", partials.mapped("debit_move_id").ids),
                    ("is_retention", "=", True),
                ]
            )
            # The invoice paid amount not related with retentions is the sum of the debit amounts
            # of the partials that are not related with the retention payments.
            invoice_paid_amount_not_related_with_retentions = sum(
                partial.debit_amount_currency
                if partial.debit_currency_id == self.env.ref("base.VEF")
                else partial.debit_amount_currency * partial.debit_move_id.foreign_inverse_rate
                for partial in partials.filtered(
                    lambda p: p.debit_move_id not in retention_payments.mapped("move_id.line_ids")
                )
            )
            return invoice_paid_amount_not_related_with_retentions

    def _get_code_of_retention(self):
        for record in self:
            type_person = record._get_islr_type_person_id()
            return record.payment_concept_id.line_payment_concept_ids.filtered(
                lambda l: l.type_person_id == type_person
            ).code if record.payment_concept_id else ""