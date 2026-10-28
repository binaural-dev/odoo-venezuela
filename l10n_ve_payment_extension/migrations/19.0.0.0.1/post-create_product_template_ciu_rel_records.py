"""Moves the `ciu_id` backed up by the `pre-` into the Many2many table and drops the temporary one.

Why: closes the Many2one → Many2many conversion that the sibling `pre-` started. It only does
    something if that `pre-` found a `ciu_id` to back up, i.e. on a client that comes from a
    version before the conversion; on one that comes from 17 there is no temporary column and
    this is a no-op.
If it does not run: the `temp_ciu_id` column is left dangling in `product_template` with the old
    values and **the Many2many relation stays empty**: products lose their economic activity
    (CIU) and with it the ISLR withholding calculation, without any visible error.
How to revert: the data stays in `temp_ciu_id` until this script drops it; after that, it is
    rebuilt from `product_template_ciu_rel`, which is already the final destination.

The `DELETE` is **limited to the templates being migrated**. The original version deleted the
whole `product_template_ciu_rel` without a filter, which would wipe out any relation that the
module or the user had created on products unrelated to this conversion.

Task: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    if not util.column_exists(cr, "product_template", "temp_ciu_id"):
        _logger.info("there is no temp_ciu_id: the pre- found nothing to convert. Nothing to do.")
        return

    if not util.table_exists(cr, "product_template_ciu_rel"):
        _logger.warning(
            "temp_ciu_id exists but the product_template_ciu_rel table does not: the ciu_ids "
            "field was never created. temp_ciu_id is kept so the data is not lost, and nothing is "
            "converted."
        )
        return

    cr.execute(
        """
        DELETE FROM product_template_ciu_rel
         WHERE product_template_id IN (
               SELECT id FROM product_template WHERE temp_ciu_id IS NOT NULL
         )
        """
    )
    deleted = cr.rowcount

    cr.execute(
        """
        INSERT INTO product_template_ciu_rel (product_template_id, ciu_id)
        SELECT id, temp_ciu_id FROM product_template WHERE temp_ciu_id IS NOT NULL
        """
    )
    inserted = cr.rowcount

    cr.execute("ALTER TABLE product_template DROP COLUMN IF EXISTS temp_ciu_id")

    _logger.info(
        "ciu_id -> ciu_ids: %s relations created (%s replaced)", inserted, deleted
    )
    if inserted:
        util.add_to_migration_reports(
            "l10n_ve_payment_extension: the economic activity (CIU) of the products changed from "
            "Many2one to Many2many: %s relations created." % inserted,
            category="Binaural · Accounting",
        )
