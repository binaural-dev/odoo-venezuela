from odoo import api, SUPERUSER_ID


RETENTION_SEQUENCE_CODES = [
    "retention.iva.control.number",
    "retention.islr.control.number",
    "retention.municipal.control.number",
]


def migrate(cr, installed_version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    sequences = env["ir.sequence"].search([("code", "in", RETENTION_SEQUENCE_CODES)])
    for sequence in sequences:
        if sequence.implementation == "no_gap":
            continue
        # Read the real next value predicted from the PostgreSQL sequence
        # (number_next_actual) *before* switching implementation, since
        # dropping the PG sequence in write() does not carry it over to
        # the table-based counter that 'no_gap' reads from (number_next).
        next_actual = sequence.number_next_actual or 1
        sequence.write(
            {
                "implementation": "no_gap",
                "number_next_actual": next_actual,
            }
        )
