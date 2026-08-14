from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CrmLead(models.Model):
    _name = "crm.lead"
    _inherit = ["crm.lead", "l10n.ve.crm.foreign.currency.mixin"]

    foreign_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda Comercial",
        compute="_compute_foreign_currency_id",
        store=True,
        help="Moneda alterna configurada en Binaural Settings",
    )

    expected_revenue_foreign = fields.Monetary(
        string="Ingreso Esperado (Moneda Comercial)",
        currency_field="foreign_currency_id",
        tracking=True,
        help="Ingreso esperado ingresado en la moneda comercial. Este valor es fijo y nunca se recalcula por cambios de tasa.",
    )

    recurring_revenue_foreign = fields.Monetary(
        string="Ingreso Recurrente (Moneda Comercial)",
        currency_field="foreign_currency_id",
        help="Ingreso recurrente ingresado en la moneda comercial. Este valor es fijo y nunca se recalcula por cambios de tasa.",
    )

    expected_revenue = fields.Monetary(
        compute="_compute_expected_revenue",
        currency_field="company_currency",
        store=False,
    )

    recurring_revenue = fields.Monetary(
        compute="_compute_recurring_revenue",
        currency_field="company_currency",
        store=False,
    )

    prorated_revenue_foreign = fields.Monetary(
        compute="_compute_prorated_revenue_foreign",
        currency_field="foreign_currency_id",
        store=True,
    )

    recurring_revenue_monthly_foreign = fields.Monetary(
        compute="_compute_recurring_revenue_monthly_foreign",
        currency_field="foreign_currency_id",
        store=True,
    )

    recurring_revenue_monthly_prorated_foreign = fields.Monetary(
        compute="_compute_recurring_revenue_monthly_prorated_foreign",
        currency_field="foreign_currency_id",
        store=True,
    )

    recurring_revenue_prorated_foreign = fields.Monetary(
        compute="_compute_recurring_revenue_prorated_foreign",
        currency_field="foreign_currency_id",
        store=True,
    )

    @api.depends("company_id")
    def _compute_foreign_currency_id(self):
        for lead in self:
            company = lead.company_id or lead.env.company
            lead.foreign_currency_id = company.foreign_currency_id

    @api.depends("expected_revenue_foreign", "foreign_currency_id", "company_id")
    def _compute_expected_revenue(self):
        for lead in self:
            lead.expected_revenue = lead._convert_foreign_to_company(lead.expected_revenue_foreign)

    @api.depends("recurring_revenue_foreign", "foreign_currency_id", "company_id")
    def _compute_recurring_revenue(self):
        for lead in self:
            lead.recurring_revenue = lead._convert_foreign_to_company(lead.recurring_revenue_foreign)

    def _round_foreign(self, amount):
        """Redondea un monto en moneda comercial según los decimales que
        defina esa moneda (no un valor fijo, que no es correcto para
        cualquier moneda)."""
        self.ensure_one()
        if not self.foreign_currency_id:
            return amount
        return self.foreign_currency_id.round(amount)

    @api.depends("expected_revenue_foreign", "probability")
    def _compute_prorated_revenue_foreign(self):
        for lead in self:
            lead.prorated_revenue_foreign = lead._round_foreign(
                (lead.expected_revenue_foreign or 0.0) * (lead.probability or 0) / 100.0
            )

    @api.depends("recurring_revenue_foreign", "recurring_plan.number_of_months")
    def _compute_recurring_revenue_monthly_foreign(self):
        for lead in self:
            lead.recurring_revenue_monthly_foreign = lead._round_foreign(
                (lead.recurring_revenue_foreign or 0.0) / (lead.recurring_plan.number_of_months or 1)
            )

    @api.depends("recurring_revenue_monthly_foreign", "probability")
    def _compute_recurring_revenue_monthly_prorated_foreign(self):
        for lead in self:
            lead.recurring_revenue_monthly_prorated_foreign = lead._round_foreign(
                (lead.recurring_revenue_monthly_foreign or 0.0) * (lead.probability or 0) / 100.0
            )

    @api.depends("recurring_revenue_foreign", "probability")
    def _compute_recurring_revenue_prorated_foreign(self):
        for lead in self:
            lead.recurring_revenue_prorated_foreign = lead._round_foreign(
                (lead.recurring_revenue_foreign or 0.0) * (lead.probability or 0) / 100.0
            )

    @api.constrains("expected_revenue_foreign")
    def _check_expected_revenue_foreign_positive(self):
        for lead in self:
            if lead.expected_revenue_foreign < 0:
                raise ValidationError(
                    _("El ingreso esperado en moneda comercial no puede ser negativo.")
                )
            if lead.expected_revenue_foreign == 0:
                raise ValidationError(
                    _("El ingreso esperado en moneda comercial debe ser mayor a 0.")
                )

    @api.constrains("recurring_revenue_foreign", "recurring_plan")
    def _check_recurring_revenue_foreign_positive(self):
        for lead in self:
            if lead.recurring_revenue_foreign < 0:
                raise ValidationError(
                    _("El ingreso recurrente en moneda comercial no puede ser negativo.")
                )
            if lead.recurring_plan and lead.recurring_revenue_foreign == 0:
                raise ValidationError(
                    _(
                        "El ingreso recurrente en moneda comercial debe ser mayor a 0 "
                        "cuando la oportunidad tiene un plan recurrente definido."
                    )
                )
