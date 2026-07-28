from odoo import http
from odoo.http import request
from io import StringIO


class GenerateTxt(http.Controller):
    @http.route("/web/binary/download_retention_iva_txt", type="http", auth="user")
    def download_retention_iva_txt(self, date_start, date_end, company_id, **kw):
        report_obj = request.env["wizard.retention.iva"]
        domain = report_obj._get_iva_retention_domain(
            date_start, date_end, int(company_id)
        )
        retentions = request.env["account.retention"].search(
            domain,
            order="date_accounting asc, number asc, id asc",
        )

        data = report_obj._retention_iva(retentions)
        f = StringIO()
        for l in data:
            f.write(l.get("RIF del agente de retención") + "\t")
            f.write(str(l.get("Período impositivo")) + "\t")
            f.write(l.get("Fecha de factura") + "\t")
            f.write(l.get("Tipo de operación") + "\t")
            f.write(l.get("Tipo de documento") + "\t")
            f.write(l.get("RIF de proveedor") + "\t")
            f.write(str(l.get("Número de documento")) + "\t")
            f.write(l.get("Número de control") + "\t")
            f.write(str("{:.2f}".format(l.get("Monto total del documento"))) + "\t")
            f.write(str("{:.2f}".format(l.get("Base imponible"))) + "\t")
            f.write(str("{:.2f}".format(l.get("Monto del Iva Retenido"))) + "\t")
            f.write(str(l.get("Número del documento afectado")) + "\t")
            f.write(str(l.get("Número de comprobante de retención")) + "\t")
            f.write(str("{:.2f}".format(l.get("Monto exento del IVA"))) + "\t")
            f.write(str("{:.2f}".format(l.get("Alícuota"))) + "\t")
            f.write(l.get("Número de Expediente"))
            f.write("\n")
        f.flush()
        f.seek(0)
        return request.make_response(
            f,
            [
                ("Content-Type", "text/plain"),
                ("Content-Disposition", "attachment; filename=retenciones_iva.txt"),
            ],
        )
