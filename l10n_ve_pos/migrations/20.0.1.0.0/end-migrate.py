"""Drop the plan of the merge of the payment methods (ADR-023).

``pre-migrate.py`` leaves ``l10n_ve_pos_method_merge`` and the ``post-migrate.py``
of ``l10n_ve_pos``, ``l10n_ve_pos_igtf`` and ``l10n_ve_pos_mf`` read it, in the
order the modules happen to update. ``end-`` scripts run once every module of the
update is loaded, so this is the first point where nobody needs the table any more.

The table is kept when a plan was not applied, or when one of the modules that
read it is installed and has not been migrated yet (it is updated in another run).
"""
import logging

_logger = logging.getLogger(__name__)

READERS = ("l10n_ve_pos_igtf", "l10n_ve_pos_mf")


def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT to_regclass('l10n_ve_pos_method_merge')")
    if not cr.fetchone()[0]:
        return
    cr.execute("SELECT COUNT(*) FROM l10n_ve_pos_method_merge WHERE NOT done")
    if cr.fetchone()[0]:
        _logger.warning(
            "l10n_ve_pos: the merge of the payment methods is not applied, "
            "the table l10n_ve_pos_method_merge is kept"
        )
        return
    cr.execute(
        """
        SELECT name
          FROM ir_module_module
         WHERE name IN %s
           AND state IN ('installed', 'to upgrade')
           AND latest_version NOT LIKE '20.%%'
        """,
        (READERS,),
    )
    pending = [row[0] for row in cr.fetchall()]
    if pending:
        _logger.warning(
            "l10n_ve_pos: %s still have to migrate from Odoo 19 and read "
            "l10n_ve_pos_method_merge, the table is kept",
            pending,
        )
        return
    cr.execute("DROP TABLE l10n_ve_pos_method_merge")
    _logger.info("l10n_ve_pos: table l10n_ve_pos_method_merge dropped")
