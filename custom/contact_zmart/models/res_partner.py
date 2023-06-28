from odoo import models, fields, api, _

class ResPartner(models.Model):
    _inherit = "res.partner"

    nit = fields.Char()
    sales_area = fields.Many2one('res.partner.sale')
    commercial_register = fields.Many2many(
        'ir.attachment',
        'commercial_register_rel',
        'commercial_register_id',
        'attachment_id'
    )
    rif = fields.Many2many(
        'ir.attachment',
        'rif_rel',
        'rif_id',
        'attachment_id'
    )
    legal_representante = fields.Many2many(
        'ir.attachment',
        'legal_representante_rel',
        'legal_representante_id',
        'attachment_id'
    )
    commercial_reference = fields.Many2many(
        'ir.attachment',
        'commercial_reference_rel',
        'commercial_reference_id',
        'attachment_id'
    )
    bank_reference = fields.Many2many(
        'ir.attachment',
        'bank_reference_rel',
        'bank_reference_id',
        'attachment_id'
    )
    other = fields.Many2many(
        'ir.attachment',
        'other_rel',
        'other_id',
        'attachment_id'
    )