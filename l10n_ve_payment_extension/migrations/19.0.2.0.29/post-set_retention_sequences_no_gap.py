from odoo import api, SUPERUSER_ID


RETENTION_SEQUENCE_CODES = [
    "retention.iva.control.number",
    "retention.islr.control.number",
    "retention.municipal.control.number",
]


def _normalize_mislabeled_municipal_sequences(env):
    """The old get_sequence_municipal_retention() had a copy/paste bug that
    created the "Municipal" sequence with the IVA code
    (retention.iva.control.number) instead of its own. Instances that hit
    that path ended up with two ir.sequence records sharing the IVA code,
    so a plain search()/limit=1 for it could silently return the
    mislabeled municipal counter instead of the real IVA one. Fix the code
    on the mislabeled record(s) before anything else touches implementation.
    """
    candidates = env["ir.sequence"].with_context(active_test=False).search(
        [("code", "=", "retention.iva.control.number")]
    )
    mislabeled = candidates.filtered(lambda s: "municipal" in (s.name or "").lower())
    if mislabeled:
        mislabeled.write({"code": "retention.municipal.control.number"})


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _normalize_mislabeled_municipal_sequences(env)

    sequences = env["ir.sequence"].with_context(active_test=False).search(
        [("code", "in", RETENTION_SEQUENCE_CODES)]
    )
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
