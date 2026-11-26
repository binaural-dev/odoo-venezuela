from odoo import api, fields, models


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    foreign_amount = fields.Float()

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._complete_amount_from_foreign(vals) for vals in vals_list])

    @api.model
    def _complete_amount_from_foreign(self, vals):
        """Completa `amount` cuando solo llega el monto en moneda extranjera.

        En el core `amount` (moneda del diario) manda y `amount_currency` solo se calcula
        desde el, nunca al reves. Una linea con USD 10,82 y `amount` en 0 deja el asiento
        en 0 Bs, y al conciliar el pago el core manda su valor en Bs al diferencial
        cambiario (ticket #16410). Aqui `amount` sale del monto en moneda extranjera a la
        tasa de la fecha del extracto.
        """
        if vals.get("amount") or not vals.get("foreign_currency_id") or not vals.get("amount_currency"):
            return vals
        journal_id = vals.get("journal_id") or self.default_get(["journal_id"]).get("journal_id")
        journal = (
            self.env["account.journal"].browse(journal_id)
            if journal_id
            else self.env["account.bank.statement"].browse(vals.get("statement_id")).journal_id
        )
        if not journal:
            return vals
        company = journal.company_id
        journal_currency = journal.currency_id or company.currency_id
        foreign_currency = self.env["res.currency"].browse(vals["foreign_currency_id"])
        if foreign_currency == journal_currency:
            return vals
        date = vals.get("date") or fields.Date.context_today(self)
        return {
            **vals,
            "amount": foreign_currency._convert(
                vals["amount_currency"], journal_currency, company, date
            ),
        }

    def edit_reconcile_line(self, move_line_id, record_data):
        """Mantiene balance y amount_currency coherentes con la tasa de la fecha del asiento.

        El dialogo "Editar linea" del widget de conciliacion deja editar a la vez el
        balance (Bs) y el monto en otra moneda, y el core guarda ambos tal cual:
        quedaba, por ejemplo, USD 1.700 con 1.700.000 Bs (tasa implicita 1000) cuando
        la tasa de la fecha era 924,3534. Aqui el ultimo campo editado manda, como el
        onchange del core en un asiento manual (ticket #16410).
        """
        record_data = self._sync_edited_line_amounts(move_line_id, record_data)
        return super().edit_reconcile_line(move_line_id, record_data)

    def _sync_edited_line_amounts(self, move_line_id, record_data):
        """Completa `record_data` para que balance y monto en moneda sigan la tasa de la fecha.

        - Cambia el monto en moneda: el balance sale de monto / tasa.
        - Cambia solo el balance o la moneda: el monto en moneda sale de balance * tasa.
        - No se toca si la moneda es la de la compania o si la linea ya esta conciliada
          (el monto parcial a conciliar sigue la tasa del documento, no la de la fecha).
        """
        self.ensure_one()
        line = self.env["account.move.line"].browse(move_line_id)
        company_currency = self.company_id.currency_id
        currency = self.env["res.currency"].browse(
            record_data.get("currency_id", line.currency_id.id)
        )
        if (
            not {"amount_currency", "balance", "currency_id"} & set(record_data)
            or currency == company_currency
            or line.reconciled_lines_ids
        ):
            return record_data
        rate = self.env["res.currency"]._get_conversion_rate(
            company_currency, currency, self.company_id, self.date
        )
        data = dict(record_data)
        if "amount_currency" in data:
            data["balance"] = company_currency.round(data["amount_currency"] / rate)
        else:
            balance = data.get("balance", line.balance)
            data["amount_currency"] = currency.round(balance * rate)
        return data

    def _prepare_move_line_default_vals(self, counterpart_account_id=None):
        liquidity_line_vals, counterpart_line_vals = super()._prepare_move_line_default_vals(
            counterpart_account_id=counterpart_account_id
        )
        if not self.env.company.foreign_currency_id.is_zero(self.foreign_amount):
            liquidity_line_vals.update(
                {
                    "foreign_debit": self.foreign_amount > 0 and self.foreign_amount or 0.0,
                    "foreign_credit": self.foreign_amount < 0 and -self.foreign_amount or 0.0,
                    "not_foreign_recalculate": True,
                }
            )
            counterpart_line_vals.update(
                {
                    "foreign_debit": -self.foreign_amount if self.foreign_amount < 0.0 else 0.0,
                    "foreign_credit": self.foreign_amount if self.foreign_amount > 0.0 else 0.0,
                    "not_foreign_recalculate": True,
                }
            )

        return [liquidity_line_vals, counterpart_line_vals]
