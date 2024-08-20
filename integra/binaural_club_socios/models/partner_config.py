from odoo import api, fields, models, _
import re

image_re = re.compile(r"data:(image/[A-Za-z]+);base64,(.*)")
EMAIL_PATTERN = "([^ ,;<@]+@[^> ,;]+)"

class PartnerConfig(models.Model):
    _name = "partner.config"
    _rec_name = "company_id"

    _sql_constraints = [
        (
            "code_company_uniq_debt",
            "unique (company_id)",
            "La configuración de miembro.",
        ),
    ]

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    active = fields.Boolean(default=True, string="Active")
    years_of_membership = fields.Integer(string="Years of membership", required=True)
    day_end_date_payment = fields.Integer(string="Cut of day", required=True)
    age_limit_for_associated_children = fields.Integer(
        string="Age limit for associated children", required=True
    )
    previous_days_alert_associates = fields.Integer(
        string="Prior days for family member partnership alert",
        required=True,
    )

    out_email_alert_associates = fields.Char(
        string="Outgoing mail for partner alert"
    )

    expiration_alert_subject = fields.Char(string="Expiration Alert Mail Subject")
    expiration_alert_body = fields.Html(
        string="Expiration alert mail body", sanitize_attributes=False
    )

    extension_alert_subject = fields.Char(string="Extension Alert Mail Subject")
    extension_alert_body = fields.Html(
        string="Extension alert mailing body", sanitize_attributes=False
    )

    signature = fields.Binary(string="Signature")

    is_postpaid = fields.Boolean()