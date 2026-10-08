"""Post-migration for l10n_ve_rate: v17 -> v19.

The column rename itself already happened in pre-migrate.py. This step
only validates the result against a NEW constraint introduced in v19,
res.company._check_foreign_currency_id(), which forbids
foreign_currency_id == currency_id. That constraint did not exist in
v17, so it is possible (if unlikely) for a company migrated from v17 to
already be in a state that would fail it on the next write. We don't
want the upgrade itself to fail on this -- we log it so it can be fixed
by hand before it surprises someone mid-write.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        SELECT id, name FROM res_company
        WHERE foreign_currency_id IS NOT NULL
          AND foreign_currency_id = currency_id
        """
    )
    offenders = cr.fetchall()
    if not offenders:
        _logger.info(
            "l10n_ve_rate post-migrate: no company has foreign_currency_id == "
            "currency_id, the new v19 constraint is already satisfied"
        )
        return

    _logger.warning(
        "l10n_ve_rate post-migrate: %s compan%s currently ha%s "
        "foreign_currency_id equal to currency_id, which violates the v19 "
        "constraint res.company._check_foreign_currency_id() and will block "
        "the next write to that record: %s. Fix manually before it blocks "
        "a user.",
        len(offenders),
        "y" if len(offenders) == 1 else "ies",
        "s" if len(offenders) == 1 else "ve",
        offenders,
    )
