from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    tax_authorities_logo = fields.Image(max_width=128, max_height=128)
    tax_authorities_name = fields.Char()
    economic_activity_number = fields.Char()

    iva_supplier_retention_journal_id = fields.Many2one(
        "account.journal",
        string="Journal for Supplier I.V.A Retentions",
    )
    iva_customer_retention_journal_id = fields.Many2one(
        "account.journal",
        string="Journal for Customer I.V.A Retentions",
    )

    islr_supplier_retention_journal_id = fields.Many2one(
        "account.journal",
        string="Journal for Supplier I.S.L.R Retentions",
    )
    islr_customer_retention_journal_id = fields.Many2one(
        "account.journal",
        string="Journal for Customer I.S.L.R Retentions",
    )

    municipal_supplier_retention_journal_id = fields.Many2one(
        "account.journal",
        string="Journal for Supplier Municipal Retentions",
    )
    municipal_customer_retention_journal_id = fields.Many2one(
        "account.journal",
        string="Journal for Customer Municipal Retentions",
    )

    condition_withholding_id = fields.Many2one(
        "account.withholding.type",
        string="The condition of this taxpayer requires the withholding of",
    )

    code_visible = fields.Boolean(string="See payment concept code")

    hide_patent_columns_extra = fields.Boolean(
        string="Hide extra columns in Patent Municipal Report related to advances",
        default=False,
    )
    create_retentions_of_suppliers_in_draft = fields.Boolean(
        string="Create Suppliers Retentions in Draft", default=False
    )

    hide_issue_date_of_municipal_withholding_receipt = fields.Boolean('Hide issue date of municipal withholding receipt',default=False)
    
    text_header_1_municipal_retention = fields.Text(
        string="Header 1 for voucher of municipal retention", 
        default="Comprobante emitido en cumplimiento de la Providencia Administrativa N° 001-2024 sobre la Designación de Sujetos Pasivos Especiales y Agentes de Retención del Impuesto sobre Actividades Económicas,"
    )
    text_header_2_municipal_retention = fields.Text(
        string="Header 2 for voucher of municipal retention", 
        default="Industria, Comercio, Servicios o de Índole Similar en el Municipio Libertador del Distrito Capital, publicada en la Gaceta Municipal N° 5030 del 08/02/2024."
    )
