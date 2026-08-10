from odoo import api, fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

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

    @api.depends("company_id")
    def _compute_foreign_currency_id(self):
        for lead in self:
            company = lead.company_id or lead.env.company
            lead.foreign_currency_id = company.foreign_currency_id

    def _convert_foreign_to_company(self, amount_foreign):
        """Convierte un monto en moneda comercial a la moneda de la compañía
        usando la tasa vigente. No modifica el monto en moneda comercial."""
        self.ensure_one()
        company = self.company_id or self.env.company
        if not amount_foreign or not self.foreign_currency_id or not company.currency_id:
            return 0.0
        return self.foreign_currency_id._convert(
            amount_foreign,
            company.currency_id,
            company,
            fields.Date.context_today(self),
        )

    @api.depends("expected_revenue_foreign", "foreign_currency_id", "company_id")
    def _compute_expected_revenue(self):
        for lead in self:
            lead.expected_revenue = lead._convert_foreign_to_company(lead.expected_revenue_foreign)

    @api.depends("recurring_revenue_foreign", "foreign_currency_id", "company_id")
    def _compute_recurring_revenue(self):
        for lead in self:
            lead.recurring_revenue = lead._convert_foreign_to_company(lead.recurring_revenue_foreign)

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

    @api.depends("expected_revenue_foreign", "probability")
    def _compute_prorated_revenue_foreign(self):
        for lead in self:
            lead.prorated_revenue_foreign = round(
                (lead.expected_revenue_foreign or 0.0) * (lead.probability or 0) / 100.0, 2
            )

    @api.depends("recurring_revenue_foreign", "recurring_plan.number_of_months")
    def _compute_recurring_revenue_monthly_foreign(self):
        for lead in self:
            lead.recurring_revenue_monthly_foreign = (
                lead.recurring_revenue_foreign or 0.0
            ) / (lead.recurring_plan.number_of_months or 1)

    @api.depends("recurring_revenue_monthly_foreign", "probability")
    def _compute_recurring_revenue_monthly_prorated_foreign(self):
        for lead in self:
            lead.recurring_revenue_monthly_prorated_foreign = (
                lead.recurring_revenue_monthly_foreign or 0.0
            ) * (lead.probability or 0) / 100.0

    @api.depends("recurring_revenue_foreign", "probability")
    def _compute_recurring_revenue_prorated_foreign(self):
        for lead in self:
            lead.recurring_revenue_prorated_foreign = (
                lead.recurring_revenue_foreign or 0.0
            ) * (lead.probability or 0) / 100.0
