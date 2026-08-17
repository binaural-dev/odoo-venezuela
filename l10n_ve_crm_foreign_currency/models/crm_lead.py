import pytz

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
        required=True,
        tracking=True,
        help="Ingreso esperado ingresado en la moneda comercial. Este valor es fijo y nunca se recalcula por cambios de tasa.",
    )

    recurring_revenue_foreign = fields.Monetary(
        string="Ingreso Recurrente (Moneda Comercial)",
        currency_field="foreign_currency_id",
        tracking=True,
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
            currency = lead.foreign_currency_id
            if not currency:
                continue
            if currency.compare_amounts(lead.expected_revenue_foreign, 0) < 0:
                raise ValidationError(
                    _("El ingreso esperado en moneda comercial no puede ser negativo.")
                )
            if currency.is_zero(lead.expected_revenue_foreign):
                raise ValidationError(
                    _("El ingreso esperado en moneda comercial debe ser mayor a 0.")
                )

    @api.constrains("recurring_revenue_foreign", "recurring_plan", "type")
    def _check_recurring_revenue_foreign_positive(self):
        for lead in self:
            if lead._is_foreign_amount_check_exempt():
                continue
            currency = lead.foreign_currency_id
            if not currency:
                continue
            if currency.compare_amounts(lead.recurring_revenue_foreign, 0) < 0:
                raise ValidationError(
                    _("El ingreso recurrente en moneda comercial no puede ser negativo.")
                )
            if lead.recurring_plan and currency.is_zero(lead.recurring_revenue_foreign):
                raise ValidationError(
                    _(
                        "El ingreso recurrente en moneda comercial debe ser mayor a 0 "
                        "cuando la oportunidad tiene un plan recurrente definido."
                    )
                )

    def copy_data(self, default=None):
        default = dict(default or {})
        # El core neutraliza recurring_revenue (default['recurring_revenue'] = 0)
        # para usuarios sin crm.group_use_recurring_revenues, pero esa
        # escritura ahora la rechaza _inverse_recurring_revenue(). Hay que
        # neutralizar el campo real (recurring_revenue_foreign) en su lugar,
        # para que copiar una oportunidad no se rompa para esos usuarios.
        if not self.env.user.has_group("crm.group_use_recurring_revenues"):
            default["recurring_revenue_foreign"] = 0
        return super().copy_data(default=default)

    def _get_rainbowman_message(self):
        # El método del core compara expected_revenue (columna SQL cruda,
        # congelada con el valor histórico en moneda de la compañía antes de
        # esta funcionalidad) contra self.expected_revenue (recalculado a la
        # tasa de hoy). Con una devaluación entre ambos momentos, casi
        # cualquier cierre se lee como "récord". Se sobrescribe el método
        # completo comparando expected_revenue_foreign en ambos lados: ese
        # campo sí está almacenado y nunca se recalcula por tasa, así que la
        # comparación queda en una moneda estable de punta a punta.
        self.ensure_one()
        if not self.user_id:
            return False
        self.flush_model()

        if len(self.message_ids) >= 25:
            return _('Phew, that took some effort — but you nailed it. Good job!')

        team_condition = f'team_id = {self.team_id.id}' if self.team_id else 'team_id IS NULL'
        source_case = f'source_id = {self.source_id.id} AND {team_condition}' if self.source_id else 'false'
        country_case = f'country_id = {self.country_id.id} AND {team_condition}' if self.country_id else 'false'
        tz_midnight = fields.Datetime.now().astimezone(pytz.timezone(self.env.user.tz or self.user_id.tz or 'UTC')).replace(hour=0, minute=0, second=0)
        tz_midnight_in_utc = tz_midnight.astimezone(pytz.UTC).replace(tzinfo=None)
        query = f"""
        SELECT
            MAX(CASE WHEN team_id = %(team_id)s AND COALESCE(date_closed, create_date) >= %(tz_midnight)s - INTERVAL '31 days' AND id <> %(lead_id)s THEN expected_revenue_foreign ELSE 0 END) AS max_team_31,
            MAX(CASE WHEN team_id = %(team_id)s AND COALESCE(date_closed, create_date) >= %(tz_midnight)s - INTERVAL '7 days'  AND id <> %(lead_id)s THEN expected_revenue_foreign ELSE 0 END) AS max_team_7,
            MAX(CASE WHEN user_id = %(user_id)s AND COALESCE(date_closed, create_date) >= %(tz_midnight)s - INTERVAL '31 days' AND id <> %(lead_id)s THEN expected_revenue_foreign ELSE 0 END) AS max_user_31,
            MAX(CASE WHEN user_id = %(user_id)s AND COALESCE(date_closed, create_date) >= %(tz_midnight)s - INTERVAL '7 days'  AND id <> %(lead_id)s THEN expected_revenue_foreign ELSE 0 END) AS max_user_7,
            MIN(CASE WHEN COALESCE(date_closed, create_date) >= %(tz_midnight)s - INTERVAL '31 days' THEN day_close ELSE 31 END) AS min_day_close_31,
            COUNT(CASE WHEN user_id = %(user_id)s THEN 1 ELSE NULL END) AS count_user_closed_year,
            COUNT(CASE WHEN user_id = %(user_id)s AND COALESCE(date_closed, create_date) >= %(tz_midnight)s - INTERVAL '3 days' AND COALESCE(date_closed, create_date) < %(tz_midnight)s - INTERVAL '2 days' THEN 1 ELSE NULL END) AS count_user_closed_minus3day,
            COUNT(CASE WHEN user_id = %(user_id)s AND COALESCE(date_closed, create_date) >= %(tz_midnight)s - INTERVAL '2 days' AND COALESCE(date_closed, create_date) < %(tz_midnight)s - INTERVAL '1 days' THEN 1 ELSE NULL END) AS count_user_closed_minus2day,
            COUNT(CASE WHEN user_id = %(user_id)s AND COALESCE(date_closed, create_date) >= %(tz_midnight)s - INTERVAL '1 days' AND COALESCE(date_closed, create_date) < %(tz_midnight)s THEN 1 ELSE NULL END) AS count_user_closed_yesterday,
            COUNT(CASE WHEN user_id = %(user_id)s AND COALESCE(date_closed, create_date) >= %(tz_midnight)s THEN 1 ELSE NULL END) AS count_user_closed_today,
            COUNT(CASE WHEN {source_case} THEN 1 ELSE NULL END) AS count_source_closed_year,
            COUNT(CASE WHEN {country_case} THEN 1 ELSE NULL END) AS count_country_closed_year
            FROM crm_lead
            WHERE
                type = 'opportunity'
            AND
                active = True
            AND
                probability = 100
            AND
                DATE_TRUNC('year', COALESCE(date_closed, create_date)) = DATE_TRUNC('year', %(tz_midnight)s)
            AND
                (user_id = %(user_id)s OR team_id = %(team_id)s)
        """
        self.env.cr.execute(query, {
            'user_id': self.env.user.id,
            'team_id': self.team_id.id or -1,
            'lead_id': self.id,
            'tz_midnight': tz_midnight_in_utc,
        })
        query_result = self.env.cr.dictfetchone()

        def _is_lower_than_expected_revenue(value):
            return self.expected_revenue_foreign and value is not None and value < self.expected_revenue_foreign

        if query_result['count_user_closed_year'] == 1:
            return _('Go, go, go! Congrats for your first deal.')
        elif _is_lower_than_expected_revenue(query_result['max_team_31']):
            return _('Boom! Team record for the past 30 days.')
        elif _is_lower_than_expected_revenue(query_result['max_team_7']):
            return _('Yeah! Best deal out of the last 7 days for the team.')
        elif _is_lower_than_expected_revenue(query_result['max_user_31']):
            return _('You just beat your personal record for the past 30 days.')
        elif _is_lower_than_expected_revenue(query_result['max_user_7']):
            return _('You just beat your personal record for the past 7 days.')
        elif query_result['count_user_closed_today'] == 5:
            return _('You\'re on fire! Fifth deal won today 🔥')
        elif query_result['count_user_closed_today'] == 1 and query_result['count_user_closed_yesterday'] and query_result['count_user_closed_minus2day'] and not query_result['count_user_closed_minus3day']:
            return _('You\'re on a winning streak. 3 deals in 3 days, congrats!')
        elif query_result['min_day_close_31'] == self.day_close and self.day_close < 31 \
                and self.date_closed and (self.date_closed - self.create_date).total_seconds() > 60:
            return _('Wow, that was fast. That deal didn’t stand a chance!')
        elif len(stage_ids := [int(stage_id) for stage_id, duration in self.duration_tracking.items() if duration >= 60]) == 1:
            first_stage = self.env['crm.stage'].search([
                '|', ('team_ids', 'in', False), ('team_ids', 'in', self.team_id.id),
            ], order='sequence ASC', limit=1)
            if first_stage.id == stage_ids[0]:
                return _('No detours, no delays - from %(stage_name)s straight to the win! 🚀', stage_name=first_stage.name)
        if query_result['count_country_closed_year'] == 1 and self.country_id:
            return _('Yeah! A first deal for the country, keep up the good work.')
        return False
