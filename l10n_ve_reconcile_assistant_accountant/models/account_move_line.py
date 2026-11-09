from odoo import models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def action_reconcile(self):
        """Botón "Reconciliar" de la conciliación manual: las selecciones que maneja el asistente
        (o que debe bloquear con explicación) lo abren; el resto sigue por la conciliación nativa."""
        lines = self.filtered(lambda line: line.balance or line.amount_currency)
        if lines and lines._l10n_ve_reconcile_classify()["handled"]:
            return lines.action_l10n_ve_reconcile_assistant()
        return super().action_reconcile()
