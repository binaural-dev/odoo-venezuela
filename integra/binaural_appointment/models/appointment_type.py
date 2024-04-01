import logging

from odoo import Command, _, api, fields, models

_logger = logging.getLogger(__name__)
class AppointmentType(models.Model):
    _inherit = "appointment.type"

    product_id = fields.Many2one(
        "product.product",
        string="Related Product",
        domain="[('is_appointment', '=', True),('sale_ok', '=', True)]",
        required=True,
    )

    invoice_ids = fields.Many2many(
        "account.move",
        compute="_compute_invoice_ids",
    )

    prefix_vat = fields.Selection(
        [
            ("V", "V"),
            ("E", "E"),
            ("J", "J"),
            ("G", "G"),
            ("P", "P"),
            ("C", "C"),
        ],
        string="Prefix VAT",
        default="V",
        help="Prefix of the VAT number",
    )

    vat = fields.Char(
        string="Tax ID",
        index=True,
        help="The Tax Identification Number. Values here will be validated based on the country format. You can use '/' to indicate that the partner is not subject to tax.",
    )

    time_limit = fields.Float(
        string='Time Limit (hours)',
        related='product_id.time_limit'
    )
    
    block_appointment = fields.Integer(
        string='Block Appointment',
        related='product_id.block_appointment'
    )

    invoice_create = fields.Boolean(
        string="Create Invoices",
        help="For each scheduled appointment, create a new invoices and assign it to the responsible user with state draft."
    )

    @api.depends('meeting_ids')
    def _compute_invoice_ids(self):
        for record in self:
            record.invoice_ids = record.meeting_ids.invoice_ids.ids

    def action_invoice_ids(self):
        self.ensure_one()

        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
        action['domain'] = [('id', 'in', self.invoice_ids.ids)]

        return action