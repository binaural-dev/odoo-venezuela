"""Make the tax units (tax.unit) global: remove their company.

What: sets tax_unit.company_id to NULL on every row and drops its NOT NULL constraint. The field
    is gone from the model in this version, so at the end of the upgrade the ORM removes the
    column together with its ir.model.fields record.

Why: the tax unit (UT) is a national value set by SENIAT and applies to every company. Until this
    version tax.unit.company_id was required and read-only and took the active company on create,
    so the UTs stayed tied to the company that created them (in Donarca, to Pedrera Santa Rosa)
    and could not be changed from the interface. The publish date is already unique globally, so
    another company could not register its own UT for the same date either. Retention
    computations never filtered the UT by company; this only removes the misleading link.

If it does not run: the column keeps its NOT NULL constraint until the ORM drops it at the end of
    the upgrade, and any tax.unit created during the upgrade itself would fail with a NOT NULL
    error because the model no longer fills company_id.

How to revert: it is not reverted. The company was only the one active when each UT was created;
    it carried no business meaning.

Ticket: https://binaural.odoo.com/odoo/my-tickets/15581
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'tax_unit' AND column_name = 'company_id'"
    )
    if not cr.fetchone():
        return

    cr.execute("ALTER TABLE tax_unit ALTER COLUMN company_id DROP NOT NULL")
    cr.execute("UPDATE tax_unit SET company_id = NULL WHERE company_id IS NOT NULL")
    _logger.info(
        "l10n_ve_accountant pre-migrate: %s tax.unit row(s) left without company (global UT)",
        cr.rowcount,
    )
