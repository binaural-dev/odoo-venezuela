from odoo import api, models, fields, _


class AccountRetention(models.Model):
    _name = "account.retention"
    _description = "Retention"
    _rec_name = "name"
    _check_company_auto = True

    def sequence_iva_retention(self):
        sequence = self.env['ir.sequence'].search([('code', '=', 'retention.iva.control.number')])
        if not sequence:
            sequence = self.env['ir.sequence'].create({
                'name': 'Numero de control',
                'code': 'retention.iva.control.number',
                'padding': 5
            })
        return sequence
    
    def sequence_islr_retention(self):
        sequence = self.env['ir.sequence'].search([('code', '=', 'retention.islr.control.number')])
        if not sequence:
            sequence = self.env['ir.sequence'].create({
                'name': 'Numero de control',
                'code': 'retention.islr.control.number',
                'padding': 5
            })
        return sequence

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )
    name = fields.Char(
        "Description",
        size=64,
        states={"draft": [("readonly", False)]},
        help="Descripción del Comprobante",
    )
    code = fields.Char(
        size=32,
        states={"draft": [("readonly", False)]},
        help="Referencia del Comprobante",
    )
    state = fields.Selection(
        [("draft", "Borrador"), ("emitted", "Emitida"), ("cancel", "Cancelada")],
        index=True,
        default="draft",
        help="Estatus del Comprobante",
    )
    retention_type = fields.Selection(
        [
            ("iva", "IVA"),
            ("islr", "ISLR"),
        ],
        "Tipo de retención",
    )
