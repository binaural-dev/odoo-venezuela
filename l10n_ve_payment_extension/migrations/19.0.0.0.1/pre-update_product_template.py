"""Respalda `product_template.ciu_id` (M2O) antes de que el esquema nuevo lo elimine.

Por qué: `ciu_id` pasó de Many2one a Many2many (`ciu_ids`, tabla `product_template_ciu_rel`).
    El valor viejo se copia a una columna temporal porque el `post-` hermano es el que puede
    escribir en la tabla de la relación, y para entonces la columna original ya no está.
    **Esta conversión es de la época 16→17**: la carpeta vivía en `migrations/16.0.18.0/` y por
    versión no corría nunca (B1.5 la renombró a `19.0.0.0.1`, que sí corre). Cualquier cliente que
    venga de 17 ya la tiene hecha — `ciu_ids` es Many2many desde entonces y la tabla de relación
    ya existe. Por eso el guard de abajo no es cosmético: es el camino normal.
Si no corre: en un cliente que **sí** tenga todavía el M2O, se pierde la actividad económica (CIU)
    de cada producto, que es la que determina la retención de ISLR. En un cliente que viene de 17
    no corre nada porque no hay nada que convertir.
Revertir: `ALTER TABLE product_template DROP COLUMN temp_ciu_id`. No se toca `ciu_id`.

Tarea: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:  # instalación limpia: nace con el Many2many
        return

    if not util.column_exists(cr, "product_template", "ciu_id"):
        _logger.info(
            "product_template.ciu_id no existe: la conversión a Many2many ya está hecha "
            "(cliente que viene de 17 o posterior). Nada que respaldar."
        )
        return

    util.create_column(cr, "product_template", "temp_ciu_id", "int4")
    cr.execute("UPDATE product_template SET temp_ciu_id = ciu_id WHERE ciu_id IS NOT NULL")
    _logger.info("product_template.ciu_id respaldado en temp_ciu_id: %s filas", cr.rowcount)
