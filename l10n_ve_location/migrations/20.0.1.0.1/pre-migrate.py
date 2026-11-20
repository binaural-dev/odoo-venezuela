"""The cities of the localization move to the cities of Odoo (res.city) — R-49.

Odoo 20 always installs base_address_extended (account -> portal -> base_address_extended), which
defines res.partner.city_id towards res.city. This module defined the same field towards its own
res.country.city: any update that initialized res.partner before this module was loaded asked for
the foreign key towards res_city and failed with the cities of the contacts. Both models have the
same fields (name, country, state), so the cities are copied to res.city (reusing one with the same
name, state and country), every column that pointed to res_country_city is remapped, the external
ids follow their records, and the old table is dropped: Odoo does not drop the table of a model that
is no longer in the code.
"""

import logging

_logger = logging.getLogger(__name__)


def _table_exists(cr, table):
    cr.execute("SELECT to_regclass(%s)", (table,))
    return bool(cr.fetchone()[0])


def _column_type(cr, table, column):
    cr.execute(
        "SELECT data_type FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    row = cr.fetchone()
    return row and row[0]


def migrate(cr, version):
    if not _table_exists(cr, "res_country_city"):
        return
    if not _table_exists(cr, "res_city"):
        _logger.warning("l10n_ve_location: res_city does not exist, the cities are not moved")
        return

    translated = _column_type(cr, "res_city", "name") == "jsonb"
    name_of_city = "rc.name->>'en_US'" if translated else "rc.name"
    name_value = "jsonb_build_object('en_US', cc.name)" if translated else "cc.name"

    cr.execute("CREATE TEMP TABLE l10n_ve_city_map (old_id integer PRIMARY KEY, new_id integer)")
    cr.execute(
        f"""
        INSERT INTO l10n_ve_city_map (old_id, new_id)
        SELECT cc.id, (
            SELECT rc.id FROM res_city rc
            WHERE rc.country_id = cc.country_id
              AND rc.state_id IS NOT DISTINCT FROM cc.state_id
              AND {name_of_city} = cc.name
            ORDER BY rc.id LIMIT 1
        )
        FROM res_country_city cc
        """
    )
    cr.execute("SELECT old_id FROM l10n_ve_city_map WHERE new_id IS NULL ORDER BY old_id")
    for (old_id,) in cr.fetchall():
        cr.execute(
            f"""
            INSERT INTO res_city (name, country_id, state_id, create_uid, create_date, write_uid, write_date)
            SELECT {name_value}, cc.country_id, cc.state_id, cc.create_uid, cc.create_date, cc.write_uid, cc.write_date
            FROM res_country_city cc WHERE cc.id = %s
            RETURNING id
            """,
            (old_id,),
        )
        cr.execute("UPDATE l10n_ve_city_map SET new_id = %s WHERE old_id = %s", (cr.fetchone()[0], old_id))

    # Every column with a foreign key to res_country_city: res_partner.city_id, and the ones of any
    # other module (their keys are dropped; the module creates them again towards res_city).
    cr.execute(
        """
        SELECT c.relname, a.attname, fk.conname
        FROM pg_constraint fk
        JOIN pg_class c ON c.oid = fk.conrelid
        JOIN pg_attribute a ON a.attrelid = fk.conrelid AND a.attnum = fk.conkey[1]
        WHERE fk.contype = 'f' AND fk.confrelid = 'res_country_city'::regclass
        """
    )
    for table, column, constraint in cr.fetchall():
        cr.execute(f'ALTER TABLE "{table}" DROP CONSTRAINT "{constraint}"')
        cr.execute(
            f'UPDATE "{table}" t SET "{column}" = m.new_id FROM l10n_ve_city_map m WHERE t."{column}" = m.old_id'
        )
        _logger.info("l10n_ve_location: %s.%s now points to res_city", table, column)

    cr.execute(
        """
        UPDATE ir_model_data d SET model = 'res.city', res_id = m.new_id
        FROM l10n_ve_city_map m
        WHERE d.model = 'res.country.city' AND d.res_id = m.old_id
        """
    )
    cr.execute("SELECT count(*) FROM l10n_ve_city_map")
    _logger.info("l10n_ve_location: %s cities moved to res.city", cr.fetchone()[0])
    cr.execute("DROP TABLE res_country_city CASCADE")
    cr.execute("DROP TABLE l10n_ve_city_map")
