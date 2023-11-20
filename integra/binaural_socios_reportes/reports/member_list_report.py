from odoo import api, models, _
from odoo.exceptions import UserError
from datetime import date


class ReportMemberList(models.AbstractModel):
    _name = "report.binaural_socios_reportes.member_list"

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
            raise UserError(_("Report Form Error"))
        state_partner = form.get("status", False)
        state_action = form.get("state_action", False)
        search_domain = []
        if state_partner and state_partner != "all":
            search_domain += [("state_partner", "=", state_partner)]
        if state_action and state_action != "all":
            search_domain += [("state_action", "=", state_action)]
        search_domain += [
            ("active", "=", True),
            ("parent_id", "=", False),
            ("customer_rank", ">", 0),
            ("action_number", "!=", False),
        ]
        docs = self.env["res.partner"].sudo().search(search_domain)
        return {
            "data": data["form"],
            "docs": docs,
            "date": date.today(),
            "name_user": name_user,
        }
