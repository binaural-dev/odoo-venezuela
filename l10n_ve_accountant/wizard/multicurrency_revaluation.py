from odoo import api, models


class AccountMulticurrencyRevaluationWizard(models.TransientModel):
    _inherit = "account.multicurrency.revaluation.wizard"

    @api.model
    def _get_move_vals(self):
        """EXTENDS core: el asiento de ajuste de monedas no realizadas solo
        mueve la moneda de la compañía (VEF).

        El asistente nativo ajusta únicamente `debit`/`credit` y crea las
        líneas con `amount_currency = 0`: en moneda alterna no hay diferencia
        alguna (100 USD siguen siendo 100 USD, solo cambia lo que valen en
        bolívares). Sin esta marca, `_get_foreign_value` descarta la rama de
        "línea ya en moneda alterna" por ser `amount_currency` cero y, al no
        ser factura, cae en `_get_non_invoice_foreign_value`, que convierte los
        bolívares del ajuste a dólares con la tasa de la fecha y deja importes
        alternos que no existen (cuentas por cobrar y por pagar y ganancia o
        pérdida cambiaria en USD).

        `not_foreign_recalculate` hace que `_skip_foreign_compute` y el cálculo
        del asiento salten estas líneas, y `foreign_debit`/`foreign_credit` se
        fijan en 0. La reversión que crea `create_entries` copia las líneas
        (y esta marca), por lo que también queda en 0 en la moneda alterna.
        """
        move_vals = super()._get_move_vals()
        for command in move_vals.get("line_ids", []):
            command[2].update(
                {
                    "not_foreign_recalculate": True,
                    "foreign_debit": 0.0,
                    "foreign_credit": 0.0,
                }
            )
        return move_vals
