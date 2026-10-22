from collections import defaultdict

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare
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
    foreign_currency_id = fields.Many2one(
        "res.currency",
        compute="_compute_foreign_currency_id",
        help=(
            "Currency of the foreign amounts of the line: the one of the invoice or, for an"
            " indexed retention over an invoice in bolivars, the alternate currency of the company."
        ),
    )
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
    move_id = fields.Many2one("account.move", "move", ondelete="cascade", store=True)
    is_retention_client = fields.Boolean(default=True)
    invoice_amount = fields.Monetary(
        currency_field="company_currency_id",
        string="Taxable income",
        compute="_compute_amounts",
        store=True,
        readonly=False,
    )
    invoice_total = fields.Monetary(
        currency_field="company_currency_id",
        string="Total invoiced",
        store=True
    )
    iva_amount = fields.Monetary(
        currency_field="company_currency_id",
        string="IVA", 
    
    )

    retention_amount = fields.Monetary(
        currency_field="company_currency_id",
        compute="_compute_retention_amount", store=True, readonly=False
    )
    foreign_retention_amount = fields.Monetary(
        currency_field="foreign_currency_id", compute="_compute_retention_amount", store=True, readonly=False
    )

    payment_concept_id = fields.Many2one(
        "payment.concept", "Payment concept", ondelete="cascade", index=True
    )

    allowed_payment_concept_ids = fields.Many2many( 'payment.concept',string="Filter payment concept for domain",
        compute="_compute_allowed_payment_concept_ids"
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
    foreign_invoice_amount = fields.Monetary(
        currency_field="foreign_currency_id",
        string="Foreign taxable income", compute="_compute_amounts", store=True, readonly=False
    )
    foreign_invoice_total = fields.Monetary(
        currency_field="foreign_currency_id",string="Foreign total invoiced")
    foreign_iva_amount = fields.Monetary(
        currency_field="foreign_currency_id",string="Foreign IVA")
    foreign_retention_amount = fields.Monetary(
        currency_field="foreign_currency_id",)
    foreign_currency_rate = fields.Float(string="Rate")
    payment_currency_id = fields.Many2one(
        "res.currency",
        string="Payment Currency",
        compute="_compute_payment_currency_id",
        store=True,
        readonly=False,
        copy=False,
        help=(
            "Currency of the payment of the retention of this invoice. In an indexed retention it"
            " is chosen between the currency of the company and the currency of the invoice; the"
            " lines of the same invoice (for example with different aliquots) share it. A"
            " non-indexed retention is always paid in the currency of the company."
        ),
    )
    allowed_payment_currency_ids = fields.Many2many(
        "res.currency", compute="_compute_allowed_payment_currency_ids"
    )

    @api.depends('move_id', 'retention_id.type_retention')
    def _compute_allowed_payment_concept_ids(self):
        for record in self:
            if record.retention_id.type_retention == 'islr' and record.move_id:
                concepts = record.move_id.invoice_line_ids.mapped('product_id.product_tmpl_id.payment_concept')
                record.allowed_payment_concept_ids = concepts.filtered(lambda c: c)
            else:
                record.allowed_payment_concept_ids = self.env['payment.concept'].search([])

    def _apply_iva_tax_group_values(self, invoice_id, tax_group, tax, withholding_amount):
        """
        Fills this retention line with the amounts of a single tax_group of
        the invoice (one real tax rate/aliquot).
        """
        self.ensure_one()
        retention_amount = abs(tax_group["tax_amount"] * (withholding_amount / 100))
        self.name = _("Iva Retention")
        self.invoice_type = invoice_id.move_type
        self.aliquot = tax.amount
        self.iva_amount = tax_group["tax_amount"]
        self.invoice_total = invoice_id.tax_totals["total_amount"]
        self.related_percentage_tax_base = withholding_amount
        self.invoice_amount = tax_group["base_amount"]
        self._set_foreign_rate(invoice_id.foreign_rate)
        self.foreign_invoice_amount = tax_group["base_amount_foreign_currency"]
        self.foreign_iva_amount = tax_group["tax_amount_foreign_currency"]
        self.foreign_invoice_total = invoice_id.tax_totals["total_amount_foreign_currency"]

        if invoice_id.move_type == "out_invoice":
            if self.env.company.auto_fill_retention_amount_iva:
                self.retention_amount = retention_amount
                self.foreign_retention_amount = self.foreign_iva_amount * (withholding_amount / 100)
            else:
                self.retention_amount = 0.0
                self.foreign_retention_amount = 0.0
        else:
            self.retention_amount = retention_amount
            self.foreign_retention_amount = self.foreign_iva_amount * (withholding_amount / 100)

    def _get_iva_tax_groups_and_taxes(self, invoice_id):
        """
        Returns [(tax_group, tax)] for every real tax_group applied on the
        invoice, in the order they appear on invoice_id.tax_totals.
        """
        tax_ids = invoice_id.invoice_line_ids.filtered(
            lambda l: l.tax_ids and l.tax_ids[0].amount > 0
        ).mapped("tax_ids")
        result = []
        for tax_group in invoice_id.tax_totals["subtotals"][0]["tax_groups"]:
            taxes = tax_ids.filtered(lambda l: l.tax_group_id.id == tax_group["id"])
            if taxes:
                result.append((tax_group, taxes[0]))
        return result

    @api.onchange("move_id")
    def _onchange_move_id(self):
        """
        Calcula y actualiza los campos de la línea de retención cuando cambia la factura.

        Cuando la factura tiene varias alícuotas de IVA (varios tax_group),
        se elige por defecto la primera alícuota que todavía no esté usada
        por otra línea de la misma factura en esta retención, en vez de
        siempre la primera - así, si se borra y se vuelve a agregar la
        misma factura, o si la factura tiene una alícuota ya cubierta por
        otra línea, se sugiere la alícuota que falta en vez de repetir la
        primera.
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

            tax_groups_and_taxes = record._get_iva_tax_groups_and_taxes(invoice_id)

            if not tax_groups_and_taxes:
                return {
                    "warning": {
                        "title": _("Atención"),
                        "message": _("The invoice has no tax."),
                    }
                }

            sibling_lines = record.retention_id.retention_line_ids.filtered(
                lambda l: l.move_id == invoice_id and l != record
            )
            used_aliquots = set(sibling_lines.mapped("aliquot"))

            tax_group, tax = next(
                (
                    (tg, t)
                    for tg, t in tax_groups_and_taxes
                    if t.amount not in used_aliquots
                ),
                tax_groups_and_taxes[0],
            )

            record._apply_iva_tax_group_values(invoice_id, tax_group, tax, withholding_amount)

    @api.onchange("aliquot")
    def _onchange_aliquot(self):
        """
        Recalcula los montos de la línea cuando el usuario cambia manualmente
        la alícuota, buscando el tax_group real de la factura que corresponde
        a esa alícuota.
        """
        for record in self:
            if not record.move_id or not record.retention_id or record.retention_id.type_retention != "iva":
                continue

            invoice_id = record.move_id
            withholding_partner = (
                record.retention_id.partner_id
                if record.retention_id.partner_id
                else invoice_id.partner_id
            )
            withholding_amount = (
                withholding_partner.withholding_type_id.value
                if withholding_partner and withholding_partner.withholding_type_id
                else 0
            )

            tax_groups_and_taxes = record._get_iva_tax_groups_and_taxes(invoice_id)
            match = next(
                (
                    (tg, t)
                    for tg, t in tax_groups_and_taxes
                    if float_compare(t.amount, record.aliquot, precision_digits=2) == 0
                ),
                None,
            )
            if not match:
                continue

            tax_group, tax = match
            record._apply_iva_tax_group_values(invoice_id, tax_group, tax, withholding_amount)

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

    def _get_islr_concept_base_amounts(self, move):
        """Return (base_amount, foreign_base_amount) for this line, matching
        the same rule the "Retención ISLR" button on the invoice uses
        (account_move._get_payment_concepts_from_invoice):

        - If the invoice has only ONE line that is a service with an ISLR
          payment concept, the base is the whole invoice subtotal by default
          (any goods on the invoice are deemed necessary for that single
          service, per the norm) - regardless of which concept this line
          declares - unless it's a SUPPLIER invoice and the company's
          islr_prioritize_product_subtotal_base setting (task #82491, scoped
          to suppliers only) opts to propose the service's own subtotal
          instead. Either way this is only the auto-proposed default:
          invoice_amount can always be edited by hand afterwards to use the
          other criterion.
        - If the invoice has SEVERAL such lines (own concept and amount
          each), every retention line gets its own matching invoice line's
          amount instead of the invoice total, and account.retention.
          _check_islr_concept_amounts still caps the declared total per
          concept at the real base for that concept.
        """
        self.ensure_one()
        if not self.payment_concept_id:
           
            return 0.0, 0.0

        concept_lines = move.invoice_line_ids.filtered(
            lambda l: l.product_id.product_tmpl_id.type == "service"
            and l.product_id.product_tmpl_id.payment_concept
        )
        if len(concept_lines) <= 1:
            is_supplier_invoice = move.move_type in ("in_invoice", "in_refund", "in_debit")
            if is_supplier_invoice and self.company_id.islr_prioritize_product_subtotal_base:
                return (
                    sum(abs(l.balance) for l in concept_lines),
                    sum(concept_lines.mapped("foreign_subtotal")),
                )
            return move.tax_totals["base_amount"], move.tax_totals["base_amount_foreign_currency"]

      
        invoice_lines_for_concept = concept_lines.filtered(
            lambda l: l.product_id.product_tmpl_id.payment_concept == self.payment_concept_id
        ).sorted("id")

        if len(invoice_lines_for_concept) <= 1:
            return (
                sum(abs(l.balance) for l in invoice_lines_for_concept),
                sum(invoice_lines_for_concept.mapped("foreign_subtotal")),
            )

        same_concept_siblings = (
            self.retention_id.retention_line_ids.filtered(
                lambda l: l.move_id == move and l.payment_concept_id == self.payment_concept_id
            )
            if self.retention_id
            else self
        )
        try:
            index = list(same_concept_siblings).index(self)
        except ValueError:
            index = len(same_concept_siblings)

        if index >= len(invoice_lines_for_concept):
            # More retention lines than invoice lines left for this concept.
            return 0.0, 0.0

        matched_line = invoice_lines_for_concept[index]
        return abs(matched_line.balance), matched_line.foreign_subtotal

    @api.onchange("payment_concept_id", "move_id")
    def _onchange_payment_concept_id_islr_warning(self):
        """
        Block immediately (instead of silently leaving invoice_amount at 0
        and only surfacing the problem later at Aprobar time) when the
        selected (invoice, concept) has no invoice line left to assign.
        """
        for record in self:
            if not (record.move_id and record.payment_concept_id and record.retention_id):
                continue
            if record.retention_id.type_retention != "islr":
                continue

            move = record.move_id
            concept_lines = move.invoice_line_ids.filtered(
                lambda l: l.product_id.product_tmpl_id.type == "service"
                and l.product_id.product_tmpl_id.payment_concept
            )
            if len(concept_lines) <= 1:
                # Single-concept invoice: base is always the whole invoice
                # subtotal, nothing to exhaust.
                continue

            invoice_lines_for_concept = concept_lines.filtered(
                lambda l: l.product_id.product_tmpl_id.payment_concept == record.payment_concept_id
            )
            if not invoice_lines_for_concept:
                continue

            same_concept_siblings = record.retention_id.retention_line_ids.filtered(
                lambda l: l.move_id == move and l.payment_concept_id == record.payment_concept_id
            )
            try:
                index = list(same_concept_siblings).index(record)
            except ValueError:
                index = len(same_concept_siblings)

            if index >= len(invoice_lines_for_concept):
                raise UserError(
                    _(
                        "There are no more products with payment concept"
                        " '%(concept)s' on invoice %(invoice)s to retain."
                    )
                    % {
                        "concept": record.payment_concept_id.display_name,
                        "invoice": move.display_name,
                    }
                )

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
            m_type = record.retention_id.type if record.retention_id else record.move_id.move_type
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
                        record._set_foreign_rate(move.foreign_rate)

                        if not record.retention_id:
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

                            if record.invoice_amount == 0 and record.invoice_total > 0:
                                concept_base, concept_foreign_base = record._get_islr_concept_base_amounts(move)
                                record.invoice_amount = concept_base
                                record.foreign_invoice_amount = concept_foreign_base

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
                            ('move_type', '=', m_type),
                            ('state', '=', 'posted'),
                            ('invoice_date', '>=', fiscalyear_start),
                            ('invoice_date', '<', invoice_date),
                            ('company_id', '=', record.company_id.id),
                        ]).filtered(lambda inv: bool(inv.retention_islr_line_ids))

                        # El acumulado se mide en UT, y el valor de la UT está en bolívares: la
                        # base de cada factura se toma en la moneda de la compañía
                        # (`amount_untaxed_signed`), nunca en la moneda del documento.
                        accumulated_base = sum(
                            abs(invoice.amount_untaxed_signed) for invoice in previous_invoices
                        ) + abs(record.move_id.amount_untaxed_signed)
                        total_taxable_base = accumulated_base / current_ut.value

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
                            record._set_foreign_rate(record.move_id.foreign_rate)
                        else:
                            record.related_pay_from = 0.0
                            record.related_percentage_tax_base = 0.0
                            record.related_percentage_fees = 0.0
                            record.related_amount_subtract_fees = 0.0
                            record._set_foreign_rate(0.0)

                        if not record.retention_id:
                            # We don't want this fields to be computed when the retention is
                            # created from a customer invoice since they are filled by the user.
                            if islr_retention_lines <= 1:
                                record.invoice_amount = record.move_id.tax_totals["base_amount"]
                                record.foreign_invoice_amount = record.move_id.tax_totals["base_amount_foreign_currency"]
                            else:
                                record.invoice_amount = record.invoice_amount or 0
                                record.foreign_invoice_amount = record.foreign_invoice_amount or 0
                        else:

                            if record.invoice_amount == 0 and record.invoice_total > 0:
                                concept_base, concept_foreign_base = record._get_islr_concept_base_amounts(
                                    record.move_id
                                )
                                record.invoice_amount = concept_base
                                record.foreign_invoice_amount = concept_foreign_base

    @api.depends("invoice_amount", "foreign_invoice_amount", "move_id")
    def _compute_amounts(self):
        base_currency_is_vef = self.env.company.currency_id.is_venezuelan_bolivar()
        if not base_currency_is_vef:
            for line in self:
                if line.move_id and line.invoice_amount > 0 and line.foreign_invoice_amount > 0:
                    line.invoice_amount = line.move_id.tax_totals["base_amount"]

    # No depende de `foreign_currency_rate` ni de `foreign_invoice_amount`: el cálculo ya no los
    # lee, y como la valoración foreign escribe la tasa, escucharla recalcularía (y pisaría) el
    # monto retenido que el usuario teclea en las retenciones de cliente.
    @api.onchange(
        "invoice_amount",
        "related_percentage_tax_base",
        "related_percentage_fees",
        "related_amount_subtract_fees",
    )
    @api.depends(
        "invoice_amount",
        "related_percentage_tax_base",
        "related_percentage_fees",
        "related_amount_subtract_fees",
        "move_id",
        "payment_concept_id"
    )
    def _compute_retention_amount(self):
        """
        This compute is used to get the retention amount from the payment concept of the partner
        to generate the ISLR retention line.

        La base del sistema es siempre VEF: el monto retenido sale de `invoice_amount` (la base en
        la moneda de la compañía) y nunca de un monto en otra moneda convertido a VEF.
        """
        islr_supplier_retention_lines = self.filtered(
            lambda l: (not l.retention_id and l.payment_concept_id)
            or (l.retention_id.type_retention == "islr")
        )
        for record in islr_supplier_retention_lines:
            related_percentage_tax_base = record.related_percentage_tax_base 
            related_percentage_fees = record.related_percentage_fees
            related_amount_subtract_fees = record.related_amount_subtract_fees
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
                base_ut = record.company_currency_id.round(record.invoice_amount / ut_value)
                aplicable_ut = base_ut * (related_percentage_tax_base / 100.0)
                retention_ut = aplicable_ut * (related_percentage_fees / 100.0)
                subtract_ut = record.company_currency_id.round(related_amount_subtract_fees / ut_value)
                record.retention_amount = abs((retention_ut - subtract_ut) * ut_value)
            else:
                record.retention_amount = abs((
                    record.invoice_amount
                    * (related_percentage_tax_base / 100.0)
                    * (related_percentage_fees / 100.0)
                ) - related_amount_subtract_fees)

            record.foreign_retention_amount = record._get_foreign_retention_amount(
                record.retention_amount
            )

    @api.depends("retention_id.indexation_mode", "move_id.currency_id", "company_id.foreign_currency_id")
    def _compute_foreign_currency_id(self):
        for line in self:
            currency, _rate_date = line._get_valuation_target()
            if not currency:
                move_currency = line.move_id.currency_id
                company = line.company_id
                # Una factura en la moneda de la compañía lleva la moneda alterna de la compañía
                currency = (
                    company.foreign_currency_id
                    if move_currency == company.currency_id and company.foreign_currency_id != move_currency
                    else move_currency
                )
            line.foreign_currency_id = currency

    @api.depends("retention_id.indexation_mode", "move_id", "move_id.currency_id")
    def _compute_allowed_payment_currency_ids(self):
        for line in self:
            currency = line.company_id.currency_id
            if line._is_indexed():
                currency |= line.move_id.currency_id
            line.allowed_payment_currency_ids = currency

    @api.depends("retention_id.indexation_mode", "move_id", "move_id.currency_id")
    def _compute_payment_currency_id(self):
        """The currency of the company, as the payments of the retentions have always been, unless
        an indexed retention chooses the currency of the invoice. Lines of the same invoice share
        the currency: a new line (born with the currency of the company, before its invoice is
        chosen) takes the one of the saved lines of its invoice."""
        for line in self:
            saved_siblings = (line._get_invoice_lines() - line).filtered(lambda other: other._origin.id)
            sibling_currency = saved_siblings.payment_currency_id[:1]
            is_new = not line._origin.id
            if is_new and sibling_currency and sibling_currency in line.allowed_payment_currency_ids:
                line.payment_currency_id = sibling_currency
            elif line.payment_currency_id and line.payment_currency_id in line.allowed_payment_currency_ids:
                continue
            elif sibling_currency and sibling_currency in line.allowed_payment_currency_ids:
                line.payment_currency_id = sibling_currency
            else:
                line.payment_currency_id = line.company_id.currency_id

    def _get_invoice_lines(self):
        """Lines that retain the same invoice (e.g. different aliquots). The line being edited in a
        form may not know its voucher yet, so without it they are looked up by invoice: an invoice
        is retained by one active voucher at a time."""
        self.ensure_one()
        if self.retention_id:
            return self.retention_id.retention_line_ids.filtered(lambda line: line.move_id == self.move_id)
        if not self.move_id:
            return self.browse()
        return self.search([
            ("move_id", "=", self.move_id.id), ("retention_id.state", "in", ("draft", "emitted")),
        ])

    def _get_effective_retention(self):
        """Voucher of the line; a new line in a form may not have it yet, then the one of the saved
        lines of its invoice."""
        self.ensure_one()
        return self.retention_id or self._get_invoice_lines().retention_id[:1]

    def _sync_payment_currency_with_invoice_lines(self):
        """Changing the payment currency of one line changes it in the others of the same invoice."""
        for line in self:
            siblings = (line._get_invoice_lines() - line).filtered(
                lambda other: other.payment_currency_id != line.payment_currency_id
            )
            if siblings:
                siblings.with_context(skip_payment_currency_sync=True).payment_currency_id = (
                    line.payment_currency_id
                )

    @api.onchange("payment_currency_id")
    def _onchange_payment_currency_id(self):
        self._sync_payment_currency_with_invoice_lines()

    @api.constrains("payment_currency_id", "move_id", "retention_id")
    def _check_payment_currency(self):
        for line in self:
            if line.payment_currency_id and line.payment_currency_id not in line.allowed_payment_currency_ids:
                raise ValidationError(
                    _(
                        "The payment currency of %(invoice)s must be one of: %(currencies)s. The"
                        " currency of the invoice is only available in indexed retentions."
                    )
                    % {
                        "invoice": line.move_id.name,
                        "currencies": ", ".join(line.allowed_payment_currency_ids.mapped("name")),
                    }
                )
        for retention in self.retention_id:
            by_invoice = defaultdict(set)
            for line in retention.retention_line_ids:
                by_invoice[line.move_id].add(line.payment_currency_id.id)
            for move, currencies in by_invoice.items():
                if len(currencies) > 1:
                    raise ValidationError(
                        _("The lines of %s must have the same payment currency.") % move.name
                    )

    def _is_indexed(self):
        """True when the line belongs to an indexed retention."""
        self.ensure_one()
        return bool(self._get_effective_retention().indexation_mode == "indexed" and self.move_id.currency_id)

    def _get_valuation_target(self):
        """Currency and date used to value the retained amount of the line in the currency of its
        invoice (the retained amount in VEF is the legal one and is the same in both modes).

        - Non-indexed: the rate of the invoice (the date its own amounts were converted with).
        - Indexed: the rate of the day of the voucher.

        An invoice in the currency of the company is valued in the alternate currency of the
        company: non-indexed with the rate of the invoice, indexed with the rate of the day of the
        voucher.
        """
        self.ensure_one()
        move = self.move_id
        currency = move.currency_id
        retention = self.retention_id
        company_currency = self.company_id.currency_id
        if not currency:
            return self.env["res.currency"], False
        if currency == company_currency:
            alternate = self.company_id.foreign_currency_id
            if not alternate or alternate == company_currency:
                return self.env["res.currency"], False
            if retention.indexation_mode == "indexed":
                return alternate, retention.date or fields.Date.context_today(self)
            if retention.type_retention == "islr":
                # Como siempre: el ISLR no indexado de una factura en Bs no tiene valoración foreign
                return self.env["res.currency"], False
            return alternate, move.invoice_date or move.date
        if retention.indexation_mode == "indexed":
            rate_date = retention.date or fields.Date.context_today(self)
        else:
            rate_date = move.invoice_date or move.date
        return currency, rate_date

    def _get_foreign_retention_amount(self, retention_amount):
        """Retained amount in the currency of the invoice: the retained amount in the currency of
        the company converted with the core conversion at the date of the valuation, so it is
        consistent with every other conversion of the system. Without any rate for the date none
        is invented (the core would fall back to 1.0): the amount is 0.
        """
        self.ensure_one()
        currency, rate_date = self._get_valuation_target()
        if not (rate_date and retention_amount and currency):
            return 0.0
        if not self.env["res.currency.rate"].compute_rate(
            currency.id, rate_date, raise_if_not_found=False
        ):
            return 0.0
        # A line that does not belong to a voucher yet has no related currencies.
        company_currency = self.company_currency_id or self.company_id.currency_id
        return company_currency._convert(retention_amount, currency, self.company_id, rate_date)

    def _apply_foreign_valuation(self):
        """Value the retention of the line in the currency of its invoice and register the rate
        used. Lines of an invoice in the currency of the company have no foreign valuation: the
        values are cleared."""
        for line in self:
            currency, rate_date = line._get_valuation_target()
            rates = (
                self.env["res.currency.rate"].compute_rate(
                    currency.id, rate_date, raise_if_not_found=False
                )
                if (currency and rate_date)
                else {}
            )
            line.update(
                {
                    "foreign_retention_amount": line._get_foreign_retention_amount(
                        line.retention_amount
                    ),
                    "foreign_currency_rate": rates.get("foreign_rate", 0.0),
                }
            )

    def _set_foreign_rate(self, rate):
        """Legacy rate of the invoice, only for a line that has no valuation of its own."""
        for line in self:
            if not line._get_valuation_target()[1]:
                line.foreign_currency_rate = rate

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
            record._set_foreign_rate(record.move_id.foreign_rate)

            record.aliquot = record.economic_activity_id.aliquot
            record.retention_amount = record.invoice_amount * record.aliquot / 100
            record.foreign_retention_amount = record._get_foreign_retention_amount(
                record.retention_amount
            )

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
            record.foreign_retention_amount = record._get_foreign_retention_amount(
                record.retention_amount
            )

    @api.onchange("retention_amount", "invoice_amount")
    def onchange_retention_amount(self):
        """
        Mantiene el monto foreign de la retención al editar el monto retenido o la base en las
        retenciones de cliente (los Bs los teclea el usuario según el comprobante del cliente).

        El monto foreign sale de los montos de la factura en su moneda (proporción base o IVA
        foreign / Bs), igual que en el resto de los cálculos, y no multiplicando por
        `foreign_inverse_rate` del documento (referencial, con menos dígitos que la tasa real).
        """
        for line in self.filtered(
            lambda l: not l.retention_id or l.retention_id.type == "out_invoice"
        ):
            line._apply_foreign_valuation()

    @api.constrains("move_id")
    def _check_retention_accounting_date(self):
        # account.retention's own @api.constrains("date_accounting",
        # "retention_line_ids") only fires when the lines are touched
        # through the parent record. A direct write on this line's move_id
        # (e.g. from account_retention_line.py:_onchange_move_id callers,
        # or a wizard) would bypass it, so re-run the same check here.
        self.retention_id._check_accounting_date_vs_invoices()

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
            ) and record.retention_id.state != "draft":
                raise ValidationError(
                    _("You can not create a retention with 0 amount.")
                )

    def check_retention_amount(self):
        for record in self:
            is_vef_the_base_currency = record.env.company.currency_id.is_venezuelan_bolivar()
            is_client_retention = record.retention_id and record.retention_id.type == "out_invoice"
            if (
                is_vef_the_base_currency
                and is_client_retention
                and record.move_id.payment_state not in ("in_payment", "paid")
                and abs(record.retention_amount) > abs(record.move_id.amount_residual_signed)
            ):
                raise ValidationError(
                    _(
                        "The total amount of the retention is greater than the residual amount of"
                        " the invoice."
                    )
                )

    def write(self, vals):
        if "payment_currency_id" in vals and not self.env.context.get("skip_payment_currency_sync"):
            # The lines of the same invoice share the payment currency: they are written together
            # so that the constraint sees them consistent, not one by one.
            targets = self
            for line in self:
                targets |= line._get_invoice_lines()
            if targets != self:
                super(AccountRetentionLine, targets).write(
                    {"payment_currency_id": vals["payment_currency_id"]}
                )
        res = super().write(vals)
        if "retention_amount" in vals or "invoice_amount" in vals:
            self.check_retention_amount()
        if "retention_amount" in vals or "move_id" in vals:
            self.filtered("retention_id")._apply_foreign_valuation()
        return res

    @api.model
    def _align_payment_currency_with_saved_lines(self, vals):
        """Las líneas de una misma factura comparten la moneda de pago. En el formulario una línea nueva
        nace con la de la compañía sin conocer a sus hermanas: si el comprobante ya tiene líneas de
        esa factura toma la suya; si el usuario eligió en la nueva otra moneda (la de la factura),
        son las hermanas las que la siguen."""
        if not (vals.get("retention_id") and vals.get("move_id")):
            return vals
        siblings = self.search([
            ("retention_id", "=", vals["retention_id"]), ("move_id", "=", vals["move_id"]),
        ])
        if not siblings:
            return vals
        sibling_currency = siblings.payment_currency_id[:1]
        company = self.env["res.company"].browse(vals.get("company_id") or self.env.company.id)
        chosen = vals.get("payment_currency_id")
        if chosen and chosen != sibling_currency.id and chosen != company.currency_id.id:
            siblings.with_context(skip_payment_currency_sync=True).write({"payment_currency_id": chosen})
        elif sibling_currency:
            vals = dict(vals, payment_currency_id=sibling_currency.id)
        return vals

    @api.model
    def create(self, vals):
        if isinstance(vals, dict):
            vals = self._align_payment_currency_with_saved_lines(vals)
        else:
            vals = [self._align_payment_currency_with_saved_lines(line_vals) for line_vals in vals]
        record = super().create(vals)
        if "retention_amount" in vals or "invoice_amount" in vals:
            record.check_retention_amount()
        # Las líneas llegan en lote cuando se crean junto con el comprobante
        record.filtered("retention_id")._apply_foreign_valuation()
        record.filtered("retention_id")._sync_payment_currency_with_invoice_lines()
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
                if partial.debit_currency_id.is_venezuelan_bolivar()
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