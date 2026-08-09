from odoo import api, fields, models
from odoo.tools import SQL


class CrmTeam(models.Model):
    _inherit = "crm.team"

    foreign_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda Comercial",
        compute="_compute_foreign_currency_id",
        store=True,
        help="Moneda alterna configurada en Binaural Settings",
    )

    invoiced_target_foreign = fields.Monetary(
        string="Objetivo de Facturación (Moneda Comercial)",
        currency_field="foreign_currency_id",
        help="Objetivo de facturación mensual ingresado en la moneda comercial. Este valor es fijo y nunca se recalcula por cambios de tasa.",
    )

    invoiced_target = fields.Float(
        compute="_compute_invoiced_target",
        store=False,
    )

    invoiced_foreign = fields.Monetary(
        string="Facturado Este Mes (Moneda Comercial)",
        compute="_compute_invoiced_foreign",
        currency_field="foreign_currency_id",
        help="Facturación real del mes en curso (facturas contabilizadas y cobradas), en moneda comercial, usando la tasa vigente al momento de contabilizar cada factura.",
    )

    @api.depends("company_id")
    def _compute_foreign_currency_id(self):
        for team in self:
            company = team.company_id or team.env.company
            team.foreign_currency_id = company.foreign_currency_id

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

    @api.depends("invoiced_target_foreign", "foreign_currency_id", "company_id")
    def _compute_invoiced_target(self):
        for team in self:
            team.invoiced_target = team._convert_foreign_to_company(team.invoiced_target_foreign)

    def _compute_invoiced_foreign(self):
        if self.ids:
            today = fields.Date.today()
            data_map = dict(self.env.execute_query(SQL(
                ''' SELECT
                        move.team_id AS team_id,
                        SUM(move.foreign_untaxed_total) AS foreign_untaxed_total
                    FROM account_move move
                    WHERE move.move_type IN ('out_invoice', 'out_refund', 'out_receipt')
                    AND move.payment_state IN ('in_payment', 'paid', 'reversed')
                    AND move.state = 'posted'
                    AND move.team_id IN %s
                    AND move.date BETWEEN %s AND %s
                    GROUP BY move.team_id
                ''',
                tuple(self.ids),
                fields.Date.to_string(today.replace(day=1)),
                fields.Date.to_string(today),
            )))
        else:
            data_map = {}

        for team in self:
            team.invoiced_foreign = data_map.get(team._origin.id, 0.0)

    def update_invoiced_target(self, value):
        # invoiced_target ya no es un campo escribible (pasó a compute=,
        # store=False): se redirige la escritura al campo en moneda
        # comercial, único punto de captura del objetivo.
        return self.write({"invoiced_target_foreign": round(float(value or 0))})
