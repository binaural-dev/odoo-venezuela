from odoo import fields, models, api, SUPERUSER_ID
from odoo import api, fields, models, modules, tools, _
from requests import request, HTTPError
import json

import logging

_logger = logging.getLogger(__name__)


class Module(models.Model):
    _inherit = "ir.module.module"

    binaural = fields.Boolean(default=False)

    def manage_module_version(self):
        binauralbot_url = self.env['ir.config_parameter'].sudo().get_param('binaural_base.binauralbot_url')

        url = f"{binauralbot_url}/webhook/modules/"
        headers = {
            "Content-Type": "application/json",
        }

        data = self.read(
            [
                "name",
                "display_name",
                "installed_version",
                "latest_version",
                "published_version",
                "binaural",
                "state",
                "id",
                "write_uid",
            ]
        )
        binauralbot_id = self.env['ir.config_parameter'].sudo().get_param('binaural_base.binauralbot_id')
        if not binauralbot_id:
            _logger.warning("Binauralbot id not defined")
            return False

        for record in data:
            record["write_uid"] = record["write_uid"][1]

        dict_data = {"modules": data, "repository_id": binauralbot_id}
        json_data = json.dumps(dict_data)

        try:
            response = request("POST", url, data=json_data, headers=headers, timeout=(4, 15))
            # If the response was successful, no Exception will be raised
            response.raise_for_status()
        except HTTPError as http_err:
            _logger.warning(f"HTTP error occurred: {http_err}")  # Python 3.6
            return False
        except Exception as err:
            _logger.warning(f"Other error occurred: {err}")  # Python 3.6
            return False

    def get_values_from_terp(self, terp):
        res = super().get_values_from_terp(terp)
        res["binaural"] = terp.get("binaural", False)
        return res

    def create(self, vals):
        res = super().create(vals)
        for record in res:
            record.manage_module_version()
        return res


    def write(self, vals):
        res = super().write(vals)
        for record in self:
            if record.binaural:
                record.manage_module_version()
        return res


