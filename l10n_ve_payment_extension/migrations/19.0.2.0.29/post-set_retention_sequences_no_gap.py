import logging

from odoo import _, api, SUPERUSER_ID


_logger = logging.getLogger(__name__)

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

    In a company where that mislabeled record was the *only* one carrying
    the IVA code, simply renaming its code would leave IVA with no counter
    at all: the next retention would fall into get_sequence_retention()'s
    `if not sequence:` branch and create a brand new one starting at 1,
    duplicating IVA control numbers already issued under the mislabeled
    sequence. Create the real IVA sequence for that company instead,
    continuing from the same (shared, conservative) counter so neither
    side resets.
    """
    IrSequence = env["ir.sequence"].with_context(active_test=False)
    candidates = IrSequence.search([("code", "=", "retention.iva.control.number")])
    mislabeled = candidates.filtered(lambda s: "municipal" in (s.name or "").lower())

    for sequence in mislabeled:
        company = sequence.company_id
        shared_next_actual = sequence.number_next_actual or 1
        has_other_iva_sequence = bool(
            (candidates - mislabeled).filtered(lambda s: s.company_id == company)
        )

        sequence.write({"code": "retention.municipal.control.number"})

        if not has_other_iva_sequence:
            new_iva_sequence = IrSequence.create({
                "name": _("Numero de control retenciones IVA"),
                "code": "retention.iva.control.number",
                "padding": 8,
                "company_id": company.id,
            })
            new_iva_sequence.number_next_actual = shared_next_actual
            _logger.info(
                "l10n_ve_payment_extension: renamed mislabeled sequence "
                "%r (id=%s, company=%r) from retention.iva.control.number "
                "to retention.municipal.control.number, and created a new "
                "IVA sequence (id=%s) for that company continuing from "
                "counter %s to avoid resetting the fiscal correlative.",
                sequence.name, sequence.id, company.display_name,
                new_iva_sequence.id, shared_next_actual,
            )


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
