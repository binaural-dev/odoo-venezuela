from collections import Counter

from odoo import models, fields, api, _
from odoo.exceptions import UserError

# Serial de relleno que el POS asigna a las órdenes cuando el S1 no trae
# serial (ver PosStore._applyFiscalResponse). No es un serial real.
PLACEHOLDER_SERIALS = {"TFHKA-LOCAL"}


class PosSession(models.Model):
    _inherit = "pos.session"

    # Se guarda en la sesión al cerrar (antes era un related al config que
    # nadie llenaba en el flujo Web Serial, por eso salía siempre vacío).
    serial_machine = fields.Char(string="Serial de la máquina fiscal", copy=False)
    report_z = fields.Char(copy=False)
    mf_z_printed = fields.Boolean(
        string="Reporte Z impreso",
        copy=False,
        help="Se marca apenas la máquina fiscal confirma la impresión del Reporte Z. "
        "Evita que un reintento del cierre emita un segundo Z (que saldría en cero).",
    )

    def set_report_z(self, values):
        """Registra en la sesión el Reporte Z recién impreso.

        ``_dailyClosureCounter`` viene del S1 leído DESPUÉS del Z, así que ya
        es el número del Z que se acaba de emitir: no se le suma 1. (Al
        facturar, en cambio, el S1 se lee antes del Z y por eso el driver
        guarda ``contador + 1`` en la orden.)
        """
        data = values.get("data") or {}
        counter = data.get("_dailyClosureCounter")
        try:
            report_z = int(counter)
        except (TypeError, ValueError):
            raise UserError(_("Número de Reporte Z inválido: %s", counter))
        if report_z <= 0:
            raise UserError(_("Número de Reporte Z inválido: %s", counter))

        serial = (data.get("_registeredMachineNumber") or "").strip()
        vals = {"report_z": str(report_z), "mf_z_printed": True}
        if serial and serial not in PLACEHOLDER_SERIALS:
            vals["serial_machine"] = serial
        self.write(vals)

        if vals.get("serial_machine"):
            configs = self.config_id.filtered(lambda c: c.serial_machine != serial)
            if configs:
                configs.sudo().write({"serial_machine": serial})
        return True

    def mark_mf_z_printed(self):
        """Se llama apenas la máquina confirma el Z, antes de leer el S1."""
        self.write({"mf_z_printed": True})
        return True

    def get_mf_close_state(self):
        """Estado fiscal de la sesión para el cierre desde el POS.

        Devuelve si el Z ya se imprimió / registró y, para la carga manual
        cuando falla el S1, el Z y el serial que tienen sus órdenes.
        """
        self.ensure_one()
        orders = self.order_ids.filtered(lambda o: o.state != "cancel")
        z_numbers = []
        for value in orders.mapped("mf_reportz"):
            try:
                z_numbers.append(int(value))
            except (TypeError, ValueError):
                continue
        serials = Counter(
            s for s in orders.mapped("fiscal_machine") if s and s not in PLACEHOLDER_SERIALS
        )
        return {
            "report_z": self.report_z or False,
            "mf_z_printed": self.mf_z_printed,
            "suggested_report_z": max(z_numbers) if z_numbers else False,
            "suggested_serial": (
                self.serial_machine
                or (serials.most_common(1)[0][0] if serials else False)
                or self.config_id.serial_machine
                or False
            ),
        }

    def _loader_params_pos_payment_method(self):
        res = super()._loader_params_pos_payment_method()
        res["search_params"]["fields"].append("code_fiscal_printer")
        return res

    def _loader_params_account_tax(self):
        res = super()._loader_params_account_tax()
        res["search_params"]["fields"].append("fiscal_code")
        return res

    def _loader_params_pos_config(self):
        return super()._loader_params_pos_config()
