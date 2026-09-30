"""Crea invoice_date_display con la fecha de factura de 17, antes de que el ORM la llene con la del día.

Qué: crea la columna account_move.invoice_date_display y la llena con invoice_date. Donde
    invoice_date está vacío (asientos, borradores sin fecha) queda vacía también.

Por qué: el campo no existe en 17. En 19 lo declara este módulo con
    default=fields.Date.context_today, y cuando el ORM crea la columna la llena con ese default en
    todas las filas: la fecha del día del -u all. En 19_proalca_run15 quedaron así las 151.110
    filas de account_move (2026-09-22). Y no es sólo lo que se muestra: _get_accounting_date_source
    devuelve invoice_date_display antes que date, así que cualquier recálculo de date en una factura
    migrada la movería al día de la migración.

    En 17 la fecha de la factura era invoice_date. En 19 ese campo queda como "fecha de tasa" y
    invoice_date_display pasa a ser la fecha fiscal, así que el valor que le corresponde a cada
    factura migrada es su invoice_date.

    Se hace en pre- porque, si la columna ya existe cuando se carga el modelo, el ORM no aplica el
    default.

Qué pasa si no corre: todas las facturas migradas muestran como fecha de factura el día de la
    migración, y los reportes que ordenan o filtran por ella (libros de compra y venta) salen mal.

Cómo revertirlo: no hace falta. El campo no existía en 17, así que no se pisa ningún dato, e
    invoice_date queda intacto.

Tarea: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version or not version.startswith("17."):
        return

    util.create_column(cr, "account_move", "invoice_date_display", "date")
    count = util.explode_execute(
        cr,
        """
        UPDATE account_move
           SET invoice_date_display = invoice_date
         WHERE invoice_date_display IS DISTINCT FROM invoice_date
        """,
        table="account_move",
    )
    _logger.info("invoice_date_display tomado de invoice_date en %s asientos", count)
