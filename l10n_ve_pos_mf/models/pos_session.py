from odoo import models, fields, api, _


class PosSession(models.Model):
    _inherit = "pos.session"

    serial_machine = fields.Char(related="config_id.serial_machine")
    report_z = fields.Char()

    def set_report_z(self, values):
        self.write({"report_z": int(values["data"]["_dailyClosureCounter"]) + 1})

    @api.model
    def _load_pos_data_fields(self, config):
        fields_list = list(super()._load_pos_data_fields(config))
        if not fields_list:
            return fields_list
        for field_name in ("serial_machine", "report_z"):
            if field_name not in fields_list:
                fields_list.append(field_name)
        return fields_list
