import time
from odoo import api, models, _
from odoo.exceptions import UserError
from datetime import date


class ReportAllPayments(models.AbstractModel):
    _name = "report.l10n_ve_accountant.financial_all_payments"

    @api.model
    def _get_report_values(self, docids, data=None):
        if (
            not data.get("form")
            or not self.env.context.get("active_model")
            or not self.env.context.get("active_id")
        ):
            raise UserError(_("Form content is missing, this report cannot be printed."))
        ctx = data.get("context", False)
        name_user = ""
        if ctx:
            uid = ctx.get("uid")
            obj_uid = self.env["res.users"].sudo().search([("id", "=", uid)])
            if obj_uid:
                name_user = obj_uid.name
        form = data.get("form", False)
        if not form:
            raise UserError("Error en formulario de reporte")
        pt = form.get("payment_type")
        journal = self.env["account.journal"].sudo().search([("id", "=", form.get("journal_id"))])
        search_domain = []
        search_domain += [("payment_type", "=", pt)]
        search_domain += [("journal_id", "=", form.get("journal_id"))]
        search_domain += [("date", ">=", form.get("start_date"))]
        search_domain += [("date", "<=", form.get("end_date"))]

        docs = self.env["account.payment"].sudo().search(search_domain)

        return {
            "data": data["form"],
            "docs": docs,
            "date": date.today(),
            "payment_type": "A Proveedores" if pt == "outbound" else "De Clientes",
            "journal": journal.name,
            "name_user": name_user,
        }
