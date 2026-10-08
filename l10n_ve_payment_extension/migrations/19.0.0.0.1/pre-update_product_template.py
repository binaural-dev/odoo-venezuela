"""Backs up `product_template.ciu_id` (M2O) before the new schema removes it.

Why: `ciu_id` changed from Many2one to Many2many (`ciu_ids`, table `product_template_ciu_rel`).
    The old value is copied to a temporary column because the sibling `post-` is the one that can
    write into the relation table, and by then the original column is gone.
    **This conversion dates from the 16→17 era**: the folder lived in `migrations/16.0.18.0/` and,
    because of its version, it never ran (B1.5 renamed it to `19.0.0.0.1`, which does run). Any
    client that comes from 17 already has it done — `ciu_ids` has been Many2many since then and
    the relation table already exists. That is why the guard below is not cosmetic: it is the
    normal path.
If it does not run: on a client that **does** still have the M2O, the economic activity (CIU) of
    each product is lost, and it is what determines the ISLR withholding. On a client that comes
    from 17 nothing runs because there is nothing to convert.
How to revert: `ALTER TABLE product_template DROP COLUMN temp_ciu_id`. `ciu_id` is not touched.

Task: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:  # clean install: it is born with the Many2many
        return

    if not util.column_exists(cr, "product_template", "ciu_id"):
        _logger.info(
            "product_template.ciu_id does not exist: the conversion to Many2many is already done "
            "(client that comes from 17 or later). Nothing to back up."
        )
        return

    util.create_column(cr, "product_template", "temp_ciu_id", "int4")
    cr.execute("UPDATE product_template SET temp_ciu_id = ciu_id WHERE ciu_id IS NOT NULL")
    _logger.info("product_template.ciu_id backed up in temp_ciu_id: %s rows", cr.rowcount)
