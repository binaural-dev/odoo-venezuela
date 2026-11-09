from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_ve_reconcile_is_special_note(self):
        """True si el asiento es una nota que solo se concilia desde su propio documento:
        la ND de IGTF o las notas y asientos del diferencial cambiario. Los campos los define
        cada módulo; si no está instalado, el atributo no existe y no aplica."""
        self.ensure_one()
        return bool(
            getattr(self, "l10n_ve_igtf_note_debit_origin", False)
            or getattr(self, "l10n_ve_exchange_original_id", False)
            or getattr(self, "l10n_ve_exchange_diff_entry", False)
        )

    def _l10n_ve_reconcile_apply_context(self):
        """Contexto con el que se aplica el origen a esta factura. Gancho para módulos que
        necesiten fijar valores por defecto (p. ej. la sucursal) en los asientos que se crean."""
        self.ensure_one()
        return {}
