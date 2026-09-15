from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    ciu_id = fields.Many2one(
        "economic.activity", string="CIU", compute="_compute_ciu_id", store=True, readonly=False
    )

    @api.depends("product_id.ciu_ids")
    def _compute_ciu_id(self):
        for line in self:
            if not line.product_id or line.ciu_id or not line.product_id.ciu_ids:
                continue
            line.ciu_id = line.product_id.ciu_ids[0]

    @api.model
    def _prepare_reconciliation_amls(self, values_list, shadowed_aml_values=None):
        # 1. Dejar que Odoo ejecute el bucle while True original
        all_results, fully_reconciled_aml_ids = super()._prepare_reconciliation_amls(
            values_list, 
            shadowed_aml_values=shadowed_aml_values
        )

        # 2. Interceptamos solo si pasamos nuestro flag en el contexto
        if self.env.context.get('no_exchange_difference') and self.env.context.get('group_in_single_partial'):
            if len(all_results) > 1:
                # Tomamos la estructura del primer parcial como base
                base_result = all_results[0]
                first_partial = base_result['partial_values']

                # Sumamos los importes de todos los parciales generados en el bucle
                total_amount = sum(r['partial_values']['amount'] for r in all_results if r.get('partial_values'))
                total_debit_curr = sum(r['partial_values']['debit_amount_currency'] for r in all_results if r.get('partial_values'))
                total_credit_curr = sum(r['partial_values']['credit_amount_currency'] for r in all_results if r.get('partial_values'))

                # Actualizamos los valores consolidados en el primer registro
                first_partial['amount'] = total_amount
                first_partial['debit_amount_currency'] = total_debit_curr
                first_partial['credit_amount_currency'] = total_credit_curr

                # Eliminamos los valores de diferencia de cambio si sobrevivió alguno
                base_result.pop('exchange_values', None)

                # Reemplazamos la lista con únicamente el resultado consolidado
                all_results = [base_result]

        return all_results, fully_reconciled_aml_ids
