import logging

from odoo import api, SUPERUSER_ID


_logger = logging.getLogger(__name__)

RETENTION_SEQUENCE_CODES = [
    "retention.iva.control.number",
    "retention.islr.control.number",
    "retention.municipal.control.number",
]


def _normalize_mislabeled_municipal_sequences(env):
    """The old get_sequence_municipal_retention() had a copy/paste bug that
    created the "Municipal" sequence with the IVA code
    (retention.iva.control.number) instead of its own -- and it did so on
    every municipal retention that needed one, so a company that hit this
    path can have *several* mislabeled records, not just one. Any of them
    could be silently returned by a plain search()/limit=1 for the IVA
    code instead of the real IVA counter. Fix the code on all mislabeled
    records for a company in one pass, before anything else touches
    implementation.

    If none of a company's IVA-coded records is the real one (i.e. every
    single one is a mislabeled municipal record), renaming them all would
    leave IVA with no counter at all: the next retention would fall into
    get_sequence_retention()'s `if not sequence:` branch and create a
    brand new one starting at 1, duplicating IVA control numbers already
    issued under the mislabeled sequence(s). Create the real IVA sequence
    for that company instead, continuing from the highest counter among
    the mislabeled records (conservative: nothing goes backward).
    """
    IrSequence = env["ir.sequence"].with_context(active_test=False)
    candidates = IrSequence.search([("code", "=", "retention.iva.control.number")])
    mislabeled = candidates.filtered(lambda s: "municipal" in (s.name or "").lower())
    if not mislabeled:
        return

    real_iva_sequences = candidates - mislabeled
    companies_with_real_iva = set(real_iva_sequences.mapped(lambda s: s.company_id.id))

    # Iterate distinct company ids (including False/no-company) rather than
    # mapped("company_id"), which silently drops empty relations -- a
    # mislabeled record without a company would otherwise never get fixed.
    for company_id in set(mislabeled.mapped(lambda s: s.company_id.id)):
        company = env["res.company"].browse(company_id) if company_id else env["res.company"]
        company_mislabeled = mislabeled.filtered(lambda s: s.company_id.id == company_id)
        max_next_actual = max(
            (seq.number_next_actual or 1) for seq in company_mislabeled
        )
        company_mislabeled.write({"code": "retention.municipal.control.number"})
        # get_sequence_retention()'s order="id asc" makes the lowest-id
        # record the one actually used going forward; raise its counter to
        # the shared max too (harmless if it was already there) so a fiscal
        # correlative never ends up lower than one already issued under a
        # sibling mislabeled record.
        company_mislabeled.sorted("id")[:1].number_next_actual = max_next_actual

        created_iva_id = None
        if company_id not in companies_with_real_iva:
            new_iva_sequence = IrSequence.create({
                "name": "Numero de control retenciones IVA",
                "code": "retention.iva.control.number",
                "padding": 8,
                "company_id": company_id,
            })
            new_iva_sequence.number_next_actual = max_next_actual
            created_iva_id = new_iva_sequence.id

        _logger.info(
            "l10n_ve_payment_extension: renamed %s mislabeled sequence(s) "
            "%s (company=%s) from retention.iva.control.number to "
            "retention.municipal.control.number.%s",
            len(company_mislabeled),
            company_mislabeled.ids,
            company.display_name,
            (
                " Created a new IVA sequence (id=%s) for that company "
                "continuing from counter %s to avoid resetting the fiscal "
                "correlative." % (created_iva_id, max_next_actual)
            ) if created_iva_id else "",
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
