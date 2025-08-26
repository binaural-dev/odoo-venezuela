from odoo import api, SUPERUSER_ID

def migrate(cr, version):
    """
    Migration script to rename the field `currency_foreign_id` to `foreign_currency_id`.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Preserve data from currency_foreign_id
    cr.execute("""
        ALTER TABLE res_company ADD COLUMN foreign_currency_id INT;
        UPDATE res_company SET foreign_currency_id = currency_foreign_id;
        ALTER TABLE res_company DROP COLUMN currency_foreign_id;
    """)

    # Log the migration
    env['ir.logging'].create({
        'name': 'Migration',
        'type': 'server',
        'level': 'info',
        'message': 'Renamed currency_foreign_id to foreign_currency_id in res_company and related tables, preserving data.',
    })
