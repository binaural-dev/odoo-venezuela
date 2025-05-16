from odoo import models, fields, api, _

import logging

_logger = logging.getLogger(__name__)


class PosOrderInherit(models.Model):
    _inherit = "pos.order"

    mf_reportz = fields.Char(string="Codigo de reporte Z", default=False, copy=False, readonly=True)
    fiscal_machine = fields.Char(
        string="Serial de Maquina fiscal", default=False, copy=False, readonly=True
    )
    mf_invoice_number = fields.Char(
        string="Sequencia en maquina fiscal", default=False, copy=False, readonly=True
    )

    def get_order_by_uid(self, uid):
        return self.env["pos.order"].search_read([("pos_reference", "ilike", uid)])

    @api.model
    def _order_fields(self, ui_order):
        res = super()._order_fields(ui_order)
        res["fiscal_machine"] = ui_order.get("fiscal_machine", False)
        res["mf_invoice_number"] = ui_order.get("mf_invoice_number", False)
        res["mf_reportz"] = ui_order.get("mf_reportz", False)
        return res

    def _export_for_ui(self, order):
        res = super()._export_for_ui(order)
        res["fiscal_machine"] = order.fiscal_machine
        res["mf_invoice_number"] = order.mf_invoice_number
        res["mf_reportz"] = order.mf_reportz
        return res

    def _prepare_invoice_vals(self):
        self.ensure_one()
        res = super()._prepare_invoice_vals()
        res["cashbox_id"] = self.config_id.id
        res["mf_serial"] = self.fiscal_machine
        res["mf_invoice_number"] = self.mf_invoice_number
        res["mf_reportz"] = self.mf_reportz
        res["iot_mf"] = self.config_id.iface_fiscal_data_module.id
        return res
