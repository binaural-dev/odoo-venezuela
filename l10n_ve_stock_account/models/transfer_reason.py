from odoo import models, fields


class TransferReason(models.Model):
    _name = "transfer.reason"
    _description = """
    Reasons for Stock Transfer

    This model stores the possible reasons for stock transfers (e.g., Sale, Donation, Return).
    The records in this model are created via data files (XML/CSV) and should not be modified by users.
    The reasons are used to categorize stock movements and are dynamically filtered based on the context of the transfer.
    """

    name = fields.Char(
        string="Reason",
        required=True,
        help="The name of the transfer reason (e.g., Sale, Donation, Return).",
    )
    code = fields.Char(
        string="Code",
        required=True,
        help="A unique code to identify the transfer reason.",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Indicates whether the transfer reason is active or archived.",
    )
