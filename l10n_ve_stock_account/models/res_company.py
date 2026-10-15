import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# Codigos de los motivos que `stock.picking._compute_allowed_reason_ids` permite
# en traslados internos (rama "Internal"). Si ese compute agrega o quita un
# motivo interno, actualizar esta tupla: la usan el dominio del campo, el de
# Ajustes y `_get_default_internal_transfer_reason`, y
# test_field_domain_matches_allowed_reasons_for_internal falla si divergen.
INTERNAL_TRANSFER_REASON_CODES = ("consignment", "transfer", "other_causes")


class ResCompany(models.Model):
    _inherit = "res.company"

    customer_journal_id = fields.Many2one(
        "account.journal",
        string="Customer Journal",
        help="To add customer journal",
    )
    vendor_journal_id = fields.Many2one(
        "account.journal",
        string="Vendor Journal",
        help="To add vendor journal",
    )

    internal_consigned_journal_id = fields.Many2one(
        "account.journal",
        string="Internal Journal",
        help="To add internal journal",
    )

    invoice_cron_type = fields.Selection(
        [("last_business_day", _("Last Business Day")), ("last_day", _("Last Day"))],
        string="Date Cron Invoice",
        default="last_business_day",
        required=True,
    )

    invoice_cron_time = fields.Float(required=True, default=18.0)

    indexed_dispatch_guide = fields.Boolean(
        string="Indexed Dispatch Guide",
        default=False,
        help="If enabled, dispatch guide amounts will use the date of the stock picking for currency conversion.",
    )
    
    hide_weight_field_dispatch_guide = fields.Boolean(
        string="Hide weight field in dispatch guide",
        default=False,
        help="If enabled, the weight field will be hidden in the dispatch guide.",
    )

    internal_transfer_reason_id = fields.Many2one(
        "transfer.reason",
        string="Default Internal Transfer Reason",
        domain=[("code", "in", INTERNAL_TRANSFER_REASON_CODES)],
        help="Reason prefilled on new internal transfers. It can be changed per transfer.",
    )

    group_dispatch_note_print = fields.Boolean(string="Print Dispatch Note")
