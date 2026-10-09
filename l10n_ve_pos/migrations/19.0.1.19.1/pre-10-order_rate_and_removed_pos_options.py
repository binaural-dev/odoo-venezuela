"""Carry the v17 POS order rate over to v19 and back up the POS options that v19 removed.

What:
    1. Sets pos_order.foreign_currency_rate to the v17 foreign_inverse_rate, creating the column
       if needed. v17 already had that column, with the rate rounded to the foreign currency
       decimals (0.00 on a VEF base, as v17's order_model.js warns), so it is overwritten.
    2. Copies to l10n_ve_pos_migration_v17_backup the v17 flags and options that v19 no longer
       declares: account.move.is_pos_cross_move, pos.payment.method.apply_one_cross_move,
       pos.config.allow_sales_on_order and product.template.pos_sale_on_order. If any POS or
       product had "sale on order" enabled, the migration report says so.

Why:
    1. In v17 each order froze its rate in foreign_inverse_rate, which l10n_ve_rate documents as
       "the rate used as factor to multiply for the computation of the foreign amounts". In v19
       the same multiplier is foreign_currency_rate (pos_order._amount_to_foreign:
       amount * rate). v19 reads it on two paths that also reach migrated orders:
       _prepare_invoice_vals sets it as the invoice foreign_rate and foreign_inverse_rate with
       manually_set_rate, and a refund converts at the original order rate
       (pos_order_line.js _refundOriginalRate). Without it, invoicing a v17 order after the
       migration gives an invoice with rate 0, and its refunds fall back to today's rate.
    2. In v19 the cross move is decided per session (pos_session._is_cross_move_eligible), and
       "sale on order" (selling in POS without stock) disappears. The ORM deletes those columns
       at the end of the -u all. The flags are only a trail, but "sale on order" is a feature
       the store stops having, and Product decides on it (D-04).

If it does not run: invoices and refunds of v17 orders come out at rate 0 or today's rate, and the
    stores that sold on order lose it without notice.

How to revert: empty foreign_currency_rate on the migrated orders. The v17 value it replaces was the
    same rate rounded to the foreign currency decimals. The backup changes nothing.

Task: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

from odoo.upgrade import util

BACKUP = "l10n_ve_pos_migration_v17_backup"

# (model, table, column)
REMOVED = [
    ("account.move", "account_move", "is_pos_cross_move"),
    ("pos.payment.method", "pos_payment_method", "apply_one_cross_move"),
    ("pos.config", "pos_config", "allow_sales_on_order"),
    ("product.template", "product_template", "pos_sale_on_order"),
]


def migrate(cr, version):
    if not version or not version.startswith("17."):
        return

    if util.column_exists(cr, "pos_order", "foreign_inverse_rate"):
        # v17 already had a foreign_currency_rate column, holding the rate rounded to the foreign
        # currency decimals (0.00 on a VEF base): it is overwritten, not only filled when created.
        util.create_column(cr, "pos_order", "foreign_currency_rate", "float8")
        util.explode_execute(
            cr,
            """
            UPDATE pos_order
               SET foreign_currency_rate = foreign_inverse_rate
             WHERE foreign_inverse_rate IS NOT NULL
               AND foreign_inverse_rate <> 0
            """,
            table="pos_order",
        )

    cr.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {BACKUP} (
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
    counts = {}
    for model, table, column in REMOVED:
        if not util.column_exists(cr, table, column):
            continue
        cr.execute(
            f"""
            INSERT INTO {BACKUP} (model, res_id, field, value, source_version)
                 SELECT %s, id, %s, 'True', %s
                   FROM {table}
                  WHERE {column} IS TRUE
            ON CONFLICT (model, res_id, field) DO NOTHING
            """,
            [model, column, version],
        )
        counts[column] = cr.rowcount

    on_order = counts.get("allow_sales_on_order", 0) + counts.get("pos_sale_on_order", 0)
    if on_order:
        util.add_to_migration_reports(
            "POS: v19 no longer sells on order (without stock). It was enabled on "
            f"{counts.get('allow_sales_on_order', 0)} points of sale and "
            f"{counts.get('pos_sale_on_order', 0)} products. Backed up in {BACKUP}.",
            category="Binaural · Sales",
        )
