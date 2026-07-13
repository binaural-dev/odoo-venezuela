import logging

_logger = logging.getLogger(__name__)

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


def migrate(cr, version):
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
