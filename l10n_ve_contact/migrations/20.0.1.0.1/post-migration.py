from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Recompute ``is_company`` with the Venezuelan rule (RIF prefix J, G or C).

    Odoo 20 stores it as a computed field. Partners created before this version, or migrated from
    Odoo 19, still hold the value of the core rule or the one chosen by hand.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    partners = env["res.partner"].with_context(active_test=False).search([])
    env.add_to_compute(partners._fields["is_company"], partners)
    partners.flush_recordset(["is_company"])
