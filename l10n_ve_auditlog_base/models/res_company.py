from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    log_outgoing_requests = fields.Selection(
        [("errors_only", "Log Only Failed Requests"),
         ("all", "Log All Outgoing Requests")],
        string="Outgoing Request Logging",
        default="errors_only",
        help="Controls how outgoing HTTP requests are logged. "
             "'Log Only Failed Requests' records only failed requests; "
             "'Log All Outgoing Requests' records both successful and failed requests.",
    )
    response_body_max_chars = fields.Integer(
        "Response Body Max Chars",
        default=0,
        help="Maximum characters to store for the response body. "
             "Set to 0 to store the full response without truncation.",
    )
