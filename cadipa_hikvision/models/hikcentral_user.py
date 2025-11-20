from odoo import models, api, exceptions, fields, _
from odoo.exceptions import ValidationError
import qrcode
from dateutil.relativedelta import relativedelta
import io
import base64
import logging
from odoo.addons.binaural_hikvision.services import hikcentral_api

_logger = logging.getLogger(__name__)


class AppointmentGuests(models.Model):
    _inherit = "hikcentral.users"

    card_no = fields.Char()
    qr_code_image = fields.Binary(
        string="Código QR (Base64)", compute="_compute_qr_code", store=True
    )

    @api.depends("card_no")
    def _compute_qr_code(self):
        for record in self:
            if record.card_no:
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(record.card_no)
                qr.make(fit=True)

                img = qr.make_image(fill_color="black", back_color="white")
                buffer = io.BytesIO()
                img.save(buffer, format="PNG")

                record.qr_code_image = base64.b64encode(buffer.getvalue())
            else:
                record.qr_code_image = False

    def sync_cards_from_hikcentral(self):
        try: 
            response = hikcentral_api.get_person_info(self.person_id)
            if response and response.get('code') == '0':
                person_data = response.get('data', {})
                cards = person_data.get('cards', [])

                if cards:
                    first_card_no = cards[0].get('cardNo')
                    
                    if self.card_no != first_card_no:
                        self.with_context(skip_hik_sync=True).write({
                            'card_no': first_card_no
                        })
                else:
                    if self.card_no:
                        self.with_context(skip_hik_sync=True).write({
                            'card_no': False
                        })
        except Exception as e:
            _logger.error("Error syncing: %s", str(e))

    def write(self, vals):
        """
        Override write to detect changes to 'card_no' and push them to HikCentral
        only when the change is not coming from a synchronization (skip_hik_sync in context).
        """
        res = super(AppointmentGuests, self).write(vals)

        if "card_no" in vals and not self.env.context.get("skip_hik_sync"):
            for record in self:
                if record.hikcentral_person_api_id:
                    record.push_card_update_to_hikcentral()

        return res

    def push_card_update_to_hikcentral(self):
        """
        Send the current Odoo card to HikCentral.
        """
        try:
            cards_payload = [{"cardNo": self.card_no}] if self.card_no else []

            payload = {"cards": cards_payload}

            response = hikcentral_api.update_person(self.env, self.hikcentral_person_api_id, payload)

            if response.get("code") == "0":
                _logger.info("Successfully updated card in HikCentral")
            else:
                raise ValidationError(
                    _("Error API HikCentral: %s") % response.get("msg")
                )

        except Exception as e:
            _logger.error("Failed to send card to HikCentral: %s", e)
            raise ValidationError(
                _("Could not update the card on the physical device: %s") % str(e)
            )
