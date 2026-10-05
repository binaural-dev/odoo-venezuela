import logging

_logger = logging.getLogger(__name__)

# Mismos patrones que l10n_ve_pos_mf/migrations/17.0.2.1.0/post-migrate.py.
# Se desactivan aquí (en pre-migrate) porque Odoo valida el árbol de vistas
# heredadas de pos.config / res.config.settings / pos.payment.method ANTES
# de llegar al post-migrate: si estas vistas huérfanas siguen activas,
# la carga de las vistas propias de este módulo falla con ParseError
# ("Field iface_fiscal_data_module does not exist") y el upgrade completo
# aborta antes de que el post-migrate tenga oportunidad de limpiarlas.
ORPHAN_VIEW_FIELD_PATTERNS = [
    "iface_fiscal_data_module",
    "enableb_cross_move",
]

COLUMNS = {
    "pos_config": [
        "serial_machine",
        "flag_21",
        "traditional_line",
        "has_cashbox",
        "access_button_mf",
        "message_in_head",
        "enable_auto_sync",
        "auto_sync_interval",
    ],
    "pos_session": [
        "serial_machine",
        "report_z",
    ],
}


def _deactivate_orphan_legacy_iot_views(cr):
    """Desactiva vistas huérfanas legacy IoT (Hallazgo #4) antes de que Odoo
    valide las vistas nuevas de este módulo, evitando el ParseError."""
    like_clauses = " OR ".join(
        "arch_db::text LIKE %s" for _ in ORPHAN_VIEW_FIELD_PATTERNS
    )
    params = tuple(f"%{pattern}%" for pattern in ORPHAN_VIEW_FIELD_PATTERNS)

    cr.execute(
        f"SELECT id, model FROM ir_ui_view WHERE active = true AND ({like_clauses})",
        params,
    )
    orphan_views = cr.fetchall()

    if not orphan_views:
        _logger.info(
            "l10n_ve_pos_mf: no se encontraron vistas huérfanas legacy IoT (Hallazgo #4)"
        )
        return

    view_ids = [row[0] for row in orphan_views]
    _logger.info(
        "l10n_ve_pos_mf: desactivando %s vista(s) huérfana(s) legacy IoT antes del upgrade: %s",
        len(view_ids), orphan_views,
    )
    cr.execute(
        "UPDATE ir_ui_view SET active = false WHERE id = ANY(%s)",
        (view_ids,),
    )


def migrate(cr, version):
    _deactivate_orphan_legacy_iot_views(cr)

    for table, fields in COLUMNS.items():
        for field in fields:
            try:
                cr.execute(
                    'ALTER TABLE "%s" ADD COLUMN IF NOT EXISTS "%s" varchar'
                    % (table, field)
                )
                _logger.info(
                    "l10n_ve_pos_mf: columna %s.%s asegurada", table, field
                )
            except Exception as e:
                _logger.warning(
                    "l10n_ve_pos_mf: no se pudo agregar %s.%s: %s",
                    table, field, e,
                )
