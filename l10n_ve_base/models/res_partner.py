from odoo import fields, models

# Last-resort fallback used only when neither the creation context nor the
# current company's partner provide a timezone. Kept as a module-level
# constant so the backfill migration (migrations/19.0.1.0.1/post-migrate.py)
# can import the exact same value instead of duplicating the literal.
DEFAULT_TZ = "America/Caracas"


class ResPartner(models.Model):
    _inherit = "res.partner"

    tz = fields.Selection(
        default=lambda self: self.env.context.get("tz")
        or self.env.company.partner_id.tz
        or DEFAULT_TZ,
    )
