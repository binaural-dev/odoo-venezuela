from odoo import api, fields, models, _


class RetentionLineReport(models.Model):
    _name = "retention.line.report"
    _description = "Retention Analysis Report"
    _auto = False
    _rec_name = "number_count"
    _order = "number_count"

    number_count = fields.Integer()
    year = fields.Char()
    month = fields.Char()
    voucher = fields.Char(string="Voucher Number")
    vat = fields.Char()
    partner = fields.Char()
    invoice_number = fields.Char()
    invoice_correlative = fields.Char()
    retention_date = fields.Date()
    retention_date_accounting = fields.Date()
    raw_aliquot = fields.Char()
    aliquot = fields.Char(compute="_compute_percentages")
    iva_amount = fields.Float()
    invoice_amount = fields.Float()
    raw_retention_percentage = fields.Char()
    retention_percentage = fields.Char(compute="_compute_percentages")
    retention_amount = fields.Float()
    state = fields.Char()
    state_show = fields.Char()
    type = fields.Char()
    type_show = fields.Char()

    @property
    def _table_query(self):
        return self._query()

    def _query(self):
        return f"""
            SELECT {self._select()}
            FROM {self._from()}
            WHERE {self._where()}
        """

    def _select(self):
        base_vef_id = self.env["ir.model.data"]._xmlid_to_res_id(
            "base.VEF", raise_if_not_found=False
        )
        use_foreign_currency = self.env.company.currency_id.id != base_vef_id
        amounts_query = """
            rl.iva_amount AS iva_amount,
            rl.invoice_amount AS invoice_amount,
            rl.retention_amount AS retention_amount,
        """
        if use_foreign_currency:
            amounts_query = """
                rl.foreign_iva_amount AS iva_amount,
                rl.foreign_invoice_amount AS invoice_amount,
                rl.foreign_retention_amount AS retention_amount,
            """

        return (
            """
                rl.id,
                row_number() OVER () AS number_count,
                EXTRACT(YEAR FROM r.date)::VARCHAR AS year,
                EXTRACT(MONTH FROM r.date)::VARCHAR AS month,
                r.number AS voucher,
                CONCAT(p.prefix_vat, '-', p.vat) AS vat,
                p.name AS partner,
                i.name AS invoice_number,
                i.correlative AS invoice_correlative,
                r.date_accounting AS retention_date_accounting,
                r.date AS retention_date,
                rl.aliquot::VARCHAR AS raw_aliquot,
                w.value::VARCHAR AS raw_retention_percentage,"""
            + amounts_query
            + """
                r.state AS state,
                r.type AS type,
                (
                    CASE
                        WHEN r.state = 'draft' THEN 'Borrador'
                        WHEN r.state = 'emitted' THEN 'Emitido'
                        WHEN r.state = 'cancel' THEN 'Anulado'
                    END
                ) AS state_show,
                (
                    CASE
                        WHEN r.type = 'out_invoice' THEN 'Factura de Cliente'
                        WHEN r.type = 'in_invoice' THEN 'Factura de Proveedor'
                    END
                ) AS type_show
            """
        )

    def _from(self):
        return """
            account_retention r
            JOIN account_retention_line rl ON r.id = rl.retention_id
            JOIN account_move i ON rl.move_id = i.id
            JOIN res_partner p ON r.partner_id = p.id
            JOIN account_withholding_type w ON p.withholding_type_id = w.id
        """

    def _where(self):
        return """
            r.type_retention = 'iva'
        """

    @api.depends("raw_aliquot", "raw_retention_percentage")
    def _compute_percentages(self):
        for record in self:
            record.aliquot = f"{record.raw_aliquot}%"
            record.retention_percentage = f"{record.raw_retention_percentage}%"
