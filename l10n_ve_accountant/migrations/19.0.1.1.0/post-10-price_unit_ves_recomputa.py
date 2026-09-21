"""Recalcula `price_unit_ves` por lotes, solo en las líneas que necesitan tasa histórica.

Por qué: el `pre-` hermano creó la columna (para que el ORM no marcara las 467.276 líneas de
    golpe) y llenó en SQL la rama trivial del compute. Queda la otra rama, la que pasa por
    `currency_id._convert(..., line._get_foreign_rate_date())`: esa sí necesita el ORM. Se hace
    con `util.recompute_fields`, que trocea y descarga a la BD por lote, en vez de un recordset
    único de cientos de miles de líneas.
Si no corre: las líneas en moneda extranjera quedan con `price_unit_ves` en NULL. El campo es
    `Monetary`, así que la UI y los reportes lo leen como **0,00** sin avisar de nada.
Revertir: volver a poner en NULL las líneas afectadas
    (`UPDATE account_move_line SET price_unit_ves = NULL WHERE currency_id <> <la de la compañía>`)
    y relanzar. El script es idempotente: solo toca lo que está en NULL.

Tarea: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)

PENDIENTES = """
    SELECT aml.id
      FROM account_move_line aml
      JOIN res_company c ON c.id = aml.company_id
     WHERE aml.price_unit_ves IS NULL
       AND aml.currency_id IS NOT NULL
       AND aml.currency_id <> c.currency_id
"""


def migrate(cr, version):
    if not version:
        return

    if not util.column_exists(cr, "account_move_line", "price_unit_ves"):
        _logger.warning("account_move_line.price_unit_ves no existe; no hay nada que recalcular")
        return

    cr.execute("SELECT count(*) FROM (%s) s" % PENDIENTES)
    pendientes = cr.fetchone()[0]
    if not pendientes:
        _logger.info("price_unit_ves: no hay líneas pendientes de recálculo")
        return

    _logger.info("price_unit_ves: recalculando %s líneas en moneda extranjera", pendientes)
    util.recompute_fields(cr, "account.move.line", ["price_unit_ves"], query=PENDIENTES)

    cr.execute("SELECT count(*) FROM (%s) s" % PENDIENTES)
    sin_resolver = cr.fetchone()[0]

    # Cuando `_convert()` no encuentra tasa para la fecha, Odoo cae a rate = 1.0 y devuelve el
    # importe sin convertir: el resultado queda idéntico al price_unit original. No es un error
    # que este script pueda arreglar (lo produce el compute de 19.0 igual que si recalculara el
    # ORM), pero es indistinguible de una conversión legítima y hay que reportarlo.
    cr.execute(
        """
        SELECT count(*)
          FROM account_move_line aml
          JOIN res_company c ON c.id = aml.company_id
         WHERE aml.currency_id IS NOT NULL
           AND aml.currency_id <> c.currency_id
           AND aml.price_unit <> 0
           AND aml.price_unit_ves = aml.price_unit
        """
    )
    sin_convertir = cr.fetchone()[0]

    mensaje = (
        "l10n_ve_accountant: `price_unit_ves` recalculado en %s líneas en moneda extranjera, "
        "por lotes." % pendientes
    )
    if sin_resolver:
        mensaje += (
            " ATENCIÓN: %s siguen en NULL después del recálculo — revisar antes de confiar en "
            "cualquier reporte que use el campo." % sin_resolver
        )
    if sin_convertir:
        mensaje += (
            " ATENCIÓN: en %s líneas el valor quedó idéntico al `price_unit` original pese a "
            "estar en otra moneda. Es lo que devuelve `_convert()` cuando no encuentra tasa para "
            "la fecha (cae a 1.0) y no se distingue de una conversión legítima: verificar que "
            "existan las tasas históricas de esas fechas." % sin_convertir
        )

    _logger.info(mensaje)
    util.add_to_migration_reports(mensaje, category="Binaural · Contabilidad")
