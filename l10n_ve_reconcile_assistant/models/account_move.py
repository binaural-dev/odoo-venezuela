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

    def _l10n_ve_reconcile_origin_payment(self):
        """Pago del que viene el asiento, con el mismo criterio que `_create_advance_payment_move`.

        Un anticipo registrado a mano trae su pago en `origin_payment_id`; el residual de un pago
        hecho desde la factura ("RESTANTE DE PAGO EN DIVISA") trae el pago en
        `origin_payment_advanced_payment_id` y deja `origin_payment_id` vacío.
        """
        self.ensure_one()
        return self.origin_payment_advanced_payment_id or self.origin_payment_id

    def _l10n_ve_reconcile_apply_context(self):
        """Contexto con el que se aplica el origen a esta factura. Gancho para módulos que
        necesiten fijar valores por defecto (p. ej. la sucursal) en los asientos que se crean."""
        self.ensure_one()
        return {}
