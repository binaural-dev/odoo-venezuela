from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL


class CrmTeam(models.Model):
    _name = "crm.team"
    _inherit = ["crm.team", "l10n.ve.crm.foreign.currency.mixin"]

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
        inverse="_inverse_invoiced_target",
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

    @api.depends("invoiced_target_foreign", "foreign_currency_id", "company_id")
    def _compute_invoiced_target(self):
        for team in self:
            team.invoiced_target = team._convert_foreign_to_company(team.invoiced_target_foreign)

    def _inverse_invoiced_target(self):
        # invoiced_target ya no es un campo escribible (compute=/store=False,
        # alimentado desde invoiced_target_foreign). Antes, una escritura
        # externa se perdía en silencio; ahora se avisa con un error. El
        # único punto de escritura del core (update_invoiced_target, usado
        # por el widget del dashboard) ya está redirigido a
        # invoiced_target_foreign y no pasa por acá.
        raise UserError(
            _(
                "El campo Objetivo de Facturación (moneda de la compañía) "
                "es de solo lectura: se calcula a partir del Objetivo de "
                "Facturación en moneda comercial. Editá ese campo en su lugar."
            )
        )

    @api.depends("foreign_currency_id")
    def _compute_invoiced_foreign(self):
        if self.ids:
            today = fields.Date.today()
            # foreign_untaxed_total (l10n_ve_accountant) no tiene signo (igual
            # que su análogo amount_untaxed): es positivo tanto para facturas
            # como para notas de crédito. Hay que negarlo explícitamente para
            # out_refund, igual que hace amount_untaxed_signed en el core.
            data_map = dict(self.env.execute_query(SQL(
                ''' SELECT
                        move.team_id AS team_id,
                        SUM(
                            CASE WHEN move.move_type = 'out_refund'
                                THEN -move.foreign_untaxed_total
                                ELSE move.foreign_untaxed_total
                            END
                        ) AS foreign_untaxed_total
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
