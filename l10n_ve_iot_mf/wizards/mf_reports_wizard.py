from odoo import fields, models, _
from odoo.exceptions import ValidationError


class MfReportsWizard(models.TransientModel):
    _name = "l10n_ve.mf.reports.wizard"
    _description = "Fiscal Machine Reports Wizard"

    date_from = fields.Date(required=True, default=fields.Date.today)
    date_to = fields.Date(required=True, default=fields.Date.today)

    def _validate_date_range(self):
        self.ensure_one()
        if self.date_to < self.date_from:
            raise ValidationError(_("Date To must be greater than or equal to Date From."))

    def get_date_range_payload(self):
        self.ensure_one()
        self._validate_date_range()
        return {
            "date_from": self.date_from.strftime("%d%m%y"),
            "date_to": self.date_to.strftime("%d%m%y"),
        }
