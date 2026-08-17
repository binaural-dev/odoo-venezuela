from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


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
        inverse="_inverse_expected_revenue",
        currency_field="company_currency",
        store=False,
    )

    recurring_revenue = fields.Monetary(
        compute="_compute_recurring_revenue",
        inverse="_inverse_recurring_revenue",
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

    def _inverse_expected_revenue(self):
        # expected_revenue ya no es un campo escribible (compute=/store=False,
        # alimentado desde expected_revenue_foreign). Antes, una escritura
        # externa (import CSV, integraciones, sale_crm) se perdía en
        # silencio; ahora se avisa con un error en vez de fallar callado.
        raise UserError(
            _(
                "El campo Ingreso Esperado (moneda de la compañía) es de "
                "solo lectura: se calcula a partir de Ingreso Esperado en "
                "moneda comercial. Editá ese campo en su lugar."
            )
        )

    @api.depends("recurring_revenue_foreign", "foreign_currency_id", "company_id")
    def _compute_recurring_revenue(self):
        for lead in self:
            lead.recurring_revenue = lead._convert_foreign_to_company(lead.recurring_revenue_foreign)

    def _inverse_recurring_revenue(self):
        raise UserError(
            _(
                "El campo Ingreso Recurrente (moneda de la compañía) es de "
                "solo lectura: se calcula a partir de Ingreso Recurrente en "
                "moneda comercial. Editá ese campo en su lugar."
            )
        )

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

    def _is_foreign_amount_check_exempt(self):
        """Exime del requisito de monto > 0 a:
        - Leads (type == 'lead'): el requisito de negocio es sobre
          oportunidades, no sobre leads sin calificar.
        - Registros creados por la pasarela de correo o el formulario web
          (mail_create_nosubscribe/mail_create_nolog en el contexto): esos
          flujos crean el registro sin que haya un usuario llenando un
          monto, y crm.lead.type puede resolver a 'opportunity' igual si el
          grupo de Leads está apagado (ver message_new() del core)."""
        self.ensure_one()
        if self.type != "opportunity":
            return True
        if self.env.context.get("mail_create_nosubscribe") or self.env.context.get("mail_create_nolog"):
            return True
        return False

    @api.constrains("expected_revenue_foreign", "type")
    def _check_expected_revenue_foreign_positive(self):
        for lead in self:
            if lead._is_foreign_amount_check_exempt():
                continue
            if lead.expected_revenue_foreign < 0:
                raise ValidationError(
                    _("El ingreso esperado en moneda comercial no puede ser negativo.")
                )
            if lead.expected_revenue_foreign == 0:
                raise ValidationError(
                    _("El ingreso esperado en moneda comercial debe ser mayor a 0.")
                )

    @api.constrains("recurring_revenue_foreign", "recurring_plan", "type")
    def _check_recurring_revenue_foreign_positive(self):
        for lead in self:
            if lead._is_foreign_amount_check_exempt():
                continue
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
