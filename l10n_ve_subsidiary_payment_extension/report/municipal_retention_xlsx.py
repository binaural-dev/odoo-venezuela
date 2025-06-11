from odoo import models

class MunicipalRetentionXlsx(models.AbstractModel):
    _inherit = "municipal.retention.xlsx"

    def _get_tax_authorities_record(self, company, retention_id):
        if not self.env.company.use_subsidiary_with_multiple_municipalities:
            return super()._get_tax_authorities_record(company, retention_id)
        retention = self.env["account.retention"].browse(retention_id)
        return retention.retention_line_ids[0].account_analytic_id
