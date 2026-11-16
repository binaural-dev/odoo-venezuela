from odoo import _, models
from odoo.exceptions import UserError


class ValidateAccountMove(models.TransientModel):
    _inherit = "validate.account.move"

    def validate_move(self):
        """Los documentos con publicacion personalizada solo los publica el cron.

        "Confirm them now" (`force_post`) escribe `auto_post = 'no'` antes de `_post`, lo
        que permitiria saltarse la programacion: los 'custom' en borrador se sacan de la
        seleccion. Si solo habia 'custom' se avisa con un error.
        """
        custom = self.move_ids.filtered(
            lambda m: m.auto_post == "custom" and m.state == "draft"
        )
        if custom:
            if custom == self.move_ids:
                raise UserError(
                    _(
                        "The selected documents are scheduled to be posted "
                        "automatically on their publication date."
                    )
                )
            self.move_ids -= custom
        return super().validate_move()
