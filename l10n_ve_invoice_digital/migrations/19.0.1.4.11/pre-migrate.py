"""Drop the hard DB-level unique constraint on account_journal.tfhka_serie_id.

What: removes the Postgres UNIQUE constraint account_journal_tfhka_serie_id_uniq,
    added by the previous version's _sql_constraints, before this version's code
    (which no longer declares it) loads.

Why: two journals sharing a TFHKA series is now allowed when one of them is the
    third-party invoicing journal (see account.journal._check_tfhka_serie_id_not_shared
    and _tfhka_serie_sharing_is_allowed) -- a Python-level check can make that
    exception, a raw DB constraint cannot. Odoo only CREATES constraints declared
    in _sql_constraints on module update, it never DROPs ones that disappear from
    the code, so the old constraint would keep silently blocking that exact case
    even after this version's code is meant to allow it (with a warning instead).

If it does not run: a third-party journal sharing a series with its parent still
    fails with a raw IntegrityError at the database level, before the new Python
    constraint (which only warns for that pair, and blocks everyone else) ever runs.

How to revert: re-declare the tuple in account.journal._sql_constraints; Odoo
    recreates the constraint on the next -u.
"""


def migrate(cr, version):
    cr.execute(
        "ALTER TABLE account_journal "
        "DROP CONSTRAINT IF EXISTS account_journal_tfhka_serie_id_uniq"
    )
