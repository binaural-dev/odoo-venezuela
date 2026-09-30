"""Llena invoice_date_display_datetime en las facturas que vienen de 17.

Qué: crea la columna account_move.invoice_date_display_datetime y le pone la fecha de
    invoice_date_display a las 12:00 (UTC). Donde invoice_date_display está vacío queda vacía.

Por qué: el campo no existe en 17. El post_init_hook de este módulo lo llena, pero ese hook sólo
    corre al instalar: a un cliente homologado, que ya tiene el módulo, le llega vacío en todas
    las facturas. En 19 el campo se escribe junto con invoice_date_display (create/write de
    account.move), así que las facturas migradas quedaban distintas a las nuevas.

    La hora de las facturas de 17 no existe en ningún lado. Se usa el mediodía UTC para que, en
    cualquier zona horaria del cliente, el campo se vea con el mismo día que invoice_date_display.
    El hook de instalación usa la hora del momento de instalar, lo que en Venezuela (UTC-4) cambia
    el día en lo que se registró después de las 20:00.

    Corre después del pre- de l10n_ve_accountant (19.0.1.1.2), que ya dejó invoice_date_display
    con la fecha de 17: este módulo depende de aquél.

Qué pasa si no corre: las facturas migradas quedan sin este campo, y lo que ordene por él las
    manda al principio o al final de la lista.

Cómo revertirlo: no hace falta. El campo no existía en 17, así que no se pisa ningún dato.

Tarea: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version or not version.startswith("17."):
        return
    if not util.column_exists(cr, "account_move", "invoice_date_display"):
        return

    util.create_column(cr, "account_move", "invoice_date_display_datetime", "timestamp")
    count = util.explode_execute(
        cr,
        """
        UPDATE account_move
           SET invoice_date_display_datetime = invoice_date_display + time '12:00'
         WHERE invoice_date_display IS NOT NULL
           AND invoice_date_display_datetime IS NULL
        """,
        table="account_move",
    )
    _logger.info("invoice_date_display_datetime llenado en %s asientos", count)
