from odoo import api, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    @api.model
    def _load_pos_self_data_fields(self, pos_config_id):
        """Expone al cliente del Kiosko los campos de configuración de la
        máquina fiscal.

        ``l10n_ve_pos_mf`` ya los inyecta en el loader de CAJA
        (``pos.config._load_pos_data_fields``), pero el Kiosko usa un loader
        propio con lista EXPLÍCITA de campos
        (``pos_self_order``.``pos.config._load_pos_self_data_fields``) que no
        los incluye. Se replican aquí para que el armado del payload fiscal y
        el botón de conexión al puerto funcionen igual en el bundle del Kiosko.

        ``receipt_header``/``receipt_footer`` son campos nativos de ``pos.config``
        que ``_extractReceiptLines`` usa para el encabezado/pie del comprobante
        fiscal; el loader del Kiosko tampoco los trae por defecto.
        """
        fields_list = list(super()._load_pos_self_data_fields(pos_config_id))
        fiscal_fields = [
            "serial_machine",
            "flag_21",
            "traditional_line",
            "has_cashbox",
            "access_button_mf",
            "message_in_head",
            "enable_auto_sync",
            "auto_sync_interval",
            "mf_skip_invoice_pdf",
            "receipt_header",
            "receipt_footer",
        ]
        for field_name in fiscal_fields:
            if field_name not in fields_list:
                fields_list.append(field_name)
        return fields_list
