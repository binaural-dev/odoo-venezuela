from odoo import SUPERUSER_ID, api

# Filled by pre-migrate in the same database session.
MERGE_LOG_TABLE = "l10n_ve_stock_merged_alter_location_lines"


def post_merge_messages(env):
    """Leave in each record's chatter the lines that pre-migrate merged."""
    cr = env.cr
    # A temp table lives in pg_temp_N, where odoo.tools.sql.table_exists
    # does not look.
    cr.execute("SELECT to_regclass(%s) IS NOT NULL", (MERGE_LOG_TABLE,))
    if not cr.fetchone()[0]:
        return
    cr.execute(
        f"""
        SELECT stock_alter_location_id, location_id, quantities, total_qty
          FROM {MERGE_LOG_TABLE}
      ORDER BY stock_alter_location_id, location_id
        """
    )
    rows = cr.fetchall()
    cr.execute(f"DROP TABLE {MERGE_LOG_TABLE}")

    # The chatter is read by the client's users, so write it in their language.
    lang = env.ref("base.user_admin", raise_if_not_found=False).lang or "en_US"
    env = env(context=dict(env.context, lang=lang))
    alter_model = env["stock.picking.alter.location"].with_context(active_test=False)
    for alter_id, location_id, quantities, total_qty in rows:
        alter = alter_model.browse(alter_id).exists()
        if alter:
            alter._post_merged_lines_message(
                env["stock.location"].browse(location_id), quantities, total_qty
            )


def migrate(cr, version):
    if not version:
        return
    post_merge_messages(api.Environment(cr, SUPERUSER_ID, {}))
