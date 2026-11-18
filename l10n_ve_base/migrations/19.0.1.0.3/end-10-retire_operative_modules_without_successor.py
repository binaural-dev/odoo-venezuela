"""Uninstall the modules of the v17 operativa line that have no successor in 19.

What: marks as "to remove" the modules of _common.MODULES_WITHOUT_SUCCESSOR that are installed,
    together with the installed modules that depend on them; Odoo uninstalls them at the end of
    the -u (step 5 of load_modules), and their records go with them. Same pattern as 19.0.1.0.2
    end-10. Before that it copies to l10n_ve_base_migration_v17_backup the members of their
    groups, which the uninstall deletes; their fields were already backed up by the conversion
    of the operativa line (migrations/_common.py). The modules of _common.MODULES_RETIRED_ALONE
    are retired without that cascade, and only when no other installed module depends on them;
    otherwise they are kept and the report says which modules hold them.

Why: these modules only existed in integra-addons 16.0/17.0 and nothing replaces them in 19.
    Left installed, Odoo keeps applying their views once their code is gone and the forms they
    extend fail.
    - binaural_base (retired alone): a binaural flag on the modules list and the binauralbot_url
      parameter, from the v16 operativa line. Left 'to upgrade' without code, every update logged
      it as a module with inconsistent states (castic_19_operativo). It is the root of the
      operativa line, so a cascade could reach modules that are only out of the addons path.
    - binaural_fiscal: the fiscal / non-fiscal flag of the journals. binaural_operative
      translates it from the binaural_v17_journal_fiscal copy, which the conversion takes.
    - binaural_fiscal_inspector, _delivery, _pos: the fiscal inspector. It has not been ported
      to 19; the members of its two groups are backed up so that a port can restore them.
    - binaural_groups_chatter: groups to hide the chatter, with no data of its own.
    - binaural_stock_purchase: liters per unit on purchase lines and the purchase order of a
      picking, backed up by the conversion.

    It only acts on a database that comes from the operativa line: no other one has them.

If it does not run: those modules stay installed without code and their views break the
    journal, invoice and purchase forms.

How to revert: restore the database. The group members and the fields are in
    l10n_ve_base_migration_v17_backup.

Task: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

import logging

from odoo.upgrade import util

from odoo.addons.l10n_ve_base.migrations import _common

_logger = logging.getLogger(__name__)

RETIRED_STATES = ("installed", "to upgrade", "to install", "to remove")


def _backup_group_members(cr, modules, version):
    """Copy the users of the groups the retired modules own, one row per group."""
    cr.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {_common.BACKUP_TABLE} (
            id serial PRIMARY KEY,
            model varchar NOT NULL,
            res_id integer NOT NULL,
            field varchar NOT NULL,
            value text,
            source_version varchar,
            backed_up_at timestamp NOT NULL DEFAULT (now() at time zone 'UTC'),
            UNIQUE (model, res_id, field)
        )
        """
    )
    cr.execute(
        f"""
        INSERT INTO {_common.BACKUP_TABLE} (model, res_id, field, value, source_version)
             SELECT 'res.groups', data.res_id, data.module || '.' || data.name,
                    string_agg(rel.uid::text, ',' ORDER BY rel.uid), %s
               FROM ir_model_data data
               JOIN res_groups_users_rel rel ON rel.gid = data.res_id
              WHERE data.model = 'res.groups' AND data.module IN %s
           GROUP BY data.res_id, data.module, data.name
        ON CONFLICT (model, res_id, field) DO NOTHING
        """,
        [version, tuple(modules)],
    )
    return cr.rowcount


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        WITH RECURSIVE retire(name) AS (
            SELECT unnest(%s::varchar[])
             UNION
            SELECT m.name
              FROM ir_module_module m
              JOIN ir_module_module_dependency d ON d.module_id = m.id
              JOIN retire r ON d.name = r.name
        )
        SELECT m.name
          FROM ir_module_module m
          JOIN retire r ON r.name = m.name
         WHERE m.state IN %s
        """,
        [list(_common.MODULES_WITHOUT_SUCCESSOR), RETIRED_STATES],
    )
    names = sorted(name for (name,) in cr.fetchall())

    cr.execute(
        """
        SELECT m.name,
               (SELECT string_agg(dependant.name, ', ' ORDER BY dependant.name)
                  FROM ir_module_module_dependency d
                  JOIN ir_module_module dependant ON dependant.id = d.module_id
                 WHERE d.name = m.name
                   AND dependant.state IN %s
                   AND NOT dependant.name = ANY(%s::varchar[]))
          FROM ir_module_module m
         WHERE m.name = ANY(%s::varchar[]) AND m.state IN %s
        """,
        [RETIRED_STATES, names, list(_common.MODULES_RETIRED_ALONE), RETIRED_STATES],
    )
    kept = []
    for name, dependants_left in cr.fetchall():
        if dependants_left:
            kept.append("%s (needed by %s)" % (name, dependants_left))
        else:
            names.append(name)
    names.sort()
    if kept:
        util.add_to_migration_reports(
            "Modules of the operativa line without a successor kept, because installed modules "
            "still depend on them; retire them by hand once those are gone: %s." % ", ".join(kept),
            category="Binaural · General",
        )
    if not names:
        return

    groups = _backup_group_members(cr, names, version)

    cr.execute("UPDATE ir_module_module SET state = 'to remove' WHERE name IN %s", [tuple(names)])
    _logger.info("Marked to be uninstalled at the end of the update: %s", ", ".join(names))

    dependants = sorted(
        set(names) - set(_common.MODULES_WITHOUT_SUCCESSOR) - set(_common.MODULES_RETIRED_ALONE)
    )
    message = (
        "Modules of the v17 operativa line without a successor in 19, uninstalled: %s."
        % ", ".join(names)
    )
    if dependants:
        message += " %s are uninstalled because they depend on them: check they were not needed." % ", ".join(
            dependants
        )
    if groups:
        message += " The members of %s of their groups were backed up in %s." % (
            groups, _common.BACKUP_TABLE,
        )
    if "binaural_fiscal_inspector" in names:
        message += " The fiscal inspector has no equivalent in 19 yet: its users lose it."
    util.add_to_migration_reports(message, category="Binaural · General")
