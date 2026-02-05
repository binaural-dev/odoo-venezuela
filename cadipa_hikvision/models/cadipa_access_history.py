from odoo import fields, models


class CadipaAccessHistory(models.Model):
    _name = "cadipa.access.history"
    _description = "CADIPA Access History"
    _order = "occurred_at desc"

    occurred_at = fields.Datetime(
        string="Date & Time",
        required=True,
        help="When the access attempt occurred.",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Person",
        required=True,
        ondelete="restrict",
        index=True,
        help="Member or beneficiary who attempted access.",
    )
    membership_id = fields.Many2one(
        "action.partner",
        string="Membership",
        ondelete="set null",
        index=True,
        help="Membership (action.partner) associated with this attempt.",
    )
    membership_number = fields.Char(
        string="Membership Number",
        index=True,
        help="Membership number for listing and search.",
    )
    device_id = fields.Many2one(
        "hikcentral.device",
        string="Device",
        ondelete="set null",
        index=True,
        help="Door/device where the attempt occurred.",
    )
    result = fields.Selection(
        [
            ("allowed", "Allowed"),
            ("pending_payment", "Pending Payment"),
            ("denied", "Denied"),
        ],
        string="Result",
        required=True,
        index=True,
    )
    access_status_code = fields.Char(
        string="Status Code",
        size=1,
        help="Code 1, 2 or 3 (aligned with realtime.message.config).",
    )
    reason = fields.Char(
        string="Reason",
        help="Message shown (e.g. Welcome, You must pay, Access denied).",
    )
    is_beneficiary = fields.Boolean(
        string="Is Beneficiary",
        default=False,
        help="True if the attempt was by a beneficiary; False if by the holder.",
    )
