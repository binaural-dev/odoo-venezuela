import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    views = env["ir.ui.view"].search([
        "|",
        ("arch_db", "like", "%iface_fiscal_data_module%"),
        ("arch_db", "like", "%enableb_cross_move%"),
    ])

    if views:
        _logger.info(
            "Eliminando %s vistas huérfanas con referencias a campos obsoletos",
            len(views),
        )
        _logger.info("Vistas a eliminar: %s", views.mapped("name"))
        views.unlink()
