from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    igtf_note_debit_mode = fields.Selection(
        [
            ("inline", "Line in the same journal entry (current flow)"),
            ("debit_note", "Automatic Fiscal Debit Note (new flow)"),
        ],
        string="IGTF Perception Mode",
        compute="_compute_igtf_note_debit_config",
        inverse="_inverse_igtf_note_debit_config",
    )
    igtf_note_debit_product_id = fields.Many2one(
        "product.product",
        string="IGTF Perception Product",
        compute="_compute_igtf_note_debit_config",
        inverse="_inverse_igtf_note_debit_config",
    )
    igtf_note_debit_include_in_payment_default = fields.Boolean(
        related="company_id.igtf_note_debit_include_in_payment_default", readonly=False,
    )
    igtf_note_debit_vef_journal_id = fields.Many2one(
        related="company_id.igtf_note_debit_vef_journal_id", readonly=False,
    )
    igtf_note_debit_valid_product_ids = fields.Json(
        related="company_id.igtf_note_debit_valid_product_ids",
    )
    igtf_note_debit_valid_journal_ids = fields.Json(
        related="company_id.igtf_note_debit_valid_journal_ids",
    )

    @api.depends("company_id")
    def _compute_igtf_note_debit_config(self):
        for wizard in self:
            wizard.igtf_note_debit_mode = wizard.company_id.igtf_note_debit_mode
            wizard.igtf_note_debit_product_id = wizard.company_id.igtf_note_debit_product_id

    def _inverse_igtf_note_debit_config(self):
        for wizard in self:
            wizard.company_id.write({
                "igtf_note_debit_mode": wizard.igtf_note_debit_mode,
                "igtf_note_debit_product_id": wizard.igtf_note_debit_product_id.id,
            })
