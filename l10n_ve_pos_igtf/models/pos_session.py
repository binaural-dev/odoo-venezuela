from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PosSession(models.Model):
    _inherit = "pos.session"

    def action_pos_session_open(self):
        # Solo exigir la cuenta IGTF del cliente cuando IGTF realmente se
        # aplica en esta caja: es decir, cuando algún método de pago del
        # config tiene apply_igtf activo. Sin esta guarda, cualquier caja de
        # una empresa con el módulo instalado pero que NO usa IGTF no podría
        # abrir sesión (y rompía los tests de l10n_ve_pos al co-instalarse).
        igtf_in_use = any(self.config_id.payment_method_ids.mapped("apply_igtf"))
        if igtf_in_use and not self.company_id.customer_account_igtf_id:
            raise ValidationError(
                _(
                    "You have the IGTF configuration turned on, first configure the account and the percentage"
                )
            )

        return super().action_pos_session_open()
