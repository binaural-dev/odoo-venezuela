from odoo import models, fields, api, _


class PosSession(models.Model):
    _inherit = "pos.session"

    # Datos del Reporte Z que cerró el día fiscal de la sesión. Los escribe
    # `set_report_z` (caja: ClosePosPopup; Kiosko: l10n_ve_pos_mf_self_order).
    # `serial_machine` es propio de la sesión (antes era relacionado con la
    # caja): guarda la máquina que imprimió la Z aunque después se cambie.
    serial_machine = fields.Char(string="Serial de Máquina Fiscal", readonly=True, copy=False)
    report_z = fields.Char()
    report_z_date = fields.Datetime(string="Report Z Date", readonly=True, copy=False)

    def set_report_z(self, values):
        """Registra en la sesión el Reporte Z leído del S1 de la máquina.

        ``values["data"]`` trae ``_dailyClosureCounter`` y
        ``_registeredMachineNumber`` (serial). El contador se lee de S1 ANTES
        de imprimir la Z (como el flujo IoT y ``account.move.report_z``), así
        que es el de la última Z y la impresa es ese número + 1. Además del
        número de Z, guarda el serial y la fecha y hora. El serial de la caja
        (``pos.config.serial_machine``) no se toca.
        """
        data = values["data"]
        self.write(
            {
                "report_z": int(data["_dailyClosureCounter"]) + 1,
                "serial_machine": data.get("_registeredMachineNumber") or False,
                "report_z_date": fields.Datetime.now(),
            }
        )

    @api.model
    def _load_pos_data_fields(self, config):
        fields_list = list(super()._load_pos_data_fields(config))
        if not fields_list:
            return fields_list
        for field_name in ("serial_machine", "report_z"):
            if field_name not in fields_list:
                fields_list.append(field_name)
        return fields_list
