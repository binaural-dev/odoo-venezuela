from odoo import models


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    def unlink(self):
        """Cancela el cruce de anticipo cuyo parcial se rompe, sea cual sea la forma de romperlo.

        Un cruce de anticipo se concilia por dos lados (anticipo contra el pago, CxC/CxP contra la factura).
        La acción nativa "Romper conciliación" (`remove_move_reconcile()`) borra solo los parciales del lado
        que se le pide: el otro queda, el cruce sigue publicado, la factura sigue pagada y el anticipo
        reaparece disponible (doble gasto). Se engancha aquí, y no en `remove_move_reconcile`, porque
        `unlink` de parcial es el único punto donde convergen todas las formas de romper una conciliación
        (acción nativa, widget, botón a borrador, wizard, código de otros módulos).

        Las rutas gestionadas (wizard de cancelar anticipo, `cancel_advance_payment_transaction`, pago a
        borrador/cancelado) ya cancelan el cruce y lo declaran con `move_action_cancel_advance_payment`:
        en ese contexto no se hace nada para no cancelar dos veces. Si la cancelación falla (fecha de
        bloqueo, hash) el error se propaga y se revierte la desconciliación.
        """
        if self.env.context.get("move_action_cancel_advance_payment"):
            return super().unlink()

        crosses = (self.debit_move_id | self.credit_move_id).move_id.filtered(
            lambda move: move.state == "posted"
            and move.origin_payment_advanced_payment_id
            and move._is_advance_cross()
        )
        result = super().unlink()

        # `cancel_advance_payment_transaction` no usa el parcial (ya borrado): recibe el pago origen y el
        # cruce. Cada cruce se cancela una sola vez aunque varios de sus parciales caigan en este lote.
        for cross in crosses:
            if cross.exists() and cross.state == "posted" and cross.origin_payment_advanced_payment_id:
                cross.cancel_advance_payment_transaction(
                    cross.origin_payment_advanced_payment_id, cross,
                )
        return result
