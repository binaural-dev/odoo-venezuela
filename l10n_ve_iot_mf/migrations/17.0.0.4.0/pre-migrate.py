import logging

_logger = logging.getLogger(__name__)

COLUMNS = {
    "res_company": [
        "mf_flag_21",
        "invoice_print_type",
    ],
}


def migrate(cr, version):
    """Agrega columnas faltantes en modelos que fueron añadidas al código
    Python después de la instalación inicial del módulo.

    Sin esta migración, Odoo lanza UndefinedColumn al intentar SELECT * desde
    res_company porque los campos existen en el modelo Python pero la columna
    no fue creada en la BD (el módulo no se ha actualizado desde que se
    agregaron los campos).
    """
    for table, fields in COLUMNS.items():
        for field in fields:
            try:
                cr.execute(
                    'ALTER TABLE "%s" ADD COLUMN IF NOT EXISTS "%s" varchar'
                    % (table, field)
                )
                _logger.info(
                    "l10n_ve_iot_mf: columna %s.%s asegurada", table, field
                )
            except Exception as e:
                _logger.warning(
                    "l10n_ve_iot_mf: no se pudo agregar %s.%s: %s",
                    table, field, e,
                )
